from team_flags import build_name_to_fifa, flag_emoji, flagcdn_slug, flag_img_html
import pandas as pd


def test_flagcdn_slug_all_teams_csv():
    teams = pd.read_csv("data/teams.csv")
    missing = []
    for code in teams["fifa_code"]:
        if not flagcdn_slug(str(code)):
            missing.append(code)
    assert missing == []


def test_flag_emoji_usa_brazil():
    assert flag_emoji("USA") == "🇺🇸"
    assert flag_emoji("BRA") == "🇧🇷"


def test_flag_img_html_contains_src():
    html_out = flag_img_html("QAT")
    assert "flagcdn.com" in html_out
    assert "qa.png" in html_out


def test_build_name_to_fifa():
    teams = pd.read_csv("data/teams.csv")
    lookup = build_name_to_fifa(teams)
    assert lookup["Brazil"] == "BRA"
    assert lookup["USA"] == "USA"
