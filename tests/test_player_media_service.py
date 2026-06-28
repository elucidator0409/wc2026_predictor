from unittest.mock import MagicMock, patch

from player_media_service import fetch_player_media_impl


def test_fetch_player_media_thesportsdb():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "player": [
            {
                "strPlayer": "Harry Kane",
                "strNationality": "England",
                "strTeam": "England",
                "strThumb": "https://example.com/kane.jpg",
                "strNumber": "9",
                "strTeamBadge": "https://example.com/badge.png",
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("player_media_service.requests.get", return_value=mock_resp):
        result = fetch_player_media_impl("Harry Kane", "ENG", "England")

    assert result["photo_url"] == "https://example.com/kane.jpg"
    assert result["shirt_number"] == "9"
    assert result["source"] == "thesportsdb"


def test_fetch_player_media_fallback_initials():
    with patch("player_media_service.requests.get", side_effect=Exception("network")):
        result = fetch_player_media_impl("Harry Kane", "ENG", "England")

    assert result["photo_url"] == ""
    assert result["initials"] == "HK"
    assert result["source"] == "initials"
