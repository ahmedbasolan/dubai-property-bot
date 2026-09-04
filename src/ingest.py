"""Ingestion pipeline: embed market reports into ChromaDB.

Transactions are loaded into DuckDB via db_setup.py.
This script only handles semantic search for market reports.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

import chromadb
from chromadb.config import Settings

from config import DATA_DIR, CHROMA_DIR, PROCESSED_DIR


def load_markdown_reports(data_dir: Path) -> List[Dict[str, Any]]:
    """Load and chunk markdown market reports."""
    docs = []
    for md_file in sorted(data_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        sections = []
        current_section = []
        current_header = "Introduction"

        for line in content.split("\n"):
            if line.startswith("## "):
                if current_section:
                    sections.append((current_header, "\n".join(current_section).strip()))
                current_header = line.replace("## ", "").strip()
                current_section = []
            else:
                current_section.append(line)

        if current_section:
            sections.append((current_header, "\n".join(current_section).strip()))

        for i, (header, body) in enumerate(sections):
            if not body or body.startswith("---"):
                continue
            community_name = md_file.stem.replace("market_report_", "").replace("_", " ").title()
            doc_text = f"[Market Report: {community_name}] {header}: {body}"
            docs.append({
                "id": f"{md_file.stem}_section_{i}",
                "text": doc_text,
                "metadata": {
                    "source": "market_report",
                    "community": community_name,
                    "section": header,
                    "filename": md_file.name,
                },
            })
    return docs


def ingest_reports():
    """Ingest market reports into ChromaDB for semantic search."""
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

    report_col = client.get_or_create_collection(
        name="market_reports",
        metadata={"description": "Dubai market reports for semantic search"},
    )

    report_docs = load_markdown_reports(DATA_DIR)
    if report_docs:
        batch_size = 50
        for i in range(0, len(report_docs), batch_size):
            batch = report_docs[i : i + batch_size]
            report_col.upsert(
                ids=[d["id"] for d in batch],
                documents=[d["text"] for d in batch],
                metadatas=[d["metadata"] for d in batch],
            )
        print(f"Ingested {len(report_docs)} market report sections into ChromaDB")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED_DIR / "market_reports.json", "w", encoding="utf-8") as f:
        json.dump(report_docs, f, indent=2, ensure_ascii=False)
    print(f"ChromaDB location: {CHROMA_DIR}")


if __name__ == "__main__":
    ingest_reports()
