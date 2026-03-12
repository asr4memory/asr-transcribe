"""Configuration management for asr-transcribe."""

import json
import shutil
from pathlib import Path

from cli_anything.asr_transcribe.utils.asr_backend import ensure_project_importable


def _load_config():
    """Load the asr-transcribe config by importing its config system."""
    root = ensure_project_importable()
    import toml

    config_path = root / "config.toml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"config.toml not found at {config_path}.\n"
            f"Run 'cli-anything-asr-transcribe config init' to create one from the example."
        )

    from config.default_config import CONST_DEFAULT_CONFIG

    with open(config_path) as f:
        data = toml.load(f)

    combined = {}
    for section in CONST_DEFAULT_CONFIG:
        combined[section] = {**CONST_DEFAULT_CONFIG[section], **data.get(section, {})}

    return combined


def show_config(as_json: bool = False) -> dict | str:
    """Return the current configuration.

    Args:
        as_json: If True, return JSON string. Otherwise return dict.
    """
    config = _load_config()
    if as_json:
        # Mask sensitive fields
        safe = _mask_sensitive(config)
        return json.dumps(safe, indent=2, default=str)
    return config


def _mask_sensitive(config: dict) -> dict:
    """Mask sensitive fields in config for display."""
    sensitive_keys = {"hf_token", "password", "api_key"}
    result = {}
    for section, values in config.items():
        result[section] = {}
        for key, value in values.items():
            if key in sensitive_keys and value:
                result[section][key] = "***"
            else:
                result[section][key] = value
    return result


def validate_config() -> dict:
    """Validate the configuration and return a report.

    Returns:
        Dict with "valid" (bool), "errors" (list), "warnings" (list).
    """
    errors = []
    warnings = []

    root = ensure_project_importable()
    config_path = root / "config.toml"

    if not config_path.exists():
        return {"valid": False, "errors": ["config.toml not found"], "warnings": []}

    try:
        import toml
        with open(config_path) as f:
            data = toml.load(f)
    except Exception as e:
        return {"valid": False, "errors": [f"Failed to parse config.toml: {e}"], "warnings": []}

    # Check required sections
    for section in ["system", "whisper"]:
        if section not in data:
            errors.append(f"Missing required section: [{section}]")

    # Check paths
    system = data.get("system", {})
    for path_key in ["input_path", "output_path"]:
        path_val = system.get(path_key, "")
        if path_val and not Path(path_val).exists():
            warnings.append(f"system.{path_key} does not exist: {path_val}")

    # Check whisper settings
    whisper = data.get("whisper", {})
    valid_devices = {"cpu", "cuda"}
    device = whisper.get("device", "cpu")
    if device not in valid_devices:
        errors.append(f"whisper.device must be one of {valid_devices}, got: {device}")

    valid_compute = {"float32", "float16", "int8"}
    compute = whisper.get("compute_type", "float32")
    if compute not in valid_compute:
        errors.append(f"whisper.compute_type must be one of {valid_compute}, got: {compute}")

    # Check LLM settings
    llm_meta = data.get("llm_meta", {})
    if llm_meta.get("use_summarization"):
        sum_config = data.get("summarization", {})
        model_path = sum_config.get("sum_model_path", "")
        if model_path and not Path(model_path).exists():
            warnings.append(f"summarization.sum_model_path does not exist: {model_path}")

    if llm_meta.get("use_toc"):
        toc_config = data.get("toc", {})
        model_path = toc_config.get("toc_model_path", "")
        if model_path and not Path(model_path).exists():
            warnings.append(f"toc.toc_model_path does not exist: {model_path}")

    # Check diarization token
    if whisper.get("use_speaker_diarization"):
        token = whisper.get("hf_token")
        if not token or token == "add your Huggingface Token here":
            warnings.append("Speaker diarization enabled but hf_token is not set")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def init_config(force: bool = False) -> dict:
    """Create config.toml from config.example.toml.

    Returns:
        Dict with "created" (bool), "path" (str), "message" (str).
    """
    root = ensure_project_importable()
    config_path = root / "config.toml"
    example_path = root / "config.example.toml"

    if config_path.exists() and not force:
        return {
            "created": False,
            "path": str(config_path),
            "message": "config.toml already exists. Use --force to overwrite.",
        }

    if not example_path.exists():
        return {
            "created": False,
            "path": str(example_path),
            "message": "config.example.toml not found in project root.",
        }

    shutil.copy2(example_path, config_path)
    return {
        "created": True,
        "path": str(config_path),
        "message": f"Created config.toml from example at {config_path}",
    }


def set_config(key: str, value: str) -> dict:
    """Set a configuration value in config.toml.

    Args:
        key: Dot-separated key, e.g. "whisper.device" or "system.zip_bags".
        value: New value (auto-converted to int/float/bool where appropriate).

    Returns:
        Dict with "updated" (bool), "key", "old_value", "new_value", "message".
    """
    root = ensure_project_importable()
    import toml

    config_path = root / "config.toml"
    if not config_path.exists():
        return {"updated": False, "message": "config.toml not found."}

    parts = key.split(".", 1)
    if len(parts) != 2:
        return {"updated": False, "message": f"Key must be section.key format, got: {key}"}

    section, field = parts

    with open(config_path) as f:
        data = toml.load(f)

    if section not in data:
        data[section] = {}

    old_value = data[section].get(field)
    new_value = _coerce_value(value)

    data[section][field] = new_value

    with open(config_path, "w") as f:
        toml.dump(data, f)

    return {
        "updated": True,
        "key": key,
        "old_value": old_value,
        "new_value": new_value,
        "message": f"Set {key} = {new_value!r} (was {old_value!r})",
    }


def _coerce_value(value: str):
    """Auto-convert string to int, float, bool, list, or keep as string."""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() == "none" or value.lower() == "null":
        return None
    # List: ["a", "b"]
    if value.startswith("[") and value.endswith("]"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def diff_config() -> dict:
    """Show differences between current config.toml and defaults.

    Returns:
        Dict mapping "section.key" -> {"default": val, "current": val} for differing values.
    """
    root = ensure_project_importable()
    import toml

    config_path = root / "config.toml"
    if not config_path.exists():
        return {"error": "config.toml not found"}

    from config.default_config import CONST_DEFAULT_CONFIG

    with open(config_path) as f:
        user_data = toml.load(f)

    diffs = {}
    for section, defaults in CONST_DEFAULT_CONFIG.items():
        user_section = user_data.get(section, {})
        for key, default_val in defaults.items():
            user_val = user_section.get(key, default_val)
            if user_val != default_val:
                diffs[f"{section}.{key}"] = {
                    "default": default_val,
                    "current": user_val,
                }

    # Also check for keys in user config that aren't in defaults
    for section, user_section in user_data.items():
        defaults = CONST_DEFAULT_CONFIG.get(section, {})
        for key, user_val in user_section.items():
            full_key = f"{section}.{key}"
            if key not in defaults and full_key not in diffs:
                diffs[full_key] = {
                    "default": "(not in defaults)",
                    "current": user_val,
                }

    return diffs
