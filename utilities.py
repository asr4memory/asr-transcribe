"""
Utilities and helper functions for the main ASR script.
"""
import re

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
    """
    Format time duration.

    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining_seconds = seconds % 60

    formatted_time = "{}h{:02}m{:02}s".format(int(hours), int(minutes),
                                              int(remaining_seconds))
    return formatted_time


def check_for_hallucination_warnings(text: str) -> list:
    """
    Check the output for the message "Failed to align segment" in the
    stdout/terminal output to identify AI hallucinations.
    """
    hallucination_regexp = 'Failed to align segment \((".*")\)'
    match = re.search(hallucination_regexp, text)

    if (match):
        return list(match.groups())
    else:
        return None
