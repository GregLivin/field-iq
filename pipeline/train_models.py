from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
import joblib
import numpy as np
import pandas as pd
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from pipeline.config import MODEL_DIR, PROCESSED_DIR, RANDOM_STATE, RAW_DIR, ensure_directories
from pipeline.features import FEATURE_COLUMNS, build_features
from pipeline.pbp_features import aggregate_team_game_pbp
from pipeline.schedule import team_name, write_schedule_payloads


def _apply_kickoff_weather(games, weather):
    if weather.empty: return games
    games=games.copy(); weather=weather.copy(); weather["forecast_start"]=pd.to_datetime(weather["forecast_start"],utc=True,errors="coerce")
    for index,game in games[games["home_score"].isna()].iterrows():
        candidates=weather[weather["team"]==game["home_team"]].dropna(subset=["forecast_start"])
        if candidates.empty: continue
        timezone=str(candidates.iloc[0]["timezone"]); kickoff=pd.Timestamp(f"{game['gameday']} {game['gametime']}",tz=timezone).tz_convert("UTC")
        closest=(candidates["forecast_start"]-kickoff).abs().idxmin(); forecast=candidates.loc[closest]
        if abs((forecast["forecast_start"].to_pydatetime()-kickoff.to_pydatetime()).total_seconds())>43200: continue
        games.at[index,"temp"]=forecast["temperature_f"]; speed=re.search(r"\d+",str(forecast["wind_speed"])); games.at[index,"wind"]=float(speed.group()) if speed else 0.0
    return games


def _models():
    return {
      "logistic":Pipeline([("imputer",SimpleImputer(strategy="median")),("scale",StandardScaler()),("model",LogisticRegression(max_iter=1000,random_state=RANDOM_STATE))]),
      "random_forest":Pipeline([("imputer",SimpleImputer(strategy="median")),("model",RandomForestClassifier(n_estimators=350,min_samples_leaf=8,max_features="sqrt",random_state=RANDOM_STATE,n_jobs=-1))]),
      "gradient_boosting":Pipeline([("imputer",SimpleImputer(strategy="median")),("model",HistGradientBoostingClassifier(max_iter=180,learning_rate=.05,max_leaf_nodes=15,l2_regularization=1.0,random_state=RANDOM_STATE))])}


def _injury_penalties(injuries):
    if injuries.empty:return {}
    pw={"QB":2.5,"OT":1.1,"WR":.8,"CB":.8,"EDGE":.8}; sw={"Out":1.0,"Doubtful":.7,"Questionable":.25}; penalties={}
    for row in injuries.to_dict(orient="records"):
        status=str(row.get("report_status") or "")
        if status not in sw:continue
        team=str(row.get("team") or ""); penalties[team]=penalties.get(team,0)+sw[status]*pw.get(str(row.get("position") or ""),.35)
    return penalties


def _confidence(p):
    e=abs(p-.5); return "High" if e>=.18 else "Medium" if e>=.07 else "Low"


def _top_factors(row):
    candidates=[(abs(row.get("elo_diff",0))/100,"Elo team strength"),(abs(row.get("point_margin_5_diff",0))/7,"Recent scoring margin"),(abs(row.get("off_epa_per_play_5_diff",0))*5,"EPA per play"),(abs(row.get("success_rate_5_diff",0))*10,"Success rate"),(abs(row.get("qb_epa_per_play_5_diff",0))*5,"Quarterback efficiency"),(abs(row.get("explosive_play_rate_5_diff",0))*10,"Explosive plays"),(abs(row.get("turnovers_5_diff",0)),"Turnover trend")]
    return [label for _,label in sorted(candidates,reverse=True)[:3]]


