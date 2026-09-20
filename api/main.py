import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_PATH = ROOT / "data" / "processed" / "predictions.json"
METRICS_PATH = ROOT / "data" / "processed" / "model_metrics.json"
MANIFEST_PATH = ROOT / "data" / "raw" / "manifest.json"
WEATHER_STATUS_PATH = ROOT / "data" / "raw" / "weather_status.json"
SCHEDULE_PATH = ROOT / "data" / "processed" / "schedule.json"
MATCHUP_HISTORY_PATH = ROOT / "data" / "processed" / "matchup_history.json"
MATCHUPS_PATH = ROOT / "data" / "processed" / "matchups.json"
MANUAL_GAMES_PATH = Path(os.getenv("FIELDIQ_MANUAL_GAMES_PATH", str(ROOT / "data" / "manual" / "games.jsonl")))

app = FastAPI(title="Field IQ NFL API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Generated artifact {path.name} is not available yet.",
        ) from exc


def _expand_meeting(values: list[Any]) -> dict[str, Any]:
    return {
        "id": values[0], "date": values[1], "season": values[2], "week": values[3],
        "gameType": values[4], "awayTeam": values[5], "awayAbbreviation": values[5],
        "awayScore": values[6], "homeTeam": values[7], "homeAbbreviation": values[7],
        "homeScore": values[8], "winner": values[9] or "Tie",
        "winnerAbbreviation": values[9],
    }


def _expand_recent_game(values: list[Any]) -> dict[str, Any]:
    return {
        "id": values[0], "date": values[1], "season": values[2], "week": values[3],
        "gameType": values[4], "teamAbbreviation": values[5],
        "opponent": values[6], "opponentAbbreviation": values[6],
        "homeAway": values[7], "teamScore": values[8], "opponentScore": values[9],
        "result": values[10], "passingYards": values[11], "rushingYards": values[12],
        "totalYards": values[13], "totalEpa": values[14], "turnovers": values[15],
        "defensiveSacks": values[16],
    }


class AlertPreferences(BaseModel):
    gameReminders: bool = True
    predictionUpdates: bool = True
    highConfidence: bool = True
    finalResults: bool = True


class TextAlertRequest(BaseModel):
    phone: str
    preferences: AlertPreferences


@app.post("/api/alerts/test")
async def send_test_alert(request: TextAlertRequest) -> dict[str, Any]:
    """Send an opt-in Field IQ test SMS through Twilio."""
    phone = request.phone.strip()
    if not phone.startswith("+") or not phone[1:].isdigit() or len(phone) < 11:
        raise HTTPException(status_code=400, detail="Enter a phone number in E.164 format, for example +17135551234.")

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    if not all((account_sid, auth_token, from_number)):
        raise HTTPException(status_code=503, detail="Text alerts are not configured on the server yet.")

    enabled = []
    labels = {
        "gameReminders": "game reminders",
        "predictionUpdates": "prediction updates",
        "highConfidence": "high-confidence alerts",
        "finalResults": "final results",
    }
    prefs = request.preferences.model_dump()
    for key, label in labels.items():
        if prefs.get(key):
            enabled.append(label)

    body = "Field IQ alerts are on. " + (", ".join(enabled) if enabled else "No alert categories selected.") + " Reply STOP to opt out."
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            url,
            data={"To": phone, "From": from_number, "Body": body},
            auth=(account_sid, auth_token),
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="The SMS provider could not send the test alert.")
    return {"ok": True, "message": "Field IQ test alert sent."}



