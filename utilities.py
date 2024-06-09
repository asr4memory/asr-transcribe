"""
Utilities and helper functions for the main ASR script.
"""
import re
from pathlib import Path
from decimal import Decimal

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


def format_timestamp(seconds, milli_separator="."):
    """
    Convert seconds to hh:mm:ss and hh:mm:ss.ms format and use decimal for precise arithmetic
    """
    time_in_seconds = Decimal(seconds)
    hours = time_in_seconds // 3600
    remainder = time_in_seconds % 3600
    minutes = remainder // 60
    seconds = remainder % 60
    milliseconds = (seconds - int(seconds)) * 1000

    formatted_time = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
    formatted_time_ms = f"{formatted_time}{milli_separator}{int(milliseconds):03}"

    return formatted_time, formatted_time_ms


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
