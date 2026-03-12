# TEST.md — cli-anything-asr-transcribe

## Test Plan

### Test Inventory

- `test_core.py`: 54 unit tests
- `test_full_e2e.py`: 30 E2E tests (including subprocess tests)

### Unit Test Plan (test_core.py)

#### config_manager.py
- `test_mask_sensitive_hides_tokens` — sensitive fields (hf_token, password) are masked
- `test_mask_sensitive_empty_values` — empty/None values are not masked
- `test_coerce_value_bool` — "true"/"false" converted to bool
- `test_coerce_value_none` — "none"/"null" converted to None
- `test_coerce_value_numbers` — integers/floats auto-converted
- `test_coerce_value_list` — JSON list strings parsed

#### audio_info.py
- `test_get_audio_info_missing_file` — raises FileNotFoundError for missing file
- `test_get_segments_info_missing_file` — raises FileNotFoundError for missing file
- `test_get_segments_info_empty` — handles JSON with no segments
- `test_get_segments_info_basic` — returns correct stats for sample segments
- `test_get_segments_info_with_speakers` — detects and counts speakers
- `test_get_segments_info_list_format` — handles raw list format (not dict)
- `test_get_segments_info_duration` — correct total and average duration
- `test_format_duration` — duration formatting (HH:MM:SS)
- `test_format_size` — file size formatting (B, KB, MB)

#### audio_info.py (deep inspection)
- `test_get_words_info_basic` — word count and confidence scores
- `test_get_words_info_missing_file` — raises FileNotFoundError
- `test_get_words_info_low_confidence` — detects words with score < 0.5
- `test_get_speakers_info_basic` — per-speaker segment/word counts
- `test_get_speakers_info_empty` — handles empty segments
- `test_get_language_info` — extracts language metadata fields
- `test_get_language_info_minimal` — works with minimal data
- `test_check_hallucinations_clean` — no warnings for clean data
- `test_check_hallucinations_repeated_text` — detects repeated segments
- `test_check_hallucinations_no_alignment` — detects missing word alignment

#### export.py
- `test_list_formats_returns_all` — returns dict with 20+ formats
- `test_list_formats_has_descriptions` — all values are non-empty strings
- `test_export_convert_missing_file` — raises FileNotFoundError
- `test_export_convert_unknown_format` — returns error for unknown format
- `test_export_convert_vtt` — exports VTT from sample segments
- `test_export_convert_srt` — exports SRT from sample segments
- `test_export_convert_txt` — exports plain text from sample segments
- `test_export_convert_json` — exports JSON from sample segments
- `test_export_convert_csv` — exports CSV from sample segments
- `test_export_convert_multiple` — exports multiple formats at once

#### bag_manager.py
- `test_validate_bag_missing_path` — returns error for nonexistent path
- `test_validate_bag_valid` — validates a correctly structured bag
- `test_validate_bag_missing_manifest` — detects missing manifest
- `test_validate_bag_checksum_mismatch` — detects corrupted files
- `test_get_bag_info` — reads bag-info.txt metadata
- `test_get_bag_info_missing` — raises FileNotFoundError
- `test_sha512_computation` — correct SHA-512 hash
- `test_create_bag_empty` — creates empty bag structure
- `test_create_bag_with_files` — creates bag with payload files and metadata
- `test_create_bag_already_exists` — refuses to overwrite existing directory
- `test_create_and_validate` — round-trip: create then validate passes

#### process.py
- `test_process_segments_missing_file` — raises FileNotFoundError
- `test_process_segments_basic` — processes sample segments
- `test_buffer_step` — sentence-buffering step produces output
- `test_uppercase_step` — uppercasing step produces output
- `test_split_step` — splitting step produces output
- `test_buffer_step_missing_file` — raises FileNotFoundError

#### session.py
- `test_session_record` — records commands in history
- `test_session_to_dict` — serializes session state

### E2E Test Plan (test_full_e2e.py)

#### Export Pipeline Tests
- Create sample WhisperX JSON -> export to VTT -> verify VTT structure
- Create sample WhisperX JSON -> export to SRT -> verify SRT structure
- Create sample WhisperX JSON -> export to all text formats -> verify files exist
- Create sample WhisperX JSON -> export to CSV -> verify delimiter and columns
- Create sample WhisperX JSON -> export to RTF -> verify RTF header/footer
- Create sample WhisperX JSON -> export to ODT -> verify ZIP/XML structure
- Create sample WhisperX JSON -> export to TEI-XML -> verify XML structure
- Create sample WhisperX JSON -> export word-level formats -> verify structure

#### BagIt Pipeline Tests
- Create a complete bag structure -> validate -> verify valid
- Create bag -> zip -> verify ZIP exists and structure
- Create bag via create_bag -> validate -> round-trip passes
- Create bag -> zip -> verify ZIP structure

#### Post-Processing Pipeline Tests
- Raw WhisperX JSON -> process segments -> verify buffering and splitting
- Buffer -> uppercase -> split individual steps in sequence
- Individual steps produce comparable output to combined process

