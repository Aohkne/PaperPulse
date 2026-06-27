"""Repo-local uvicorn shim for Windows-safe ``python -m uvicorn``."""

from __future__ import annotations

import asyncio
import importlib.machinery
import importlib.util
import pathlib
import sys


_CUSTOM_LOOP = "backend.main:_uvicorn_loop_factory"
_REPO_ROOT = pathlib.Path(__file__).resolve().parent


def _is_repo_path(entry: str) -> bool:
    if entry == "":
        return True
    try:
        return pathlib.Path(entry).resolve() == _REPO_ROOT
    except OSError:
        return False


def _load_real_uvicorn():
    search_path = [entry for entry in sys.path if not _is_repo_path(entry)]
    spec = importlib.machinery.PathFinder.find_spec("uvicorn", search_path)
    if spec is None or spec.loader is None:
        raise ImportError("Could not locate the installed uvicorn package outside the repo shim")

    module = importlib.util.module_from_spec(spec)
    sys.modules["uvicorn"] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        if "--loop" not in sys.argv and not any(arg.startswith("--loop=") for arg in sys.argv[1:]):
            sys.argv[1:1] = ["--loop", _CUSTOM_LOOP]

    _load_real_uvicorn()

    from uvicorn.main import main

    main()
else:
    _real_uvicorn = _load_real_uvicorn()
    globals().update(_real_uvicorn.__dict__)