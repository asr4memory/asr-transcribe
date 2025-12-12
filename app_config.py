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


def whisper_config_html(blacklist=["initial_prompt", "hf_token", "api_key"]):
    "Returns Whisper configuration as HTML."
    return _section_config_html("whisper", blacklist)


def llm_config_html():
    "Returns LLM configuration as HTML."
    return _section_config_html("llm")


def bag_config_html():
    "Returns bag metadata configuration as HTML."
    return _section_config_html("bag")


def _section_config_html(section_name, blacklist=None):
    "Helper to convert a config section into HTML key/value rows."
    blacklist = set(blacklist or [])
    config = get_config()
    section_items = config.get(section_name, {})

    result = ""
    for key, value in section_items.items():
        if key in blacklist:
            continue
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        result += f"{key.capitalize()}: {value}<br>"

    return result


initialize_config()
