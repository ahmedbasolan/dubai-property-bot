"""Generated reports must be reproducible.

CI and every `make setup` regenerate data/reports/. With no tie-breaker, two
projects with the same sales count swapped places between runs (Town Square's
LIVA and TOWN SQUARE JENNA AND WARDA, 41 sales each), so a clean rebuild
showed a diff against the committed reports.
"""

import re
import sys
from pathlib import Path

import duckdb
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

DB_PATH = PROJECT_ROOT / "data" / "dubai_properties.duckdb"

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(), reason="database missing - run `make setup` first"
)


@pytest.fixture(scope="module")
def reports():
    from build_reports import build_report

    conn = duckdb.connect(str(DB_PATH), read_only=True)
    names = [r[0] for r in conn.execute("SELECT community FROM v_investment_scores").fetchall()]
    return {c: build_report(conn, c) for c in names}


def test_tied_projects_are_listed_alphabetically(reports):
    for community, text in reports.items():
        line = next((l for l in text.splitlines() if l.startswith("Most active ready projects")), None)
        if not line:
            continue
        entries = re.findall(r"(?:: |; )([^:;]+?): ([\d,]+) sales", line)
        for (p1, n1), (p2, n2) in zip(entries, entries[1:]):
            if n1 == n2:
                assert p1 <= p2, f"{community}: {p1} listed before {p2} with {n1} sales each"
