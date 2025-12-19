#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"

VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"

TARGET="${VENV_DIR}/lib/python3.12/site-packages/lightning_fabric/utilities/cloud_io.py"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "ERROR: ${PYTHON_BIN} nicht gefunden/ausführbar. Hast du 'uv sync' (oder 'uv venv') schon gemacht?"
  exit 1
fi

if [[ ! -f "${TARGET}" ]]; then
  echo "ERROR: Ziel-Datei nicht gefunden:"
  echo "  ${TARGET}"
  echo "Ist lightning_fabric installiert? (z.B. 'uv sync')"
  exit 1
fi

# Use patch
"${PYTHON_BIN}" - <<PY
from pathlib import Path
import re

path = Path(r"""${TARGET}""")
txt = path.read_text(encoding="utf-8")

# Schon gepatcht?
if "Defaulting to `weights_only=False` for local checkpoint" in txt:
    print(f"OK: Patch bereits vorhanden: {path}")
    raise SystemExit(0)

# Wir wollen direkt VOR der lokalen fs-Zeile einfügen:
#   fs = get_filesystem(path_or_url)
m = re.search(r'^(?P<indent>\s*)fs\s*=\s*get_filesystem\(path_or_url\)\s*$', txt, flags=re.M)
if not m:
    raise SystemExit(
        f"ERROR: Zielzeile 'fs = get_filesystem(path_or_url)' nicht gefunden in {path} "
        f"(Datei/Version weicht ab)."
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

print(f"PATCHED: {path} (local default weights_only=False eingefügt)")
PY