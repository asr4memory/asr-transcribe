import sys
from pathlib import Path
from config.app_config import get_config
from utils.utilities import cleanup_cuda_memory
from subprocesses.llm_subprocess import load_model_config, load_model_from_config, generate, parse_json_output

config = get_config()
MODEL_PATH = config["toc"]["toc_model_path"]
MODEL_CONFIG_PATH = config["toc"].get("toc_model_config", "")

MAX_TOKENS = 16384
TEMPERATURE = 0.3
TOP_P = 0.9
REPEAT_PENALTY = 1.1


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


def run(segments: list[dict], languages: list[str]) -> dict:
    """Runs TOC with retries. Returns {lang: json_data}."""
    model_cfg = load_model_config(MODEL_CONFIG_PATH)
    effective_max_profiles = len(model_cfg.get("profiles", [])) or 3
    user_prompt_text = build_user_prompt(segments)
    results = {}
    llm = None

    translation = False
    language = None

    if languages == ["de", "en"] or languages == ["en", "de"]:
        language = "de"
        translation = True
    else:
        language = languages[0]

    for profile in range(1, effective_max_profiles + 1):
        try:
            if llm is None:
                llm = load_model_from_config(MODEL_PATH, profile, model_cfg)
            results = {}
            meta = {
                "task": "TOC",
                "lang": language,
                "profile": profile,
            }
            output, finish_reason = generate(
                llm,
                get_system_prompt(language),
                user_prompt_text,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                top_p=TOP_P,
                repeat_penalty=REPEAT_PENALTY,
                meta=meta,
            )
            parsed = parse_json_output(output)
            if isinstance(parsed, dict) and "_error" in parsed:
                parsed["_truncated"] = finish_reason == "length"
                results[language] = parsed
                label = "truncated" if parsed["_truncated"] else "invalid"
                print(
                    f"TOC ({language}): JSON parsing failed ({label})",
                    file=sys.stderr,
                )
            else:
                results[language] = parsed
                print(f"TOC ({language}): done", file=sys.stderr)

        except Exception as e:
            if llm is not None:
                llm.close()
                del llm
            llm = None
            cleanup_cuda_memory()
            if profile < effective_max_profiles:
                print(f"TOC error on profile {profile}: {e}, retrying...", file=sys.stderr)
            else:
                print(f"TOC failed: {e}", file=sys.stderr)
                results[language] = {"_error": str(e)}
    
    if translation:
        de_toc = results.get(language)
        if de_toc and not (isinstance(de_toc, dict) and "_error" in de_toc):
            import json
            toc_json_str = json.dumps(de_toc, ensure_ascii=False)
            try:
                if llm is None:
                    llm = load_model_from_config(MODEL_PATH, 1, model_cfg)
                meta = {
                    "task": "TOC Translation",
                    "lang": "en",
                    "profile": 1,
                }
                output, finish_reason = generate(
                    llm,
                    get_translation_prompt(),
                    toc_json_str,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                    top_p=TOP_P,
                    repeat_penalty=REPEAT_PENALTY,
                    meta=meta,
                )
                parsed = parse_json_output(output)
                if isinstance(parsed, dict) and "_error" in parsed:
                    parsed["_truncated"] = finish_reason == "length"
                    results["en"] = parsed
                    label = "truncated" if parsed["_truncated"] else "invalid"
                    print(
                        f"TOC Translation (en): JSON parsing failed ({label})",
                        file=sys.stderr,
                    )
                else:
                    results["en"] = parsed
                    print(f"TOC Translation (en): done", file=sys.stderr)

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
