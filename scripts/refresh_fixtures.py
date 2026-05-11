#!/usr/bin/env python
"""Refresh pinned wikitext snapshots in tests/fixtures/.

Run this when a Wikipedia page's content legitimately changes (e.g. matches
are added for a new round) and the existing snapshots need updating.

Usage:
    uv run python scripts/refresh_fixtures.py
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from scraper import HEADERS, WIKIPEDIA_API

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"

PAGES = {
    "2026 FIFA World Cup Group A": f"group_a_{date.today()}.wikitext",
    "2026 FIFA World Cup knockout stage": f"knockout_{date.today()}.wikitext",
}


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    resp = requests.get(
        WIKIPEDIA_API,
        params={
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "titles": "|".join(PAGES),
            "format": "json",
            "formatversion": "2",
        },
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()

    saved = []
    for page in resp.json()["query"]["pages"]:
        title = page["title"]
        if title not in PAGES:
            print(f"WARNING: unexpected page in response: {title!r}", file=sys.stderr)
            continue
        if "revisions" not in page:
            print(f"WARNING: no revisions for {title!r}", file=sys.stderr)
            continue
        filename = PAGES[title]
        path = FIXTURES_DIR / filename
        path.write_text(page["revisions"][0]["content"])
        saved.append(str(path))
        print(f"Saved {path} ({len(page['revisions'][0]['content'])} chars)")

    if saved:
        print(f"\nUpdate test assertions in tests/test_scraper.py to match the new snapshot filenames:")
        for p in saved:
            print(f"  {p}")


if __name__ == "__main__":
    main()