@app.post("/api/market-screenshot")
async def analyze_market_screenshot(file: UploadFile = File(...)) -> dict[str, Any]:
    """Extract NFL market lines from a screenshot with OpenAI vision."""
    import base64
    image = await file.read()
    if not image or len(image) > 8_000_000:
        raise HTTPException(status_code=400, detail="Upload a screenshot smaller than 8 MB.")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured on the server.")
    mime=file.content_type or "image/jpeg"
    data_url=f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}"
    schema={
      "type":"object","additionalProperties":False,
      "properties":{"games":{"type":"array","items":{"type":"object","additionalProperties":False,
        "properties":{
          "awayTeam":{"type":"string"},"homeTeam":{"type":"string"},
          "awaySpread":{"type":["number","null"]},"homeSpread":{"type":["number","null"]},
          "total":{"type":["number","null"]},"awayMoneyline":{"type":["number","null"]},
          "homeMoneyline":{"type":["number","null"]}
        },
        "required":["awayTeam","homeTeam","awaySpread","homeSpread","total","awayMoneyline","homeMoneyline"]
      }}},
      "required":["games"]
    }
    request_body={
      "model":os.getenv("FIELDIQ_VISION_MODEL","gpt-5.6-luna"),
      "input":[{"role":"user","content":[
        {"type":"input_text","text":"Read this sports-market screenshot. Extract NFL matchups only. Team values must be standard NFL abbreviations such as CIN and HOU. Preserve the displayed spread signs and numeric totals. For decimal moneyline multipliers such as 2.24x, return 2.24. Use null when a field is absent or unreadable. Do not infer a missing number."},
        {"type":"input_image","image_url":data_url}
      ]}],
      "text":{"format":{"type":"json_schema","name":"field_iq_markets","strict":True,"schema":schema}}
    }
    async with httpx.AsyncClient(timeout=45) as client:
        response=await client.post("https://api.openai.com/v1/responses",headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},json=request_body)
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="The screenshot vision service could not analyze this image.")
    payload=response.json()
    output_text=payload.get("output_text")
    if not output_text:
        for item in payload.get("output",[]):
            for part in item.get("content",[]):
                if part.get("type")=="output_text":
                    output_text=part.get("text"); break
    try:
        parsed=json.loads(output_text or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="The screenshot vision service returned invalid structured data.") from exc
    games=parsed.get("games",[])
    return {"games":games,"message":f"Found {len(games)} matchup(s). Review every extracted line before analysis."}

@app.get("/health")
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "time": datetime.now(UTC).isoformat(),
        "predictions": "ready" if PREDICTIONS_PATH.exists() else "pending",
    }


@app.get("/api/predictions")
async def predictions(
    season: int | None = Query(None, ge=2000, le=2100),
    week: int | None = Query(None, ge=1, le=22),
) -> dict[str, Any]:
    payload = _load_json(PREDICTIONS_PATH)
    if season is not None and season != payload.get("season"):
        return {**payload, "predictions": []}
    if week is not None and week != payload.get("week"):
        return {**payload, "predictions": []}
    return payload


@app.get("/api/schedule")
async def schedule(
    season: int | None = Query(None, ge=2000, le=2100),
    week: int | None = Query(None, ge=1, le=22),
    team: str | None = Query(None, min_length=2, max_length=3),
    status: str | None = Query(None, pattern="^(upcoming|final)$"),
) -> dict[str, Any]:
    payload = _load_json(SCHEDULE_PATH)
    games = payload.get("games", [])
    if season is not None and season != payload.get("season"):
        games = []
    if week is not None:
        games = [game for game in games if game.get("week") == week]
    if team is not None:
        abbreviation = team.upper()
        games = [
            game
            for game in games
            if abbreviation in (game.get("awayAbbreviation"), game.get("homeAbbreviation"))
        ]
    if status is not None:
        games = [game for game in games if game.get("status") == status]
    return {**payload, "games": games, "count": len(games)}


@app.get("/api/matchup/{game_id}")
async def matchup_intelligence(game_id: str) -> dict[str, Any]:
    payload=_load_json(MATCHUPS_PATH)
    record=payload.get("games",{}).get(game_id)
    if record is None: raise HTTPException(status_code=404,detail="Matchup not found.")
    return {**record,"asOf":payload.get("asOf"),"provider":payload.get("provider")}


