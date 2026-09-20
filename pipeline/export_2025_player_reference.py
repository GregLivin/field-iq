from __future__ import annotations

"""Build an auditable 2025 player-stat reference layer.

Automated nflverse season totals provide complete player/team coverage. NFL.com
category pages remain the official reference source and are recorded separately
so Field IQ never mislabels automated data as an NFL.com scrape.
"""
import json
from datetime import UTC, datetime
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data"/"raw"/"player_season.parquet"
OUT=ROOT/"data"/"manual"/"2025_player_stats_reference.csv"
AUDIT=ROOT/"data"/"manual"/"2025_player_stats_reference_audit.json"
NFL={
 "passing":"https://www.nfl.com/stats/player-stats/category/passing/2025/REG/all/passingyards/DESC",
 "rushing":"https://www.nfl.com/stats/player-stats/category/rushing/2025/REG/all/rushingyards/DESC",
 "receiving":"https://www.nfl.com/stats/player-stats/category/receiving/2025/REG/all/receivingyards/DESC",
 "tackles":"https://www.nfl.com/stats/player-stats/category/tackles/2025/REG/all/defensivesacks/DESC",
 "interceptions":"https://www.nfl.com/stats/player-stats/category/interceptions/2025/REG/all/defensiveinterceptions/DESC",
 "punting":"https://www.nfl.com/stats/player-stats/category/punts/2025/REG/all/puntingaverageyards/DESC",
 "kickoff_returns":"https://www.nfl.com/stats/player-stats/category/kickoff-returns/2025/REG/all/kickreturns/DESC",
 "punt_returns":"https://www.nfl.com/stats/player-stats/category/punt-returns/2025/REG/all/puntreturnsyards/DESC",
}
def main():
    if not RAW.exists(): raise FileNotFoundError(RAW)
    df=pd.read_parquet(RAW); df=df[df["season"].astype(int)==2025].copy()
    team_col=next((x for x in ("team","recent_team") if x in df.columns),None)
    name_col=next((x for x in ("player_display_name","player_name","player") if x in df.columns),None)
    id_col="player_id" if "player_id" in df.columns else None
    meta={"season","season_type","week","position","position_group","headshot_url",team_col,name_col,id_col}
    stat_cols=[c for c in df.columns if c not in meta and pd.api.types.is_numeric_dtype(df[c])]
    rows=[]
    for _,r in df.iterrows():
        for stat in stat_cols:
            v=r.get(stat)
            if pd.isna(v): continue
            rows.append({"season":2025,"player_id":str(r.get(id_col,"")) if id_col else "","player":str(r.get(name_col,"")) if name_col else "",
              "team":str(r.get(team_col,"")) if team_col else "","position":str(r.get("position","")),"stat":stat,"value":float(v),
              "scope":"full_regular_season","coverage":"automated_complete_layer","source":"nflverse","official_reference":"NFL.com"})
    out=pd.DataFrame(rows); OUT.parent.mkdir(parents=True,exist_ok=True); out.to_csv(OUT,index=False)
    audit={"season":2025,"generatedAt":datetime.now(UTC).isoformat(),"players":int(df[id_col].nunique()) if id_col else int(len(df)),
      "teams":int(df[team_col].nunique()) if team_col else None,"statFields":stat_cols,"rows":len(out),
      "automatedSource":"nflverse","officialReferenceProvider":"NFL.com","officialReferencePages":NFL,
      "policy":"NFL.com is the official validation/reference layer. This export is not labeled as a row-by-row NFL.com scrape."}
    AUDIT.write_text(json.dumps(audit,indent=2)+"\n")
    print(json.dumps(audit,indent=2))
if __name__=="__main__": main()
