"""Unit tests for tournament._matches_to_fixtures_df Winner column."""

from tournament import _matches_to_fixtures_df


def _match(
    home="A", away="B", hs=None, aws=None,
    aet=False, ph=None, pa=None, stage="Group A", status="finished",
):
    return {
        "date": "1 Jun 2026",
        "time": "20:00",
        "datetime_utc": None,
        "home_team": home, "away_team": away,
        "home_score": hs, "away_score": aws,
        "pen_home": ph, "pen_away": pa,
        "aet": aet,
        "stage": stage,
        "status": status,
    }


def test_winner_home_regulation():
    df = _matches_to_fixtures_df([_match(hs=2, aws=1)])
    assert df.iloc[0]["Winner"] == "HOME"


def test_winner_away_regulation():
    df = _matches_to_fixtures_df([_match(hs=0, aws=3)])
    assert df.iloc[0]["Winner"] == "AWAY"


def test_winner_group_draw():
    df = _matches_to_fixtures_df([_match(hs=1, aws=1)])
    assert df.iloc[0]["Winner"] == "DRAW"


def test_winner_aet_decisive_no_pens():
    df = _matches_to_fixtures_df([_match(hs=2, aws=1, aet=True)])
    assert df.iloc[0]["Winner"] == "HOME"


def test_winner_pens_home():
    df = _matches_to_fixtures_df([_match(hs=1, aws=1, aet=True, ph=4, pa=3)])
    assert df.iloc[0]["Winner"] == "HOME"


def test_winner_pens_away():
    df = _matches_to_fixtures_df([_match(hs=1, aws=1, aet=True, ph=3, pa=5)])
    assert df.iloc[0]["Winner"] == "AWAY"


def test_winner_unplayed():
    df = _matches_to_fixtures_df([_match(status="upcoming")])
    assert df.iloc[0]["Winner"] == ""
