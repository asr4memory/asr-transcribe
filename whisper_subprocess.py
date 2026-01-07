"""
Subprocess wrapper for Whisper transcription pipeline.
Runs complete Whisper workflow (transcribe + align + diarize) in isolated subprocess.
Models stay loaded within the subprocess for efficiency, then all memory is freed on exit.
"""

import sys
import pickle
import logging
import warnings
from typing import Optional
import whisperx
from app_config import get_config
from logger import logger

# Suppress whisperx and its dependencies' logging to keep stdout clean for pickle
logging.getLogger("whisperx").setLevel(logging.WARNING)
logging.getLogger("pyannote").setLevel(logging.WARNING)
logging.getLogger("speechbrain").setLevel(logging.WARNING)
logging.getLogger("torch").setLevel(logging.WARNING)
logging.getLogger("torchaudio").setLevel(logging.WARNING)

# Suppress specific warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Save original stdout and redirect to stderr to prevent any output from contaminating the pickle data
# This ensures stdout is clean for the pickled result only
_original_stdout = sys.stdout
sys.stdout = sys.stderr

config = get_config()

# Whisper configuration
requested_model_name = config["whisper"]["model"]
device = config["whisper"]["device"]
batch_size = config["whisper"]["batch_size"]
beam_size = config["whisper"]["beam_size"]
compute_type = config["whisper"]["compute_type"]
language_audio = config["whisper"].get("language")
translation_enabled = config["whisper"].get("translation_enabled", False)
translation_target_language = config["whisper"].get("translation_target_language", "en") or "en"
translation_model_preference = config["whisper"].get("translation_model", "large-v3")
initial_prompt = config["whisper"]["initial_prompt"]
use_initial_prompt = config["whisper"].get("use_initial_prompt", False)
min_speakers = config["whisper"]["min_speakers"]
max_speakers = config["whisper"]["max_speakers"]
hf_token = config["whisper"]["hf_token"]
use_speaker_diarization = config["whisper"]["use_speaker_diarization"]
MULTILINGUAL_PREFIXES = ("tiny", "base", "small", "medium", "large")


def is_multilingual_model(name: Optional[str]) -> bool:
    """Return True if the provided model name is multilingual-capable."""
    if not name:
        return False
    name = name.lower()
    return any(name.startswith(prefix) for prefix in MULTILINGUAL_PREFIXES)


def resolve_model_name() -> str:
    """
    Determine the actual model name to load.
    Translation requires a multilingual model; fall back to the configured translation model.
    """
    model = requested_model_name
    if translation_enabled and not is_multilingual_model(model):
        fallback = translation_model_preference or "large-v3"
        if not is_multilingual_model(fallback):
            fallback = "large-v3"
        logger.warning(
            "Translation enabled but model '%s' is not multilingual. Using '%s' instead.",
            model,
            fallback,
        )
        model = fallback
    return model


model_name = resolve_model_name()


def get_audio(path: str):
    """
    Load audio file on path.
    Returns numpy rank-1 tensor with 16,000 values per second
    (16kHz).
    """
    result = whisperx.load_audio(path)
    return result


def get_audio_length(audio):
    "Gets audio length in seconds."
    sampling_rate = 16000
    seconds = len(audio) / sampling_rate
    return seconds


def load_transcription_model():
    """Load WhisperX transcription model."""
    asr_options = {"beam_size": beam_size}
    if use_initial_prompt:
        asr_options["initial_prompt"] = initial_prompt

    model = whisperx.load_model(
        model_name,
        device,
        language=language_audio,
        compute_type=compute_type,
        asr_options=asr_options,
    )
    return model


def load_alignment_model(language_code: str):
    """Load WhisperX alignment model."""
    model, metadata = whisperx.load_align_model(
        language_code=language_code, device=device
    )
    return model, metadata


def load_diarization_model():
    """Load WhisperX diarization model."""
    diarize_model = whisperx.diarize.DiarizationPipeline(
        use_auth_token=hf_token, device=device
    )
    return diarize_model


def transcribe_audio(model, audio, task: Optional[str] = None):
    """Transcribe or translate audio with the loaded Whisper model."""
    kwargs = {"batch_size": batch_size}
    if task == "translate":
        kwargs["task"] = "translate"
        if language_audio:
            kwargs["language"] = language_audio
    return model.transcribe(audio, **kwargs)


def align_transcription(transcription_result, audio_data):
    """Align transcription output with the alignment model."""
    language = transcription_result["language"]
    alignment_model, metadata = load_alignment_model(language)
    aligned = whisperx.align(
        transcription_result["segments"],
        alignment_model,
        metadata,
        audio_data,
        device,
        return_char_alignments=False,
    )
    del alignment_model, metadata
    return aligned


def process_audio_file(audio_path: str):
    """
    Complete Whisper pipeline: transcribe + align + (optional) diarize.
    Keeps models loaded for efficiency within this subprocess.
    """
    # Load audio
    audio = get_audio(audio_path)

    # Step 1: Transcribe (always capture original language)
    transcription_model = load_transcription_model()
    base_transcription = transcribe_audio(transcription_model, audio)
    translation_transcription = None
    if translation_enabled:
        translation_transcription = transcribe_audio(
            transcription_model, audio, task="translate"
        )
    del transcription_model  # Free model before alignment

    # Step 2: Align
    result = align_transcription(base_transcription, audio)
    translation_aligned = (
        align_transcription(translation_transcription, audio)
        if translation_transcription
        else None
    )

    # Step 3: Diarize (optional) - reuse diarization output for both results
    if use_speaker_diarization:
        diarization_model = load_diarization_model()
        diarize_segments = diarization_model(
            audio, min_speakers=min_speakers, max_speakers=max_speakers
        )
        result = whisperx.assign_word_speakers(diarize_segments, result)
        if translation_aligned:
            translation_aligned = whisperx.assign_word_speakers(
                diarize_segments, translation_aligned
            )
        del diarization_model  # Free diarization model

    # Attach metadata for downstream consumers
    source_language = base_transcription.get("language")
    translation_output_language = (
        translation_transcription.get("language") if translation_transcription else None
    )
    result["source_language"] = source_language
    result["requested_language"] = language_audio
    result["translation_enabled"] = translation_enabled
    result["translation_target_language"] = (
        translation_target_language if translation_enabled else None
    )
    result["translation_output_language"] = translation_output_language
    result["output_language"] = source_language
    result["model_name"] = model_name
    result["requested_model_name"] = requested_model_name
    result["language"] = result.get("language") or result["output_language"]
    result["translation_result"] = translation_aligned
    if translation_aligned:
        translation_aligned["language"] = (
            translation_aligned.get("language") or translation_output_language
        )

    # Return complete result
    # Subprocess exit will free all remaining memory
    return result


def main():
    """Main subprocess entry point."""
    if len(sys.argv) < 2:
        print("Usage: whisper_subprocess.py <audio_path>", file=sys.stderr)
        sys.exit(1)

    audio_path = sys.argv[1]

    try:
        # Process the audio file
        result = process_audio_file(audio_path)

        # Restore stdout and serialize result to clean stdout
        sys.stdout = _original_stdout
        sys.stdout.buffer.write(pickle.dumps(result))
        sys.exit(0)

    except Exception as e:
        # Write error to stderr and exit with error code
        print(f"Whisper subprocess error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
