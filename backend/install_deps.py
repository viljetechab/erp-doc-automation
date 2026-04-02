"""Temporary script to install dependencies and print output."""

import subprocess
import sys

packages = [
    "structlog",
    "pydantic-settings",
    "aiosqlite",
    "python-multipart",
    "openai",
    "PyMuPDF",
    "lxml",
    "httpx",
]

for pkg in packages:
    print(f"Installing {pkg}...", flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-cache-dir", pkg],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        # Get the last meaningful line
        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
        status = lines[-1] if lines else "OK"
        print(f"  ✓ {pkg}: {status}", flush=True)
    else:
        print(f"  ✗ {pkg} FAILED: {result.stderr.strip()}", flush=True)

print("\nDone! All packages processed.", flush=True)