@app.get("/api/matchups")
async def matchup_history(
    team1: str = Query(..., min_length=2, max_length=3),
    team2: str = Query(..., min_length=2, max_length=3),
    limit: int = Query(5, ge=1, le=25),
) -> dict[str, Any]:
    payload = _load_json(MATCHUP_HISTORY_PATH)
    teams = sorted((team1.upper(), team2.upper()))
    key = "__".join(teams)
    meetings = [
        _expand_meeting(meeting)
        for meeting in payload.get("matchups", {}).get(key, [])[:limit]
    ]
    recent_form = {
        team: [
            _expand_recent_game(game)
            for game in payload.get("recentForm", {}).get(team, [])[:limit]
        ]
        for team in teams
    }
    return {
        "asOf": payload.get("asOf"),
        "provider": payload.get("provider"),
        "teams": teams,
        "meetings": meetings,
        "recentForm": recent_form,
        "seasonSummaries": {team: payload.get("seasonSummaries", {}).get(team, {}) for team in teams},
        "count": len(meetings),
    }



def _parse_manual_stats(raw: str) -> dict[str, Any]:
    """Parse both team-site tables and compact ATL PASSING/RUSHING-style copies."""
    import re
    lines=[line.strip() for line in raw.splitlines() if line.strip()]
    text="\n".join(lines)
    kinds=("passing","rushing","receiving","tackles","interceptions","fieldGoals","punting","puntReturn","kickReturn","fumbles")
    parsed: dict[str, Any]={"teamStats":{},"players":{k:[] for k in kinds},"unparsed":False,"format":"team_site","sourceScope":"game","warnings":[]}

    if re.search(r"\bSEASON STATS\b", text, re.I):
        parsed["sourceScope"]="season_to_date"
        parsed["warnings"].append("Source says SEASON STATS. Store as season-to-date unless you confirm this is a single-game view.")

    def number(v: str):
        return float(v) if "." in v else int(v)

    def paired(label: str, key: str):
        m=re.search(rf"(-?\d+(?:\.\d+)?)\s*\n{re.escape(label)}\s*\n(-?\d+(?:\.\d+)?)", text, re.I)
        if m: parsed["teamStats"][key]={"team":number(m.group(1)),"opponent":number(m.group(2))}

    for label,key in [("TOTAL FIRST DOWNS","firstDowns"),("TOTAL OFFENSIVE YARDS","totalYards"),("TOTAL RUSHING YARDS","rushingYards"),("TOTAL PASSING YARDS","passingYards"),("SACKS","sacks"),("TOUCHDOWNS","touchdowns"),("TURNOVER RATIO","turnoverRatio"),("FINAL SCORE","score")]:
        paired(label,key)
    for label,key in [("THIRD DOWN CONVERSIONS","thirdDown"),("FOURTH DOWN CONVERSIONS","fourthDown"),("FIELD GOALS","fieldGoals")]:
        m=re.search(rf"(\d+\s*/\s*\d+)\s*\n{re.escape(label)}\s*\n(\d+\s*/\s*\d+)",text,re.I)
        if m: parsed["teamStats"][key]={"team":m.group(1).replace(" ",""),"opponent":m.group(2).replace(" ","")}

    # Format A: team-site copies where a Player header and tab-separated row values are preserved.
    section_names={"Passing":"passing","Rushing":"rushing","Receiving":"receiving","Tackles":"tackles","Interceptions":"interceptions","Field Goals":"fieldGoals","Punting":"punting","Punt Return":"puntReturn","Kick Return":"kickReturn"}
    i=0
    while i < len(lines):
        kind=section_names.get(lines[i])
        if not kind: i+=1; continue
        j=i+1
        while j < len(lines) and not lines[j].startswith("Player"): j+=1
        if j>=len(lines): i+=1; continue
        headers=lines[j].split("\t"); j+=1
        while j+1<len(lines):
            if lines[j] in section_names or lines[j] in ("Defense","Special Teams","OFFENSE","DEFENSE","SPECIAL TEAMS"): break
            name=lines[j]; vals=lines[j+1].split("\t")
            if len(vals)>=2 and len(headers)>=2:
                parsed["players"][kind].append({"player":name,"values":dict(zip(headers[1:],vals))}); j+=2
            else: break
        i=max(i+1,j)

    # Format B: copied game/season page: ATL PASSING, ATL RUSHING, etc., one value per line.
    compact={
      "PASSING":("passing",["CMP","ATT","YDS","CMP%","AVG","TD","INT","SACKS","RATING"]),
      "RUSHING":("rushing",["ATT","YDS","TD","AVG","LONG","FUM","20+"]),
      "RECEIVING":("receiving",["REC","YDS","TD","TGTS","LONG","YAC"]),
      "FUMBLES":("fumbles",["FUM","LOST","FR"]),
      "DEFENSE":("tackles",["TOT","SOLO","SACKS","TFL","PD","INT","QBP","INT TD","FF","FR"]),
      "KICKING":("fieldGoals",["FGM","FGA","XP","50+","LONG"]),
      "KICKOFF RETURNS":("kickReturn",["RET","AVG","TD","LONG"]),
      "PUNTING":("punting",["PUNTS","AVG","IN 20","LONG"]),
      "PUNT RETURNS":("puntReturn",["RET","AVG","TD","LONG"]),
    }
    heading=re.compile(r"^[A-Z]{2,3} ("+"|".join(re.escape(x) for x in compact)+r")$")
    found_compact=False
    i=0
    while i < len(lines):
        hm=heading.match(lines[i])
        if not hm: i+=1; continue
        found_compact=True; label=hm.group(1); kind,expected=compact[label]; i+=1
        if i < len(lines) and lines[i]=="PLAYER": i+=1
        headers=[]
        while i < len(lines) and lines[i] in expected:
            headers.append(lines[i]); i+=1
        if not headers: headers=expected
        while i < len(lines) and not heading.match(lines[i]):
            if lines[i]=="TEAM": break
            name=lines[i]
            if i+1<len(lines) and lines[i+1]==name: i+=1
            vals=lines[i+1:i+1+len(headers)]
            if len(vals)==len(headers) and all(re.fullmatch(r"-?\d+(?:\.\d+)?",v) for v in vals):
                parsed["players"][kind].append({"player":name,"values":dict(zip(headers,vals))})
                i+=1+len(headers)
            else: i+=1
    if found_compact: parsed["format"]="compact_team_stats"

    # Resolve abbreviated names when the same paste also contains a full-name leaderboard.
    full_names=[]
    for line in lines:
        if re.fullmatch(r"[A-Z][A-Za-z.'-]+(?: [A-Z][A-Za-z.'-]+)+", line) and line.upper() not in ("Atlanta Falcons".upper(),):
            full_names.append(line)
    def abbr(name: str) -> str:
        parts=name.split()
        return f"{parts[0][0].upper()}. {parts[-1].upper()}" if len(parts)>1 else name.upper()
    name_map={}
    for full in full_names:
        name_map.setdefault(abbr(full),[]).append(full)
    for kind,rows in parsed["players"].items():
        for row in rows:
            short=row["player"]
            candidates=list(dict.fromkeys(name_map.get(short,[])))
            if len(candidates)==1:
                row["sourcePlayer"]=short
                row["player"]=candidates[0]
                row["identityStatus"]="resolved_from_paste"
            elif re.match(r"^[A-Z]\.\s",short):
                row["identityStatus"]="ambiguous" if len(candidates)>1 else "unresolved"
                row["identityCandidates"]=candidates

    # Flag initials that collide inside a section (e.g. two B. ROBINSON rows).
    for kind,rows in parsed["players"].items():
        counts={}
        for row in rows:
            original=row.get("sourcePlayer",row["player"])
            counts[original]=counts.get(original,0)+1
        for name,count in counts.items():
            if count>1 and re.match(r"^[A-Z]\.\s",name):
                parsed["warnings"].append(f"Ambiguous abbreviated player in {kind}: {name}. Review identity before ML approval.")

    parsed["unparsed"]=not bool(parsed["teamStats"] or any(parsed["players"].values()))
    return parsed


