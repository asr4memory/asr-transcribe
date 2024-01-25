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
