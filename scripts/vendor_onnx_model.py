"""Copy ChromaDB's embedding model into vendor/ so the deployment bundles it.

On Vercel, Python dependencies are installed into /tmp when a function
starts, which leaves no room for ChromaDB to download its 79 MB ONNX model
there on the first chat question ("No space left on device"). Bundling the
extracted model means nothing is downloaded or written at runtime;
api/vercel_entry.py points ChromaDB at it.

    python scripts/vendor_onnx_model.py

vendor/ is gitignored (the model is ~91 MB) and allowlisted in .vercelignore.
"""

import shutil
import sys
from pathlib import Path

from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

DEST = Path(__file__).resolve().parent.parent / "vendor" / "onnx_models" / ONNXMiniLM_L6_V2.MODEL_NAME


def main():
    ef = ONNXMiniLM_L6_V2()
    ef._download_model_if_not_exists()  # no-op when already in the local cache
    src = Path(ef.DOWNLOAD_PATH) / ef.EXTRACTED_FOLDER_NAME
    dest = DEST / ef.EXTRACTED_FOLDER_NAME
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    size = sum(f.stat().st_size for f in dest.iterdir()) / 1e6
    print(f"Copied {len(list(dest.iterdir()))} model files ({size:.0f} MB) to {dest}")


if __name__ == "__main__":
    sys.exit(main())
