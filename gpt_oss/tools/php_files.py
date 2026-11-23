import re
from pathlib import Path

MAX_LINES = 300
MAX_CHARS = 30_000
MAX_HITS = 40

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "vendor",
}

ROOT = Path(".").resolve()


def set_root(root: str | Path):
    """Set the PHP project root."""
    global ROOT
    ROOT = Path(root).resolve()

    if not ROOT.is_dir():
        raise ValueError(f"Project root does not exist: {ROOT}")


def _safe_path(rel: str) -> Path:
    p = (ROOT / rel).resolve()

    if ROOT != p and ROOT not in p.parents:
        raise ValueError("Path is outside the project root")

    return p


def _excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def read(
    path: str,
    start_line: int = 1,
    end_line: int | None = None,
) -> str:
    try:
        p = _safe_path(path)

        if not p.is_file():
            return f"ERROR: file not found: {path}"

        raw = p.read_bytes()

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")

        lines = text.splitlines()
        total = len(lines)

        start = max(1, int(start_line or 1))

        if start > total:
            return (
                f"FILE {path} | lines {start}-{start} of {total}\n"
                "[end of file]"
            )

        end = (
            min(total, int(end_line))
            if end_line is not None
            else min(total, start + MAX_LINES - 1)
        )

        end = min(end, start + MAX_LINES - 1)

        out = [
            f"{i:>5}| {lines[i - 1]}"
            for i in range(start, end + 1)
        ]

        body = "\n".join(out)

        if len(body) > MAX_CHARS:
            body = body[:MAX_CHARS] + "\n...[truncated by size]"

        header = (
            f"FILE {path} | lines {start}-{end} of {total}"
        )

        footer = (
            f"\n[more: call read again with start_line={end + 1}]"
            if end < total
            else "\n[end of file]"
        )

        return header + "\n" + body + footer

    except Exception as e:
        return f"ERROR: {e}"


def search_files(
    pattern: str,
    glob: str = "**/*.php",
) -> str:
    """Case-insensitive regex search across project files."""

    try:
        rx = re.compile(pattern, re.I)
    except re.error as e:
        return f"ERROR: bad regex: {e}"

    hits = []

    try:
        files = ROOT.glob(glob)

        for p in files:
            if not p.is_file():
                continue

            if _excluded(p.relative_to(ROOT)):
                continue

            try:
                # Prevent symlink traversal outside project root.
                resolved = p.resolve()

                if ROOT not in resolved.parents:
                    continue

                lines = resolved.read_text(
                    encoding="utf-8",
                    errors="replace",
                ).splitlines()

                for n, line in enumerate(lines, 1):
                    if rx.search(line):
                        hits.append(
                            f"{p.relative_to(ROOT).as_posix()}:"
                            f"{n}: {line.strip()[:160]}"
                        )

                        if len(hits) >= MAX_HITS:
                            return (
                                "\n".join(hits)
                                + f"\n[stopped at {MAX_HITS} hits; "
                                  "narrow the pattern]"
                            )

            except Exception:
                continue

    except Exception as e:
        return f"ERROR: {e}"

    return "\n".join(hits) if hits else "no matches"


DISPATCH = {
    "read": read,
    "search_files": search_files,
}
