from scoring import build_pred_adv_fields


def test_build_pred_adv_ko_draw_with_team():
    name_to_id = {"Portugal": "10", "Croatia": "11"}
    outcome, adv_id = build_pred_adv_fields("D", "Portugal", True, name_to_id)
    assert outcome == "D"
    assert adv_id == "10"


def test_build_pred_adv_ko_win_clears_adv():
    name_to_id = {"Portugal": "10"}
    outcome, adv_id = build_pred_adv_fields("A", "Portugal", True, name_to_id)
    assert outcome == "A"
    assert adv_id == ""


def test_build_pred_adv_group_draw_no_pen():
    name_to_id = {"Mexico": "1"}
    outcome, adv_id = build_pred_adv_fields("D", "Mexico", False, name_to_id)
    assert outcome == "D"
    assert adv_id == ""


def test_build_pred_adv_tbd_sentinel():
    outcome, adv_id = build_pred_adv_fields("D", "TBD", True, {"A": "1"})
    assert outcome == "D"
    assert adv_id == ""
