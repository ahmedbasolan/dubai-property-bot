"""Entrypoint for Vercel (see vercel.json): prepares a read-only host, then
exposes the FastAPI app unchanged.

Vercel Functions can only write under /tmp, and on a cold start Vercel
installs the Python dependencies there, which leaves little free space.

* ChromaDB opens its store read-write, so the bundled chroma_db/ is copied to
  /tmp once per instance and CHROMA_DIR points there.
* ChromaDB's ONNX embedding model (~91 MB) is bundled under vendor/ by
  scripts/vendor_onnx_model.py, and ChromaDB is pointed at it, so nothing is
  downloaded or written. Downloading it into /tmp failed with "No space left
  on device". HOME still points at /tmp for anything else that caches.

All of this happens before api.main (and through it rag.py) is imported,
because rag.py opens the clients at import time. DuckDB is opened read-only
in place. Locally nothing uses this module: `make run-api` imports api.main.
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

from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2  # noqa: E402

_model = PROJECT_ROOT / "vendor" / "onnx_models" / ONNXMiniLM_L6_V2.MODEL_NAME
if (_model / ONNXMiniLM_L6_V2.EXTRACTED_FOLDER_NAME / "model.onnx").exists():
    ONNXMiniLM_L6_V2.DOWNLOAD_PATH = _model

from api.main import app  # noqa: E402,F401
