import sys
from pathlib import Path
from config.app_config import get_config
from utils.utilities import cleanup_cuda_memory
from subprocesses.llm_subprocess import (
    load_model_config,
    load_model_from_config,
    generate,
    parse_json_output,
    select_profile,
)

config = get_config()
MODEL_PATH = config["toc"]["toc_model_path"]
MODEL_CONFIG_PATH = config["toc"].get("toc_model_config", "")

## TOC WORKFLOW ##


def get_system_prompt(language: str) -> str:
    base = Path(__file__).parent / "prompts" / "toc"
    filename = "toc_en.md" if language == "en" else "toc_de.md"
    return (base / filename).read_text()


def get_translation_prompt() -> str:
    base = Path(__file__).parent / "prompts" / "toc"
    return (base / "toc_translate_en.md").read_text()


def build_user_prompt(segments) -> str:
    lines = ["start\tend\ttranscript"]
    for seg in segments:
        start = seg.get("start", 0)
        end = seg.get("end", start)
        text = seg.get("text", "")
        lines.append(f"{start}\t{end}\t{text}")
    return "\n".join(lines)


def validate_translation_fields(original: list[dict], translated) -> str | None:
    """Validate translated TOC against original.
    Checks: same entry count, no extra/missing fields,
    and level/start/end values are identical to original.
    Returns error message if invalid, None if valid.
    """
    expected_fields = {"level", "title", "start", "end"}
    if not isinstance(translated, list):
        return "translated TOC is not a list"
    if len(translated) != len(original):
        return f"entry count mismatch: original={len(original)}, translated={len(translated)}"
    for i, (orig, trans) in enumerate(zip(original, translated)):
        extra = set(trans.keys()) - expected_fields
        if extra:
            return f"entry {i}: unexpected fields {extra}"
        missing = expected_fields - set(trans.keys())
        if missing:
            return f"entry {i}: missing fields {missing}"
        for field in ("level", "start", "end"):
            if trans[field] != orig[field]:
                return f"entry {i}: '{field}' changed from {orig[field]!r} to {trans[field]!r}"
    return None


