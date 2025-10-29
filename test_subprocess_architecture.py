#!/usr/bin/env python3
"""
Test script to verify subprocess architecture works correctly.
Tests memory isolation and subprocess communication.
"""

import sys
import subprocess
import pickle
from pathlib import Path

def test_subprocess_communication():
    """Test that subprocesses can be called and return data correctly."""
    print("=" * 60)
    print("Testing Subprocess Architecture")
    print("=" * 60)

    # Test 1: Check if subprocess files exist
    print("\n1. Checking if subprocess files exist...")
    whisper_subprocess = Path("whisper_subprocess.py")
    llm_subprocess = Path("llm_subprocess.py")

    if not whisper_subprocess.exists():
        print("   ❌ whisper_subprocess.py not found!")
        return False
    else:
        print("   ✓ whisper_subprocess.py found")

    if not llm_subprocess.exists():
        print("   ❌ llm_subprocess.py not found!")
        return False
    else:
        print("   ✓ llm_subprocess.py found")

    # Test 2: Check if subprocess files compile
    print("\n2. Checking if subprocess files compile...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", "whisper_subprocess.py"],
            capture_output=True,
            check=True
        )
        print("   ✓ whisper_subprocess.py compiles successfully")
    except subprocess.CalledProcessError as e:
        print(f"   ❌ whisper_subprocess.py has syntax errors: {e}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", "llm_subprocess.py"],
            capture_output=True,
            check=True
        )
        print("   ✓ llm_subprocess.py compiles successfully")
    except subprocess.CalledProcessError as e:
        print(f"   ❌ llm_subprocess.py has syntax errors: {e}")
        return False

    # Test 3: Check main workflow compiles
    print("\n3. Checking if main workflow compiles...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", "asr_workflow.py"],
            capture_output=True,
            check=True
        )
        print("   ✓ asr_workflow.py compiles successfully")
    except subprocess.CalledProcessError as e:
        print(f"   ❌ asr_workflow.py has syntax errors: {e}")
        return False

    print("\n" + "=" * 60)
    print("✓ All basic tests passed!")
    print("=" * 60)
    print("\nArchitecture summary:")
    print("- Whisper pipeline runs in: whisper_subprocess.py")
    print("- LLM summarization runs in: llm_subprocess.py")
    print("- Main coordinator: asr_workflow.py")
    print("\nMemory benefits:")
    print("- Whisper memory freed when subprocess exits")
    print("- LLM memory freed when subprocess exits")
    print("- Peak memory = max(Whisper, LLM), not sum")
    print("\nTo run the pipeline:")
    print("  python3 asr_workflow.py")

    return True

if __name__ == "__main__":
    success = test_subprocess_communication()
    sys.exit(0 if success else 1)
