import pandas as pd

from players_service import (
    PLAYERS_CSV_PATH,
    filter_squad,
    load_players_df,
    normalize_team_code,
    prep_players,
    squad_summary,
    top_players,
)


def _teams_df():
    return pd.read_csv(PLAYERS_CSV_PATH.parent / "teams.csv")


def test_normalize_team_code_cuw_alias():
    assert normalize_team_code("CUW") == "CUR"


def test_load_players_from_csv():
    df = load_players_df(sh=None)
    assert len(df) == 1248
    assert df["team_code"].nunique() == 48


def test_prep_players_joins_teams():
    players = load_players_df(sh=None)
    teams = _teams_df()
    prepped = prep_players(players, teams)

    assert prepped["fifa_code"].notna().all()
    assert prepped["group_letter"].str.len().gt(0).sum() == 1248
    curacao = prepped[prepped["fifa_code"] == "CUR"]
    assert len(curacao) == 26

    korea = prepped[prepped["team"] == "Korea Republic"]
    assert korea.iloc[0]["fifa_code"] == "KOR"
    assert korea.iloc[0]["team_name_sheet"] == "South Korea"


def test_filter_squad_mexico():
    players = prep_players(load_players_df(sh=None), _teams_df())
    squad = filter_squad(players, "MEX")
    assert len(squad) == 26

    gk = filter_squad(players, "MEX", position="GK")
    assert len(gk) >= 3
    assert (gk["position"] == "GK").all()


def test_filter_squad_search():
    players = prep_players(load_players_df(sh=None), _teams_df())
    squad = filter_squad(players, "ARG", search="MESSI")
    assert len(squad) >= 1
    assert squad.iloc[0]["player_name"].upper().find("MESSI") >= 0


def test_squad_summary_and_top_players():
    players = prep_players(load_players_df(sh=None), _teams_df())
    squad = filter_squad(players, "ALG")
    summary = squad_summary(squad)

    assert summary["count"] == 26
    assert summary["total_caps"] > 0
    assert summary["avg_height"] > 150

    top = top_players(players, "ALG", limit=3)
    assert len(top) == 3
    assert top.iloc[0]["goals"] >= top.iloc[1]["goals"]
