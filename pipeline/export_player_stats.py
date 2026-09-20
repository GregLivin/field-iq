from __future__ import annotations
import json
from datetime import UTC, datetime
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data"/"raw"/"player_season.parquet"
OUT=ROOT/"data"/"processed"/"player_stats.json"
FIELDS=["passing_yards","passing_tds","passing_interceptions","completions","attempts","rushing_yards","rushing_tds","carries","receptions","targets","receiving_yards","receiving_tds","def_tackles_solo","def_tackle_assists","def_sacks","def_qb_hits","def_interceptions","def_pass_defended","def_fumbles_forced","fg_made","fg_att","fg_pct","pat_made","pat_att","pt_att","pt_yards","punt_returns","punt_return_yards","kickoff_returns","kickoff_return_yards"]
def val(r,n):
    v=r.get(n)
    return None if v is None or pd.isna(v) else float(v)
def build_player_stats():
    df=pd.read_parquet(RAW); team_col="team" if "team" in df.columns else "recent_team"; name_col=next((x for x in ("player_display_name","player_name","player") if x in df.columns),"player_id")
    payload={"asOf":datetime.now(UTC).isoformat(),"provider":"nflverse automated coverage layer","officialReference":"NFL.com validation layer","seasons":{}}
    for season in (2025,2026):
        sdf=df[df["season"].astype(int)==season]
        teams={}
        for team,g in sdf.groupby(team_col):
            players=[]
            for _,r in g.iterrows():
                p={"playerId":str(r.get("player_id") or ""),"playerName":str(r.get(name_col) or r.get("player_id") or "Unknown"),"position":str(r.get("position") or "")}
                for f in FIELDS: p[f]=val(r,f) if f in r else None
                players.append(p)
            def top(field): return sorted([p for p in players if p.get(field) is not None and p.get(field)!=0],key=lambda p:p[field],reverse=True)[:5]
            teams[str(team)]={"players":players,"leaders":{"passing":top("passing_yards"),"rushing":top("rushing_yards"),"receiving":top("receiving_yards"),"defense":top("def_tackles_solo"),"kicking":top("fg_made")}}
        payload["seasons"][str(season)]={"scope":"full_season" if season==2025 else "season_to_date","teams":teams}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,separators=(",",":"))+"\n")
    return {"path":str(OUT),"seasons":{s:len(v["teams"]) for s,v in payload["seasons"].items()}}
if __name__=="__main__": print(json.dumps(build_player_stats(),indent=2))