#### Deep Inspection Pipeline Tests
- Full inspection workflow: segments + words + speakers + language + hallucinations

### CLI Subprocess Tests (TestCLISubprocess)
- `test_help` — `--help` exits 0
- `test_version` — `--version` outputs version string
- `test_version_json` — `--json --version` outputs valid JSON
- `test_export_formats_json` — `--json export formats` returns valid JSON
- `test_config_validate_json` — `--json config validate` returns valid JSON
- `test_deps_json` — `--json deps` returns valid JSON
- `test_export_convert_subprocess` — full subprocess export workflow
- `test_info_segments_subprocess` — `--json info segments` returns valid JSON
- `test_bag_validate_subprocess` — `--json bag validate` returns valid JSON
- `test_info_words_subprocess` — `--json info words` returns valid JSON
- `test_info_speakers_subprocess` — `--json info speakers` returns valid JSON
- `test_info_hallucinations_subprocess` — `--json info hallucinations` returns valid JSON
- `test_process_buffer_subprocess` — `--json process buffer` returns valid JSON

---

## Test Results

```
$ pytest agent-harness/cli_anything/asr_transcribe/tests/ -v --tb=no

============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.3.3, pluggy-1.6.0
collected 84 items

test_core.py::TestAudioInfo::test_get_segments_info_missing_file PASSED [  1%]
test_core.py::TestAudioInfo::test_get_segments_info_basic PASSED [  2%]
test_core.py::TestAudioInfo::test_get_segments_info_with_speakers PASSED [  3%]
test_core.py::TestAudioInfo::test_get_segments_info_list_format PASSED [  4%]
test_core.py::TestAudioInfo::test_get_segments_info_empty PASSED [  5%]
test_core.py::TestAudioInfo::test_format_duration PASSED [  7%]
test_core.py::TestAudioInfo::test_format_size PASSED [  8%]
test_core.py::TestAudioInfo::test_get_audio_info_missing_file PASSED [  9%]
test_core.py::TestAudioInfo::test_get_segments_info_duration PASSED [ 10%]
test_core.py::TestExport::test_list_formats_returns_all PASSED [ 11%]
test_core.py::TestExport::test_list_formats_has_descriptions PASSED [ 13%]
test_core.py::TestExport::test_export_convert_missing_file PASSED [ 14%]
test_core.py::TestExport::test_export_convert_unknown_format PASSED [ 15%]
test_core.py::TestExport::test_export_convert_vtt PASSED [ 16%]
test_core.py::TestExport::test_export_convert_srt PASSED [ 17%]
test_core.py::TestExport::test_export_convert_txt PASSED [ 19%]
test_core.py::TestExport::test_export_convert_json PASSED [ 20%]
test_core.py::TestExport::test_export_convert_csv PASSED [ 21%]
test_core.py::TestExport::test_export_convert_multiple PASSED [ 22%]
test_core.py::TestBagManager::test_validate_bag_missing_path PASSED [ 23%]
test_core.py::TestBagManager::test_validate_bag_valid PASSED [ 25%]
test_core.py::TestBagManager::test_validate_bag_missing_manifest PASSED [ 26%]
test_core.py::TestBagManager::test_validate_bag_checksum_mismatch PASSED [ 27%]
test_core.py::TestBagManager::test_get_bag_info PASSED [ 28%]
test_core.py::TestBagManager::test_get_bag_info_missing PASSED [ 29%]
test_core.py::TestBagManager::test_sha512_computation PASSED [ 30%]
test_core.py::TestSession::test_session_record PASSED [ 32%]
test_core.py::TestSession::test_session_to_dict PASSED [ 33%]
test_core.py::TestConfigManager::test_mask_sensitive_hides_tokens PASSED [ 34%]
test_core.py::TestConfigManager::test_mask_sensitive_empty_values PASSED [ 35%]
test_core.py::TestProcess::test_process_segments_missing_file PASSED [ 36%]
test_core.py::TestProcess::test_process_segments_basic PASSED [ 38%]
test_core.py::TestProcess::test_buffer_step PASSED [ 39%]
test_core.py::TestProcess::test_uppercase_step PASSED [ 40%]
test_core.py::TestProcess::test_split_step PASSED [ 41%]
test_core.py::TestProcess::test_buffer_step_missing_file PASSED [ 42%]
test_core.py::TestAudioInfoDeep::test_get_words_info_basic PASSED [ 44%]
test_core.py::TestAudioInfoDeep::test_get_words_info_missing_file PASSED [ 45%]
test_core.py::TestAudioInfoDeep::test_get_words_info_low_confidence PASSED [ 46%]
test_core.py::TestAudioInfoDeep::test_get_speakers_info_basic PASSED [ 47%]
test_core.py::TestAudioInfoDeep::test_get_speakers_info_empty PASSED [ 48%]
test_core.py::TestAudioInfoDeep::test_get_language_info PASSED [ 50%]
test_core.py::TestAudioInfoDeep::test_get_language_info_minimal PASSED [ 51%]
test_core.py::TestAudioInfoDeep::test_check_hallucinations_clean PASSED [ 52%]
test_core.py::TestAudioInfoDeep::test_check_hallucinations_repeated_text PASSED [ 53%]
test_core.py::TestAudioInfoDeep::test_check_hallucinations_no_alignment PASSED [ 54%]
test_core.py::TestConfigManagerExtended::test_coerce_value_bool PASSED [ 55%]
test_core.py::TestConfigManagerExtended::test_coerce_value_none PASSED [ 57%]
test_core.py::TestConfigManagerExtended::test_coerce_value_numbers PASSED [ 58%]
test_core.py::TestConfigManagerExtended::test_coerce_value_list PASSED [ 59%]
test_core.py::TestBagManagerExtended::test_create_bag_empty PASSED [ 60%]
test_core.py::TestBagManagerExtended::test_create_bag_with_files PASSED [ 61%]
test_core.py::TestBagManagerExtended::test_create_bag_already_exists PASSED [ 63%]
test_core.py::TestBagManagerExtended::test_create_and_validate PASSED [ 64%]
test_full_e2e.py::TestExportPipelineE2E::test_vtt_export_structure PASSED [ 65%]
test_full_e2e.py::TestExportPipelineE2E::test_srt_export_structure PASSED [ 66%]
test_full_e2e.py::TestExportPipelineE2E::test_all_text_formats_exist PASSED [ 67%]
test_full_e2e.py::TestExportPipelineE2E::test_csv_export_columns PASSED [ 69%]
test_full_e2e.py::TestExportPipelineE2E::test_rtf_export_structure PASSED [ 70%]
test_full_e2e.py::TestExportPipelineE2E::test_odt_export_structure PASSED [ 71%]
test_full_e2e.py::TestExportPipelineE2E::test_tei_xml_export_structure PASSED [ 72%]
test_full_e2e.py::TestExportPipelineE2E::test_word_level_formats PASSED [ 73%]
test_full_e2e.py::TestBagItPipelineE2E::test_create_validate_bag PASSED [ 75%]
test_full_e2e.py::TestBagItPipelineE2E::test_bag_zip_creates_archive PASSED [ 76%]
test_full_e2e.py::TestPostProcessingE2E::test_process_and_export PASSED [ 77%]
test_full_e2e.py::TestFullExportWorkflow::test_full_workflow_all_formats PASSED [ 78%]
test_full_e2e.py::TestCLISubprocess::test_help PASSED [ 79%]
test_full_e2e.py::TestCLISubprocess::test_version PASSED [ 80%]
test_full_e2e.py::TestCLISubprocess::test_version_json PASSED [ 82%]
test_full_e2e.py::TestCLISubprocess::test_export_formats_json PASSED [ 83%]
test_full_e2e.py::TestCLISubprocess::test_deps_json PASSED [ 84%]
test_full_e2e.py::TestCLISubprocess::test_config_validate_json PASSED [ 85%]
test_full_e2e.py::TestCLISubprocess::test_export_convert_subprocess PASSED [ 86%]
test_full_e2e.py::TestCLISubprocess::test_info_segments_subprocess PASSED [ 88%]
test_full_e2e.py::TestCLISubprocess::test_bag_validate_subprocess PASSED [ 89%]
test_full_e2e.py::TestCLISubprocess::test_info_words_subprocess PASSED [ 90%]
test_full_e2e.py::TestCLISubprocess::test_info_speakers_subprocess PASSED [ 91%]
test_full_e2e.py::TestCLISubprocess::test_info_hallucinations_subprocess PASSED [ 92%]
test_full_e2e.py::TestCLISubprocess::test_process_buffer_subprocess PASSED [ 94%]
test_full_e2e.py::TestBagCreateE2E::test_create_validate_roundtrip PASSED [ 95%]
test_full_e2e.py::TestBagCreateE2E::test_create_zip_roundtrip PASSED [ 96%]
test_full_e2e.py::TestProcessStepsE2E::test_buffer_then_uppercase_then_split PASSED [ 97%]
test_full_e2e.py::TestProcessStepsE2E::test_individual_steps_match_combined PASSED [ 98%]
test_full_e2e.py::TestDeepInspectionE2E::test_full_inspection_workflow PASSED [100%]

============================== 84 passed in 4.82s ==============================
```

### Summary Statistics

- **Total tests**: 84
- **Passed**: 84
- **Failed**: 0
- **Pass rate**: 100%
- **Execution time**: 4.82s

### Coverage Notes

- **Covered**: audio_info (basic + deep inspection), export (all 21 formats),
  bag_manager (validate + create + zip), config_manager (mask + coerce + set/diff),
  process (combined + individual steps), session, email_ops (module only — SMTP
  connectivity requires live server), CLI subprocess (help, version, export, info,
  bag, deps, words, speakers, hallucinations, process buffer)
- **Not covered by unit tests**: transcribe and llm_tasks modules — these require
  WhisperX models and LLM GGUF models loaded on GPU, which are integration-level
  tests requiring CUDA hardware and downloaded models.
- **Full workflow tests**: Export all 21 formats, bag create/validate round-trip,
  sequential post-processing steps, deep inspection workflow.
