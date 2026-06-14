"""Unit tests for app._apply_flags."""

import pandas as pd

from app import FLAGS, _apply_flags


def test_show_names_false_returns_flag_only():
    df = pd.DataFrame({"Team": ["Brazil", "Qatar"], "Stage": ["Group A", "Group B"]})
    out = _apply_flags(df, ["Team"], show_names=False)
    assert out.loc[0, "Team"] == FLAGS["Brazil"]
    assert out.loc[1, "Team"] == FLAGS["Qatar"]
    assert out is not df


def test_show_names_true_prepends_flag():
    df = pd.DataFrame({"Team": ["Qatar", "Ghana"]})
    out = _apply_flags(df, ["Team"], show_names=True)
    assert out.loc[0, "Team"] == f"{FLAGS['Qatar']} Qatar"
    assert out.loc[1, "Team"] == f"{FLAGS['Ghana']} Ghana"


def test_unmapped_falls_through_to_original():
    df = pd.DataFrame({"Team": ["Qatar", "Winner of Match 57"]})
    out = _apply_flags(df, ["Team"], show_names=True)
    assert out.loc[0, "Team"] == f"{FLAGS['Qatar']} Qatar"
    assert out.loc[1, "Team"] == "Winner of Match 57"


def test_multiple_columns_substituted_independently():
    df = pd.DataFrame({"Home": ["Qatar"], "Away": ["Ghana"], "Stage": ["Group A"]})
    out = _apply_flags(df, ["Home", "Away"], show_names=True)
    assert out.loc[0, "Home"] == f"{FLAGS['Qatar']} Qatar"
    assert out.loc[0, "Away"] == f"{FLAGS['Ghana']} Ghana"
    assert out.loc[0, "Stage"] == "Group A"


def test_missing_column_is_noop():
    df = pd.DataFrame({"Team": ["Qatar"]})
    out = _apply_flags(df, ["Home", "Team"], show_names=True)
    assert out.loc[0, "Team"] == f"{FLAGS['Qatar']} Qatar"


def test_empty_dataframe_returns_empty_copy():
    df = pd.DataFrame({"Team": []})
    out = _apply_flags(df, ["Team"], show_names=True)
    assert out.empty
