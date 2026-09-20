import pandas as pd

from pipeline.features import build_features


def test_upcoming_features_only_use_completed_games() -> None:
    games = pd.DataFrame(
        [
            {
                "game_id": "2025_01_A_B", "season": 2025, "week": 1,
                "gameday": "2025-09-01", "gametime": "12:00", "away_team": "A",
                "home_team": "B", "away_score": 10, "home_score": 20,
                "away_rest": 7, "home_rest": 7, "roof": "outdoors", "temp": 70,
                "wind": 5, "stadium": "Test Field",
            },
            {
                "game_id": "2025_02_B_A", "season": 2025, "week": 2,
                "gameday": "2025-09-08", "gametime": "12:00", "away_team": "B",
                "home_team": "A", "away_score": None, "home_score": None,
                "away_rest": 7, "home_rest": 7, "roof": "outdoors", "temp": 70,
                "wind": 5, "stadium": "Test Field",
            },
        ]
    )
    stats = pd.DataFrame(
        [
            {"game_id": "2025_01_A_B", "team": "A", "passing_epa": -2,
             "rushing_epa": 1, "passing_yards": 150, "rushing_yards": 80,
             "passing_interceptions": 1, "fumbles_lost_total": 0, "def_sacks": 1},
            {"game_id": "2025_01_A_B", "team": "B", "passing_epa": 4,
             "rushing_epa": 2, "passing_yards": 240, "rushing_yards": 110,
             "passing_interceptions": 0, "fumbles_lost_total": 0, "def_sacks": 3},
        ]
    )

    training, upcoming, _ = build_features(games, stats)

    assert len(training) == 1
    assert len(upcoming) == 1
    assert upcoming.iloc[0]["point_margin_5_diff"] == -20
    assert upcoming.iloc[0]["win_rate_5_diff"] == -1



def test_prior_season_record_features_are_pregame_only() -> None:
    games=pd.DataFrame([{"game_id":"2025_01_A_B","season":2025,"week":1,"gameday":"2025-09-01","gametime":"12:00","away_team":"A","home_team":"B","away_score":10,"home_score":20},{"game_id":"2026_01_A_B","season":2026,"week":1,"gameday":"2026-09-01","gametime":"12:00","away_team":"A","home_team":"B","away_score":None,"home_score":None}])
    _, upcoming, _=build_features(games,pd.DataFrame(columns=["game_id","team"]))
    row=upcoming.iloc[0]
    assert row["prior_season_win_pct_diff"] == 1.0
    assert row["prior_season_point_diff_pg_diff"] == 20.0
