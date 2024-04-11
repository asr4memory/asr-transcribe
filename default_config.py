"""
Default configuration.
These settings are overridden by the settings in the config.toml file,
if present.
"""

CONST_DEFAULT_CONFIG = {
    'system': {
        'input_path': '',
        'output_path': '',
        'email_notifications': False
    },
    'whisper': {
        'model': 'large-v3',
        'device': 'cpu',
        'thread_count': 5,
        'batch_size': 28,
        'beam_size': 5,
        'compute_type': 'float32',
        'language': None,
        'use_initial_prompt': False,
        'initial_prompt': '',
        'max_sentence_lentgh': 120,
        'use_speaker_diarization': False,
        'min_speakers': None,
        'max_speakers': None,
        'hf_token': None,
    },
    'email': {
        'smtp_server': '',
        'smtp_port': 25,
        'username': None,
        'password': None,
        'from': 'notifications@example.com',
        'to': ['alice@example.com']
    }
}
