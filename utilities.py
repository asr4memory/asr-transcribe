"""
Utilities and helper functions for the main ASR script.
"""
import io

class Tee(io.StringIO):
    "What does this class do?"
    def __init__(self, terminal):
        self.terminal = terminal
        super().__init__()

    def write(self, message):
        self.terminal.write(message)
        super().write(message)


def ignore_file(file):
    "Checks whether the file should be ignored. File has which type?"
    if file.endswith(".DS_Store"):
        return True
    elif file.endswith("backup"):
        return True
    elif file.endswith("_test_"):
        return True
    elif file.startswith("_"):
        return True
    elif file.startswith("_test"):
        return True
    elif file.startswith("."):
        return True
    else:
        return False


def format_duration(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60

    formatted_time = "{}h{:02}m{:02}s".format(int(hours), int(minutes),
                                              int(remaining_seconds))
    return formatted_time
