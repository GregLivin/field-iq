import pandas as pd

from pipeline.player_features import attach_player_form, build_team_player_week_features


def test_player_form_uses_only_prior_weeks():
    players = pd.DataFrame([
        {"season":2026,"week":1,"team":"HOU","position":"QB","passing_yards":200,"passing_tds":1,"passing_interceptions":0,"completions":20,"attempts":30},
        {"season":2026,"week":2,"team":"HOU","position":"QB","passing_yards":300,"passing_tds":3,"passing_interceptions":1,"completions":25,"attempts":35},
    ])
    form=build_team_player_week_features(players)
    w2=form[(form.season==2026)&(form.week==2)&(form.team=="HOU")].iloc[0]
    assert w2.qb_pass_yards_5 == 200
    assert w2.qb_pass_tds_5 == 1
    w3=form[(form.season==2026)&(form.week==3)&(form.team=="HOU")].iloc[0]
    assert w3.qb_pass_yards_5 == 250
    assert w3.qb_pass_tds_5 == 2


def test_attach_player_form_creates_home_away_diffs():
    players=pd.DataFrame([
        {"season":2026,"week":1,"team":"HOU","position":"QB","passing_yards":300},
        {"season":2026,"week":1,"team":"DAL","position":"QB","passing_yards":200},
    ])
    games=pd.DataFrame([{"season":2026,"week":2,"home_team":"HOU","away_team":"DAL"}])
    training,_,_=attach_player_form(games,pd.DataFrame(),players)
    assert training.iloc[0].player_qb_pass_yards_5_diff == 100