def train_and_predict()->dict[str,Any]:
    ensure_directories(); games=pl.read_parquet(RAW_DIR/"games.parquet").to_pandas(); team_stats=pl.read_parquet(RAW_DIR/"team_weekly.parquet").to_pandas()
    pbp_path=RAW_DIR/"pbp.parquet"
    if pbp_path.exists():
        pbp=pl.read_parquet(pbp_path).to_pandas(); pbp_team=aggregate_team_game_pbp(pbp)
        if not pbp_team.empty:
            team_stats=team_stats.copy(); team_stats["game_id"]=team_stats["game_id"].astype(str); pbp_team["game_id"]=pbp_team["game_id"].astype(str)
            team_stats=team_stats.merge(pbp_team,on=["game_id","team"],how="left")
            pbp_team.to_parquet(PROCESSED_DIR/"team_game_pbp_features.parquet",index=False)
    injuries=pl.read_parquet(RAW_DIR/"injuries.parquet").to_pandas() if (RAW_DIR/"injuries.parquet").exists() else pd.DataFrame()
    weather=pl.read_parquet(RAW_DIR/"weather_daily.parquet").to_pandas() if (RAW_DIR/"weather_daily.parquet").exists() else pd.DataFrame(); games=_apply_kickoff_weather(games,weather)
    training,upcoming,_=build_features(games,team_stats); training=training.sort_values(["gameday","gametime","game_id"])
    if len(training)<200:raise RuntimeError(f"Need at least 200 completed games; found {len(training)}")
    latest=int(training["season"].max()); test_mask=training["season"]==latest; validation=f"season-{latest}"
    if test_mask.sum()<32 or (~test_mask).sum()<200:
        split=int(len(training)*.8); test_mask=pd.Series(False,index=training.index); test_mask.iloc[split:]=True; validation="chronological-20-percent"
    Xtr=training.loc[~test_mask,FEATURE_COLUMNS]; ytr=training.loc[~test_mask,"home_win"]; Xte=training.loc[test_mask,FEATURE_COLUMNS]; yte=training.loc[test_mask,"home_win"]
    fitted={}; metrics={}
    for name,model in _models().items():
        model.fit(Xtr,ytr); p=model.predict_proba(Xte)[:,1]; metrics[name]={"accuracy":round(float(accuracy_score(yte,p>=.5)),4),"logLoss":round(float(log_loss(yte,p,labels=[0,1])),4),"brierScore":round(float(brier_score_loss(yte,p)),4)}; joblib.dump(model,MODEL_DIR/f"{name}.joblib",compress=3); fitted[name]=model
    if upcoming.empty: next_games=upcoming
    else:
        nd=upcoming["gameday"].dropna().min(); window=upcoming[upcoming["gameday"]<=nd+pd.DateOffset(days=7)]; first=window.sort_values("gameday").iloc[0]; next_games=upcoming[(upcoming["season"]==int(first["season"]))&(upcoming["week"]==int(first["week"]))]
    penalties=_injury_penalties(injuries); predictions=[]
    if not next_games.empty:
        probs=np.column_stack([m.predict_proba(next_games[FEATURE_COLUMNS])[:,1] for m in fitted.values()]).mean(axis=1)
        for offset,(_,row) in enumerate(next_games.iterrows()):
            hp=float(np.clip(probs[offset]+(penalties.get(row["away_team"],0)-penalties.get(row["home_team"],0))/100,.08,.92)); hn=team_name(row["home_team"]); an=team_name(row["away_team"])
            predictions.append({"id":row["game_id"],"awayTeam":an,"awayAbbreviation":row["away_team"],"homeTeam":hn,"homeAbbreviation":row["home_team"],"kickoff":f"{row['gameday'].date().isoformat()} {row['gametime']}","predictedWinner":hn if hp>=.5 else an,"homeWinProbability":round(hp*100),"awayWinProbability":round((1-hp)*100),"confidence":_confidence(hp),"factors":_top_factors(row)})
    season=int(next_games.iloc[0]["season"]) if not next_games.empty else latest; week=int(next_games.iloc[0]["week"]) if not next_games.empty else int(training.iloc[-1]["week"]); now=datetime.now(UTC).isoformat()
    payload={"season":season,"week":week,"asOf":now,"provider":"nflverse + NOAA/NWS","model":"fieldiq-ensemble-v2-pbp","predictions":predictions}; (PROCESSED_DIR/"predictions.json").write_text(json.dumps(payload,indent=2)+"\n")
    mp={"generatedAt":now,"trainingGames":int(len(Xtr)),"validationGames":int(len(Xte)),"validationMethod":validation,"features":FEATURE_COLUMNS,"models":metrics}; (PROCESSED_DIR/"model_metrics.json").write_text(json.dumps(mp,indent=2)+"\n")
    write_schedule_payloads(games,season,PROCESSED_DIR,now,team_stats); training.to_parquet(PROCESSED_DIR/"game_features.parquet",index=False); return {"predictionCount":len(predictions),**mp}

if __name__=="__main__": print(json.dumps(train_and_predict(),indent=2))