class ManualGameRequest(BaseModel):
    rawText: str
    season: int
    seasonType: str = "Regular season"
    week: int | None = None
    gameDate: str | None = None
    team: str | None = None
    opponent: str | None = None
    homeAway: str | None = None
    teamScore: int | None = None
    opponentScore: int | None = None
    includeInTraining: bool = False


class ManualApprovalRequest(BaseModel):
    approved: bool = True


@app.post("/api/manual-games")
async def save_manual_game(request: ManualGameRequest) -> dict[str, Any]:
    raw=request.rawText.strip()
    if len(raw)<40: raise HTTPException(status_code=400,detail="Paste the team/game statistics before saving.")
    import hashlib
    record_id=hashlib.sha256(" ".join(raw.lower().split()).encode()).hexdigest()[:16]
    MANUAL_GAMES_PATH.parent.mkdir(parents=True,exist_ok=True)
    records=[]
    if MANUAL_GAMES_PATH.exists():
        for line in MANUAL_GAMES_PATH.read_text(encoding="utf-8").splitlines():
            try: records.append(json.loads(line))
            except json.JSONDecodeError: continue
    if any(r.get("id")==record_id for r in records): raise HTTPException(status_code=409,detail="This pasted stat record already exists.")
    parsed=_parse_manual_stats(raw)
    # Keep explicit final scores separate from raw source text.
    if request.teamScore is not None and request.opponentScore is not None:
        parsed["teamStats"]["score"]={"team":request.teamScore,"opponent":request.opponentScore}
    player_count=sum(len(rows) for rows in parsed.get("players",{}).values())
    required={"week":request.week,"gameDate":request.gameDate,"team":request.team,"opponent":request.opponent,"homeAway":request.homeAway,"teamScore":request.teamScore,"opponentScore":request.opponentScore}
    missing=[key for key,value in required.items() if value is None or value==""]
    ambiguous=[w for w in parsed.get("warnings",[]) if w.startswith("Ambiguous abbreviated player")]
    readiness={"ready":not missing and not parsed.get("unparsed") and player_count>0 and not ambiguous,"missing":missing,"playerRecords":player_count,"format":parsed.get("format"),"sourceScope":parsed.get("sourceScope"),"warnings":parsed.get("warnings",[])}
    record=request.model_dump()
    record["parsed"]=parsed
    record["readiness"]=readiness
    record.update({"id":record_id,"source":"manual","createdAt":datetime.now(UTC).isoformat(),"validated":False,"approvedForTraining":False})
    records.append(record)
    MANUAL_GAMES_PATH.write_text("\n".join(json.dumps(r) for r in records)+"\n",encoding="utf-8")
    warnings=[]
    if request.includeInTraining: warnings.append("Review the parsed record, then approve it before ML training.")
    return {"ok":True,"id":record_id,"warnings":warnings,"parsed":parsed,"readiness":readiness}


