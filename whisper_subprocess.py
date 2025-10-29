"""
Subprocess wrapper for Whisper transcription pipeline.
Runs complete Whisper workflow (transcribe + align + diarize) in isolated subprocess.
Models stay loaded within the subprocess for efficiency, then all memory is freed on exit.
"""

import sys
import pickle
import whisperx
from app_config import get_config
from whisper_tools import get_audio

config = get_config()

# Whisper configuration
model_name = config["whisper"]["model"]
device = config["whisper"]["device"]
batch_size = config["whisper"]["batch_size"]
beam_size = config["whisper"]["beam_size"]
compute_type = config["whisper"]["compute_type"]
language_audio = config["whisper"]["language"]
initial_prompt = config["whisper"]["initial_prompt"]
use_initial_prompt = config["whisper"].get("use_initial_prompt", False)
min_speakers = config["whisper"]["min_speakers"]
max_speakers = config["whisper"]["max_speakers"]
hf_token = config["whisper"]["hf_token"]
use_speaker_diarization = config["whisper"]["use_speaker_diarization"]


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


def process_audio_file(audio_path: str):
    """
    Complete Whisper pipeline: transcribe + align + (optional) diarize.
    Keeps models loaded for efficiency within this subprocess.
    """
    # Load audio
    audio = get_audio(audio_path)

    # Step 1: Transcribe
    transcription_model = load_transcription_model()
    transcription_result = transcription_model.transcribe(audio, batch_size=batch_size)
    del transcription_model  # Free this model before loading next

    # Step 2: Align
    language = transcription_result["language"]
    alignment_model, metadata = load_alignment_model(language)
    result = whisperx.align(
        transcription_result["segments"],
        alignment_model,
        metadata,
        audio,
        device,
        return_char_alignments=False,
    )
    del alignment_model, metadata  # Free alignment model

    # Step 3: Diarize (optional)
    if use_speaker_diarization:
        diarization_model = load_diarization_model()
        diarize_segments = diarization_model(
            audio, min_speakers=min_speakers, max_speakers=max_speakers
        )
        result = whisperx.assign_word_speakers(diarize_segments, result)
        del diarization_model  # Free diarization model

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

        # Serialize result to stdout
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
