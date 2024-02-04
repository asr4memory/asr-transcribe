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
    config = get_config()

    print("\033[1m" + "System configuration:" + "\033[0m")
    for key, value in config["system"].items():
        print(f"{key}: {value}")
    #print("-" * 79)

    print("\033[1m" + "Whisper configuration:" + "\033[0m")
    for key, value in config["whisper"].items():
        print(f"{key}: {value}")
    print("-" * 79)
