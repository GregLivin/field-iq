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


def test_recent_form_includes_last_games_and_team_stats() -> None:
    games = pd.DataFrame(
        [
            {
                "game_id": "2025_18_BUF_NE", "season": 2025, "week": 18,
                "game_type": "REG", "gameday": "2026-01-04", "gametime": "13:00",
                "away_team": "BUF", "home_team": "NE", "away_score": 30,
                "home_score": 13, "stadium": "Test Field", "roof": "outdoors", "surface": "turf",
            },
            {
                "game_id": "2026_01_MIA_BUF", "season": 2026, "week": 1,
                "game_type": "REG", "gameday": "2026-09-10", "gametime": "20:15",
                "away_team": "MIA", "home_team": "BUF", "away_score": 20,
                "home_score": 31, "stadium": "New Field", "roof": "outdoors", "surface": "grass",
            },
        ]
    )
    team_stats = pd.DataFrame(
        [
            {
                "game_id": "2026_01_MIA_BUF", "team": "BUF", "passing_yards": 275,
                "rushing_yards": 124, "passing_epa": 8.5, "rushing_epa": 2.5,
                "passing_interceptions": 1, "fumbles_lost_total": 0, "def_sacks": 3,
            }
        ]
    )

    _, histories = build_schedule_payloads(
        games, 2026, "2026-09-17T00:00:00Z", team_stats
    )

    recent = histories["recentForm"]["BUF"]
    assert len(recent) == 2
    assert recent[0][1] == "2026-09-10"
    assert recent[0][10] == "W"
    assert recent[0][13] == 399
    assert recent[0][14] == 11
