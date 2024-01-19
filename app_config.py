"""
Application configuration.
"""
import toml

with open("config.toml") as f:
    data = toml.load(f)

def get_config() -> dict:
    "Returns app configuration as a dictionary."
    return data
