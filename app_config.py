"""
Application configuration.
"""

from pathlib import Path
import toml

from logger import logger
from default_config import CONST_DEFAULT_CONFIG

combined_config = {}


def initialize_config():
    global combined_config
    config_file_path = Path.cwd() / "config.toml"

    with open(config_file_path) as f:
        data = toml.load(f)
    combined_config = {
        "system": CONST_DEFAULT_CONFIG["system"] | data.get("system", {}),
        "whisper": CONST_DEFAULT_CONFIG["whisper"] | data.get("whisper", {}),
        "llm": CONST_DEFAULT_CONFIG["llm"] | data.get("llm", {}),
        "email": CONST_DEFAULT_CONFIG["email"] | data.get("email", {}),
        "bag": CONST_DEFAULT_CONFIG["bag"] | data.get("bag", {}),
    }


def get_config() -> dict:
    "Returns app configuration as a dictionary."
    return combined_config


def log_config(blacklist=["hf_token"]):
    "Logs configuration items."
    config = get_config()
    config_items = config["system"] | config["whisper"] | config["llm"] 

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
