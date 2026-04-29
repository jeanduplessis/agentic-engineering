from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import venv
from typing import Any, TextIO

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
    except ModuleNotFoundError as exc:
        sys.modules.pop("tiktoken", None)
        if os.environ.get(NO_BOOTSTRAP_ENV) == "1":
            raise RuntimeError(
                f"tiktoken is required for exact counts. Auto-bootstrap disabled by {NO_BOOTSTRAP_ENV}=1."
            ) from exc
        return bootstrap_and_import(exc)


def import_tiktoken_for_cli(stderr: TextIO) -> Any | None:
    try:
        return import_tiktoken()
    except RuntimeError as exc:
        print(str(exc), file=stderr)
        return None


def bootstrap_and_import(original: ModuleNotFoundError):
    directory = venv_dir()
    python = venv_python(directory)
    purelib = ""
    inserted = False
    try:
        if not python.exists():
            venv.EnvBuilder(with_pip=True).create(directory)
        check = subprocess.run(
            [str(python), "-c", "import tiktoken"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if check.returncode != 0:
            subprocess.run(
                [str(python), "-m", "pip", "install", "tiktoken>=0.12.0"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        purelib = subprocess.check_output(
            [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
            text=True,
        ).strip()
        if purelib and purelib not in sys.path:
            sys.path.insert(0, purelib)
            inserted = True
        import tiktoken

        return tiktoken
    except Exception as exc:
        if inserted and purelib in sys.path:
            sys.path.remove(purelib)
        sys.modules.pop("tiktoken", None)
        raise RuntimeError(
            f"tiktoken is required for exact counts. Auto-bootstrap failed: {exc}"
        ) from original


def bootstrap_and_reexec(stderr: TextIO) -> None:
    directory = venv_dir()
    python = venv_python(directory)

    try:
        if not python.exists():
            print(f"Creating token-count venv: {directory}", file=stderr)
            venv.EnvBuilder(with_pip=True).create(directory)

        check = subprocess.run(
            [str(python), "-c", "import tiktoken"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if check.returncode != 0:
            install_cmd = [str(python), "-m", "pip", "install", "tiktoken>=0.12.0"]
            print(f"Installing tiktoken in {directory}", file=stderr)
            subprocess.run(install_cmd, check=True, stdout=stderr, stderr=stderr)

        env = os.environ.copy()
        env[BOOTSTRAPPED_ENV] = "1"
        os.execvpe(str(python), [str(python), "-m", "tools.llm_token_count", *sys.argv[1:]], env)
    except Exception as exc:  # pragma: no cover - user-facing recovery path
        print(f"tiktoken is required for exact counts. Auto-bootstrap failed: {exc}", file=stderr)
        print(
            f"Create a venv, install tiktoken>=0.12.0, or set {VENV_ENV} to a usable venv path and retry.",
            file=stderr,
        )
        return None


def count_text(text: str, *, encoding: str | None = None, model: str | None = None) -> dict[str, Any]:
    """Return exact token metrics for caller-provided text."""
    if model is not None and encoding is not None:
        raise ValueError("model and encoding are mutually exclusive")
    try:
        tiktoken = import_tiktoken()
    except RuntimeError:
        if os.environ.get(NO_BOOTSTRAP_ENV) == "1":
            raise
        return count_text_via_venv(text, encoding=encoding, model=model)
    model_name = model
    if model_name is None and encoding is None:
        model_name = DEFAULT_MODEL

    try:
        if model_name:
            try:
                enc = tiktoken.encoding_for_model(model_name)
                source = f"model:{model_name}"
            except Exception:
                if model_name not in MODEL_ENCODINGS:
                    raise
                resolved_encoding = MODEL_ENCODINGS[model_name]
                enc = tiktoken.get_encoding(resolved_encoding)
                source = f"model:{model_name}->encoding:{resolved_encoding}"
        else:
            enc = tiktoken.get_encoding(encoding)
            source = f"encoding:{encoding}"
    except Exception as exc:  # tiktoken raises different errors across versions
        raise RuntimeError(f"Could not load tiktoken encoding ({exc}).") from exc

    count = len(enc.encode(text, disallowed_special=()))
    return {
        "tokens": count,
        "encoding": enc.name,
        "source": source,
        "characters": len(text),
    }


def count_text_via_venv(text: str, *, encoding: str | None = None, model: str | None = None) -> dict[str, Any]:
    directory = venv_dir()
    python = venv_python(directory)
    try:
        if not python.exists():
            venv.EnvBuilder(with_pip=True).create(directory)
        check = subprocess.run(
            [str(python), "-c", "import tiktoken"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if check.returncode != 0:
            subprocess.run(
                [str(python), "-m", "pip", "install", "tiktoken>=0.12.0"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        code = r'''
import json
import sys
import tiktoken
cfg = json.loads(sys.argv[1])
text = sys.stdin.read()
model = cfg.get("model")
encoding = cfg.get("encoding")
if model is None and encoding is None:
    model = cfg["default_model"]
try:
    if model:
        try:
            enc = tiktoken.encoding_for_model(model)
            source = f"model:{model}"
        except Exception:
            mappings = cfg.get("model_encodings", {})
            if model not in mappings:
                raise
            resolved = mappings[model]
            enc = tiktoken.get_encoding(resolved)
            source = f"model:{model}->encoding:{resolved}"
    else:
        enc = tiktoken.get_encoding(encoding)
        source = f"encoding:{encoding}"
except Exception as exc:
    print(f"Could not load tiktoken encoding ({exc}).", file=sys.stderr)
    sys.exit(2)
print(json.dumps({"tokens": len(enc.encode(text, disallowed_special=())), "encoding": enc.name, "source": source, "characters": len(text)}, ensure_ascii=False))
'''
        completed = subprocess.run(
            [
                str(python),
                "-c",
                code,
                json.dumps({"model": model, "encoding": encoding, "default_model": DEFAULT_MODEL, "model_encodings": MODEL_ENCODINGS}),
            ],
            input=text,
            text=True,
            capture_output=True,
        )
    except Exception as exc:  # pragma: no cover - user-facing recovery path
        raise RuntimeError(f"tiktoken is required for exact counts. Auto-bootstrap failed: {exc}") from exc
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "token counting failed"
        raise RuntimeError(message)
    return json.loads(completed.stdout)


def format_plain(result: dict[str, Any]) -> str:
    return (
        f"tokens={result['tokens']} encoding={result['encoding']} "
        f"source={result['source']} characters={result['characters']}"
    )


def main(argv: list[str] | None = None, *, stdin: TextIO | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    args = parser().parse_args(argv)
    text = stdin.read()
    try:
        result = count_text(text, encoding=args.encoding, model=args.model)
    except Exception as exc:
        print(str(exc), file=stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False), file=stdout)
    else:
        print(format_plain(result), file=stdout)
    return 0


__all__ = [
    "DEFAULT_MODEL",
    "MODEL_ENCODINGS",
    "count_text",
    "format_plain",
    "main",
]