@app.post("/api/manual-games/{record_id}/approval")
async def approve_manual_game(record_id: str, request: ManualApprovalRequest) -> dict[str, Any]:
    if not MANUAL_GAMES_PATH.exists(): raise HTTPException(status_code=404,detail="Manual record not found.")
    records=[]; found=None
    for line in MANUAL_GAMES_PATH.read_text(encoding="utf-8").splitlines():
        try: record=json.loads(line)
        except json.JSONDecodeError: continue
        if record.get("id")==record_id:
            found=record
            if request.approved:
                readiness=record.get("readiness") or {}
                if record.get("parsed",{}).get("unparsed"):
                    raise HTTPException(status_code=400,detail="This record has not been parsed successfully.")
                if not readiness.get("ready"):
                    raise HTTPException(status_code=400,detail=f"Record is not ML-ready. Missing: {', '.join(readiness.get('missing', [])) or 'player statistics'}.")
            record["validated"]=request.approved
            record["approvedForTraining"]=request.approved
        records.append(record)
    if found is None: raise HTTPException(status_code=404,detail="Manual record not found.")
    MANUAL_GAMES_PATH.write_text("\n".join(json.dumps(r) for r in records)+"\n",encoding="utf-8")
    return {"ok":True,"id":record_id,"approvedForTraining":request.approved}


