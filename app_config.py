"""
Application configuration.
"""
import os
import toml

config_file_path = os.path.join(os.getcwd(), 'config.toml')

with open(config_file_path) as f:
    data = toml.load(f)

def get_config() -> dict:
    "Returns app configuration as a dictionary."
    return data


def print_config():
    "Prints configuration on the console."
    config = get_config()

    print("\033[1m" + "System configuration:" + "\033[0m")
    for key, value in config["system"].items():
        print(f"{key.capitalize()}: {value}")

    print("\033[1m" + "Whisper configuration:" + "\033[0m")
    for key, value in config["whisper"].items():
        print(f"{key.capitalize()}: {value}")
    print("-" * 79)


def whisper_config_html(blacklist = ["initial_prompt"]):
    "Returns Whisper configuration as HTML."
    config = get_config()

    result = ""
    for key, value in config["whisper"].items():
        if key in blacklist: continue
        result += f"{key.capitalize()}: {value}<br>"

    return result
