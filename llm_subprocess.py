"""
Subprocess wrapper for LLM tasks.
Runs LLM model in isolated subprocess to ensure memory is freed after processing.
This allows large models (20GB+) to be loaded and fully cleaned up between files.

Returns a unified result dict:
{
    "summaries": {"de": "...", "en": "..."},
    "toc": {"de": "...", "en": "..."},  # future
    ...
    "_meta": {"trial": 1}
}
"""

import sys
import pickle
from llama_cpp import Llama
from app_config import get_config
from utilities import cleanup_cuda_memory
from llm_workflows.llm_summarization import system_prompt_summaries
from llm_workflows.llm_toc import system_prompt_toc

config = get_config()
n_gpu_layers = config["llm"]["n_gpu_layers"]
model_path = config["llm"]["model_path"]
verbose = config["llm"].get("verbose", False)


def get_languages() -> list[str]:
    languages = config["llm"].get("summary_languages", ["de", "en"])
    if isinstance(languages, str):
        languages = [languages]
    cleaned = []
    for lang in languages:
        if isinstance(lang, str) and lang.strip():
            cleaned.append(lang.strip().lower())
    return cleaned


def load_model(trial: int) -> Llama:
    """Initialise the Llama model with trial-specific context settings."""
    if trial == 1:
        return Llama(
            model_path=model_path,
            n_gpu_layers=n_gpu_layers,
            n_ctx=32768,
            n_batch=512,
            verbose=verbose,
        )
    return Llama(
        model_path=model_path,
        n_gpu_layers=n_gpu_layers,
        n_ctx=65536,
        n_batch=256,
        verbose=verbose,
    )


def user_prompt(segments) -> str:
    """Concatenate all segment texts for the user prompt."""
    return "\n".join(segment["text"] for segment in segments)


def generate(llm: Llama, system_prompt: str, user_prompt: str) -> str:
    """Generate a summary using llama_cpp for a given prompt."""
    output = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=4000,
        temperature=0.3,
        top_p=0.9,
        repeat_penalty=1.2,
    )
    summary = output["choices"][0]["message"]["content"]

    delimiter = "|end|><|start|>assistant<|channel|>final<|message|>"
    if delimiter in summary:
        summary = summary.split(delimiter, 1)[1]

    return summary.strip()


def main():
    """Main subprocess entry point."""
    max_trials = 2
    languages = get_languages()
    llm = None

    # Return empty result if no languages configured
    if not languages:
        result = {"summaries": {}, "_meta": {"trial": 0}}
        sys.stdout.buffer.write(pickle.dumps(result))
        sys.exit(0)

    for trial in range(1, max_trials + 1):
        try:
            # Read pickled segments from stdin (only on first attempt)
            if trial == 1:
                input_data = sys.stdin.buffer.read()
                segments = pickle.loads(input_data)

            llm = load_model(trial)
            user_prompt_text = user_prompt(segments)

            # Generate LLM outputs for each language
            # 1. Summaries
            summaries = {}
            for language in languages:
                system_prompt = system_prompt_summaries(language)
                summaries[language] = generate(llm, system_prompt, user_prompt_text)

            # 2. Table of Contents
            toc = {}  
            for language in languages:
                system_prompt = system_prompt_toc(language)
                toc[language] = generate(llm, system_prompt, user_prompt_text)

            # Build unified result dict
            result = {
                "summaries": summaries,
                "toc": toc,
                "_meta": {"trial": trial},
            }
            sys.stdout.buffer.write(pickle.dumps(result))
            sys.exit(0)

        except Exception as e:
            # Cleanup the failed model and free GPU memory
            if llm is not None:
                del llm
            cleanup_cuda_memory()

            if trial < max_trials:
                print(
                    f"LLM subprocess error on trial {trial}. Retrying with trial {trial + 1}...",
                    file=sys.stderr,
                )
            else:
                # Letzter Versuch fehlgeschlagen
                print(f"LLM subprocess error: {e}", file=sys.stderr)
                import traceback

                traceback.print_exc(file=sys.stderr)
                sys.exit(1)


if __name__ == "__main__":
    main()
