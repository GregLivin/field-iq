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
  projectedHomeScore?: number;
  projectedAwayScore?: number;
  projectedMargin?: number;
  projectedTotal?: number;
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

export type MatchupMeeting = {
  id: string;
  date: string;
  season: number;
  week: number;
  gameType: string;
  awayTeam: string;
  awayAbbreviation: string;
  awayScore: number | null;
  homeTeam: string;
  homeAbbreviation: string;
  homeScore: number | null;
  winner: string | null;
  winnerAbbreviation: string | null;
};

export type ScheduleGame = MatchupMeeting & {
  time: string | null;
  status: "upcoming" | "final";
  stadium: string | null;
  roof: string | null;
  surface: string | null;
  lastMeeting: MatchupMeeting | null;
};

export type SchedulePayload = {
  season: number;
  asOf: string;
  provider: string;
  weeks: number[];
  teams: string[];
  count: number;
  games: ScheduleGame[];
};

export type MatchupPayload = {
  asOf: string;
  provider: string;
  teams: string[];
  count: number;
  meetings: MatchupMeeting[];
  recentForm: Record<string, RecentTeamGame[]>;
};

export type RecentTeamGame = {
  id: string;
  date: string;
  season: number;
  week: number;
  gameType: string;
  teamAbbreviation: string;
  opponent: string;
  opponentAbbreviation: string;
  homeAway: "Home" | "Away";
  teamScore: number;
  opponentScore: number;
  result: "W" | "L" | "T";
  passingYards: number | null;
  rushingYards: number | null;
  totalYards: number | null;
  totalEpa: number | null;
  turnovers: number | null;
  defensiveSacks: number | null;
};
