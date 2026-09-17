import { demoPredictions } from "../data/demoPredictions";
import { Prediction, PredictionPayload } from "../types";
import { Platform } from "react-native";

const configuredApiUrl = process.env.EXPO_PUBLIC_FIELD_IQ_API_URL?.replace(/\/$/, "");
const API_URL = configuredApiUrl ?? (Platform.OS === "web" ? "" : undefined);

export type PredictionResult = {
  predictions: Prediction[];
  source: "live" | "demo";
  season: number;
  week: number;
  model: string;
  asOf?: string;
};

export async function getPredictions(): Promise<PredictionResult> {
  if (API_URL === undefined) {
    return {
      predictions: demoPredictions,
      source: "demo",
      season: 2026,
      week: 2,
      model: "demo",
    };
  }

  try {
    const response = await fetch(`${API_URL}/api/predictions`);
    if (!response.ok) {
      throw new Error(`FieldIQ API returned ${response.status}`);
    }

    const data = (await response.json()) as PredictionPayload;
    if (!data.predictions.length) {
      throw new Error("No generated predictions are available");
    }
    return {
      predictions: data.predictions,
      source: "live",
      season: data.season,
      week: data.week,
      model: data.model,
      asOf: data.asOf,
    };
  } catch {
    return {
      predictions: demoPredictions,
      source: "demo",
      season: 2026,
      week: 2,
      model: "demo",
    };
  }
}
