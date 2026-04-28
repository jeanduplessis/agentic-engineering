#!/usr/bin/env python3
"""Count text tokens with OpenAI tiktoken.

Usage:
  python scripts/count_tokens.py < file.txt
  python scripts/count_tokens.py <<'TEXT'
  hello world
  TEXT
  python scripts/count_tokens.py --encoding o200k_base --json < file.txt

If tiktoken is missing, the script bootstraps it into a persistent venv
(default: ~/.agents/.venvs/llm-optimized-rewrite) and re-executes itself.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

DEFAULT_MODEL = "gpt-5"
MODEL_ENCODINGS = {"gpt-5": "o200k_base"}
VENV_ENV = "LLM_OPTIMIZED_REWRITE_VENV"
LEGACY_VENV_ENV = "TOKEN_EFFICIENT_REWRITE_VENV"
BOOTSTRAPPED_ENV = "LLM_OPTIMIZED_REWRITE_BOOTSTRAPPED"
NO_BOOTSTRAP_ENV = "LLM_OPTIMIZED_REWRITE_NO_BOOTSTRAP"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Count tokens for stdin using tiktoken.")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--encoding", help="tiktoken encoding name")
    group.add_argument("--model", help=f"OpenAI model name (default: {DEFAULT_MODEL})")
    p.add_argument("--json", action="store_true", help="emit JSON instead of plain text")
    return p


def venv_dir() -> Path:
    configured = os.environ.get(VENV_ENV) or os.environ.get(LEGACY_VENV_ENV)
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".agents" / ".venvs" / "llm-optimized-rewrite"


def venv_python(directory: Path) -> Path:
    if os.name == "nt":
        return directory / "Scripts" / "python.exe"
    return directory / "bin" / "python"


def import_tiktoken():
    try:
        import tiktoken

        return tiktoken
    except ModuleNotFoundError:
        if os.environ.get(NO_BOOTSTRAP_ENV) == "1":
            print(
                f"tiktoken is required for exact counts. Auto-bootstrap disabled by {NO_BOOTSTRAP_ENV}=1.",
                file=sys.stderr,
            )
            return None
        if os.environ.get(BOOTSTRAPPED_ENV) == "1":
            print(
                "tiktoken is required for exact counts. It was still unavailable after bootstrapping.",
                file=sys.stderr,
            )
            return None
        return bootstrap_and_reexec()


def bootstrap_and_reexec():
    directory = venv_dir()
    python = venv_python(directory)
    skill_dir = Path(__file__).resolve().parents[1]
    requirements = skill_dir / "requirements.txt"

    try:
        if not python.exists():
            print(f"Creating token-count venv: {directory}", file=sys.stderr)
            venv.EnvBuilder(with_pip=True).create(directory)

        check = subprocess.run(
            [str(python), "-c", "import tiktoken"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if check.returncode != 0:
            install_cmd = [str(python), "-m", "pip", "install"]
            if requirements.exists():
                install_cmd += ["-r", str(requirements)]
            else:
                install_cmd += ["tiktoken>=0.12.0"]
            print(f"Installing tiktoken in {directory}", file=sys.stderr)
            subprocess.run(install_cmd, check=True, stdout=sys.stderr, stderr=sys.stderr)

        env = os.environ.copy()
        env[BOOTSTRAPPED_ENV] = "1"
        os.execvpe(str(python), [str(python), str(Path(__file__).resolve()), *sys.argv[1:]], env)
    except Exception as exc:  # pragma: no cover - user-facing recovery path
        print(f"tiktoken is required for exact counts. Auto-bootstrap failed: {exc}", file=sys.stderr)
        print(
            f"Create a venv, install {requirements if requirements.exists() else 'tiktoken>=0.12.0'}, "
            f"or set {VENV_ENV} to a usable venv path and retry.",
            file=sys.stderr,
        )
        return None


def main() -> int:
    args = parser().parse_args()
    tiktoken = import_tiktoken()
    if tiktoken is None:
        return 2

    text = sys.stdin.read()

    model = args.model
    if model is None and args.encoding is None:
        model = DEFAULT_MODEL

    try:
        if model:
            try:
                enc = tiktoken.encoding_for_model(model)
                source = f"model:{model}"
            except Exception:
                if model not in MODEL_ENCODINGS:
                    raise
                encoding = MODEL_ENCODINGS[model]
                enc = tiktoken.get_encoding(encoding)
                source = f"model:{model}->encoding:{encoding}"
        else:
            enc = tiktoken.get_encoding(args.encoding)
            source = f"encoding:{args.encoding}"
    except Exception as exc:  # tiktoken raises different errors across versions
        print(f"Could not load tiktoken encoding ({exc}).", file=sys.stderr)
        return 2

    # Treat special-token sentinel strings as normal user text. Compression snippets may
    # contain arbitrary prompt text and should not fail because a sentinel appears.
    count = len(enc.encode(text, disallowed_special=()))
    result = {
        "tokens": count,
        "encoding": enc.name,
        "source": source,
        "characters": len(text),
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"tokens={count} encoding={enc.name} source={source} characters={len(text)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
