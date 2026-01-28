"""
Default configuration.
These settings are overridden by the settings in the config.toml file,
if present.
"""

CONST_DEFAULT_CONFIG = {
    "system": {
        "input_path": "",
        "output_path": "",
        "email_notifications": False,
        "zip_bags": True,
    },
    "whisper": {
        "model": "large-v3",
        "device": "cpu",
        "thread_count": 5,
        "batch_size": 28,
        "beam_size": 5,
        "compute_type": "float32",
        "language": None,
        "translation_enabled": False,
        "translation_target_language": "en",
        "translation_model": "large-v3",
        "use_initial_prompt": False,
        "initial_prompt": "",
        "max_sentence_length": 120,
        "use_speaker_diarization": False,
        "min_speakers": None,
        "max_speakers": None,
        "hf_token": None,
        "pause_marker_threshold": 2.0,
        "api_key": None,
    },
    "llm": {
        "use_summarization": False,
        "use_toc": False,
        "model_path": "",
        "n_gpu_layers": 5,
        "llm_languages": ["de", "en"],
        "verbose": False,
        "debug_file": "",
        "output_debug": "",
    },
    "email": {
        "smtp_server": "",
        "smtp_port": 25,
        "username": None,
        "password": None,
        "from": "notifications@example.com",
        "to": ["alice@example.com"],
    },
    "bag": {
        "group_identifier": None,
        "bag_count": None,
        "internal_sender_identifier": None,
        "internal_sender_description": None,
    },
}
