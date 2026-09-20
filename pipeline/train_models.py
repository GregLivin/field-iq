from __future__ import annotations

import json
import re
from math import erf, sqrt
from datetime import UTC, datetime
from typing import Any
import joblib
import numpy as np
import pandas as pd
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from pipeline.config import MODEL_DIR, PROCESSED_DIR, RANDOM_STATE, RAW_DIR, ensure_directories
from pipeline.features import FEATURE_COLUMNS, build_features
from pipeline.pbp_features import aggregate_team_game_pbp
from pipeline.schedule import team_name, write_schedule_payloads
from pipeline.player_features import PLAYER_FEATURE_COLUMNS, attach_player_form


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


def _regressors():
    return {
      "random_forest": Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", RandomForestRegressor(n_estimators=350, min_samples_leaf=8, max_features="sqrt", random_state=RANDOM_STATE, n_jobs=-1))]),
      "gradient_boosting": Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", HistGradientBoostingRegressor(max_iter=180, learning_rate=.05, max_leaf_nodes=15, l2_regularization=1.0, random_state=RANDOM_STATE))]),
    }


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


def _normal_cdf(value: float, mean: float, sd: float) -> float:
    sd=max(float(sd), 1.0)
    return .5 * (1 + erf((value-mean)/(sd*sqrt(2))))


def _reconcile_home_probability(classifier_prob: float, projected_margin: float, margin_sd: float) -> tuple[float, float]:
    score_prob = 1.0 - _normal_cdf(0.0, projected_margin, margin_sd)
    blended = 0.65 * float(classifier_prob) + 0.35 * float(score_prob)
    return float(np.clip(blended, .08, .92)), float(score_prob)


def _market_probabilities(projected_margin: float, projected_total: float, home_spread: float | None, market_total: float | None, margin_sd: float, total_sd: float):
    result={}
    if home_spread is not None:
        threshold=-home_spread
        result["homeCoverProbability"]=round((1-_normal_cdf(threshold,projected_margin,margin_sd))*100)
        result["awayCoverProbability"]=100-result["homeCoverProbability"]
    if market_total is not None:
        result["overProbability"]=round((1-_normal_cdf(market_total,projected_total,total_sd))*100)
        result["underProbability"]=100-result["overProbability"]
    return result


def _top_factors(row):
    candidates=[(abs(row.get("elo_diff",0))/100,"Elo team strength"),(abs(row.get("point_margin_5_diff",0))/7,"Recent scoring margin"),(abs(row.get("off_epa_per_play_5_diff",0))*5,"EPA per play"),(abs(row.get("success_rate_5_diff",0))*10,"Success rate"),(abs(row.get("qb_epa_per_play_5_diff",0))*5,"Quarterback efficiency"),(abs(row.get("explosive_play_rate_5_diff",0))*10,"Explosive plays"),(abs(row.get("turnovers_5_diff",0)),"Turnover trend")]
    return [label for _,label in sorted(candidates,reverse=True)[:3]]



def _merge_approved_manual_games(games: pd.DataFrame, team_stats: pd.DataFrame):
    """Merge only approved manual records into provider frames without overwriting provider games."""
    manual_path=PROCESSED_DIR.parent/"manual"/"games.jsonl"
    if not manual_path.exists(): return games,team_stats,{"approved":0,"merged":0,"duplicates":0,"skipped":0}
    game_rows=[]; stat_rows=[]; seen=set(games["game_id"].astype(str)); summary={"approved":0,"merged":0,"duplicates":0,"skipped":0}
    for line in manual_path.read_text(encoding="utf-8").splitlines():
        try: r=json.loads(line)
        except json.JSONDecodeError: summary["skipped"]+=1; continue
        if not (r.get("validated") and r.get("approvedForTraining")): continue
        summary["approved"]+=1
        p=r.get("parsed") or {}; ts=p.get("teamStats") or {}
        team=str(r.get("team") or "").upper(); opp=str(r.get("opponent") or "").upper()
        date=r.get("gameDate"); week=r.get("week"); season=r.get("season")
        # ML requires matchup identity, date/week, and final scores. Never infer them.
        score=ts.get("score") or {}
        if not (team and opp and date and week and season and "team" in score and "opponent" in score):
            summary["skipped"]+=1; continue
        gid=f"manual_{season}_{week}_{date}_{team}_{opp}"
        # Provider data wins. Also reject same season/week/team pairing even if IDs differ.
        duplicate=((games.get("season")==season)&(games.get("week")==week)&
          (((games.get("home_team")==team)&(games.get("away_team")==opp))|((games.get("home_team")==opp)&(games.get("away_team")==team)))).any()
        if gid in seen or duplicate: summary["duplicates"]+=1; continue
        home=team if r.get("homeAway","home")=="home" else opp; away=opp if home==team else team
        hs=score["team"] if home==team else score["opponent"]; aws=score["opponent"] if home==team else score["team"]
        game_rows.append({"game_id":gid,"season":season,"week":week,"gameday":date,"gametime":"00:00","home_team":home,"away_team":away,"home_score":hs,"away_score":aws})
        def add_stats(t, side):
            vals={k:(v.get(side) if isinstance(v,dict) else None) for k,v in ts.items()}
            stat_rows.append({"game_id":gid,"team":t,"passing_yards":vals.get("passingYards"),"rushing_yards":vals.get("rushingYards"),"def_sacks":vals.get("sacks")})
        add_stats(team,"team"); add_stats(opp,"opponent"); seen.add(gid); summary["merged"]+=1
    if game_rows: games=pd.concat([games,pd.DataFrame(game_rows)],ignore_index=True,sort=False)
    if stat_rows: team_stats=pd.concat([team_stats,pd.DataFrame(stat_rows)],ignore_index=True,sort=False)
    return games,team_stats,summary


