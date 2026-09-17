import pandas as pd

from pipeline.schedule import build_schedule_payloads


def test_schedule_includes_last_meeting_before_each_game() -> None:
    games = pd.DataFrame(
        [
            {
                "game_id": "2025_01_BUF_DET", "season": 2025, "week": 1,
                "game_type": "REG", "gameday": "2025-09-01", "gametime": "13:00",
                "away_team": "BUF", "home_team": "DET", "away_score": 27,
                "home_score": 20, "stadium": "Test Field", "roof": "dome", "surface": "turf",
            },
            {
                "game_id": "2026_02_DET_BUF", "season": 2026, "week": 2,
                "game_type": "REG", "gameday": "2026-09-17", "gametime": "20:15",
                "away_team": "DET", "home_team": "BUF", "away_score": None,
                "home_score": None, "stadium": "New Field", "roof": "outdoors", "surface": "grass",
            },
        ]
    )

    schedule, histories = build_schedule_payloads(games, 2026, "2026-09-17T00:00:00Z")

    assert schedule["games"][0]["lastMeeting"]["winnerAbbreviation"] == "BUF"
    assert schedule["games"][0]["lastMeeting"]["date"] == "2025-09-01"
    assert histories["matchups"]["BUF__DET"][0][6] == 27
