# FieldIQ

**Smarter predictions. Better picks.**

## Live app

[Open the FieldIQ app](https://field-iq-yepyup-s-projects25.vercel.app)

FieldIQ is an NFL-only mobile prediction app that displays game-winner probabilities and the factors behind each pick. The first MVP includes an Expo/React Native app, an NFL API proxy, and a transparent baseline prediction method ready to be replaced by a trained machine-learning model.

## MVP features

- Weekly NFL matchup cards
- Predicted winner and win probability
- Confidence level and key prediction factors
- SportsDataIO NFL integration through a backend proxy
- Demo-data fallback when the API is unavailable
- iOS, Android, and web support through Expo

## Project structure

- `App.tsx` — mobile dashboard
- `src/services/fieldIqApi.ts` — mobile-to-backend API client
- `src/data/demoPredictions.ts` — safe demo fallback
- `api/main.py` — FastAPI server and SportsDataIO integration

## Run the mobile app

Requirements: Node.js 20.19.4 or newer and the Expo Go app.

```bash
npm install
npx expo install --fix
npm start
```

Scan the QR code with Expo Go on your phone.

## Run the NFL API

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SPORTSDATAIO_API_KEY="your_key"
uvicorn main:app --reload
```

Copy `.env.example` to `.env` and set `EXPO_PUBLIC_FIELD_IQ_API_URL` to the backend address reachable from your phone. Never commit a real API key.

SportsDataIO offers NFL schedules, scores, rosters, injuries, statistics, and related feeds. Confirm that your subscription permits your planned commercial use.

## Prediction roadmap

1. Collect licensed historical NFL game and team data.
2. Create pregame features without leaking postgame information.
3. Train and compare logistic regression, random forest, and gradient-boosted models.
4. Calibrate probabilities and evaluate accuracy, log loss, and Brier score.
5. Publish model version and validation results with every prediction.

## Important

Current live predictions use a clearly labeled spread-based baseline, not a trained ML model. Demo predictions are fictional examples. FieldIQ is not affiliated with or endorsed by the NFL.
