import toml

with open("config.toml") as f:
    data = toml.load(f)

def get_config():
    return data
