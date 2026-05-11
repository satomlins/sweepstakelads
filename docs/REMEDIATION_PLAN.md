# Remediation plan — May 2026

Cleanup and hardening pass following the full-repo audit. Phases are ordered by
risk-adjusted value: each phase is independently shippable and the early ones
unblock the later ones.

## Why Wikipedia needs 12 group pages, not the main page

Tested 2026-05-11: the main page (`2026 FIFA World Cup`) only **references**
matches via labelled-section transclusion:

```wikitext
{{#lst:2026 FIFA World Cup Group A|A1}}
{{#lst:2026 FIFA World Cup Group A|A2}}
```

The actual `{{#invoke:football box|main ...}}` template invocations (with
team/score/time/date parameters) live on the per-group pages and get pulled in
at render time. Fetching `prop=wikitext` for the main page returns the `#lst:`
references only — no team data.

We could fetch the rendered HTML (`prop=text`) of the main page and parse the
expanded football-box divs, but that means screen-scraping HTML instead of
parsing named template parameters — more brittle.

**Better fix:** Wikipedia's `action=query&prop=revisions&rvprop=content` accepts
up to 50 titles in a single request. All 13 pages come back in one HTTP call,
~215 KB, ~0.7 s on a cold connection. See Phase 2.

---

## Phase 1 — Data hygiene ✅ COMPLETE (2026-05-11)

Small, safe, no behavioural change. ~30 min total.

### 1.1 Revert `assets/draw_2026.csv` to headers-only ✅

The committed file (`c02bd6c`) contains the dev_seed fake assignments. The 2026
draw was held in December 2025 — these need replacing with the real draw
results, but right now the file ships fake data to production.

- Write `Who,Team\n` and commit.
- Once real draw results are typed in, commit those.

### 1.2 Untrack `assets/group_standings.json` ✅

It's listed in `.gitignore:13` but `git ls-files` shows it tracked (gitignore
doesn't untrack existing files). Stale fake standings ride along on every
commit that runs after `dev_seed.py`.

```bash
git rm --cached assets/group_standings.json
git commit -m "stop tracking cached group standings JSON"
```

### 1.3 Delete `requirements.txt` ✅

Production runs `uv run gunicorn ...` (per `CLAUDE.md` and the systemd unit), so
`uv.lock` is the source of truth. The file is dead weight and dangerously
stale — `dash==2.17.1` vs `dash 4.1.0` in `uv.lock`, plus `dash-iconify` is
missing entirely. Anyone who reads it and tries `pip install -r requirements.txt`
will deploy a broken build.

- Delete the file.
- Update `CLAUDE.md` "Dependencies are managed with `uv`" sentence to drop the
  requirements.txt reference.
- Update `docs/DEPLOY_PLAN.md` if it mentions pip install (it doesn't currently
  but worth a re-read).

### 1.4 Add a `README.md` ✅

`pyproject.toml:5` declares `readme = "README.md"` but the file doesn't exist
— `uv sync` warns about it. A minimal one is fine:

```markdown
# sweepstakelads

2026 FIFA World Cup sweepstake dashboard. Plotly Dash, deployed on Oracle Cloud
via cloudflared tunnel at https://sweepstakelads.stomlins.com.

## Dev

    uv sync
    uv run python app.py

See `CLAUDE.md` for architecture, `docs/DEPLOY_PLAN.md` for deployment.
```

### 1.5 Fix CLAUDE.md drift ✅

- Remove the `archive/` row from the "Key assets" table (directory was deleted
  in `4a67970`).
- Replace "ships with headers only" claim with the actual current state
  (whatever we land in 1.1).
- Spot-check participant counts — both PLAN_2026 and CLAUDE.md should agree
  on 12.

---

## Phase 2 — Scraper rewrite: one HTTP request ✅ COMPLETE (2026-05-11)

~2 hours including tests. **This is the biggest user-visible win.**

### 2.1 Replace `fetch_all_matches()` with a batched query ✅

Current `scraper.py:343-365` does 13 sequential `action=parse` calls, each up
to 20 s timeout = up to ~4 min worst-case latency. Under `--workers 1` that
blocks the entire app.

New approach (one request, same wikitext output):

