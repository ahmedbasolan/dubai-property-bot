"""Entrypoint for Vercel (see vercel.json): prepares a read-only host, then
exposes the FastAPI app unchanged.

Vercel Functions can only write under /tmp. Two things need to write:

* ChromaDB opens its store read-write, so the bundled chroma_db/ is copied to
  /tmp once per instance and CHROMA_DIR points there.
* ChromaDB downloads its ONNX embedding model to ~/.cache on first use, so
  HOME points at /tmp.

Both happen before api.main (and through it rag.py) is imported, because
rag.py opens the clients at import time. DuckDB is opened read-only in place.
Locally nothing uses this module: `make run-api` imports api.main directly.
"""

import os
import shutil
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
_tmp = Path(tempfile.gettempdir())

_chroma = _tmp / "chroma_db"
if not _chroma.exists():
    shutil.copytree(PROJECT_ROOT / "chroma_db", _chroma)
os.environ["CHROMA_DIR"] = str(_chroma)
os.environ["HOME"] = str(_tmp)

from api.main import app  # noqa: E402,F401
