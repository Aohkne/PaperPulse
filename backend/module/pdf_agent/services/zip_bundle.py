"""Safe .zip extraction + main.tex discovery for the `tex_bundle` branch (Step P1).

Every uploaded .zip is untrusted input — extract_zip_safe() validates every
member path stays inside dest_dir before extracting (zip slip / path
traversal, OWASP) instead of calling ZipFile.extractall() directly.
"""

from __future__ import annotations

import os
import zipfile
from glob import glob


class SecurityError(Exception):
    """Raised when a zip entry would extract outside dest_dir (zip slip)."""


class NoMainTexFoundError(Exception):
    """Raised when no .tex file with \\documentclass + \\begin{document} is found."""


def extract_zip_safe(zip_path: str, dest_dir: str) -> str:
    """Extract *zip_path* into *dest_dir*, rejecting any path-traversal entry.

    Validates `os.path.realpath()` of every member resolves inside dest_dir
    BEFORE calling extractall() — a single malicious entry (e.g. `../../etc/passwd`
    or an absolute path) aborts the whole extraction with no partial writes.
    """
    os.makedirs(dest_dir, exist_ok=True)
    real_dest = os.path.realpath(dest_dir)

    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            resolved = os.path.realpath(os.path.join(dest_dir, member))
            if not (resolved == real_dest or resolved.startswith(real_dest + os.sep)):
                raise SecurityError(f"Zip slip detected: {member!r} resolves outside {dest_dir!r}")
        zf.extractall(dest_dir)

    return dest_dir


def find_main_tex(extract_dir: str) -> str:
    """Heuristic: first .tex file containing both \\documentclass and \\begin{document}.

    Identified Gap #9 (PLAN §9): doesn't handle multi-file projects with
    \\input{}/\\include{} — picks the first candidate that looks like a root file.
    """
    candidates = sorted(glob(f"{extract_dir}/**/*.tex", recursive=True))
    for path in candidates:
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue
        if r"\documentclass" in content and r"\begin{document}" in content:
            return path
    raise NoMainTexFoundError("Could not find main.tex (must contain \\documentclass + \\begin{document}) in the zip")


def resolve_relative(extract_dir: str, raw_path: str) -> str:
    """Resolve a \\includegraphics{} path relative to the zip's extract dir."""
    return os.path.normpath(os.path.join(extract_dir, raw_path))
