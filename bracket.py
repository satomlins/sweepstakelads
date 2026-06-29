"""
Bracket resolver — substitutes placeholder team names in knockout fixtures
with actual teams.

Resolves two kinds of placeholder:
  - "Winner Group X" / "Runner-up Group X" → group winner / runner-up, taken
    from the computed group standings (only when all group matches are finished).
  - "Winner Match N" / "Loser Match N" → winner / loser of the referenced
    knockout match, derived from the knockout page's bracket section combined
    with FIFA match numbers extracted from each football box's score field.

Does NOT touch 3rd-placer slots like "3rd Group A/B/C/D/F" — third-placer
allocation is FIFA's complex cross-group ranking; we leave those for Wikipedia
editors to fill in.
"""

import logging
import re
from typing import Optional

from scraper import FIFA_TEAM_NAMES, _split_on_pipe

logger = logging.getLogger(__name__)

GROUP_PLACEHOLDER_RE = re.compile(
    r"^\s*(Winners?|Runners?-?up)\s+Group\s+([A-L])\s*$", re.IGNORECASE
)
WINNER_MATCH_RE = re.compile(r"^\s*Winner\s+Match\s+(\d+)\s*$", re.IGNORECASE)
LOSER_MATCH_RE = re.compile(r"^\s*Loser\s+Match\s+(\d+)\s*$", re.IGNORECASE)

# Standard pairing math for a 32-team single-elim bracket.
# Round R position k is fed by round (R-1) positions (2k-1) and (2k);
# Final and 3rd-place both consume Semifinal positions 1 and 2.
_PAIRINGS = {
    "Round of 16": ("Round of 32", lambda k: (2 * k - 1, 2 * k)),
    "Quarterfinals": ("Round of 16", lambda k: (2 * k - 1, 2 * k)),
    "Semifinals": ("Quarterfinals", lambda k: (2 * k - 1, 2 * k)),
    "Final": ("Semifinals", lambda _k: (1, 2)),
    "Match for third place": ("Semifinals", lambda _k: (1, 2)),
}

_ROUND_NAMES = (
    "Round of 32",
    "Round of 16",
    "Quarterfinals",
    "Semifinals",
    "Final",
    "Match for third place",
)


