import { demoPredictions } from "../data/demoPredictions";
import { Prediction } from "../types";

const API_URL = process.env.EXPO_PUBLIC_FIELD_IQ_API_URL?.replace(/\/$/, "");

export async function getPredictions(
  season = 2026,
  week = 2,
): Promise<{ predictions: Prediction[]; source: "live" | "demo" }> {
  if (!API_URL) {
    return { predictions: demoPredictions, source: "demo" };
  }

  try {
    const response = await fetch(
      `${API_URL}/api/predictions?season=${season}&week=${week}`,
    );

    if (!response.ok) {
      throw new Error(`FieldIQ API returned ${response.status}`);
    }

    const data = (await response.json()) as { predictions: Prediction[] };
    return { predictions: data.predictions, source: "live" };
  } catch {
    return { predictions: demoPredictions, source: "demo" };
  }
}
