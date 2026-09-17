import { demoPredictions } from "../data/demoPredictions";
import {
  MatchupPayload,
  Prediction,
  PredictionPayload,
  SchedulePayload,
} from "../types";
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

export async function getSchedule(): Promise<SchedulePayload | null> {
  if (API_URL === undefined) {
    return null;
  }
  try {
    const response = await fetch(`${API_URL}/api/schedule`);
    if (!response.ok) {
      throw new Error(`FieldIQ API returned ${response.status}`);
    }
    return (await response.json()) as SchedulePayload;
  } catch {
    return null;
  }
}

export async function getMatchupHistory(
  teamOne: string,
  teamTwo: string,
): Promise<MatchupPayload | null> {
  if (API_URL === undefined) {
    return null;
  }
  try {
    const query = new URLSearchParams({ team1: teamOne, team2: teamTwo, limit: "5" });
    const response = await fetch(`${API_URL}/api/matchups?${query}`);
    if (!response.ok) {
      throw new Error(`FieldIQ API returned ${response.status}`);
    }
    return (await response.json()) as MatchupPayload;
  } catch {
    return null;
  }
}