```python
BATCH_TITLES = [f"2026 FIFA World Cup Group {L}" for L in "ABCDEFGHIJKL"] + [
    "2026 FIFA World Cup knockout stage"
]

def fetch_all_wikitext() -> dict[str, str]:
    """Fetch wikitext for all 13 pages in a single HTTP request."""
    resp = requests.get(
        WIKIPEDIA_API,
        params={
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "titles": "|".join(BATCH_TITLES),
            "format": "json",
            "formatversion": "2",
        },
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return {
        page["title"]: page["revisions"][0]["content"]
        for page in resp.json()["query"]["pages"]
        if "revisions" in page  # skip missing pages
    }

def fetch_all_matches() -> list[dict]:
    pages = fetch_all_wikitext()
    matches = []
    for title, wikitext in pages.items():
        if title.startswith("2026 FIFA World Cup Group "):
            group = title.split("Group ")[-1]
            matches.extend(parse_matches(wikitext, stage_override=f"Group {group}"))
        else:
            matches.extend(parse_matches(wikitext))
    return matches
```

`parse_matches` is unchanged — it already handles `{{#invoke:football box|main}}`
(`scraper.py:195-197`).

### 2.2 Add atomic cache writes ✅

`tournament.py:132-143` writes 4 files in sequence. A kill during a refresh
leaves a half-written CSV; the next `read_cache()` raises in `pd.read_csv`.

Wrap each write to use temp file + atomic replace, and write `last_updated.txt`
**last** so a half-written cache shows as stale.

```python
def _atomic_write_csv(df: pd.DataFrame, path: str) -> None:
    tmp = f"{path}.tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)
```

### 2.3 Background refresh instead of blocking refresh ✅

`tournament.get_data()` currently does the slow refresh inline on the user's
request thread. Even with batching down to ~1 s, a thread-safe background
refresh is the right shape:

- On every `get_data()` call, return whatever's in cache (read-only).
- If the cache is stale **and** no refresh is currently in flight, fire one in
  a `threading.Thread(daemon=True)`.
- On first-ever start (no cache), do block — but this is a one-time cost.

```python
_refresh_lock = threading.Lock()
_refresh_in_flight = False

def _maybe_refresh_async():
    global _refresh_in_flight
    with _refresh_lock:
        if _refresh_in_flight:
            return
        _refresh_in_flight = True
    def _run():
        global _refresh_in_flight
        try:
            refresh()
        finally:
            with _refresh_lock:
                _refresh_in_flight = False
    threading.Thread(target=_run, daemon=True).start()

def get_data(force_refresh: bool = False) -> dict:
    cache_exists = all(os.path.exists(p) for p in [...])
    if not cache_exists:
        return refresh()
    if force_refresh or _cache_age_minutes() >= CACHE_TTL_MINUTES:
        _maybe_refresh_async()
    return read_cache()
```

Net effect: every UI render is ~5 ms (CSV read), refresh happens off the hot
path.

### 2.4 Replace `print()` warnings with `logging` ✅

`scraper.py:353, 355, 361, 363` use `print` for partial-failure signals. Under
gunicorn these end up in `journalctl` with no level and no timestamp. Switch
to a module-level `logger = logging.getLogger(__name__)` and `logger.warning`
/ `logger.info` calls — then `journalctl -u sweepstakelads -p err` actually
finds failures.

---

## Phase 3 — Test infrastructure ✅ COMPLETE (2026-05-11)

~2 hours. `docs/PLAN_2026.md:44, 60-62` already called this out as a risk: if
Wikipedia changes the football-box template format the scraper will silently
return zero matches and the app will go blank.

### 3.1 Snapshot the wikitext ✅

```
tests/
  fixtures/
    group_a_2026-05-11.wikitext      # captured from the live page
    knockout_2026-05-11.wikitext
  test_scraper.py
  test_scoring.py
```

Add a `scripts/refresh_fixtures.py` so we can regenerate snapshots when the
upstream page legitimately changes (e.g. a new round added).

### 3.2 Scraper regression tests ✅

```python
def test_parse_group_a_2026_05_11():
    wikitext = Path("tests/fixtures/group_a_2026-05-11.wikitext").read_text()
    matches = parse_matches(wikitext, stage_override="Group A")
    assert len(matches) == 6
    assert matches[0]["home_team"] == "Mexico"
    assert matches[0]["datetime_utc"].isoformat() == "2026-06-11T19:00:00+00:00"
    # …
```

### 3.3 Scoring regression tests ✅

Pin a small set of deterministic match dicts and the expected `team_table` /
`person_table` output. Cover: regular win, AET win, penalty shootout,
third-place playoff, group draw, knockout placeholder names.

### 3.4 Wire into CI ✅

A 5-line GitHub Action — `uv sync && uv run pytest -q` on push and PR. Free
on public repos.

---

## Phase 4 — Auto-deploy on push to main ← START HERE NEXT

~30 min once Oracle bits are in place.

