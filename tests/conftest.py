"""Shared helpers: import the skill modules and run the script as a subprocess."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "charfit" / "scripts"
SCRIPT = SCRIPTS / "charfit.py"
sys.path.insert(0, str(SCRIPTS))

import _charfit_i18n as i18n  # noqa: E402
import _charfit_rules as rules  # noqa: E402

FAMILY = "\U0001F468\u200d\U0001F469\u200d\U0001F467"
PARTY = "\U0001F389"


def clean_env(**extra: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("CHARFIT_LANG", "LC_ALL", "LC_MESSAGES", "LANG")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"  # the script runs in a subprocess: keep __pycache__ out of the skill
    env.update(extra)
    return env


def run_cli(*args: str, env: Optional[dict] = None, stdin: Optional[bytes] = None, cwd: Path = ROOT):
    """Run the script; returns CompletedProcess with text stdout/stderr (bytes in .stdout_bytes)."""
    proc = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, input=stdin,
                          env=env if env is not None else clean_env(), cwd=str(cwd), timeout=60)
    proc.stdout_bytes = proc.stdout
    proc.stdout = proc.stdout.decode("utf-8")
    proc.stderr = proc.stderr.decode("utf-8")
    return proc


def run_json(*args: str, **kw):
    proc = run_cli(*args, "--json", **kw)
    return proc, json.loads(proc.stdout)
