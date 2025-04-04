"""
Application configuration.
"""

from pathlib import Path

import toml

from default_config import CONST_DEFAULT_CONFIG
from logger import logger

combined_config = {}


def initialize_config():
    global combined_config
    config_file_path = Path.cwd() / "config.toml"

    with open(config_file_path) as f:
        data = toml.load(f)
        combined_config = {
            "system": CONST_DEFAULT_CONFIG["system"] | data["system"],
            "whisper": CONST_DEFAULT_CONFIG["whisper"] | data["whisper"],
            "email": CONST_DEFAULT_CONFIG["email"] | data["email"],
        }


def get_config() -> dict:
    "Returns app configuration as a dictionary."
    return combined_config


def log_config(blacklist=["hf_token"]):
    "Logs configuration items."
    config = get_config()
    config_items = config["system"] | config["whisper"]

    for key, value in config_items.items():
        if key in blacklist:
            continue
        logger.debug(f"Config: {key} -> {value}")


def whisper_config_html(blacklist=["initial_prompt", "hf_token"]):
    "Returns Whisper configuration as HTML."
    config = get_config()

    result = ""
    for key, value in config["whisper"].items():
        if key in blacklist:
            continue
        result += f"{key.capitalize()}: {value}<br>"

    return result


initialize_config()
