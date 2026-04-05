#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


def run_step(script_name: str):
    script = Path(__file__).parent / script_name
    print(f"\\n=== Running {script_name} ===")
    subprocess.run([sys.executable, str(script)], check=True)


def main():
    run_step("extract_epic_notes.py")
    run_step("clean_note_text.py")
    run_step("extract_fields.py")
    run_step("build_import_csv.py")
    print("\\nPipeline complete.")


if __name__ == "__main__":
    main()
