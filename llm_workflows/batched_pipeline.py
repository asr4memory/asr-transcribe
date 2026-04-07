"""
Batched pipeline orchestration for long transcripts.

Loads model once, generates shared chunk synopses, then runs
summary reduction and TOC normalization through the same instance.
"""

import json
import sys
from pathlib import Path

from config.app_config import get_config
from utils.utilities import cleanup_cuda_memory
from subprocesses.llm_subprocess import (
    load_model_config,
    load_model_from_config,
    generate,
    parse_json_output,
)
from llm_workflows.chunking import chunk_segments
from llm_workflows.shared_synopsis import generate_all_synopses
from llm_workflows.llm_task_summary import run_batched as summary_reduce
from llm_workflows.llm_task_toc import (
    run_batched as toc_normalize,
    get_translation_prompt,
    validate_translation_fields,
)

config = get_config()


def run(segments, languages, use_summarization, use_toc):
    """Batched pipeline entry point. Returns result dict."""
    language, translation = _resolve_language(languages)
    model_cfg, model_path = _load_model_cfg()

    transcript_start = segments[0].get("start", 0.0) if segments else 0.0
    transcript_end = segments[-1].get("end", 0.0) if segments else 0.0

    chunks = chunk_segments(segments)
    print(
        f"Batched mode: {len(segments)} segments → {len(chunks)} chunks",
        file=sys.stderr,
    )

    emit_debug = config["llm_meta"].get("emit_debug_artifacts", False)
    debug_artifacts = {}
    if emit_debug:
        debug_artifacts["chunks"] = [
            {
                "chunk_id": c["chunk_id"],
                "start": c["start"],
                "end": c["end"],
                "segment_count": len(c["segments"]),
            }
            for c in chunks
        ]

    llm = load_model_from_config(model_path, 1, model_cfg)
    result = {}
    try:
        synopses = generate_all_synopses(llm, chunks, language, model_cfg)

        if emit_debug:
            debug_artifacts["synopses"] = synopses

        if use_summarization:
            result["summaries"] = _reduce_summary(
                synopses, language, translation, llm, model_cfg
            )

        if use_toc:
            toc_result, toc_debug = _normalize_toc(
                synopses,
                language,
                translation,
                llm,
                model_cfg,
                transcript_start,
                transcript_end,
                emit_debug,
            )
            result["toc"] = toc_result
            debug_artifacts.update(toc_debug)

    finally:
        llm.close()
        del llm
        cleanup_cuda_memory()

    if emit_debug:
        debug_output_dir = config["llm_meta"].get("output_debug", "")
        if debug_output_dir:
            _write_debug_artifacts(debug_output_dir, debug_artifacts)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_language(languages):
    """Returns (primary_language, needs_translation)."""
    if set(languages) == {"de", "en"}:
        return "de", True
    return languages[0], False


def _load_model_cfg():
    """Load model config for batched mode. Returns (model_cfg, model_path)."""
    model_path = config["summarization"]["sum_model_path"]
    config_path = config["summarization"].get("sum_model_config", "")
    return load_model_config(config_path), model_path


def _reduce_summary(synopses, language, translation, llm, model_cfg):
    """Run summary reduction + optional translation. Returns summaries dict."""
    summaries = {}
    try:
        summaries[language] = summary_reduce(synopses, language, llm, model_cfg)
    except Exception as e:
        print(f"Batched summary reduce failed: {e}", file=sys.stderr)
        summaries[language] = ""

    if translation:
        summaries["en"] = _translate_summary(summaries.get(language, ""), llm)

    return summaries


def _translate_summary(de_summary, llm):
    """Translate German summary to English. Returns translated text or empty string."""
    if not de_summary:
        return ""
    try:
        translation_prompt = (
            "Reasoning: low.\n"
            "Du bist ein präziser Übersetzer. Übersetze die folgende "
            "Zusammenfassung eines Transkript ins Englische."
        )
        output, _finish_reason = generate(
            llm,
            translation_prompt,
            de_summary,
            max_tokens=1024,
            temperature=0.0,
            top_p=1.0,
            repeat_penalty=1.0,
            meta={"task": "Summary Translation", "lang": "en"},
        )
        print("Summary (en): done", file=sys.stderr)
        return output
    except Exception as e:
        print(f"Batched summary translation failed: {e}", file=sys.stderr)
        return ""


def _normalize_toc(
    synopses,
    language,
    translation,
    llm,
    model_cfg,
    transcript_start,
    transcript_end,
    emit_debug,
):
    """Run TOC normalization + optional translation. Returns (toc_dict, debug_dict)."""
    toc = {}
    debug = {}

    try:
        toc_data = toc_normalize(
            synopses,
            language,
            llm,
            model_cfg,
            transcript_start,
            transcript_end,
        )
        toc[language] = toc_data

        if emit_debug:
            debug["toc_candidates"] = [
                e
                for s in synopses
                if isinstance(s, dict) and "_error" not in s
                for e in s.get("toc_entries", [])
            ]
            debug["toc_normalized"] = toc_data
    except Exception as e:
        print(f"Batched TOC normalize failed: {e}", file=sys.stderr)
        toc[language] = {"_error": str(e)}

    if translation:
        toc["en"] = _translate_toc(toc.get(language), llm)

    return toc, debug


def _translate_toc(de_toc, llm):
    """Translate German TOC to English. Returns parsed JSON or error dict."""
    if not de_toc or (isinstance(de_toc, dict) and "_error" in de_toc):
        return {"_error": "skipped: German TOC failed"}

    toc_json_str = json.dumps(de_toc, ensure_ascii=False)
    try:
        translation_prompt = get_translation_prompt()
        MAX_JSON_RETRIES = 3
        for json_attempt in range(1, MAX_JSON_RETRIES + 1):
            meta = {
                "task": "TOC Translation",
                "lang": "en",
                "json_attempt": json_attempt,
            }
            output, finish_reason = generate(
                llm,
                translation_prompt,
                toc_json_str,
                max_tokens=16384,
                temperature=0.3,
                top_p=0.9,
                repeat_penalty=1.1,
                meta=meta,
            )
            parsed = parse_json_output(output)
            if isinstance(parsed, dict) and "_error" in parsed:
                if finish_reason == "length":
                    parsed["_truncated"] = True
                    return parsed
                if json_attempt < MAX_JSON_RETRIES:
                    continue
                return parsed

            validation_error = validate_translation_fields(de_toc, parsed)
            if validation_error:
                if json_attempt < MAX_JSON_RETRIES:
                    continue
                return {"_error": f"validation failed: {validation_error}"}

            print("TOC Translation (en): done", file=sys.stderr)
            return parsed

    except Exception as e:
        print(f"Batched TOC translation failed: {e}", file=sys.stderr)
        return {"_error": str(e)}

    return {"_error": "unreachable"}


def _write_debug_artifacts(output_dir, artifacts):
    """Write debug JSON files alongside output."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    mapping = {
        "chunks": "_debug_chunks.json",
        "synopses": "_debug_synopses.json",
        "toc_candidates": "_debug_toc_candidates.json",
        "toc_normalized": "_debug_toc_normalized.json",
    }
    for key, filename in mapping.items():
        if key in artifacts:
            try:
                (out / filename).write_text(
                    json.dumps(artifacts[key], ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"Debug: wrote {filename}", file=sys.stderr)
            except Exception as e:
                print(f"Debug: failed to write {filename}: {e}", file=sys.stderr)