def _strip_wikitext(text: str) -> str:
    """Strip wikitext markup, returning a clean team name, code, or placeholder string."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"\{\{#invoke:flag\|[^|}]+\|([A-Z]{2,4})\s*\}\}", r"\1", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text.strip()


def _decode(text: str) -> str:
    return FIFA_TEAM_NAMES.get(text.upper(), text)


def _parse_int(text: str) -> Optional[int]:
    text = text.strip()
    m = re.match(r"^(\d+)", text)
    return int(m.group(1)) if m else None


def parse_bracket_section(wikitext: str) -> list[dict]:
    """Extract bracket entries in bracket order from the knockout page's
    {{#invoke:RoundN|N32}} section.

    Each entry: {round, position, team1, team2, score1, score2}.
    team1/team2 are decoded to display names (e.g. "South Africa") where the
    bracket holds a FIFA 3-letter code, or kept as placeholder strings.
    """
    m = re.search(
        r'<section\s+begin\s*=\s*"?Bracket"?\s*/>(.*?)<section\s+end\s*=\s*"?Bracket"?\s*/>',
        wikitext,
        re.DOTALL,
    )
    if not m:
        return []
    body = m.group(1)
    parts = re.split(
        r"<!--\s*(" + "|".join(_ROUND_NAMES) + r")\s*-->",
        body,
    )
    entries: list[dict] = []
    pos_in_round: dict[str, int] = {}
    for i in range(1, len(parts), 2):
        round_name = parts[i].strip()
        content = parts[i + 1] if i + 1 < len(parts) else ""
        for line in content.split("\n"):
            line = line.strip()
            if not line.startswith("|") or line.startswith("|}"):
                continue
            fields = _split_on_pipe(line[1:])
            if len(fields) < 5:
                continue
            team1 = _decode(_strip_wikitext(fields[1]))
            team2 = _decode(_strip_wikitext(fields[3]))
            pos = pos_in_round.get(round_name, 0) + 1
            pos_in_round[round_name] = pos
            entries.append(
                {
                    "round": round_name,
                    "position": pos,
                    "team1": team1,
                    "team2": team2,
                    "score1": _parse_int(fields[2]),
                    "score2": _parse_int(fields[4]),
                }
            )
    return entries


def _derive_feeder_match_numbers(entries: list[dict]) -> dict[tuple, int]:
    """Parse "Winner/Loser Match N" references from later-round entries and assign
    those match numbers to feeder positions in the earlier round.

    Returns {(round_name, position): match_number}.
    """
    numbers: dict[tuple, int] = {}
    for e in entries:
        pairing = _PAIRINGS.get(e["round"])
        if not pairing:
            continue
        feeder_round, pair_fn = pairing
        feeder_positions = pair_fn(e["position"])
        for slot_text, fpos in zip([e["team1"], e["team2"]], feeder_positions):
            ref = WINNER_MATCH_RE.match(slot_text) or LOSER_MATCH_RE.match(slot_text)
            if ref:
                numbers[(feeder_round, fpos)] = int(ref.group(1))
    return numbers


def _is_placeholder(text: str) -> bool:
    return bool(
        GROUP_PLACEHOLDER_RE.match(text)
        or WINNER_MATCH_RE.match(text)
        or LOSER_MATCH_RE.match(text)
    )


def _assign_match_numbers_from_matches(
    entries: list[dict],
    matches: list[dict],
) -> dict[tuple, int]:
    """Match each football box (from the matches list) to a bracket entry by team
    set, and assign its wiki_match_number (extracted by the scraper from the
    score field) to that bracket position. Works for upcoming matches; finished
    matches don't carry a wiki_match_number on the score field.
    """
    numbers: dict[tuple, int] = {}
    for e in entries:
        teams = frozenset([e["team1"], e["team2"]])
        for m in matches:
            if m.get("stage") != e["round"]:
                continue
            if m.get("wiki_match_number") is None:
                continue
            if frozenset([m["home_team"], m["away_team"]]) == teams:
                numbers[(e["round"], e["position"])] = m["wiki_match_number"]
                break
    return numbers


def _backfill_by_elimination(
    entries: list[dict],
    numbers: dict[tuple, int],
) -> dict[tuple, int]:
    """For each round, infer remaining match numbers from a consecutive range.

    FIFA numbers knockout matches sequentially within each round. If we already
    have N-1 of N match numbers for a round, the missing number is fully
    determined and we can assign it to the one un-numbered position. When more
    than one position is missing, we don't attempt to disambiguate.
    """
    filled = dict(numbers)
    by_round: dict[str, list[dict]] = {}
    for e in entries:
        by_round.setdefault(e["round"], []).append(e)
    for round_name, round_entries in by_round.items():
        known_nums = [
            filled[(round_name, e["position"])]
            for e in round_entries
            if (round_name, e["position"]) in filled
        ]
        missing_entries = [
            e for e in round_entries if (round_name, e["position"]) not in filled
        ]
        if not known_nums or not missing_entries:
            continue
        size = len(round_entries)
        # Pick the size-length consecutive window that contains every known number.
        candidates = set()
        for n in known_nums:
            for start in range(n - size + 1, n + 1):
                window = set(range(start, start + size))
                if set(known_nums).issubset(window):
                    candidates.add(tuple(sorted(window)))
        if len(candidates) != 1:
            continue
        expected = set(next(iter(candidates)))
        missing_nums = sorted(expected - set(known_nums))
        if len(missing_nums) == len(missing_entries) == 1:
            filled[(round_name, missing_entries[0]["position"])] = missing_nums[0]
    return filled


def _entry_outcome(entry: dict) -> tuple[Optional[str], Optional[str]]:
    """Return (winner, loser) for a finished bracket entry, else (None, None)."""
    t1, t2 = entry["team1"], entry["team2"]
    s1, s2 = entry["score1"], entry["score2"]
    if _is_placeholder(t1) or _is_placeholder(t2):
        return (None, None)
    if s1 is None or s2 is None:
        return (None, None)
    if s1 > s2:
        return (t1, t2)
    if s2 > s1:
        return (t2, t1)
    return (None, None)


def resolve_placeholders(
    matches: list[dict],
    group_standings: dict,
    knockout_wikitext: str,
) -> list[dict]:
    """Return a NEW matches list with knockout team-name placeholders resolved.

    Group placeholders ("Winner Group X", "Runner-up Group X") are substituted
    from `group_standings` once all 6 matches in the group are finished.

    Knockout-cascade placeholders ("Winner Match N", "Loser Match N") are
    substituted from outcomes observed in the bracket section of
    `knockout_wikitext`. The substitution loops to fixed point so an R32 result
    propagates through R16 → QF → SF → Final in a single call.

    Match numbers for each bracket position are assembled from three sources, in
    order: (1) the wiki_match_number extracted by the scraper from each
    upcoming match's score field, (2) "Winner/Loser Match N" references in
    later-round bracket entries (covers feeders for finished matches whose R16
    slot Wikipedia has not yet auto-filled), and (3) per-round elimination on
    the consecutive match-number range.

    Third-placer slots like "3rd Group A/B/C/D/F" are left untouched.
    """
    resolved = [dict(m) for m in matches]

    for m in resolved:
        for key in ("home_team", "away_team"):
            mg = GROUP_PLACEHOLDER_RE.match(m[key])
            if not mg:
                continue
            role, letter = mg.group(1).lower(), mg.group(2).upper()
            df = group_standings.get(letter)
            if df is None or len(df) < 2 or "PL" not in df.columns:
                continue
            if not (df["PL"] == 3).all():
                continue
            pos = 1 if role.startswith("winner") else 2
            m[key] = df.iloc[pos - 1]["Team"]

    if not knockout_wikitext:
        return resolved

    entries = parse_bracket_section(knockout_wikitext)
    if not entries:
        return resolved

    numbers = _assign_match_numbers_from_matches(entries, resolved)
    for pos_key, num in _derive_feeder_match_numbers(entries).items():
        numbers.setdefault(pos_key, num)
    numbers = _backfill_by_elimination(entries, numbers)

    by_pos = {(e["round"], e["position"]): e for e in entries}
    outcomes: dict[int, tuple[str, str]] = {}
    for pos_key, num in numbers.items():
        entry = by_pos.get(pos_key)
        if entry is None:
            continue
        winner, loser = _entry_outcome(entry)
        if winner and loser:
            outcomes[num] = (winner, loser)

    changed = True
    while changed:
        changed = False
        for m in resolved:
            for key in ("home_team", "away_team"):
                text = m[key]
                mw = WINNER_MATCH_RE.match(text)
                ml = LOSER_MATCH_RE.match(text)
                if mw:
                    num = int(mw.group(1))
                    if num in outcomes:
                        m[key] = outcomes[num][0]
                        changed = True
                elif ml:
                    num = int(ml.group(1))
                    if num in outcomes:
                        m[key] = outcomes[num][1]
                        changed = True

    return resolved
