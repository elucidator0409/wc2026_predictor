import pandas as pd

from data_service import (
    PREDICTIONS_COLUMNS,
    _predictions_header_offset,
    _row_looks_like_prediction,
    normalize_predictions_df,
    repair_predictions_sheet_header,
    upsert_user_predictions,
)


class FakeWorksheet:
    def __init__(self, rows: list[list[str]]):
        self.rows = [list(r) for r in rows]

    def get_all_values(self):
        return [list(r) for r in self.rows]

    def update(self, range_name, values, value_input_option=None):
        if range_name == "A1:E1":
            self.rows[0] = list(values[0])

    def insert_row(self, values, index=1, value_input_option=None):
        self.rows.insert(index - 1, list(values))

    def batch_update(self, updates):
        for item in updates:
            row_num = int(item["range"].split(":")[0][1:])
            self.rows[row_num - 1] = list(item["values"][0])

    def append_rows(self, rows, value_input_option=None):
        self.rows.extend([list(r) for r in rows])


def test_row_looks_like_prediction():
    assert _row_looks_like_prediction(["U01", "1", "A", "", "2026-06-11"])
    assert not _row_looks_like_prediction(list(PREDICTIONS_COLUMNS))


def test_header_offset_with_missing_header():
    data = [
        ["U01", "1", "A", "", "2026-06-11"],
        ["U02", "1", "B", "", "2026-06-11"],
    ]
    assert _predictions_header_offset(data) == 0


def test_header_offset_with_correct_header():
    data = [list(PREDICTIONS_COLUMNS), ["U01", "1", "A", "", "2026-06-11"]]
    assert _predictions_header_offset(data) == 1


def test_read_predictions_sheet_missing_header():
    class FakeSh:
        def __init__(self, ws):
            self._ws = ws

        def worksheet(self, name):
            return self._ws

    from data_service import read_predictions_sheet

    ws = FakeWorksheet([["U01", "1", "A", "", "t1"]])
    out = read_predictions_sheet(FakeSh(ws))
    assert len(out) == 1
    assert out.iloc[0]["user_id"] == "U01"
    assert out.iloc[0]["match_id"] == "1"


def test_normalize_predictions_filters_invalid_user_ids():
    df = pd.DataFrame(
        {
            "user_id": ["U01", "nan"],
            "match_id": ["1", "2"],
            "pred_outcome": ["A", "B"],
            "pred_advanced_team_id": ["", ""],
            "timestamp": ["", ""],
        }
    )
    out = normalize_predictions_df(df)
    assert len(out) == 1
    assert out.iloc[0]["user_id"] == "U01"


def test_repair_inserts_header_without_deleting_first_row():
    ws = FakeWorksheet([["U01", "1", "A", "", "2026-06-11"]])
    action = repair_predictions_sheet_header(ws)
    assert action == "inserted_header"
    assert ws.rows[0] == list(PREDICTIONS_COLUMNS)
    assert ws.rows[1][0] == "U01"


def test_upsert_without_header():
    ws = FakeWorksheet([["U01", "1", "A", "", "t1"]])
    updated, inserted = upsert_user_predictions(ws, "U01", [("2", "B", "", "t2")])
    assert updated == 0
    assert inserted == 1
    assert ws.rows[-1][1] == "2"


def test_upsert_updates_existing_row():
    ws = FakeWorksheet(
        [
            list(PREDICTIONS_COLUMNS),
            ["U01", "1", "A", "", "t1"],
        ]
    )
    updated, inserted = upsert_user_predictions(ws, "U01", [("1", "B", "", "t2")])
    assert updated == 1
    assert inserted == 0
    assert ws.rows[1][2] == "B"
