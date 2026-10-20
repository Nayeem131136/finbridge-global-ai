"""Tiny .env loader (no extra dependency). Reads KEY=VALUE lines from backend/.env or ./.env.
Real environment variables always win. The .env file is git-ignored; never commit keys."""
import os
from pathlib import Path


def load() -> None:
    for p in (Path(__file__).resolve().parents[1] / ".env", Path.cwd() / ".env"):
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip().removeprefix("export ").strip()
            if not os.environ.get(k):          # real non-empty environment variables win
                os.environ[k] = v.strip().strip('"').strip("'")
