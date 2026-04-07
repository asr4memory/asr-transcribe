import sys
from pathlib import Path
from config.app_config import get_config
from utils.utilities import cleanup_cuda_memory
from subprocesses.llm_subprocess import (
    load_model_config,
    load_model_from_config,
    generate,
    select_profile,
)
from llm_workflows.shared_synopsis import collect_summary_points, collect_key_entities

config = get_config()
MODEL_PATH_SUMMARIZATION = config["summarization"]["sum_model_path"]
SUMMARIZATION_MODEL_CONFIG_PATH = config["summarization"].get("sum_model_config", "")

MODEL_PATH_TRANSLATION = config["translation"]["translation_model_path"]
TRANSLATION_MODEL_CONFIG_PATH = config["translation"].get("translation_model_config", "")


## SUMMARY WORKFLOW ##


def get_system_prompt(language: str) -> str:
    base = Path(__file__).parent / "prompts" / "summarization"
    filename = "summary_en.md" if language == "en" else "summary_de.md"
    return (base / filename).read_text()


def get_reduce_prompt(language: str) -> str:
    base = Path(__file__).parent / "prompts" / "summarization"
    filename = "summary_reduce_en.md" if language == "en" else "summary_reduce_de.md"
    return (base / filename).read_text()


def build_user_prompt(segments) -> str:
    return "\n".join(segment["text"] for segment in segments)


def build_reduce_user_prompt(synopses: list[dict]) -> str:
    """Build user prompt for the reduction step from synopses."""
    points = collect_summary_points(synopses)
    entities = collect_key_entities(synopses)
    sections = []
    sections.append("## Stichpunkte / Bullet Points\n")
    for i, point in enumerate(points, 1):
        sections.append(f"{i}. {point}")
    if entities:
        sections.append("\n## Entitäten / Key Entities\n")
        sections.append(", ".join(entities))
    return "\n".join(sections)


def run_batched(synopses: list[dict], language: str, llm, model_cfg: dict) -> str:
    """Reduce synopses into a single prose summary. Returns summary text."""
    system_prompt = get_reduce_prompt(language)
    user_prompt = build_reduce_user_prompt(synopses)

    max_tokens = 8192
    temperature = 0.0
    top_p = 1.0
    repeat_penalty = 1.0

    meta = {
        "task": "Summary Reduce",
        "lang": language,
    }
    output, _finish_reason = generate(
        llm,
        system_prompt,
        user_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        repeat_penalty=repeat_penalty,
        meta=meta,
    )
    print(f"Summary reduce ({language}): done", file=sys.stderr)
    return output


def run(segments: list[dict], languages: list[str]) -> dict:
    """Runs Summary with retries. Returns {lang: text}."""

    model_cfg_sum = load_model_config(SUMMARIZATION_MODEL_CONFIG_PATH)
    effective_max_profiles = len(model_cfg_sum.get("profiles", [])) or 3
    user_prompt_text = build_user_prompt(segments)

    max_tokens = 8192
    temperature = 0.0
    top_p = 1.0
    repeat_penalty = 1.0

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
    start_profile = select_profile(model_cfg_sum, input_chars, max_tokens)
    print(
        f"Summary: estimated input {input_chars} chars → starting at profile {start_profile}",
        file=sys.stderr,
    )

    for profile in range(start_profile, effective_max_profiles + 1):
        try:
            if llm is None:
                llm = load_model_from_config(MODEL_PATH_SUMMARIZATION, profile, model_cfg_sum)
            meta = {
                "task": "Summary",
                "lang": language,
                "profile": profile,
            }
            output, _finish_reason = generate(
                llm,
                system_prompt_text,
                user_prompt_text,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                repeat_penalty=repeat_penalty,
                meta=meta,
            )
            results[language] = output
            print(f"Summary ({language}): done", file=sys.stderr)
            break

        except Exception as e:
            if llm is not None:
                llm.close()
                del llm
            llm = None
            cleanup_cuda_memory()
            if profile < effective_max_profiles:
                print(
                    f"Summary error on profile {profile}: {e}, retrying...",
                    file=sys.stderr,
                )
            else:
                print(f"Summary failed: {e}", file=sys.stderr)
                results[language] = ""

    ## TRANSLATION OF SUMMARY WORKFLOW ##

    if translation:
        de_summary = results.get(language)
        if de_summary:
            max_tokens = 1024
            temperature = 0.0
            top_p = 1.0
            repeat_penalty = 1.0
            model_cfg_trans = load_model_config(TRANSLATION_MODEL_CONFIG_PATH)

            try:
                translation_prompt = (
                    "Reasoning: low.\n"
                    "Du bist ein präziser Übersetzer. Übersetze die folgende Zusammenfassung eines Transkript ins Englische."
                )
                translation_input_chars = len(translation_prompt) + len(de_summary)
                translation_profile = select_profile(
                    model_cfg_trans, translation_input_chars, max_tokens
                )
                if llm is not None:
                    llm.close()
                    del llm
                    llm = None
                    cleanup_cuda_memory()
                llm = load_model_from_config(MODEL_PATH_TRANSLATION, translation_profile, model_cfg_trans)
                print(
                    f"Summary translation: input {translation_input_chars} chars → profile {translation_profile}",
                    file=sys.stderr,
                )
                meta = {
                    "task": "Summary Translation",
                    "lang": "en",
                    "profile": translation_profile,
                }
                output, _finish_reason = generate(
                    llm,
                    translation_prompt,
                    de_summary,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    repeat_penalty=repeat_penalty,
                    meta=meta,
                )
                results["en"] = output
                print("Summary (en): done", file=sys.stderr)
            except Exception as e:
                print(f"Summary translation failed: {e}", file=sys.stderr)
                results["en"] = ""
        else:
            print("Summary translation skipped: German summary failed", file=sys.stderr)
            results["en"] = ""

    if llm is not None:
        llm.close()
        del llm

    return results
