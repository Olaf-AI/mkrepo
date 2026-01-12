from __future__ import annotations

from pathlib import Path


def safe_join(base_dir: Path, rel_path: str) -> Path:
    """
    Prevent path traversal. rel_path must be relative and cannot escape base_dir.
    """
    rel_path = rel_path.replace("\\", "/").lstrip("/")
    target = (base_dir / rel_path).resolve()
    base = base_dir.resolve()

    # Ensure target is within base
    if base == target or str(target).startswith(str(base) + str(Path.sep)):
        return target
    raise ValueError(f"Unsafe path (path traversal?): {rel_path}")


def write_text_file(base_dir: Path, rel_path: str, content: str) -> Path:
    p = safe_join(base_dir, rel_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p
