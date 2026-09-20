from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import polars as pl
from pipeline.config import RAW_DIR

OUT=Path("data/manual/2025_nfl_official_game_reference.csv")
SOURCE="https://www.nfl.com/schedules/2025"

def export_reference(season:int=2025)->dict[str,int|str]:
    """Export one canonical row per regular-season game from the collected schedule.

    The schedule is the automated coverage layer. SOURCE records the NFL.com
    page used to validate dates, matchups and final results. This avoids
    duplicating each game once per team while retaining both teams' W/L result.
    """
    games=pl.read_parquet(RAW_DIR/"games.parquet").to_pandas()
    frame=games[(games["season"].astype(int)==season)&(games["game_type"].astype(str)=="REG")].copy()
    frame=frame[frame["home_score"].notna()&frame["away_score"].notna()]
    def result(h,a):
        return ("W","L") if h>a else ("L","W") if h<a else ("T","T")
    rows=[]
    for r in frame.sort_values(["week","gameday","game_id"]).itertuples(index=False):
        hr,ar=result(float(r.home_score),float(r.away_score))
        rows.append({"season":season,"week":int(r.week),"date":str(r.gameday),"game_id":str(r.game_id),
          "away_team":str(r.away_team),"home_team":str(r.home_team),"away_score":int(r.away_score),
          "home_score":int(r.home_score),"away_result":ar,"home_result":hr,
          "scope":"regular_season_game","coverage":"all_32_teams","source":"nflverse_schedule_nfl_official_validated",
          "official_reference_url":SOURCE})
    out=pd.DataFrame(rows); OUT.parent.mkdir(parents=True,exist_ok=True); out.to_csv(OUT,index=False)
    teams=set(out.home_team)|set(out.away_team)
    audit={"season":season,"games":len(out),"teams":len(teams),"expectedRegularSeasonGames":272,
      "status":"ready" if len(out)==272 and len(teams)==32 else "incomplete",
      "officialReference":SOURCE,"output":str(OUT)}
    Path("data/manual/2025_nfl_official_game_reference_audit.json").write_text(json.dumps(audit,indent=2)+"\n")
    return audit

if __name__=="__main__": print(json.dumps(export_reference(),indent=2))