### 4.1 SSH key + sudoers on Oracle

```bash
# Local
ssh-keygen -t ed25519 -f ~/.ssh/sweepstakelads_deploy -N ""
ssh-copy-id -i ~/.ssh/sweepstakelads_deploy.pub opc@<oracle-host>

# Oracle — passwordless service restart
echo 'opc ALL=(root) NOPASSWD: /usr/bin/systemctl restart sweepstakelads' \
  | sudo tee /etc/sudoers.d/sweepstakelads
sudo chmod 0440 /etc/sudoers.d/sweepstakelads
```

Lock the key down with a forced command in `~/.ssh/authorized_keys` so even if
the key leaks it can only run the deploy script:

```
command="/home/opc/sweepstakelads/scripts/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA…
```

And `scripts/deploy.sh` (checked in):

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /home/opc/sweepstakelads
git fetch --quiet origin main
git reset --hard origin/main
/usr/local/bin/uv sync --frozen
sudo /usr/bin/systemctl restart sweepstakelads
sleep 2
curl -fsS http://127.0.0.1:8050/ > /dev/null
```

### 4.2 GitHub Actions workflow

```yaml
# .github/workflows/deploy.yml
name: deploy
on:
  push:
    branches: [main]
concurrency:
  group: deploy
  cancel-in-progress: false
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --frozen
      - run: uv run pytest -q
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.ORACLE_DEPLOY_KEY }}
      - run: |
          ssh -o StrictHostKeyChecking=accept-new \
              -o UserKnownHostsFile=/dev/null \
              opc@${{ secrets.ORACLE_HOST }} deploy
      - name: Smoke test
        run: curl -fsS https://sweepstakelads.stomlins.com/ > /dev/null
```

Secrets to add in GitHub:
- `ORACLE_DEPLOY_KEY` — the private key generated above
- `ORACLE_HOST` — the host (kept secret to reduce drive-by attack surface)

### 4.3 Rollback plan

If the deploy breaks production, `ssh stomlins-oracle` and
`git reset --hard <previous-sha> && sudo systemctl restart sweepstakelads`.
Worth documenting in `docs/DEPLOY_PLAN.md`.

---

## Phase 5 — Code tidy-up (low priority)

Skip until phases 1-4 are done.

### 5.1 Hoist deterministic style rules

`app.py:540-555` rebuilds the same style-rule dicts on every callback. The
`COLOURS`-dependent rules (`_person_stripe_rules`, `_person_row_colour_rules`,
`_team_row_colour_rules`, `_numeric_align(NUMERIC_COLS)`) are constants. Move
them to module scope; only `_team_stripe_rules(draw, …)` and friends need to
stay in the callback (they depend on the draw).

### 5.2 Drop the unused `Time` column from `fixtures.csv`

`tournament.py:69-96` writes the raw Wikipedia time string (e.g.
"1:00 p.m. UTC−6"); `app.py:_localize_fixtures` overwrites it on every render
from `DatetimeUTC`. Column is dead — remove from the CSV schema and from
`_RESULT_COLS` / `_FIXTURE_COLS` formats. (Tests in Phase 3 should cover this
before changing.)

### 5.3 Tighten error handling

`app.py:201-210` `_fmt_local` catches bare `Exception`. Narrow to
`(ValueError, TypeError)` and log anything else — silent empty times is
worse than a stack trace.

### 5.4 Fix dev_seed placeholder match numbers

`dev_seed.py:161` emits `Winner of Match {89 + i}` but match numbers in the
app are computed from chronological sort order, not this offset. Either
compute the real number from the sorted fixture list, or use a non-numeric
placeholder ("Winner of QF1 / R16 M5", etc.) — current value is misleading.

### 5.5 Consolidate `_apply_match`

`scoring.py:23-83` has duplicate `hs > aws` / `aws > hs` branches. Refactor
to a single winner-determination step + a points-table dict keyed on
(third_place, aet, via_penalties). Pure refactor — tests in 3.3 must pass
unchanged.

---

## Suggested order and dependencies

```
Phase 1 (hygiene)              ← independent, ~30 min
  └─ Phase 2 (scraper rewrite) ← independent of 1 but easier after 1.5
       └─ Phase 3 (tests)      ← gates Phase 4
            └─ Phase 4 (CD)    ← needs tests to run in CI first
                 └─ Phase 5    ← tidy, refactor under test coverage
```

Phase 1 in a single commit; Phase 2 in 3-4 commits (one per sub-task); Phase 3
in one PR; Phase 4 in one PR with secrets set up first.
