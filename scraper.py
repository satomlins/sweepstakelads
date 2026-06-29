import logging
import re
import requests
from datetime import date, datetime, timezone, timedelta

logger = logging.getLogger(__name__)

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

# FIFA 3-letter code → display name used throughout the app.
# draw_2026.csv must use these same names.
FIFA_TEAM_NAMES = {
    # CONCACAF
    "MEX": "Mexico",
    "USA": "United States",
    "CAN": "Canada",
    "CRC": "Costa Rica",
    "PAN": "Panama",
    "JAM": "Jamaica",
    "HON": "Honduras",
    "TRI": "Trinidad & Tobago",
    "HAI": "Haiti",
    "CUB": "Cuba",
    "SLV": "El Salvador",
    "NCA": "Nicaragua",
    "GUA": "Guatemala",
    # UEFA
    "GER": "Germany",
    "FRA": "France",
    "ESP": "Spain",
    "POR": "Portugal",
    "ENG": "England",
    "NED": "Netherlands",
    "BEL": "Belgium",
    "ITA": "Italy",
    "SUI": "Switzerland",
    "CRO": "Croatia",
    "AUT": "Austria",
    "TUR": "Turkey",
    "DEN": "Denmark",
    "SRB": "Serbia",
    "SCO": "Scotland",
    "UKR": "Ukraine",
    "SVK": "Slovakia",
    "SVN": "Slovenia",
    "CZE": "Czech Republic",
    "HUN": "Hungary",
    "GEO": "Georgia",
    "ALB": "Albania",
    "ROU": "Romania",
    "ROM": "Romania",
    "POL": "Poland",
    "WAL": "Wales",
    "NOR": "Norway",
    "SWE": "Sweden",
    "GRE": "Greece",
    "FIN": "Finland",
    "ISL": "Iceland",
    "NIR": "Northern Ireland",
    "IRL": "Republic of Ireland",
    "LUX": "Luxembourg",
    "MKD": "North Macedonia",
    "BIH": "Bosnia and Herzegovina",
    "MNE": "Montenegro",
    # CONMEBOL
    "BRA": "Brazil",
    "ARG": "Argentina",
    "URU": "Uruguay",
    "COL": "Colombia",
    "CHI": "Chile",
    "ECU": "Ecuador",
    "PAR": "Paraguay",
    "BOL": "Bolivia",
    "PER": "Peru",
    "VEN": "Venezuela",
    # AFC
    "JPN": "Japan",
    "KOR": "South Korea",
    "AUS": "Australia",
    "IRN": "Iran",
    "SAU": "Saudi Arabia",
    "KSA": "Saudi Arabia",  # IOC code used in some Wikipedia flag templates
    "QAT": "Qatar",
    "IRQ": "Iraq",
    "JOR": "Jordan",
    "CHN": "China",
    "UZB": "Uzbekistan",
    "BHR": "Bahrain",
    "OMA": "Oman",
    "KUW": "Kuwait",
    "UAE": "United Arab Emirates",
    "SYR": "Syria",
    "KGZ": "Kyrgyzstan",
    "TJK": "Tajikistan",
    "IDN": "Indonesia",
    "THA": "Thailand",
    "VIE": "Vietnam",
    "PAL": "Palestine",
    # CAF
    "MAR": "Morocco",
    "EGY": "Egypt",
    "SEN": "Senegal",
    "NGA": "Nigeria",
    "CMR": "Cameroon",
    "CIV": "Ivory Coast",
    "GHA": "Ghana",
    "ALG": "Algeria",
    "TUN": "Tunisia",
    "RSA": "South Africa",
    "MLI": "Mali",
    "COD": "DR Congo",
    "TAN": "Tanzania",
    "ZAM": "Zambia",
    "MOZ": "Mozambique",
    "COM": "Comoros",
    "CAP": "Cape Verde",
    "CPV": "Cape Verde",
    "BEN": "Benin",
    "ETH": "Ethiopia",
    "GAB": "Gabon",
    "ZIM": "Zimbabwe",
    "GAM": "Gambia",
    "BFA": "Burkina Faso",
    "UGA": "Uganda",
    "KEN": "Kenya",
    "SUD": "Sudan",
    # OFC
    "NZL": "New Zealand",
    "CUW": "Curaçao",
}

