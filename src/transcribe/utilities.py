"""
Utilities and helper functions for the main ASR script.
"""
import re
from pathlib import Path

def should_be_processed(filepath: Path):
    "Checks whether the file should be processed. File has which type?"
    filename = filepath.name
    if filename.startswith("_"):
        return False
    elif filename.startswith("."):
        return False
    elif filename.endswith("backup"):
        return False
    elif filename.endswith("_test_"):
        return False
    else:
        return True


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
    hallucination_regexp = r'Failed to align segment \((".*")\)'
    match = re.search(hallucination_regexp, text)

    if (match):
        return list(match.groups())
    else:
        return None
