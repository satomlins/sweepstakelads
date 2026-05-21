"""Unit tests for app._apply_flags."""

import pandas as pd

from app import FLAGS, _apply_flags


def test_show_false_returns_unchanged_copy():
    df = pd.DataFrame({"Team": ["Brazil", "Qatar"], "Stage": ["Group A", "Group B"]})
    out = _apply_flags(df, ["Team"], show=False)
    assert list(out["Team"]) == ["Brazil", "Qatar"]
    assert out is not df  # copy, not the same object


def test_show_true_substitutes_mapped_names():
    df = pd.DataFrame({"Team": ["Qatar", "Ghana"]})
    out = _apply_flags(df, ["Team"], show=True)
    assert out.loc[0, "Team"] == FLAGS["Qatar"]
    assert out.loc[1, "Team"] == FLAGS["Ghana"]


def test_unmapped_falls_through_to_original():
    df = pd.DataFrame({"Team": ["Qatar", "Winner of Match 57"]})
    out = _apply_flags(df, ["Team"], show=True)
    assert out.loc[0, "Team"] == FLAGS["Qatar"]
    assert out.loc[1, "Team"] == "Winner of Match 57"  # unchanged


def test_multiple_columns_substituted_independently():
    df = pd.DataFrame({"Home": ["Qatar"], "Away": ["Ghana"], "Stage": ["Group A"]})
    out = _apply_flags(df, ["Home", "Away"], show=True)
    assert out.loc[0, "Home"] == FLAGS["Qatar"]
    assert out.loc[0, "Away"] == FLAGS["Ghana"]
    assert out.loc[0, "Stage"] == "Group A"  # untouched


def test_missing_column_is_noop():
    df = pd.DataFrame({"Team": ["Qatar"]})
    # 'Home' is not a column; should not raise.
    out = _apply_flags(df, ["Home", "Team"], show=True)
    assert out.loc[0, "Team"] == FLAGS["Qatar"]


def test_empty_dataframe_returns_empty_copy():
    df = pd.DataFrame({"Team": []})
    out = _apply_flags(df, ["Team"], show=True)
    assert out.empty
