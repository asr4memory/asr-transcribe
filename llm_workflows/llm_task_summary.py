import sys
from pathlib import Path
from config.app_config import get_config
from utils.utilities import cleanup_cuda_memory
from subprocesses.llm_subprocess import load_model_config, load_model_from_config, generate

config = get_config()
MODEL_PATH = config["summarization"]["sum_model_path"]
MODEL_CONFIG_PATH = config["summarization"].get("sum_model_config", "")

MAX_TOKENS = 1024
TEMPERATURE = 0.0
TOP_P = 1.0
REPEAT_PENALTY = 1.0


def get_system_prompt(language: str) -> str:
    base = Path(__file__).parent / "prompts" / "summarization"
    filename = "summary_en.md" if language == "en" else "summary_de.md"
    return (base / filename).read_text()


def build_user_prompt(segments) -> str:
    return "\n".join(segment["text"] for segment in segments)


def run(segments: list[dict], languages: list[str]) -> dict:
    """Runs Summary with retries. Returns {lang: text}."""

    model_cfg = load_model_config(MODEL_CONFIG_PATH)
    effective_max_trials = len(model_cfg.get("trials", [])) or 3
    user_prompt_text = build_user_prompt(segments)
    results = {}
    llm = None

    translation = False
    language = None

    if languages == ["de", "en"] or languages == ["en", "de"]:
        language = ["de"]
        translation = True
    elif languages == ["de"] or languages == ["en"]:
        language = languages[0]

    for trial in range(1, effective_max_trials + 1):
        try:
            if llm is None:
                llm = load_model_from_config(MODEL_PATH, trial, model_cfg)
            results = {}
            meta = {
                "task": "Summary",
                "lang": language,
                "trial": trial,
            }
            output = generate(
                llm,
                get_system_prompt(language),
                user_prompt_text,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                top_p=TOP_P,
                repeat_penalty=REPEAT_PENALTY,
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
            if trial < effective_max_trials:
                print(f"Summary error on trial {trial}: {e}, retrying...", file=sys.stderr)
            else:
                print(f"Summary failed: {e}", file=sys.stderr)
                results[language] = ""
        
    if translation:
        try:
            if llm is None:
                llm = load_model_from_config(MODEL_PATH, 1, model_cfg)
            system_prompt = "Du bist ein präziser Übersetzer. Übersetze die folgende Zusammenfassung eines Transkript ins Englische"
            meta = {
                "task": "Summary",
                "lang": "en",
                "trial": 1,
            }
            output = generate(
                llm,
                system_prompt,
                results[language],
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                top_p=TOP_P,
                repeat_penalty=REPEAT_PENALTY,
                meta=meta,
            )
            results["en"] = output
            print(f"Summary (en): done", file=sys.stderr)
        except Exception as e:
            print(f"Summary translation failed: {e}", file=sys.stderr)
            results["en"] = ""

    if llm is not None:
        llm.close()
        del llm

    return results
