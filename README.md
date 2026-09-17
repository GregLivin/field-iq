# FieldIQ

**Smarter predictions. Better picks.**

## Live app

[Open the FieldIQ app](https://api-liard-five-70.vercel.app)

FieldIQ is an NFL-only mobile prediction app that displays game-winner probabilities and the factors behind each pick. It now includes an automated multi-source data pipeline and a trained three-model ensemble.

## MVP features

- Weekly NFL matchup cards
- Mobile-first Picks, Schedule, and Matchups navigation
- Complete 18-week schedule for all 32 teams with week and team filters
- Last-meeting winner, date, score, and five-game head-to-head history
- Predicted winner and win probability
- Confidence level and key prediction factors
- Daily nflverse schedules, team stats, player stats, rosters, and injury snapshots
- Official NOAA/National Weather Service hourly forecasts matched to kickoff
- Leakage-safe rolling game features using only information available before kickoff
- Logistic regression, random forest, and gradient-boosting ensemble
- Model accuracy, log loss, and Brier-score reporting
- Demo-data fallback when the API is unavailable
- iOS, Android, and web support through Expo

## Project structure

- `App.tsx` — mobile dashboard
- `src/services/fieldIqApi.ts` — mobile-to-backend API client
- `src/data/demoPredictions.ts` — safe demo fallback
- `api/main.py` — lightweight FastAPI service for generated prediction artifacts
- `pipeline/collect_nflverse.py` — independent NFL dataset collection
- `pipeline/collect_weather.py` — official NWS forecast collection
- `pipeline/features.py` — chronological rolling-feature construction
- `pipeline/train_models.py` — model training, evaluation, and prediction
- `pipeline/schedule.py` — season schedule and head-to-head history generation
- `.github/workflows/daily-data.yml` — automatic daily refresh

## Run the mobile app

Requirements: Node.js 20.19.4 or newer and the Expo Go app.

```bash
npm install
npx expo install --fix
npm start
```

Scan the QR code with Expo Go on your phone.

## Run the daily ML pipeline

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-ml.txt
python -m pipeline.run_daily
```

This produces separate Parquet datasets under `data/raw/`, model artifacts under `models/`, and the small JSON files served by the app under `data/processed/`.

## Run the NFL API

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Copy `.env.example` to `.env` and set `EXPO_PUBLIC_FIELD_IQ_API_URL` to the backend address reachable from your phone. Never commit a real API key.

Set `FIELDIQ_CONTACT_EMAIL` for the User-Agent required by the NWS API. No paid sports API key is required for this version.

## Daily automation

The GitHub Actions workflow runs every morning and can also be started manually from **Actions → Daily FieldIQ data and predictions → Run workflow**. Large raw datasets and model files are uploaded as a 30-day workflow artifact; the small prediction, schedule, matchup-history, and metrics files are committed for Vercel to deploy.

## Prediction roadmap

1. Add historical injury-value features and quarterback starter changes.
2. Calibrate ensemble probabilities by season.
3. Backtest against simple home-team and Elo baselines.
4. Move daily snapshots to durable object storage when the project grows.
5. Upgrade to an officially licensed Genius Sports feed when funding permits.

## Important

The free NFL datasets are supplied by the community-maintained nflverse project and are not an official NFL feed. Weather forecasts come from the official NWS API. Predictions are estimates, not guarantees. Demo predictions are fictional examples. FieldIQ is not affiliated with or endorsed by the NFL.