def run(segments: list[dict], languages: list[str]) -> dict:
    """Runs TOC with retries. Returns {lang: json_data}."""
    model_cfg = load_model_config(MODEL_CONFIG_PATH)
    effective_max_profiles = len(model_cfg.get("profiles", [])) or 3
    user_prompt_text = build_user_prompt(segments)

    max_tokens = 16384
    temperature = 0.3
    top_p = 0.9
    repeat_penalty = 1.1

    results = {}
    llm = None

    translation = False
    language = None

    if languages == ["de", "en"] or languages == ["en", "de"]:
        language = "de"
        translation = True
    else:
        language = languages[0]

    system_prompt_text = get_system_prompt(language)
    input_chars = len(system_prompt_text) + len(user_prompt_text)
    start_profile = select_profile(model_cfg, input_chars, max_tokens)
    print(
        f"TOC: estimated input {input_chars} chars → starting at profile {start_profile}",
        file=sys.stderr,
    )

    MAX_JSON_RETRIES = 3
    success = False
    for profile in range(start_profile, effective_max_profiles + 1):
        try:
            if llm is None:
                llm = load_model_from_config(MODEL_PATH, profile, model_cfg)
            for json_attempt in range(1, MAX_JSON_RETRIES + 1):
                meta = {
                    "task": "TOC",
                    "lang": language,
                    "profile": profile,
                    "json_attempt": json_attempt,
                }
                output, finish_reason = generate(
                    llm,
                    system_prompt_text,
                    user_prompt_text,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    repeat_penalty=repeat_penalty,
                    meta=meta,
                )
                parsed = parse_json_output(output)
                if isinstance(parsed, dict) and "_error" in parsed:
                    if finish_reason == "length":
                        # Truncated — max_tokens is the hard limit, no retry helps
                        parsed["_truncated"] = True
                        results[language] = parsed
                        print(
                            f"TOC ({language}): truncated (max_tokens={max_tokens}), stopping",
                            file=sys.stderr,
                        )
                        success = True  # not a success, but signals to stop all retries
                        break
                    results[language] = parsed
                    if json_attempt < MAX_JSON_RETRIES:
                        print(
                            f"TOC ({language}): invalid JSON on profile {profile} attempt {json_attempt}, retrying...",
                            file=sys.stderr,
                        )
                    else:
                        print(
                            f"TOC ({language}): invalid JSON after {MAX_JSON_RETRIES} attempts on profile {profile}",
                            file=sys.stderr,
                        )
                else:
                    results[language] = parsed
                    print(
                        f"TOC ({language}): done (profile {profile}, attempt {json_attempt})",
                        file=sys.stderr,
                    )
                    success = True
                    break
            if success:
                break

        except Exception as e:
            if llm is not None:
                llm.close()
                del llm
            llm = None
            cleanup_cuda_memory()
            if profile < effective_max_profiles:
                print(
                    f"TOC error on profile {profile}: {e}, retrying...", file=sys.stderr
                )
            else:
                print(f"TOC failed: {e}", file=sys.stderr)
                results[language] = {"_error": str(e)}

    ## TRANSLATION OF TOC WORKFLOW ##

    if translation:
        de_toc = results.get(language)
        if de_toc and not (isinstance(de_toc, dict) and "_error" in de_toc):
            import json

            max_tokens = 16384
            temperature = 0.3
            top_p = 0.9
            repeat_penalty = 1.1

            toc_json_str = json.dumps(de_toc, ensure_ascii=False)
            try:
                translation_prompt = get_translation_prompt()
                translation_input_chars = len(translation_prompt) + len(toc_json_str)
                translation_profile = select_profile(
                    model_cfg, translation_input_chars, max_tokens
                )
                if llm is not None:
                    llm.close()
                    del llm
                    llm = None
                    cleanup_cuda_memory()
                llm = load_model_from_config(MODEL_PATH, translation_profile, model_cfg)
                print(
                    f"TOC translation: input {translation_input_chars} chars → profile {translation_profile}",
                    file=sys.stderr,
                )
                for json_attempt in range(1, MAX_JSON_RETRIES + 1):
                    meta = {
                        "task": "TOC Translation",
                        "lang": "en",
                        "profile": translation_profile,
                        "json_attempt": json_attempt,
                    }
                    output, finish_reason = generate(
                        llm,
                        translation_prompt,
                        toc_json_str,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        repeat_penalty=repeat_penalty,
                        meta=meta,
                    )
                    parsed = parse_json_output(output)
                    if isinstance(parsed, dict) and "_error" in parsed:
                        if finish_reason == "length":
                            parsed["_truncated"] = True
                            results["en"] = parsed
                            print(
                                f"TOC Translation (en): truncated (max_tokens={max_tokens}), stopping",
                                file=sys.stderr,
                            )
                            break
                        results["en"] = parsed
                        if json_attempt < MAX_JSON_RETRIES:
                            print(
                                f"TOC Translation (en): invalid JSON attempt {json_attempt}, retrying...",
                                file=sys.stderr,
                            )
                        else:
                            print(
                                f"TOC Translation (en): invalid JSON after {MAX_JSON_RETRIES} attempts",
                                file=sys.stderr,
                            )
                        continue
                    # Valid JSON — validate structure against original
                    validation_error = validate_translation_fields(de_toc, parsed)
                    if validation_error:
                        results["en"] = {
                            "_error": f"validation failed: {validation_error}"
                        }
                        if json_attempt < MAX_JSON_RETRIES:
                            print(
                                f"TOC Translation (en): {validation_error}, retrying...",
                                file=sys.stderr,
                            )
                        else:
                            print(
                                f"TOC Translation (en): validation failed after {MAX_JSON_RETRIES} attempts: {validation_error}",
                                file=sys.stderr,
                            )
                        continue
                    results["en"] = parsed
                    print(
                        f"TOC Translation (en): done (attempt {json_attempt})",
                        file=sys.stderr,
                    )
                    break

            except Exception as e:
                if llm is not None:
                    llm.close()
                    del llm
                llm = None
                cleanup_cuda_memory()
                print(f"TOC Translation failed: {e}", file=sys.stderr)
                results["en"] = {"_error": str(e)}
        else:
            results["en"] = {"_error": "skipped: German TOC failed"}

    if llm is not None:
        llm.close()
        del llm

    return results
