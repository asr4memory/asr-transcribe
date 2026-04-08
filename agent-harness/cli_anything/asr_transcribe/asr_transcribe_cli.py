"""cli-anything ASR Transcribe — CLI harness for asr-transcribe pipeline.

Provides both one-shot subcommands and an interactive REPL for the
asr-transcribe audio transcription pipeline.
"""

import json
import sys

import click

from cli_anything.asr_transcribe import __version__

# ── JSON output helper ────────────────────────────────────────────────


class _Ctx:
    """Shared context passed between Click commands."""

    def __init__(self):
        self.json_mode = False


pass_ctx = click.make_pass_decorator(_Ctx, ensure=True)


def _output(data, ctx_obj: _Ctx):
    """Print *data* as JSON or human-readable depending on mode."""
    if ctx_obj.json_mode:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        _pretty(data)


def _pretty(data, indent=0):
    """Simple recursive pretty-printer for dicts/lists."""
    prefix = "  " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                click.echo(f"{prefix}{key}:")
                _pretty(value, indent + 1)
            else:
                click.echo(f"{prefix}{key}: {value}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                _pretty(item, indent)
                click.echo()
            else:
                click.echo(f"{prefix}- {item}")
    else:
        click.echo(f"{prefix}{data}")


# ── Main CLI group ────────────────────────────────────────────────────


@click.group(invoke_without_command=True)
@click.option("--json", "json_mode", is_flag=True, help="Output in JSON format.")
@click.option("--version", is_flag=True, help="Show version and exit.")
@click.pass_context
def cli(ctx, json_mode, version):
    """cli-anything-asr-transcribe — CLI harness for the asr-transcribe pipeline."""
    ctx.ensure_object(_Ctx)
    ctx.obj.json_mode = json_mode

    if version:
        if json_mode:
            click.echo(json.dumps({"version": __version__}))
        else:
            click.echo(f"cli-anything-asr-transcribe v{__version__}")
        ctx.exit(0)
        return

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── config ────────────────────────────────────────────────────────────


@cli.group()
def config():
    """Configuration management."""
    pass


@config.command("show")
@pass_ctx
def config_show(ctx_obj):
    """Display current configuration."""
    from cli_anything.asr_transcribe.core.config_manager import show_config

    result = show_config(as_json=ctx_obj.json_mode)
    if ctx_obj.json_mode:
        click.echo(result)
    else:
        _output(show_config(as_json=False), ctx_obj)


@config.command("validate")
@pass_ctx
def config_validate(ctx_obj):
    """Validate config.toml."""
    from cli_anything.asr_transcribe.core.config_manager import validate_config

    result = validate_config()
    _output(result, ctx_obj)


@config.command("init")
@click.option("--force", is_flag=True, help="Overwrite existing config.toml.")
@pass_ctx
def config_init(ctx_obj, force):
    """Create config.toml from example template."""
    from cli_anything.asr_transcribe.core.config_manager import init_config

    result = init_config(force=force)
    _output(result, ctx_obj)


@config.command("set")
@click.argument("key")
@click.argument("value")
@pass_ctx
def config_set(ctx_obj, key, value):
    """Set a config value (e.g. config set whisper.device cuda)."""
    from cli_anything.asr_transcribe.core.config_manager import set_config

    result = set_config(key, value)
    _output(result, ctx_obj)


@config.command("diff")
@pass_ctx
def config_diff(ctx_obj):
    """Show differences between current config and defaults."""
    from cli_anything.asr_transcribe.core.config_manager import diff_config

    result = diff_config()
    _output(result, ctx_obj)


# ── transcribe ────────────────────────────────────────────────────────


@cli.group()
def transcribe():
    """Transcription operations."""
    pass


@transcribe.command("file")
@click.argument("audio_path")
@click.option("-o", "--output-dir", default=None, help="Output directory.")
@pass_ctx
def transcribe_file(ctx_obj, audio_path, output_dir):
    """Transcribe a single audio file."""
    from cli_anything.asr_transcribe.core.transcribe import transcribe_file as _transcribe

    result = _transcribe(audio_path, output_dir)
    _output(result, ctx_obj)


@transcribe.command("batch")
@click.argument("directory")
@click.option("-o", "--output-dir", default=None, help="Output directory.")
@pass_ctx
def transcribe_batch(ctx_obj, directory, output_dir):
    """Transcribe all eligible files in a directory."""
    from cli_anything.asr_transcribe.core.transcribe import transcribe_batch as _batch

    result = _batch(directory, output_dir)
    _output(result, ctx_obj)


# ── info ──────────────────────────────────────────────────────────────


@cli.group()
def info():
    """Inspection commands."""
    pass


@info.command("audio")
@click.argument("path")
@pass_ctx
def info_audio(ctx_obj, path):
    """Show audio file metadata."""
    from cli_anything.asr_transcribe.core.audio_info import get_audio_info

    result = get_audio_info(path)
    _output(result, ctx_obj)


@info.command("segments")
@click.argument("json_path")
@pass_ctx
def info_segments(ctx_obj, json_path):
    """Show statistics from a WhisperX JSON file."""
    from cli_anything.asr_transcribe.core.audio_info import get_segments_info

    result = get_segments_info(json_path)
    _output(result, ctx_obj)


@info.command("bag")
@click.argument("bag_path")
@pass_ctx
def info_bag(ctx_obj, bag_path):
    """Show BagIt archive metadata."""
    from cli_anything.asr_transcribe.core.bag_manager import get_bag_info

    result = get_bag_info(bag_path)
    _output(result, ctx_obj)


@info.command("files")
@click.argument("directory")
@pass_ctx
def info_files(ctx_obj, directory):
    """List eligible audio files in a directory."""
    from cli_anything.asr_transcribe.core.audio_info import list_eligible_files

    result = list_eligible_files(directory)
    _output(result, ctx_obj)


@info.command("words")
@click.argument("json_path")
@pass_ctx
def info_words(ctx_obj, json_path):
    """Show word-level detail and confidence scores."""
    from cli_anything.asr_transcribe.core.audio_info import get_words_info

    result = get_words_info(json_path)
    _output(result, ctx_obj)


@info.command("speakers")
@click.argument("json_path")
@pass_ctx
def info_speakers(ctx_obj, json_path):
    """Show per-speaker statistics."""
    from cli_anything.asr_transcribe.core.audio_info import get_speakers_info

    result = get_speakers_info(json_path)
    _output(result, ctx_obj)


@info.command("language")
@click.argument("json_path")
@pass_ctx
def info_language(ctx_obj, json_path):
    """Show language metadata from WhisperX output."""
    from cli_anything.asr_transcribe.core.audio_info import get_language_info

    result = get_language_info(json_path)
    _output(result, ctx_obj)


@info.command("hallucinations")
@click.argument("json_path")
@pass_ctx
def info_hallucinations(ctx_obj, json_path):
    """Check for potential hallucination indicators."""
    from cli_anything.asr_transcribe.core.audio_info import check_hallucinations

    result = check_hallucinations(json_path)
    _output(result, ctx_obj)


# ── process ───────────────────────────────────────────────────────────


@cli.group()
def process():
    """Post-processing operations."""
    pass


@process.command("segments")
@click.argument("json_path")
@click.option("-o", "--output", "output_path", default=None, help="Output path for processed JSON.")
@pass_ctx
def process_segments(ctx_obj, json_path, output_path):
    """Post-process WhisperX segments (buffer, uppercase, split)."""
    from cli_anything.asr_transcribe.core.process import process_segments as _process

    result = _process(json_path, output_path)
    _output(result, ctx_obj)


@process.command("buffer")
@click.argument("json_path")
@click.option("-o", "--output", "output_path", default=None, help="Output path.")
@pass_ctx
def process_buffer(ctx_obj, json_path, output_path):
    """Run only sentence-buffering on segments."""
    from cli_anything.asr_transcribe.core.process import buffer_step

    result = buffer_step(json_path, output_path)
    _output(result, ctx_obj)


@process.command("uppercase")
@click.argument("json_path")
@click.option("-o", "--output", "output_path", default=None, help="Output path.")
@pass_ctx
def process_uppercase(ctx_obj, json_path, output_path):
    """Run only first-letter uppercasing on segments."""
    from cli_anything.asr_transcribe.core.process import uppercase_step

    result = uppercase_step(json_path, output_path)
    _output(result, ctx_obj)


@process.command("split")
@click.argument("json_path")
@click.option("-o", "--output", "output_path", default=None, help="Output path.")
@click.option("--max-length", default=120, type=int, help="Max sentence length before splitting.")
@pass_ctx
def process_split(ctx_obj, json_path, output_path, max_length):
    """Run only long-sentence splitting on segments."""
    from cli_anything.asr_transcribe.core.process import split_step

    result = split_step(json_path, output_path, max_length=max_length)
    _output(result, ctx_obj)


# ── export ────────────────────────────────────────────────────────────


@cli.group()
def export():
    """Output format generation."""
    pass


@export.command("formats")
@pass_ctx
def export_formats(ctx_obj):
    """List all available export formats."""
    from cli_anything.asr_transcribe.core.export import list_formats

    result = list_formats()
    _output(result, ctx_obj)


@export.command("convert")
@click.argument("json_path")
@click.option("-f", "--formats", "format_list", default=None,
              help="Comma-separated list of formats (default: all).")
@click.option("-o", "--output-dir", default=None, help="Output directory.")
@pass_ctx
def export_convert(ctx_obj, json_path, format_list, output_dir):
    """Export WhisperX JSON to one or more output formats."""
    from cli_anything.asr_transcribe.core.export import export_convert as _export

    formats = format_list.split(",") if format_list else None
    result = _export(json_path, formats=formats, output_dir=output_dir)
    _output(result, ctx_obj)


# ── llm ───────────────────────────────────────────────────────────────


@cli.group()
def llm():
    """LLM workflow operations."""
    pass


@llm.command("summarize")
@click.argument("json_path")
@click.option("-o", "--output-dir", default=None, help="Output directory.")
@pass_ctx
def llm_summarize(ctx_obj, json_path, output_dir):
    """Generate summaries from a transcript JSON file."""
    from cli_anything.asr_transcribe.core.llm_tasks import run_summarize

    result = run_summarize(json_path, output_dir)
    _output(result, ctx_obj)


@llm.command("toc")
@click.argument("json_path")
@click.option("-o", "--output-dir", default=None, help="Output directory.")
@pass_ctx
def llm_toc(ctx_obj, json_path, output_dir):
    """Generate table of contents from a transcript JSON file."""
    from cli_anything.asr_transcribe.core.llm_tasks import run_toc

    result = run_toc(json_path, output_dir)
    _output(result, ctx_obj)


@llm.command("chunk")
@click.argument("json_path")
@click.option("--target-minutes", type=float, default=None,
              help="Override chunk target duration in minutes.")
@click.option("--max-chars", type=int, default=None,
              help="Override max characters per chunk.")
@pass_ctx
def llm_chunk(ctx_obj, json_path, target_minutes, max_chars):
    """Preview how a transcript would be chunked for batched processing."""
    from cli_anything.asr_transcribe.core.llm_tasks import run_chunk_preview

    result = run_chunk_preview(json_path, target_minutes, max_chars)
    _output(result, ctx_obj)


@llm.command("models")
@pass_ctx
def llm_models(ctx_obj):
    """Inspect loaded model configurations and profiles."""
    from cli_anything.asr_transcribe.core.llm_tasks import run_models_info

    result = run_models_info()
    _output(result, ctx_obj)


@llm.command("validate-toc")
@click.argument("toc_path")
@click.option("--transcript-json", default=None,
              help="Source WhisperX JSON for boundary validation.")
@pass_ctx
def llm_validate_toc(ctx_obj, toc_path, transcript_json):
    """Validate a TOC JSON file structure and boundaries."""
    from cli_anything.asr_transcribe.core.llm_tasks import run_validate_toc

    result = run_validate_toc(toc_path, transcript_json)
    _output(result, ctx_obj)


@llm.command("debug")
@pass_ctx
def llm_debug(ctx_obj):
    """Run LLM debug mode using configured debug_file."""
    from cli_anything.asr_transcribe.core.llm_tasks import run_debug

    result = run_debug()
    _output(result, ctx_obj)


# ── bag ───────────────────────────────────────────────────────────────


@cli.group()
def bag():
    """BagIt archive operations."""
    pass


@bag.command("validate")
@click.argument("bag_path")
@pass_ctx
def bag_validate(ctx_obj, bag_path):
    """Validate a BagIt directory structure."""
    from cli_anything.asr_transcribe.core.bag_manager import validate_bag

    result = validate_bag(bag_path)
    _output(result, ctx_obj)


@bag.command("zip")
@click.argument("bag_path")
@pass_ctx
def bag_zip(ctx_obj, bag_path):
    """Create ZIP archive of a bag directory."""
    from cli_anything.asr_transcribe.core.bag_manager import zip_bag

    result = zip_bag(bag_path)
    _output(result, ctx_obj)


@bag.command("create")
@click.argument("output_dir")
@click.option("--files", "file_list", default=None, help="Comma-separated file paths to include.")
@pass_ctx
def bag_create(ctx_obj, output_dir, file_list):
    """Create a new BagIt directory structure."""
    from cli_anything.asr_transcribe.core.bag_manager import create_bag

    files = file_list.split(",") if file_list else None
    result = create_bag(output_dir, files=files)
    _output(result, ctx_obj)


# ── email ─────────────────────────────────────────────────────────────


@cli.group()
def email():
    """Email notification operations."""
    pass


@email.command("test")
@pass_ctx
def email_test(ctx_obj):
    """Test SMTP connectivity using config settings."""
    from cli_anything.asr_transcribe.core.email_ops import test_email

    result = test_email()
    _output(result, ctx_obj)


# ── deps ──────────────────────────────────────────────────────────────


@cli.command("deps")
@pass_ctx
def deps(ctx_obj):
    """Check backend dependency availability."""
    from cli_anything.asr_transcribe.utils.asr_backend import check_dependencies

    result = check_dependencies()
    _output(result, ctx_obj)


# ── REPL ──────────────────────────────────────────────────────────────


@cli.command("repl", hidden=True)
@click.pass_context
def repl(ctx):
    """Interactive REPL mode."""
    from cli_anything.asr_transcribe.utils.repl_skin import ReplSkin
    from cli_anything.asr_transcribe.core.session import Session

    skin = ReplSkin("asr_transcribe", version=__version__)
    session = Session()

    skin.print_banner()

    # Create prompt_toolkit session if available
    pt_session = skin.create_prompt_session()

    commands_help = {
        "config show": "Display current configuration",
        "config validate": "Validate config.toml",
        "config init": "Create config.toml from example",
        "config set <key> <val>": "Set a config value (e.g. whisper.device cuda)",
        "config diff": "Show differences from defaults",
        "transcribe file <path>": "Transcribe a single audio file",
        "transcribe batch <dir>": "Transcribe all files in directory",
        "info audio <path>": "Show audio file metadata",
        "info segments <json>": "Show segment statistics",
        "info words <json>": "Word-level detail and confidence",
        "info speakers <json>": "Per-speaker statistics",
        "info language <json>": "Language metadata",
        "info hallucinations <json>": "Check for hallucination indicators",
        "info files <dir>": "List eligible audio files",
        "info bag <path>": "Show BagIt metadata",
        "process segments <json>": "Post-process WhisperX segments (all steps)",
        "process buffer <json>": "Sentence-buffering only",
        "process uppercase <json>": "First-letter uppercasing only",
        "process split <json>": "Long-sentence splitting only",
        "export formats": "List available export formats",
        "export convert <json>": "Export to format(s)",
        "llm summarize <json>": "Generate summaries",
        "llm toc <json>": "Generate table of contents",
        "llm chunk <json>": "Preview chunking for batched mode",
        "llm models": "Inspect model configs and profiles",
        "llm validate-toc <json>": "Validate a TOC JSON file",
        "llm debug": "Run LLM debug mode",
        "bag validate <path>": "Validate BagIt structure",
        "bag zip <path>": "ZIP a bag directory",
        "bag create <dir>": "Create a new bag structure",
        "email test": "Test SMTP connectivity",
        "deps": "Check dependency availability",
        "help": "Show this help",
        "quit / exit": "Exit the REPL",
    }

    while True:
        try:
            line = skin.get_input(pt_session)
        except (KeyboardInterrupt, EOFError):
            skin.print_goodbye()
            break

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            skin.print_goodbye()
            break

        if cmd == "help":
            skin.help(commands_help)
            continue

        if cmd == "status":
            _output(session.to_dict(), ctx.obj)
            continue

        # Dispatch to Click commands by re-invoking the CLI
        try:
            # Check for --json flag in args
            args = parts
            json_mode = "--json" in args
            if json_mode:
                args = [a for a in args if a != "--json"]

            old_json = ctx.obj.json_mode
            ctx.obj.json_mode = json_mode

            cli.main(args, standalone_mode=False, **{"parent": ctx})

            ctx.obj.json_mode = old_json
            session.record(line)
        except click.exceptions.UsageError as e:
            skin.error(str(e))
        except SystemExit:
            pass
        except Exception as e:
            skin.error(f"{type(e).__name__}: {e}")


# ── Entry point ───────────────────────────────────────────────────────


def main():
    cli()


if __name__ == "__main__":
    main()
