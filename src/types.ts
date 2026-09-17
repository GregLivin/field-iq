export type Prediction = {
  id: string;
  awayTeam: string;
  awayAbbreviation: string;
  homeTeam: string;
  homeAbbreviation: string;
  kickoff: string;
  predictedWinner: string;
  homeWinProbability: number;
  awayWinProbability: number;
  confidence: "Low" | "Medium" | "High";
  factors: string[];
};

export type PredictionPayload = {
  season: number;
  week: number;
  asOf: string;
  provider: string;
  model: string;
  predictions: Prediction[];
};
