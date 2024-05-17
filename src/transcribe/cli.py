"""Command Line Interface (CLI) for asr-transcribe."""

from pathlib import Path
import sys
import click

from transcribe import __version__
from transcribe.workflow import process_directory
from transcribe.app_config import get_config, log_config

class TranscribeException(Exception):
    """An error has occurred."""


# The main entry point for transcribe.
@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.version_option(version=__version__)
def transcribe_cli():
    """Automatic speech transcription software."""


@transcribe_cli.command(help="start process")
def batch():
    """Start transcription processs."""
    try:
        config = get_config()

        input_directory = Path(config['system']['input_path'])
        output_directory = Path(config['system']['output_path'])

        if not input_directory.exists():
            raise FileNotFoundError(f"Input directory does not exist: {input_directory}")

        if not output_directory.exists():
            raise FileNotFoundError(f"Output directory does not exist: {output_directory}")

        log_config()
        process_directory(input_directory, output_directory)
    except Exception:
        sys.exit(f'An error occurred.')


if __name__ == '__main__':
    transcribe_cli()
