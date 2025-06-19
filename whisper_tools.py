import whisperx, torch
from app_config import get_config
from datetime import timedelta
import gc
from utilities import cleanup_cuda_memory

config = get_config()

# Set the number of threads used by PyTorch (only relevant when CPU as device is used)
number_threads = config["whisper"]["thread_count"]

# Define parameters for WhisperX model
model_name = config["whisper"]["model"]
custom_model = config["whisper"].get("custom_model", False)
model_dir = config["whisper"]["model_dir"]
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

SAMPLING_RATE = 16000

torch.set_num_threads(number_threads)


def get_transcription_model():
    """
    Load WhisperX transcription model.
    """
    asr_options = {"beam_size": beam_size}
    if use_initial_prompt:
        asr_options["initial_prompt"] = initial_prompt

    if custom_model == False:
        model = whisperx.load_model(
            model_name, 
            device,
            language=language_audio,
            compute_type=compute_type,
            asr_options=asr_options,
        )
    else:
        model = whisperx.load_model(
            model_name,      
            device,
            language=language_audio,
            compute_type=compute_type,
            asr_options=asr_options,
            download_root=model_dir,      
        )

    return model


def get_alignment_model(language_code: str, large_model=False):
    """
    Load WhisperX alignment model.
    Set large_model to True for larger align model which uses more computing
    ressources.
    """
    if large_model:
        result = whisperx.load_align_model(
            model_name="WAV2VEC2_ASR_LARGE_LV60K_960H",
            language_code=language_code,
            device=device,
        )
    else:
        result = whisperx.load_align_model(language_code=language_code, device=device)

    return result


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
    seconds = len(audio) / SAMPLING_RATE
    return seconds


def transcribe(audio):
    """
    Transcribe audio data with whisper model.
    """
    model = get_transcription_model()
    result = model.transcribe(audio, batch_size=batch_size)
    del model
    cleanup_cuda_memory()
    return result


def align(audio, segments, language: str):
    """
    Align transcribed segments to original audio and get time stamps
    for start and end of each segment.
    """
    model, metadata = get_alignment_model(language)
    result = whisperx.align(
        segments, model, metadata, audio, device, return_char_alignments=False
    )
    del model, metadata
    cleanup_cuda_memory()
    return result


def diarize(audio, result):
    """
    Diarize transcribed segments using
    WhisperX' implemenation of pyannote.
    """
    diarize_model = whisperx.diarize.DiarizationPipeline(use_auth_token=hf_token, device=device)
    diarize_segments = diarize_model(
        audio, min_speakers=min_speakers, max_speakers=max_speakers
    )
    result = whisperx.assign_word_speakers(diarize_segments, result)
    del diarize_model
    cleanup_cuda_memory()
    return result
