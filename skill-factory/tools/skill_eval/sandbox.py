from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Sandbox:
    path: Path
    fixture_type: str


def create_sandbox(base_dir: str | Path, case_id: str, fixture: dict[str, Any] | None = None) -> Sandbox:
    fixture = fixture or {"type": "empty"}
    fixture_type = fixture.get("type", "empty")
    sandbox_root = Path(base_dir) / "sandboxes"
    sandbox_root.mkdir(parents=True, exist_ok=True)
    safe_case_id = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in case_id)
    path = Path(tempfile.mkdtemp(prefix=f"{safe_case_id}-", dir=sandbox_root))

    if fixture_type == "empty":
        return Sandbox(path=path, fixture_type="empty")

    if fixture_type == "copy":
        source = Path(fixture["path"]).expanduser()
        if not source.is_absolute():
            source = Path.cwd() / source
        for item in source.iterdir():
            destination = path / item.name
            if item.is_dir():
                shutil.copytree(item, destination)
            else:
                shutil.copy2(item, destination)
        return Sandbox(path=path, fixture_type="copy")

    raise ValueError(f"Unsupported fixture type: {fixture_type}")