def train_and_predict()->dict[str,Any]:
    ensure_directories(); games=pl.read_parquet(RAW_DIR/"games.parquet").to_pandas(); team_stats=pl.read_parquet(RAW_DIR/"team_weekly.parquet").to_pandas()
    games, team_stats, manual_summary = _merge_approved_manual_games(games, team_stats)
    pbp_path = RAW_DIR / "pbp.parquet"
    if pbp_path.exists():
        pbp=pl.read_parquet(pbp_path).to_pandas(); pbp_team=aggregate_team_game_pbp(pbp)
        if not pbp_team.empty:
            team_stats=team_stats.copy(); team_stats["game_id"]=team_stats["game_id"].astype(str); pbp_team["game_id"]=pbp_team["game_id"].astype(str)
            team_stats=team_stats.merge(pbp_team,on=["game_id","team"],how="left")
            pbp_team.to_parquet(PROCESSED_DIR/"team_game_pbp_features.parquet",index=False)
    injuries=pl.read_parquet(RAW_DIR/"injuries.parquet").to_pandas() if (RAW_DIR/"injuries.parquet").exists() else pd.DataFrame()
    weather=pl.read_parquet(RAW_DIR/"weather_daily.parquet").to_pandas() if (RAW_DIR/"weather_daily.parquet").exists() else pd.DataFrame(); games=_apply_kickoff_weather(games,weather)
    training,upcoming,_=build_features(games,team_stats)
    player_path=RAW_DIR/"player_weekly.parquet"
    player_weekly=pl.read_parquet(player_path).to_pandas() if player_path.exists() else pd.DataFrame()
    training,upcoming,player_form=attach_player_form(training,upcoming,player_weekly)
    if not player_form.empty: player_form.to_parquet(PROCESSED_DIR/"team_player_form.parquet",index=False)
    model_features=FEATURE_COLUMNS+[f"player_{c}_diff" for c in PLAYER_FEATURE_COLUMNS]
    training=training.sort_values(["gameday","gametime","game_id"])
    if len(training)<200:raise RuntimeError(f"Need at least 200 completed games; found {len(training)}")
    latest=int(training["season"].max()); test_mask=training["season"]==latest; validation=f"season-{latest}"
    if test_mask.sum()<32 or (~test_mask).sum()<200:
        split=int(len(training)*.8); test_mask=pd.Series(False,index=training.index); test_mask.iloc[split:]=True; validation="chronological-20-percent"
    Xtr=training.loc[~test_mask,model_features]; ytr=training.loc[~test_mask,"home_win"]; Xte=training.loc[test_mask,model_features]; yte=training.loc[test_mask,"home_win"]
    fitted={}; metrics={}
    score_models={}; score_metrics={}
    score_targets={"home_score":"homeScore","away_score":"awayScore","home_margin":"homeMargin","game_total":"gameTotal"}
    for target, label in score_targets.items():
        target_models={}; target_metrics={}
        for name, model in _regressors().items():
            model.fit(Xtr, training.loc[~test_mask, target])
            pred=model.predict(Xte)
            target_metrics[name]={"mae":round(float(mean_absolute_error(training.loc[test_mask,target],pred)),3),"rmse":round(float(mean_squared_error(training.loc[test_mask,target],pred)**.5),3)}
            joblib.dump(model, MODEL_DIR/f"{target}_{name}.joblib", compress=3)
            target_models[name]=model
        score_models[target]=target_models
        score_metrics[label]=target_metrics
    margin_ensemble=np.column_stack([m.predict(Xte) for m in score_models["home_margin"].values()]).mean(axis=1)
    total_ensemble=np.column_stack([m.predict(Xte) for m in score_models["game_total"].values()]).mean(axis=1)
    margin_sd=float(np.std(training.loc[test_mask,"home_margin"].to_numpy()-margin_ensemble, ddof=1))
    total_sd=float(np.std(training.loc[test_mask,"game_total"].to_numpy()-total_ensemble, ddof=1))
    for name,model in _models().items():
        model.fit(Xtr,ytr); p=model.predict_proba(Xte)[:,1]; metrics[name]={"accuracy":round(float(accuracy_score(yte,p>=.5)),4),"logLoss":round(float(log_loss(yte,p,labels=[0,1])),4),"brierScore":round(float(brier_score_loss(yte,p)),4)}; joblib.dump(model,MODEL_DIR/f"{name}.joblib",compress=3); fitted[name]=model
    if upcoming.empty: next_games=upcoming
    else:
        nd=upcoming["gameday"].dropna().min(); window=upcoming[upcoming["gameday"]<=nd+pd.DateOffset(days=7)]; first=window.sort_values("gameday").iloc[0]; next_games=upcoming[(upcoming["season"]==int(first["season"]))&(upcoming["week"]==int(first["week"]))]
    penalties=_injury_penalties(injuries); predictions=[]
    if not next_games.empty:
        probs=np.column_stack([m.predict_proba(next_games[model_features])[:,1] for m in fitted.values()]).mean(axis=1)
        score_preds={target:np.column_stack([m.predict(next_games[model_features]) for m in models.values()]).mean(axis=1) for target,models in score_models.items()}
        for offset,(_,row) in enumerate(next_games.iterrows()):
            raw_hp=float(np.clip(probs[offset]+(penalties.get(row["away_team"],0)-penalties.get(row["home_team"],0))/100,.08,.92)); hn=team_name(row["home_team"]); an=team_name(row["away_team"])
            projected_home=max(0,round(float(score_preds["home_score"][offset]),1)); projected_away=max(0,round(float(score_preds["away_score"][offset]),1))
            projected_margin=round(float(score_preds["home_margin"][offset]),1); projected_total=round(float(score_preds["game_total"][offset]),1)
            hp, score_hp = _reconcile_home_probability(raw_hp, projected_margin, margin_sd)
            predictions.append({"id":row["game_id"],"awayTeam":an,"awayAbbreviation":row["away_team"],"homeTeam":hn,"homeAbbreviation":row["home_team"],"kickoff":f"{row['gameday'].date().isoformat()} {row['gametime']}","predictedWinner":hn if hp>=.5 else an,"homeWinProbability":round(hp*100),"awayWinProbability":round((1-hp)*100),"classifierHomeProbability":round(raw_hp*100),"scoreModelHomeProbability":round(score_hp*100),"projectedHomeScore":projected_home,"projectedAwayScore":projected_away,"projectedMargin":projected_margin,"projectedTotal":projected_total,"confidence":_confidence(hp),"factors":_top_factors(row)})
    season=int(next_games.iloc[0]["season"]) if not next_games.empty else latest; week=int(next_games.iloc[0]["week"]) if not next_games.empty else int(training.iloc[-1]["week"]); now=datetime.now(UTC).isoformat()
    payload={"season":season,"week":week,"asOf":now,"provider":"nflverse + NOAA/NWS","model":"fieldiq-ensemble-v4-reconciled","predictions":predictions}; (PROCESSED_DIR/"predictions.json").write_text(json.dumps(payload,indent=2)+"\n")
    mp={"generatedAt":now,"trainingGames":int(len(Xtr)),"validationGames":int(len(Xte)),"validationMethod":validation,"features":model_features,"models":metrics,"manualData":manual_summary,"scoreModels":score_metrics,"marketCalibration":{"marginResidualSd":round(margin_sd,3),"totalResidualSd":round(total_sd,3),"method":"validation residual normal approximation"}}; (PROCESSED_DIR/"model_metrics.json").write_text(json.dumps(mp,indent=2)+"\n")
    write_schedule_payloads(games,season,PROCESSED_DIR,now,team_stats,payload); training.to_parquet(PROCESSED_DIR/"game_features.parquet",index=False); return {"predictionCount":len(predictions),**mp}

if __name__=="__main__": print(json.dumps(train_and_predict(),indent=2))