GROUP_PAGES = [
    f"2026 FIFA World Cup Group {letter}" for letter in "ABCDEFGHIJKL"
]
KNOCKOUT_PAGE = "2026 FIFA World Cup knockout stage"
FINAL_PAGE = "2026 FIFA World Cup final"


HEADERS = {
    "User-Agent": "sweepstakelads/1.0 (https://sweepstakelads.stomlins.com; scott@stomlins.com)"
}


BATCH_TITLES = GROUP_PAGES + [KNOCKOUT_PAGE, FINAL_PAGE]

_LST_PATTERN = re.compile(r"\{\{#lst:([^|}\n]+)\|([^}\n]+)\}\}", re.IGNORECASE)


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
        if "revisions" in page
    }


def _split_on_pipe(text: str) -> list[str]:
    """Split on | but not inside {{ }} or [[ ]]."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    i = 0
    while i < len(text):
        two = text[i : i + 2]
        if two in ("{{", "[["):
            depth += 1
            current.append(two)
            i += 2
        elif two in ("}}", "]]"):
            depth -= 1
            current.append(two)
            i += 2
        elif text[i] == "|" and depth == 0:
            parts.append("".join(current))
            current = []
            i += 1
        else:
            current.append(text[i])
            i += 1
    parts.append("".join(current))
    return parts


def _parse_params(template_inner: str) -> dict[str, str]:
    """Extract key=value params from template body (after template name)."""
    parts = _split_on_pipe(template_inner)
    params: dict[str, str] = {}
    for part in parts:
        if "=" in part:
            key, _, val = part.partition("=")
            params[key.strip()] = val.strip()
    return params


def _find_football_boxes(wikitext: str) -> list[tuple[int, str]]:
    """Return (start_pos, template_text) for every football box template."""
    pattern = re.compile(
        r"\{\{(?:Football box\b|#invoke:football box\|main\b)", re.IGNORECASE
    )
    results: list[tuple[int, str]] = []
    for m in pattern.finditer(wikitext):
        start = m.start()
        depth = 0
        i = start
        while i < len(wikitext):
            two = wikitext[i : i + 2]
            if two == "{{":
                depth += 1
                i += 2
            elif two == "}}":
                depth -= 1
                i += 2
                if depth == 0:
                    results.append((start, wikitext[start:i]))
                    break
            else:
                i += 1
    return results


def _section_at(wikitext: str, pos: int) -> str:
    """Return the most recent level-2 == section heading == before pos."""
    headings = list(re.finditer(r"(?<!=)==(?!=)\s*(.+?)\s*(?<!=)==(?!=)", wikitext[:pos]))
    if headings:
        return headings[-1].group(1).strip()
    return ""


def _extract_code(flag_text: str) -> str:
    """Extract FIFA 3-letter code from a flag template like {{#invoke:flag|fb|MEX}}."""
    m = re.search(r"\|([A-Z]{2,4})\s*\}\}", flag_text)
    return m.group(1) if m else ""


def _code_to_name(code: str) -> str:
    return FIFA_TEAM_NAMES.get(code, code)


def _parse_score(text: str) -> tuple[int | None, int | None]:
    """Return (home, away) goals or (None, None) if not played."""
    m = re.search(r"(\d+)\s*[-–—]\s*(\d+)", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _parse_match_number(score_field: str) -> int | None:
    """Extract the FIFA match number from a `{{score link|anchor|Match N}}` field.

    Wikipedia editors set the display text of the score-link template to "Match N"
    for upcoming matches and to the actual score (e.g. "0–1") once played; the
    number is therefore only recoverable from upcoming entries.
    """
    score_field = score_field.strip()
    if not score_field.lower().startswith("{{score link"):
        return None
    inside = score_field[2:-2]
    parts = _split_on_pipe(inside)
    # parts[0]="score link", parts[1]=anchor, parts[2]=display, ...
    if len(parts) < 3:
        return None
    m = re.match(r"\s*Match\s+(\d+)", parts[2], re.IGNORECASE)
    return int(m.group(1)) if m else None


def _parse_date(text: str) -> date | None:
    m = re.search(r"Start date\|(\d{4})\|(\d{1,2})\|(\d{1,2})", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _clean_time(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&\w+;", " ", text)
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text.strip()


def _parse_datetime_utc(match_date: date | None, time_str: str) -> datetime | None:
    """Parse 'H:MM a.m./p.m. UTC±N' + date into a UTC datetime. Returns None on failure."""
    if not match_date or not time_str:
        return None
    # Normalise Unicode minus sign (U+2212) used by Wikipedia
    normalized = time_str.replace("−", "-")
    m = re.match(
        r"(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)\s*UTC([+\-])(\d+)",
        normalized,
        re.IGNORECASE,
    )
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    meridiem = m.group(3).lower().replace(".", "")
    sign, offset_h = m.group(4), int(m.group(5))
    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    offset = timedelta(hours=(-offset_h if sign == "-" else offset_h))
    local_dt = datetime(match_date.year, match_date.month, match_date.day, hour, minute, tzinfo=timezone(offset))
    return local_dt.astimezone(timezone.utc)


def _extract_labeled_section(wikitext: str, section_name: str) -> str:
    """Extract content between <section begin=name/> and <section end=name/> markers.

    Wikipedia editors write the name bare (`begin=R32-1`) or quoted
    (`begin="R32-1"`); both forms are matched.
    """
    name = re.escape(section_name)
    pattern = re.compile(
        rf'<section\s+begin\s*=\s*"?{name}"?\s*/>'
        rf"(.*?)"
        rf'<section\s+end\s*=\s*"?{name}"?\s*/>',
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(wikitext)
    return m.group(1) if m else ""


def _resolve_transclusions(pages: dict[str, str]) -> dict[str, str]:
    """Replace {{#lst:Page|section}} transclusions with actual content."""
    targets: dict[str, set[str]] = {}
    for wikitext in pages.values():
        for m in _LST_PATTERN.finditer(wikitext):
            page_title = m.group(1).strip()
            if page_title not in pages:
                targets.setdefault(page_title, set()).add(m.group(2).strip())

    if not targets:
        return pages

    titles_to_fetch = list(targets)
    fetched: dict[str, str] = {}
    if titles_to_fetch:
        try:
            resp = requests.get(
                WIKIPEDIA_API,
                params={
                    "action": "query",
                    "prop": "revisions",
                    "rvprop": "content",
                    "titles": "|".join(titles_to_fetch),
                    "format": "json",
                    "formatversion": "2",
                },
                headers=HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            for page in resp.json()["query"]["pages"]:
                if "revisions" in page:
                    fetched[page["title"]] = page["revisions"][0]["content"]
        except Exception as exc:
            logger.warning("Failed to fetch transclusion targets: %s", exc)
            return pages

    all_sources = {**pages, **fetched}

    resolved = {}
    for title, wikitext in pages.items():
        def replacer(m: re.Match, _sources: dict = all_sources) -> str:
            page_title = m.group(1).strip()
            section_name = m.group(2).strip()
            source = _sources.get(page_title, "")
            if not source:
                logger.warning("Transclusion target not found: %s", page_title)
                return m.group(0)
            content = _extract_labeled_section(source, section_name)
            if not content:
                logger.warning("Section '%s' not found in '%s'", section_name, page_title)
                return m.group(0)
            return content

        resolved[title] = _LST_PATTERN.sub(replacer, wikitext)

    return resolved


def parse_matches(wikitext: str, stage_override: str = "") -> list[dict]:
    """Parse all football box templates from wikitext into match dicts."""
    boxes = _find_football_boxes(wikitext)
    matches: list[dict] = []

    for pos, tmpl in boxes:
        inner = tmpl[2:-2]  # strip outer {{ }}
        pipe = inner.find("|")
        if pipe == -1:
            continue
        params = _parse_params(inner[pipe:])

        team1_text = params.get("team1", "")
        team2_text = params.get("team2", "")
        code1 = _extract_code(team1_text)
        code2 = _extract_code(team2_text)
        home_team = _code_to_name(code1) if code1 else team1_text
        away_team = _code_to_name(code2) if code2 else team2_text

        # Strip any remaining wikitext and HTML comments from team names
        home_team = re.sub(r"<!--.*?-->|\{\{.*?\}\}|\[\[.*?\]\]", "", home_team).strip()
        away_team = re.sub(r"<!--.*?-->|\{\{.*?\}\}|\[\[.*?\]\]", "", away_team).strip()

        if not home_team or not away_team:
            continue

        score_field = params.get("score", "")
        home_score, away_score = _parse_score(score_field)
        wiki_match_number = _parse_match_number(score_field)
        pen_home, pen_away = _parse_score(params.get("penaltyscore", ""))
        aet = params.get("aet", "").strip().lower() in ("yes", "y")

        match_date = _parse_date(params.get("date", ""))
        match_time = _clean_time(params.get("time", ""))
        datetime_utc = _parse_datetime_utc(match_date, match_time)

        stage = stage_override or _section_at(wikitext, pos)

        status = "finished" if home_score is not None else "upcoming"

        matches.append(
            {
                "date": match_date,
                "time": match_time,
                "datetime_utc": datetime_utc,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "aet": aet,
                "pen_home": pen_home,
                "pen_away": pen_away,
                "stage": stage,
                "status": status,
                "wiki_match_number": wiki_match_number,
            }
        )

    return matches


def fetch_all() -> tuple[list[dict], dict[str, str]]:
    """Fetch and parse all matches; also return the resolved pages dict.

    Returns (matches, pages). The pages dict has transclusions already resolved,
    so callers (e.g. `bracket.resolve_placeholders`) can read the knockout
    wikitext directly without re-fetching.
    """
    try:
        pages = fetch_all_wikitext()
    except Exception as exc:
        logger.warning("Failed to fetch Wikipedia batch: %s", exc)
        return [], {}

    missing = [t for t in BATCH_TITLES if t not in pages]
    if missing:
        logger.warning("Pages missing from Wikipedia response: %s", missing)

    pages = _resolve_transclusions(pages)
    matches = _parse_pages(pages)
    return matches, pages


def fetch_all_matches() -> list[dict]:
    """Fetch and parse all matches via a single batched HTTP request."""
    matches, _ = fetch_all()
    return matches


def _parse_pages(pages: dict[str, str]) -> list[dict]:
    """Parse all football boxes from the pages dict into a deduped match list."""
    matches: list[dict] = []
    for title, wikitext in pages.items():
        if title.startswith("2026 FIFA World Cup Group "):
            group = title.split("Group ")[-1]
            group_matches = parse_matches(wikitext, stage_override=f"Group {group}")
            logger.info("%s: %d matches", title, len(group_matches))
            matches.extend(group_matches)
        elif title == FINAL_PAGE:
            final_matches = parse_matches(wikitext, stage_override="Final")
            logger.info("%s: %d matches", title, len(final_matches))
            matches.extend(final_matches)
        else:
            ko_matches = parse_matches(wikitext)
            logger.info("%s: %d matches", title, len(ko_matches))
            matches.extend(ko_matches)

    # The knockout page transcludes the final from FINAL_PAGE, and we also parse
    # FINAL_PAGE directly as a fallback. Collapse the resulting duplicate.
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for m in matches:
        key = (m["date"], m["home_team"], m["away_team"], m["stage"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)
    return deduped