@app.get("/api/player-stats")
async def player_stats(
    team: str = Query(..., min_length=2, max_length=3),
    season: int = Query(..., ge=2000, le=2100),
) -> dict[str, Any]:
    """Return season player leaders for a team from the automated player layer."""
    path = ROOT / "data" / "raw" / "player_season.parquet"
    if not path.exists():
        raise HTTPException(status_code=503, detail="Player season data is not available.")
    import polars as pl
    frame=pl.read_parquet(path).to_pandas()
    frame=frame[(frame["season"].astype(int)==season)&(frame["team"].astype(str)==team.upper())].copy()
    def n(row,*names):
        for name in names:
            if name in row and pd.notna(row[name]): return float(row[name])
        return None
    def player(row):
        return str(row.get("player_display_name") or row.get("player_name") or row.get("player") or row.get("player_id") or "Unknown")
    records=[]
    for _,r in frame.iterrows():
        records.append({"playerId":str(r.get("player_id") or ""),"playerName":player(r),"position":str(r.get("position") or ""),
          "passingYards":n(r,"passing_yards"),"passingTds":n(r,"passing_tds"),"interceptions":n(r,"interceptions","passing_interceptions"),
          "completions":n(r,"completions"),"attempts":n(r,"attempts"),"rushingYards":n(r,"rushing_yards"),"rushingTds":n(r,"rushing_tds"),
          "receptions":n(r,"receptions"),"targets":n(r,"targets"),"receivingYards":n(r,"receiving_yards"),"receivingTds":n(r,"receiving_tds")})
    def top(field,count=5): return sorted([x for x in records if x.get(field) is not None],key=lambda x:x[field],reverse=True)[:count]
    return {"team":team.upper(),"season":season,"scope":"full_season" if season<2026 else "season_to_date","provider":"nflverse automated coverage layer","asOf":datetime.now(UTC).isoformat(),
      "leaders":{"passing":top("passingYards"),"rushing":top("rushingYards"),"receiving":top("receivingYards")},"players":records}


@app.get("/api/player-impact")
async def player_impact(
    away: str = Query(..., min_length=2, max_length=3),
    home: str = Query(..., min_length=2, max_length=3),
    season: int = Query(..., ge=2000, le=2100),
) -> dict[str, Any]:
    """Compare pregame-safe rolling player-form features used by Field IQ."""
    path=ROOT/"data"/"processed"/"team_player_form.parquet"
    if not path.exists(): raise HTTPException(status_code=503,detail="Player form features are not available.")
    import polars as pl
    df=pl.read_parquet(path).to_pandas()
    cols=set(df.columns)
    team_col="team" if "team" in cols else "team_abbr" if "team_abbr" in cols else None
    if not team_col: raise HTTPException(status_code=503,detail="Player form team identity is unavailable.")
    if "season" in cols: df=df[df["season"].astype(int)==season]
    if "week" in cols: df=df.sort_values("week")
    def latest(team):
        x=df[df[team_col].astype(str)==team.upper()]
        return None if x.empty else x.iloc[-1]
    a,h=latest(away),latest(home)
    if a is None or h is None: raise HTTPException(status_code=404,detail="Player form not found for one or both teams.")
    groups={"Quarterback":{"metric":"qb_pass_yards_5","label":"5-game QB pass yards"},
      "Rushing":{"metric":"rush_yards_5","label":"5-game rushing yards"},
      "Receiving":{"metric":"receiving_yards_5","label":"5-game receiving yards"}}
    comparisons=[]
    for name,g in groups.items():
        m=g["metric"]; av=float(a[m]) if m in cols and pd.notna(a[m]) else None; hv=float(h[m]) if m in cols and pd.notna(h[m]) else None
        edge=None if av is None or hv is None or abs(av-hv)<1e-9 else (away.upper() if av>hv else home.upper())
        comparisons.append({"category":name,"metric":g["label"],"awayValue":av,"homeValue":hv,"edge":edge})
    return {"season":season,"away":away.upper(),"home":home.upper(),"method":"pregame rolling player form","comparisons":comparisons,
      "notice":"Uses prior-game rolling player features only; no same-game or future player statistics."}


@app.get("/api/model")
async def model_metrics() -> dict[str, Any]:
    return _load_json(METRICS_PATH)


@app.get("/api/data-status")
@app.get("/api/data_status")
async def data_status() -> dict[str, Any]:
    return {
        "nflverse": _load_json(MANIFEST_PATH),
        "weather": _load_json(WEATHER_STATUS_PATH),
        "officialNFLFeed": False,
        "notice": "nflverse is community-maintained and is not an official NFL feed.",
    }
