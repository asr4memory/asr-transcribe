#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"

VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"

TARGET="${VENV_DIR}/lib/python3.12/site-packages/lightning_fabric/utilities/cloud_io.py"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "ERROR: ${PYTHON_BIN} not found/executable. Have you run 'uv sync' (or 'uv venv') yet?"
  exit 1
fi

if [[ ! -f "${TARGET}" ]]; then
  echo "ERROR: Target file not found:"
  echo "  ${TARGET}"
  echo "Is lightning_fabric installed? (e.g. 'uv sync')"
  exit 1
fi

# Use patch
"${PYTHON_BIN}" - <<PY
from pathlib import Path
import re

path = Path(r"""${TARGET}""")
txt = path.read_text(encoding="utf-8")

# Already patched?
if "Defaulting to `weights_only=False` for local checkpoint" in txt:
    print(f"OK: Patch already applied: {path}")
    raise SystemExit(0)

# We want to insert directly BEFORE the local fs line:
#   fs = get_filesystem(path_or_url)
m = re.search(r'^(?P<indent>\s*)fs\s*=\s*get_filesystem\(path_or_url\)\s*$', txt, flags=re.M)
if not m:
    raise SystemExit(
        f"ERROR: Target line 'fs = get_filesystem(path_or_url)' not found in {path} "
        f"(file/version differs)."
    )

indent = m.group("indent")

insertion = (
    f"{indent}# Defaulting to `weights_only=False` for local checkpoint to match remote behavior\n"
    f"{indent}if weights_only is None:\n"
    f"{indent}    weights_only = False\n"
)

pos = m.start()
txt2 = txt[:pos] + insertion + txt[pos:]
path.write_text(txt2, encoding="utf-8")

print(f"PATCHED: {path} (local default weights_only=False inserted)")
PY