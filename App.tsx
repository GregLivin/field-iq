import { StatusBar } from "expo-status-bar";
import * as ImagePicker from "expo-image-picker";
import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  Switch,
  useWindowDimensions,
  View,
} from "react-native";

import {
  getMatchupHistory,
  getPlayerStats,
  PlayerStatsPayload,
  getPredictions,
  getSchedule,
  sendTextAlertTest,
  analyzeMarketScreenshot,
  ExtractedMarket,
  saveManualGame,
  approveManualGame,
} from "./src/services/fieldIqApi";
import { MatchupMeeting, Prediction, RecentTeamGame, ScheduleGame, TeamSeasonSummary } from "./src/types";

const colors = {
  background: "#06100c",
  panel: "#0e1b16",
  panelRaised: "#14251d",
  green: "#53ed98",
  greenDark: "#153d29",
  text: "#f2fff7",
  muted: "#90a79b",
  border: "#20372c",
  gold: "#f5c15d",
};

type Tab = "picks" | "analyze" | "schedule" | "matchups" | "data";
type ConfidenceFilter = "ALL" | Prediction["confidence"];
type HistoryView = "overview" | "players" | "recent" | "headToHead";

function formatDate(date: string, includeYear = false) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    ...(includeYear ? { year: "numeric" as const } : {}),
  }).format(new Date(`${date}T12:00:00`));
}

function TeamBadge({ abbreviation }: { abbreviation: string }) {
  return (
    <View style={styles.badge}>
      <Text style={styles.badgeText}>{abbreviation}</Text>
    </View>
  );
}

function PredictionCard({
  prediction,
  lastMeeting,
  game,
  onHistory,
}: {
  prediction: Prediction;
  lastMeeting?: MatchupMeeting | null;
  game?: ScheduleGame;
  onHistory: (game: ScheduleGame) => void;
}) {
  const homeIsWinner = prediction.homeWinProbability >= prediction.awayWinProbability;
  const winnerProbability = Math.max(
    prediction.homeWinProbability,
    prediction.awayWinProbability,
  );
  return (
    <View style={styles.card}>
      <View style={styles.cardTop}>
        <View>
          <Text style={styles.nextGameLabel}>NEXT SCHEDULED GAME</Text>
          <Text style={styles.kickoff}>
            {game
              ? `${formatDate(game.date, true)}${game.time ? ` • ${game.time}` : ""}`
              : prediction.kickoff}
          </Text>
        </View>
        <View style={styles.confidencePill}>
          <Text style={styles.confidenceText}>{prediction.confidence} confidence</Text>
        </View>
      </View>
      <View style={styles.matchup}>
        <View style={styles.team}>
          <TeamBadge abbreviation={prediction.awayAbbreviation} />
          <Text style={styles.teamName}>{prediction.awayTeam}</Text>
          <Text style={!homeIsWinner ? styles.winnerProbability : styles.probability}>
            {prediction.awayWinProbability}%
          </Text>
        </View>
        <Text style={styles.at}>@</Text>
        <View style={styles.team}>
          <TeamBadge abbreviation={prediction.homeAbbreviation} />
          <Text style={styles.teamName}>{prediction.homeTeam}</Text>
          <Text style={homeIsWinner ? styles.winnerProbability : styles.probability}>
            {prediction.homeWinProbability}%
          </Text>
        </View>
      </View>
      <View
        accessibilityLabel={`${prediction.awayTeam} ${prediction.awayWinProbability} percent, ${prediction.homeTeam} ${prediction.homeWinProbability} percent`}
        style={styles.probabilityTrack}
      >
        <View
          style={[
            styles.awayProbabilityFill,
            { width: `${prediction.awayWinProbability}%` },
          ]}
        />
        <View
          style={[
            styles.homeProbabilityFill,
            { width: `${prediction.homeWinProbability}%` },
          ]}
        />
      </View>
      <View style={styles.pick}>
        <View>
          <Text style={styles.pickLabel}>FIELD IQ PICK</Text>
          <Text style={styles.pickWinner}>{prediction.predictedWinner}</Text>
        </View>
        <View style={styles.edgeBlock}>
          <Text style={styles.pickLabel}>WIN CHANCE</Text>
          <Text style={styles.edgeValue}>{winnerProbability}%</Text>
        </View>
      </View>
      <View style={styles.factorRow}>
        {prediction.factors.slice(0, 3).map((factor) => (
          <View key={factor} style={styles.factor}>
            <Text style={styles.factorText}>{factor}</Text>
          </View>
        ))}
      </View>
      <View style={styles.methodBlock}>
        <Text style={styles.methodLabel}>HOW THIS PICK WAS BUILT</Text>
        <Text style={styles.methodText}>
          Field IQ compared {prediction.factors.slice(0, 3).join(", ").toLowerCase()} across both teams. The model combined those signals with current team data to estimate a {prediction.homeWinProbability}% chance for {prediction.homeTeam} and {prediction.awayWinProbability}% for {prediction.awayTeam}.
        </Text>
      </View>
      {lastMeeting && (
        <View style={styles.predictionHistory}>
          <Text style={styles.predictionHistoryLabel}>LAST MEETING</Text>
          <Text style={styles.predictionHistoryValue}>
            {formatDate(lastMeeting.date, true)} • {lastMeeting.winnerAbbreviation ? `${lastMeeting.winnerAbbreviation} won` : "Tie game"}
          </Text>
          <Text style={styles.predictionHistoryScore}>
            {lastMeeting.awayAbbreviation} {lastMeeting.awayScore} — {lastMeeting.homeScore} {lastMeeting.homeAbbreviation}
          </Text>
        </View>
      )}
      {game && (
        <Pressable
          accessibilityLabel={`View previous ${prediction.awayTeam} and ${prediction.homeTeam} game statistics and outcomes`}
          accessibilityRole="button"
          onPress={() => onHistory(game)}
          style={({ pressed }) => [styles.previousGamesButton, pressed && styles.pressed]}
        >
          <Text style={styles.previousGamesButtonText}>Previous games, stats & outcomes</Text>
          <Text style={styles.previousGamesArrow}>→</Text>
        </Pressable>
      )}
    </View>
  );
}

function MeetingLine({ meeting }: { meeting: MatchupMeeting }) {
  return (
    <View style={styles.meetingLine}>
      <View>
        <Text style={styles.meetingDate}>
          {formatDate(meeting.date, true)} • {meeting.gameType}
        </Text>
        <Text style={styles.meetingTeams}>
          {meeting.awayAbbreviation} {meeting.awayScore} — {meeting.homeScore} {meeting.homeAbbreviation}
        </Text>
      </View>
      <View style={styles.winnerBlock}>
        <Text style={styles.winnerLabel}>WINNER</Text>
        <Text style={styles.winnerName}>{meeting.winnerAbbreviation ?? "TIE"}</Text>
      </View>
    </View>
  );
}

function RecentGameLine({ game }: { game: RecentTeamGame }) {
  const location = game.homeAway === "Home" ? "vs" : "at";
  const availableStats = [
    game.totalYards !== null ? `${Math.round(game.totalYards)} YDS` : null,
    game.totalEpa !== null ? `${game.totalEpa > 0 ? "+" : ""}${game.totalEpa.toFixed(1)} EPA` : null,
    game.turnovers !== null ? `${Math.round(game.turnovers)} TO` : null,
    game.defensiveSacks !== null ? `${game.defensiveSacks.toFixed(1)} SACKS` : null,
  ].filter(Boolean);

  return (
    <View style={styles.recentGameLine}>
      <View style={styles.recentGameTop}>
        <View style={styles.recentGameCopy}>
          <Text style={styles.meetingDate}>
            {formatDate(game.date, true)} • {game.gameType}
          </Text>
          <Text style={styles.recentOpponent}>
            {location} {game.opponentAbbreviation}
          </Text>
        </View>
        <View style={[styles.resultPill, game.result === "W" ? styles.winPill : styles.lossPill]}>
          <Text style={[styles.resultLetter, game.result === "W" ? styles.winText : styles.lossText]}>
            {game.result}
          </Text>
          <Text style={styles.recentScore}>{game.teamScore}–{game.opponentScore}</Text>
        </View>
      </View>
      {availableStats.length > 0 && (
        <Text style={styles.recentStats}>{availableStats.join("  •  ")}</Text>
      )}
    </View>
  );
}

function RecentTeamSection({
  team,
  games,
}: {
  team: string;
  games: RecentTeamGame[];
}) {
  return (
    <View style={styles.recentTeamSection}>
      <View style={styles.recentTeamHeader}>
        <TeamBadge abbreviation={team} />
        <View style={styles.recentTeamHeading}>
          <Text style={styles.recentTeamName}>{team} RECENT FORM</Text>
          <Text style={styles.recentTeamSubhead}>Last {games.length} completed games</Text>
        </View>
      </View>
      {games.map((game) => <RecentGameLine key={`${team}-${game.id}`} game={game} />)}
      {games.length === 0 && <Text style={styles.emptyCompact}>No recent games found.</Text>}
    </View>
  );
}

function ScheduleCard({
  game,
  showHistory,
  onHistory,
}: {
  game: ScheduleGame;
  showHistory: boolean;
  onHistory: (game: ScheduleGame) => void;
}) {
  const isFinal = game.status === "final";
  return (
    <View style={styles.scheduleCard}>
      <View style={styles.cardTop}>
        <View>
          <Text style={styles.gameWeek}>WEEK {game.week}</Text>
          <Text style={styles.gameDate}>
            {formatDate(game.date, true)}{game.time ? ` • ${game.time}` : ""}
          </Text>
        </View>
        <View style={isFinal ? styles.finalPill : styles.upcomingPill}>
          <Text style={isFinal ? styles.finalText : styles.upcomingText}>
            {isFinal ? "FINAL" : "UPCOMING"}
          </Text>
        </View>
      </View>

      <View style={styles.scheduleTeams}>
        <View style={styles.scheduleTeam}>
          <TeamBadge abbreviation={game.awayAbbreviation} />
          <Text style={styles.scheduleTeamName}>{game.awayTeam}</Text>
          {isFinal && <Text style={styles.score}>{game.awayScore}</Text>}
        </View>
        <Text style={styles.at}>{isFinal ? "—" : "@"}</Text>
        <View style={styles.scheduleTeam}>
          <TeamBadge abbreviation={game.homeAbbreviation} />
          <Text style={styles.scheduleTeamName}>{game.homeTeam}</Text>
          {isFinal && <Text style={styles.score}>{game.homeScore}</Text>}
        </View>
      </View>

      {game.stadium && <Text style={styles.venue}>{game.stadium}</Text>}

      {showHistory && (
        <View style={styles.lastMeeting}>
          <Text style={styles.lastMeetingLabel}>LAST MEETING</Text>
          {game.lastMeeting ? (
            <>
              <Text style={styles.lastMeetingResult}>
                {formatDate(game.lastMeeting.date, true)} • {game.lastMeeting.winnerAbbreviation} won
              </Text>
              <Text style={styles.lastMeetingScore}>
                {game.lastMeeting.awayAbbreviation} {game.lastMeeting.awayScore} — {game.lastMeeting.homeScore} {game.lastMeeting.homeAbbreviation}
              </Text>
            </>
          ) : (
            <Text style={styles.lastMeetingScore}>No recent meeting in the dataset</Text>
          )}
          <Pressable
            accessibilityRole="button"
            onPress={() => onHistory(game)}
            style={({ pressed }) => [styles.historyButton, pressed && styles.pressed]}
          >
            <Text style={styles.historyButtonText}>View matchup history</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}

function FilterChips({
  values,
  selected,
  onSelect,
}: {
  values: Array<string | number>;
  selected: string | number;
  onSelect: (value: string | number) => void;
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
      {values.map((value) => {
        const active = value === selected;
        return (
          <Pressable
            key={String(value)}
            onPress={() => onSelect(value)}
            style={[styles.chip, active && styles.chipActive]}
          >
            <Text style={[styles.chipText, active && styles.chipTextActive]}>{value}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

export default function App() {
  const { width } = useWindowDimensions();
  const compact = width < 700;
  const [activeTab, setActiveTab] = useState<Tab>("picks");
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [schedule, setSchedule] = useState<ScheduleGame[]>([]);
  const [weeks, setWeeks] = useState<number[]>([]);
  const [teams, setTeams] = useState<string[]>([]);
  const [source, setSource] = useState<"live" | "demo">("demo");
  const [season, setSeason] = useState(2026);
  const [week, setWeek] = useState(2);
  const [model, setModel] = useState("demo");
  const [selectedWeek, setSelectedWeek] = useState<string | number>(2);
  const [selectedTeam, setSelectedTeam] = useState<string | number>("ALL");
  const [selectedGame, setSelectedGame] = useState<ScheduleGame | null>(null);
  const [confidenceFilter, setConfidenceFilter] = useState<ConfidenceFilter>("ALL");
  const [history, setHistory] = useState<MatchupMeeting[]>([]);
  const [recentForm, setRecentForm] = useState<Record<string, RecentTeamGame[]>>({});
  const [seasonSummaries, setSeasonSummaries] = useState<Record<string, {current?: TeamSeasonSummary; previous?: TeamSeasonSummary}>>({});
  const [historyView, setHistoryView] = useState<HistoryView>("recent");
  const [historyLoading, setHistoryLoading] = useState(false);
  const [playerStats, setPlayerStats] = useState<Record<string, Record<number, PlayerStatsPayload | null>>>({});
  const [playerSeason, setPlayerSeason] = useState(2026);
  const [playerStatsErrors, setPlayerStatsErrors] = useState<Record<string, Record<number, string | null>>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [marketHome, setMarketHome] = useState("HOU");
  const [marketAway, setMarketAway] = useState("CIN");
  const [marketSpread, setMarketSpread] = useState("-2.5");
  const [marketTotal, setMarketTotal] = useState("45.5");
  const [screenshotUri, setScreenshotUri] = useState<string | null>(null);
  const [screenshotStatus, setScreenshotStatus] = useState("");
  const [manualStats, setManualStats] = useState("");
  const [manualSeason, setManualSeason] = useState("2026");
  const [manualWeek, setManualWeek] = useState("");
  const [manualTeam, setManualTeam] = useState("");
  const [manualOpponent, setManualOpponent] = useState("");
  const [manualDate, setManualDate] = useState("");
  const [manualHomeAway, setManualHomeAway] = useState<"home" | "away">("home");
  const [manualTeamScore, setManualTeamScore] = useState("");
  const [manualOpponentScore, setManualOpponentScore] = useState("");
  const [manualTraining, setManualTraining] = useState(false);
  const [manualStatus, setManualStatus] = useState("");
  const [manualSaving, setManualSaving] = useState(false);
  const [manualParsed, setManualParsed] = useState<any>(null);
  const [manualRecordId, setManualRecordId] = useState<string | null>(null);

  async function submitManualStats() {
    setManualSaving(true); setManualStatus("Validating pasted data…");
    try {
      const result = await saveManualGame({
        rawText: manualStats, season: Number(manualSeason), seasonType: "Regular season",
        week: manualWeek ? Number(manualWeek) : undefined, gameDate: manualDate || undefined,
        homeAway: manualHomeAway, teamScore: manualTeamScore ? Number(manualTeamScore) : undefined,
        opponentScore: manualOpponentScore ? Number(manualOpponentScore) : undefined, team: manualTeam || undefined,
        opponent: manualOpponent || undefined, includeInTraining: manualTraining,
      });
      setManualParsed(result.parsed ?? null);
      setManualRecordId(result.id);
      setManualStatus(`Saved as manual record ${result.id}. ${result.warnings.join(" ")}`);
      setManualStats("");
    } catch (error) {
      setManualStatus(error instanceof Error ? error.message : "Unable to save manual data.");
    } finally { setManualSaving(false); }
  }
  const [extractedMarkets, setExtractedMarkets] = useState<ExtractedMarket[]>([]);
  const [screenshotAnalyzing, setScreenshotAnalyzing] = useState(false);

  async function runScreenshotAnalysis() {
    if (!screenshotUri) return;
    setScreenshotAnalyzing(true); setScreenshotStatus("Reading matchup lines…");
    try {
      const result = await analyzeMarketScreenshot(screenshotUri);
      setExtractedMarkets(result.games);
      setScreenshotStatus(result.message ?? "Review the extracted lines below.");
    } catch (error) {
      setScreenshotStatus(error instanceof Error ? error.message : "Unable to analyze screenshot.");
    } finally { setScreenshotAnalyzing(false); }
  }

  function useExtractedMarket(game: ExtractedMarket) {
    setMarketAway(game.awayTeam);
    setMarketHome(game.homeTeam);
    if (game.homeSpread !== null && game.homeSpread !== undefined) setMarketSpread(String(game.homeSpread));
    if (game.total !== null && game.total !== undefined) setMarketTotal(String(game.total));
  }

  async function chooseMarketScreenshot() {
    setScreenshotStatus("");
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setScreenshotStatus("Photo access is required to select a screenshot.");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.9 });
    if (result.canceled || !result.assets[0]) return;
    setScreenshotUri(result.assets[0].uri);
    setScreenshotStatus("Screenshot selected. Automatic line extraction is ready for the vision API connection.");
  }
  const normalCdf = (x: number) => {
    const t = 1 / (1 + 0.2316419 * Math.abs(x));
    const d = 0.3989423 * Math.exp((-x * x) / 2);
    let p = 1 - d * t * (0.31938153 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))));
    if (x < 0) p = 1 - p;
    return p;
  };
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [phone, setPhone] = useState("");
  const [alertSending, setAlertSending] = useState(false);
  const [alertMessage, setAlertMessage] = useState("");
  const [alertPrefs, setAlertPrefs] = useState({
    gameReminders: true,
    predictionUpdates: true,
    highConfidence: true,
    finalResults: true,
  });

  async function enableTextAlerts() {
    setAlertSending(true);
    setAlertMessage("");
    const result = await sendTextAlertTest(phone, alertPrefs);
    setAlertMessage(result.message);
    setAlertSending(false);
  }

  async function loadData(isRefresh = false) {
    isRefresh ? setRefreshing(true) : setLoading(true);
    const [predictionResult, scheduleResult] = await Promise.all([
      getPredictions(),
      getSchedule(),
    ]);
    setPredictions(predictionResult.predictions);
    setSource(predictionResult.source);
    setSeason(scheduleResult?.season ?? predictionResult.season);
    setWeek(predictionResult.week);
    setModel(predictionResult.model);
    setSelectedWeek(predictionResult.week);
    if (scheduleResult) {
      setSchedule(scheduleResult.games);
      setWeeks(scheduleResult.weeks);
      setTeams(scheduleResult.teams);
    }
    setLoading(false);
    setRefreshing(false);
  }

  useEffect(() => {
    void loadData();
  }, []);

  const filteredSchedule = useMemo(
    () => schedule.filter((game) => {
      const matchesWeek = selectedWeek === "ALL" || game.week === selectedWeek;
      const matchesTeam = selectedTeam === "ALL" ||
        game.awayAbbreviation === selectedTeam || game.homeAbbreviation === selectedTeam;
      return matchesWeek && matchesTeam;
    }),
    [schedule, selectedTeam, selectedWeek],
  );

  const currentMatchups = useMemo(
    () => schedule.filter((game) => game.week === week),
    [schedule, week],
  );

  const predictionGames = useMemo(() => {
    const games = new Map<string, ScheduleGame>();
    [...schedule]
      .filter((game) => game.status === "upcoming")
      .sort((a, b) => `${a.date} ${a.time ?? ""}`.localeCompare(`${b.date} ${b.time ?? ""}`))
      .forEach((game) => {
        const key = [game.awayAbbreviation, game.homeAbbreviation].sort().join("-");
        if (!games.has(key)) games.set(key, game);
      });
    return games;
  }, [schedule]);

  const filteredPredictions = useMemo(
    () => predictions
      .filter((prediction) =>
        confidenceFilter === "ALL" || prediction.confidence === confidenceFilter)
      .sort((a, b) => {
        const aKey = [a.awayAbbreviation, a.homeAbbreviation].sort().join("-");
        const bKey = [b.awayAbbreviation, b.homeAbbreviation].sort().join("-");
        const aGame = predictionGames.get(aKey);
        const bGame = predictionGames.get(bKey);
        const aDate = aGame ? `${aGame.date} ${aGame.time ?? ""}` : "9999";
        const bDate = bGame ? `${bGame.date} ${bGame.time ?? ""}` : "9999";
        return aDate.localeCompare(bDate);
      }),
    [confidenceFilter, predictionGames, predictions],
  );

  const matchupHistory = useMemo(() => {
    const meetings = new Map<string, MatchupMeeting | null>();
    schedule.forEach((game) => {
      const key = [game.awayAbbreviation, game.homeAbbreviation].sort().join("-");
      if (!meetings.has(key) && game.lastMeeting) meetings.set(key, game.lastMeeting);
    });
    return meetings;
  }, [schedule]);

  const highConfidenceCount = useMemo(
    () => predictions.filter((prediction) => prediction.confidence === "High").length,
    [predictions],
  );

  async function openHistory(game: ScheduleGame) {
    setSelectedGame(game);
    setHistory([]);
    setRecentForm({});
    setHistoryView("overview");
    setHistoryLoading(true);
    setPlayerSeason(game.season);
    const [result, awayCurrent, homeCurrent, awayPrevious, homePrevious] = await Promise.all([
      getMatchupHistory(game.awayAbbreviation, game.homeAbbreviation),
      getPlayerStats(game.awayAbbreviation, game.season), getPlayerStats(game.homeAbbreviation, game.season),
      getPlayerStats(game.awayAbbreviation, game.season - 1), getPlayerStats(game.homeAbbreviation, game.season - 1),
    ]);
    setPlayerStats({
      [game.awayAbbreviation]: {[game.season]:awayCurrent.data,[game.season-1]:awayPrevious.data},
      [game.homeAbbreviation]: {[game.season]:homeCurrent.data,[game.season-1]:homePrevious.data},
    });
    setPlayerStatsErrors({
      [game.awayAbbreviation]: {[game.season]:awayCurrent.error,[game.season-1]:awayPrevious.error},
      [game.homeAbbreviation]: {[game.season]:homeCurrent.error,[game.season-1]:homePrevious.error},
    });
    setHistory(result?.meetings ?? []);
    setRecentForm(result?.recentForm ?? {});
    setSeasonSummaries(result?.seasonSummaries ?? {});
    setHistoryLoading(false);
  }

  const title = activeTab === "picks" ? "Predictions" : activeTab === "schedule" ? "NFL Schedule" : "Matchup History";

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" />
      <View style={styles.shell}>
        <View style={styles.header}>
          <View>
            <Text style={styles.brand}>Field IQ</Text>
            <Text style={styles.subtitle}>Let intelligence guide the chance.</Text>
          </View>
          <View style={styles.headerActions}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Set up Field IQ text alerts"
              onPress={() => setAlertsOpen(true)}
              style={({ pressed }) => [styles.alertButton, pressed && styles.pressed]}
            >
              <Text style={styles.alertButtonText}>🔔 Alerts</Text>
            </Pressable>
            <View style={styles.weekPill}>
              <Text style={styles.weekText}>NFL {season} • W{week}</Text>
            </View>
          </View>
        </View>

        <ScrollView
          style={styles.scroller}
          contentContainerStyle={styles.container}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={() => void loadData(true)} tintColor={colors.green} />
          }
        >
          {activeTab === "analyze" && (
            <>
              <View style={styles.screenIntro}>
                <Text style={styles.eyebrow}>FIELD IQ MARKET ANALYZER</Text>
                <Text style={styles.screenTitle}>Compare the setup</Text>
                <Text style={styles.heroBody}>
                  Enter the matchup, spread, and total. Field IQ compares those numbers with its model probabilities. This is model analysis, not a guarantee of an outcome.
                </Text>
              </View>
              <View style={styles.marketCard}>
                <Text style={styles.filterLabel}>MATCHUP</Text>
                <View style={styles.marketRow}>
                  <TextInput value={marketAway} onChangeText={setMarketAway} autoCapitalize="characters" placeholder="AWAY" placeholderTextColor={colors.muted} style={styles.marketInput} />
                  <Text style={styles.at}>@</Text>
                  <TextInput value={marketHome} onChangeText={setMarketHome} autoCapitalize="characters" placeholder="HOME" placeholderTextColor={colors.muted} style={styles.marketInput} />
                </View>
                <View style={styles.marketRow}>
                  <View style={styles.marketField}><Text style={styles.filterLabel}>HOME SPREAD</Text><TextInput value={marketSpread} onChangeText={setMarketSpread} keyboardType="numbers-and-punctuation" style={styles.marketInputWide} /></View>
                  <View style={styles.marketField}><Text style={styles.filterLabel}>TOTAL</Text><TextInput value={marketTotal} onChangeText={setMarketTotal} keyboardType="decimal-pad" style={styles.marketInputWide} /></View>
                </View>
                {(() => {
                  const prediction = predictions.find((item) =>
                    item.homeAbbreviation === marketHome.trim().toUpperCase() &&
                    item.awayAbbreviation === marketAway.trim().toUpperCase());
                  if (!prediction) return <Text style={styles.marketHint}>Choose a matchup available in the current Field IQ prediction set.</Text>;
                  const homeProbability = prediction.homeWinProbability;
                  const impliedMargin = Math.round(((homeProbability - 50) / 5) * 10) / 10;
                  const enteredSpread = Number(marketSpread);
                  return (
                    <View style={styles.analysisPanel}>
                      <Text style={styles.pickLabel}>FIELD IQ MODEL VIEW</Text>
                      <Text style={styles.analysisWinner}>{prediction.predictedWinner}</Text>
                      <Text style={styles.analysisLine}>{prediction.homeAbbreviation} win probability: {homeProbability}%</Text>
                      <Text style={styles.analysisLine}>{prediction.awayAbbreviation} win probability: {prediction.awayWinProbability}%</Text>
                      {prediction.projectedHomeScore !== undefined && prediction.projectedAwayScore !== undefined && (
                        <Text style={styles.analysisLine}>Projected score: {prediction.awayAbbreviation} {prediction.projectedAwayScore} – {prediction.homeAbbreviation} {prediction.projectedHomeScore}</Text>
                      )}
                      {prediction.projectedMargin !== undefined && <Text style={styles.analysisLine}>Projected home margin: {prediction.projectedMargin > 0 ? "+" : ""}{prediction.projectedMargin}</Text>}
                      {prediction.projectedTotal !== undefined && <Text style={styles.analysisLine}>Projected total: {prediction.projectedTotal}</Text>}
                      <Text style={styles.analysisLine}>Market setup: {prediction.homeAbbreviation} {Number.isFinite(enteredSpread) ? (enteredSpread > 0 ? "+" : "") + enteredSpread : "—"} • Total {marketTotal || "—"}</Text>
                      {prediction.projectedMargin !== undefined && Number.isFinite(enteredSpread) && (() => {
                        const residualSd = 13.5;
                        const cover = Math.round((1 - normalCdf((-enteredSpread - prediction.projectedMargin) / residualSd)) * 100);
                        return <Text style={styles.analysisLine}>Estimated cover probability: {prediction.homeAbbreviation} {cover}% • {prediction.awayAbbreviation} {100-cover}%</Text>;
                      })()}
                      {prediction.projectedTotal !== undefined && Number.isFinite(Number(marketTotal)) && (() => {
                        const residualSd = 14.0;
                        const over = Math.round((1 - normalCdf((Number(marketTotal) - prediction.projectedTotal) / residualSd)) * 100);
                        return <Text style={styles.analysisLine}>Estimated total probability: Over {over}% • Under {100-over}%</Text>;
                      })()}
                      <Text style={styles.marketHint}>{prediction.projectedTotal !== undefined ? "Score, margin, and total are generated by Field IQ regression models. Cover and O/U percentages are uncertainty estimates and are not guarantees." : "Run the v3 ML pipeline to generate score, margin, and total projections."}</Text>
                    </View>
                  );
                })()}
              </View>
              <View style={styles.marketCard}>
                <Text style={styles.eyebrow}>SCREENSHOT ANALYZER</Text>
                <Text style={styles.sectionTitle}>Import the setup</Text>
                <Text style={styles.heroBody}>Choose a sportsbook-style screenshot. Field IQ will use it to identify matchup lines and prepare them for model comparison.</Text>
                <Pressable onPress={() => void chooseMarketScreenshot()} style={({pressed}) => [styles.screenshotButton, pressed && styles.pressed]}>
                  <Text style={styles.screenshotButtonText}>{screenshotUri ? "Choose another screenshot" : "Choose screenshot"}</Text>
                </Pressable>
                {screenshotUri ? <Text style={styles.alertStatus}>✓ Screenshot loaded</Text> : null}
                {screenshotUri ? <Pressable disabled={screenshotAnalyzing} onPress={() => void runScreenshotAnalysis()} style={({pressed}) => [styles.secondaryMarketButton, pressed && styles.pressed]}><Text style={styles.secondaryMarketButtonText}>{screenshotAnalyzing ? "Analyzing…" : "Read matchup lines"}</Text></Pressable> : null}
                {extractedMarkets.map((game, index) => (
                  <Pressable key={`${game.awayTeam}-${game.homeTeam}-${index}`} onPress={() => useExtractedMarket(game)} style={styles.extractedGame}>
                    <Text style={styles.analysisLine}>{game.awayTeam} {game.awaySpread ?? "—"} @ {game.homeTeam} {game.homeSpread ?? "—"}</Text>
                    <Text style={styles.marketHint}>Total {game.total ?? "—"} • ML {game.awayMoneyline ?? "—"} / {game.homeMoneyline ?? "—"} • Tap to load</Text>
                  </Pressable>
                ))}
                {screenshotStatus ? <Text style={styles.marketHint}>{screenshotStatus}</Text> : null}
                <Text style={styles.marketHint}>Field IQ does not place wagers. Extracted lines will be shown for review before analysis.</Text>
              </View>
            </>
          )}

          {activeTab === "data" && (
            <>
              <View style={styles.screenIntro}>
                <Text style={styles.eyebrow}>FIELD IQ DATA CENTER</Text>
                <Text style={styles.screenTitle}>Add missing game data</Text>
                <Text style={styles.heroBody}>Paste a full NFL game stats page, identify the game, review what Field IQ parsed, then approve it before it can be used for model training.</Text>
              </View>
              <View style={styles.marketCard}>
                <Text style={styles.filterLabel}>GAME IDENTITY</Text>
                <View style={styles.marketRow}>
                  <TextInput value={manualSeason} onChangeText={setManualSeason} keyboardType="number-pad" placeholder="Season" placeholderTextColor={colors.muted} style={styles.marketInput} />
                  <TextInput value={manualWeek} onChangeText={setManualWeek} keyboardType="number-pad" placeholder="Week" placeholderTextColor={colors.muted} style={styles.marketInput} />
                </View>
                <View style={styles.marketRow}>
                  <TextInput value={manualTeam} onChangeText={setManualTeam} autoCapitalize="characters" placeholder="Team (ATL)" placeholderTextColor={colors.muted} style={styles.marketInput} />
                  <TextInput value={manualOpponent} onChangeText={setManualOpponent} autoCapitalize="characters" placeholder="Opponent" placeholderTextColor={colors.muted} style={styles.marketInput} />
                </View>
                <View style={styles.marketRow}>
                  <TextInput value={manualDate} onChangeText={setManualDate} placeholder="YYYY-MM-DD" placeholderTextColor={colors.muted} style={styles.marketInput} />
                  <Pressable onPress={() => setManualHomeAway(manualHomeAway === "home" ? "away" : "home")} style={styles.marketInput}>
                    <Text style={styles.analysisLine}>Team is {manualHomeAway.toUpperCase()}</Text>
                  </Pressable>
                </View>
                <View style={styles.marketRow}>
                  <TextInput value={manualTeamScore} onChangeText={setManualTeamScore} keyboardType="number-pad" placeholder="Team score" placeholderTextColor={colors.muted} style={styles.marketInput} />
                  <TextInput value={manualOpponentScore} onChangeText={setManualOpponentScore} keyboardType="number-pad" placeholder="Opponent score" placeholderTextColor={colors.muted} style={styles.marketInput} />
                </View>
                <Text style={styles.filterLabel}>PASTE RAW GAME STATS</Text>
                <TextInput value={manualStats} onChangeText={setManualStats} multiline textAlignVertical="top" placeholder="Paste the complete stats page here…" placeholderTextColor={colors.muted} style={styles.manualPasteBox} />
                <Pressable
                  disabled={manualSaving || manualStats.trim().length < 40 || !manualWeek || !manualDate || !manualTeam || !manualOpponent || !manualTeamScore || !manualOpponentScore}
                  onPress={() => void submitManualStats()}
                  style={({pressed}) => [styles.screenshotButton, (manualSaving || manualStats.trim().length < 40 || !manualWeek || !manualDate || !manualTeam || !manualOpponent || !manualTeamScore || !manualOpponentScore) && {opacity: 0.45}, pressed && styles.pressed]}
                >
                  <Text style={styles.screenshotButtonText}>{manualSaving ? "Saving…" : "Parse & save for review"}</Text>
                </Pressable>
                {manualStatus ? <Text style={styles.marketHint}>{manualStatus}</Text> : null}
              </View>
              {manualParsed && (
                <View style={styles.marketCard}>
                  <Text style={styles.eyebrow}>PARSE REVIEW</Text>
                  <Text style={styles.sectionTitle}>{manualParsed.unparsed ? "Needs attention" : "Data recognized"}</Text>
                  <Text style={styles.marketHint}>Detected format: {manualParsed.format ?? "team_site"} • Scope: {manualParsed.sourceScope ?? "game"}</Text>
                  <Text style={styles.marketHint}>Team stat fields: {Object.keys(manualParsed.teamStats ?? {}).length} • Player records: {Object.values(manualParsed.players ?? {}).reduce((total: number, rows: any) => total + (Array.isArray(rows) ? rows.length : 0), 0)}</Text>
                  {(manualParsed.warnings ?? []).map((warning: string, index: number) => <Text key={index} style={styles.marketHint}>⚠ {warning}</Text>)}
                  {manualRecordId && !manualParsed.unparsed ? (
                    <Pressable onPress={async () => {
                      try {
                        const result = await approveManualGame(manualRecordId, true);
                        setManualStatus(result.approvedForTraining ? "Approved for ML training." : "Saved, but not approved for training.");
                      } catch (error) {
                        setManualStatus(error instanceof Error ? error.message : "Unable to approve manual data.");
                      }
                    }} style={styles.secondaryMarketButton}>
                      <Text style={styles.secondaryMarketButtonText}>Approve for ML training</Text>
                    </Pressable>
                  ) : null}
                </View>
              )}
            </>
          )}

          {activeTab === "picks" && (
            <>
              <View style={[styles.hero, compact && styles.heroCompact]}>
                <View style={styles.heroHeadingRow}>
                  <View style={styles.heroCopy}>
                    <Text style={styles.eyebrow}>FIELD IQ MODEL CENTER</Text>
                    <Text style={[styles.heroTitle, compact && styles.heroTitleCompact]}>Let intelligence guide the chance.</Text>
                  </View>
                  {!compact && (
                    <View style={styles.modelMark}>
                      <Text style={styles.modelMarkText}>IQ</Text>
                    </View>
                  )}
                </View>
                <Text style={styles.heroBody}>
                  Multiple prediction models analyze daily NFL data such as team form, player availability, injuries, weather, efficiency, and matchup history. These models turn the data into clear win probabilities.
                </Text>
                <View style={styles.modelSummary}>
                  <View style={styles.summaryItem}>
                    <Text style={styles.summaryValue}>{predictions.length}</Text>
                    <Text style={styles.summaryLabel}>GAME PICKS</Text>
                  </View>
                  <View style={styles.summaryDivider} />
                  <View style={styles.summaryItem}>
                    <Text style={styles.summaryValue}>{highConfidenceCount}</Text>
                    <Text style={styles.summaryLabel}>HIGH CONFIDENCE</Text>
                  </View>
                  <View style={styles.summaryDivider} />
                  <View style={styles.summaryItem}>
                    <View style={styles.sourceInline}>
                      <View style={source === "live" ? styles.liveDot : styles.demoDot} />
                      <Text style={styles.summaryValueSmall}>{source === "live" ? "LIVE" : "DEMO"}</Text>
                    </View>
                    <Text style={styles.summaryLabel}>{source === "live" ? model : "MODEL DATA"}</Text>
                  </View>
                </View>
              </View>
              <View style={styles.resultsRow}>
                <Text style={styles.sectionTitle}>{title}</Text>
                <Text style={styles.resultCount}>{filteredPredictions.length} games</Text>
              </View>
              <FilterChips
                values={["ALL", "High", "Medium", "Low"]}
                selected={confidenceFilter}
                onSelect={(value) => setConfidenceFilter(value as ConfidenceFilter)}
              />
              {loading ? <ActivityIndicator color={colors.green} size="large" style={styles.loader} /> :
                filteredPredictions.map((prediction) => {
                  const key = [prediction.awayAbbreviation, prediction.homeAbbreviation].sort().join("-");
                  const game = predictionGames.get(key);
                  return (
                    <PredictionCard
                      key={prediction.id}
                      prediction={prediction}
                      lastMeeting={matchupHistory.get(key)}
                      game={game}
                      onHistory={openHistory}
                    />
                  );
                })}
              {!loading && filteredPredictions.length === 0 && (
                <Text style={styles.empty}>No predictions match this confidence level.</Text>
              )}
            </>
          )}

          {activeTab === "schedule" && (
            <>
              <View style={styles.screenIntro}>
                <Text style={styles.eyebrow}>ALL 32 TEAMS</Text>
                <Text style={styles.screenTitle}>Season schedule</Text>
                <Text style={styles.heroBody}>Filter every game by week or team. Pull down anytime to refresh.</Text>
              </View>
              <Text style={styles.filterLabel}>WEEK</Text>
              <FilterChips values={["ALL", ...weeks]} selected={selectedWeek} onSelect={setSelectedWeek} />
              <Text style={styles.filterLabel}>TEAM</Text>
              <FilterChips values={["ALL", ...teams]} selected={selectedTeam} onSelect={setSelectedTeam} />
              <View style={styles.resultsRow}>
                <Text style={styles.sectionTitle}>{title}</Text>
                <Text style={styles.resultCount}>{filteredSchedule.length} games</Text>
              </View>
              {loading ? <ActivityIndicator color={colors.green} size="large" style={styles.loader} /> :
                filteredSchedule.map((game) => (
                  <ScheduleCard key={game.id} game={game} showHistory={false} onHistory={openHistory} />
                ))}
              {!loading && filteredSchedule.length === 0 && <Text style={styles.empty}>No games match these filters.</Text>}
            </>
          )}

          {activeTab === "matchups" && (
            <>
              <View style={styles.screenIntro}>
                <Text style={styles.eyebrow}>HEAD TO HEAD</Text>
                <Text style={styles.screenTitle}>Know the history</Text>
                <Text style={styles.heroBody}>See who won the last meeting, when it happened, and the previous five results.</Text>
              </View>
              <View style={styles.resultsRow}>
                <Text style={styles.sectionTitle}>Week {week} matchups</Text>
                <Text style={styles.resultCount}>{currentMatchups.length} games</Text>
              </View>
              {loading ? <ActivityIndicator color={colors.green} size="large" style={styles.loader} /> :
                currentMatchups.map((game) => (
                  <ScheduleCard key={game.id} game={game} showHistory onHistory={openHistory} />
                ))}
            </>
          )}

          <Text style={styles.disclaimer}>
            Predictions are estimates, not guarantees. Field IQ is not affiliated with or endorsed by the NFL.
          </Text>
        </ScrollView>

        <View style={styles.bottomNav}>
          {(["picks", "analyze", "data", "schedule", "matchups"] as Tab[]).map((tab) => (
            <Pressable
              accessibilityRole="button"
              key={tab}
              onPress={() => setActiveTab(tab)}
              style={[styles.navItem, activeTab === tab && styles.navItemActive]}
            >
              <Text style={[styles.navIcon, activeTab === tab && styles.navTextActive]}>
                {tab === "picks" ? "◎" : tab === "analyze" ? "⌁" : tab === "data" ? "≡" : tab === "schedule" ? "▦" : "↔"}
              </Text>
              <Text style={[styles.navText, activeTab === tab && styles.navTextActive]}>{tab}</Text>
            </Pressable>
          ))}
        </View>
      </View>

      <Modal visible={alertsOpen} transparent animationType="slide" onRequestClose={() => setAlertsOpen(false)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setAlertsOpen(false)}>
          <Pressable style={styles.alertSheet} onPress={(event) => event.stopPropagation()}>
            <View style={styles.modalHandle} />
            <View style={styles.modalHeader}>
              <View style={styles.alertTitleWrap}>
                <Text style={styles.eyebrow}>FIELD IQ TEXT ALERTS</Text>
                <Text style={styles.modalTitle}>Stay ahead of kickoff</Text>
              </View>
              <Pressable onPress={() => setAlertsOpen(false)} style={styles.closeButton}>
                <Text style={styles.closeText}>×</Text>
              </Pressable>
            </View>
            <Text style={styles.alertIntro}>
              Choose the NFL updates you want Field IQ to send. Message and data rates may apply.
            </Text>
            <TextInput
              accessibilityLabel="Mobile phone number"
              keyboardType="phone-pad"
              onChangeText={setPhone}
              placeholder="+17135551234"
              placeholderTextColor={colors.muted}
              style={styles.phoneInput}
              value={phone}
            />
            {([
              ["gameReminders", "Game reminders"],
              ["predictionUpdates", "Prediction updates"],
              ["highConfidence", "High-confidence alerts"],
              ["finalResults", "Final results"],
            ] as const).map(([key, label]) => (
              <View key={key} style={styles.alertOption}>
                <Text style={styles.alertOptionText}>{label}</Text>
                <Switch
                  value={alertPrefs[key]}
                  onValueChange={(value) => setAlertPrefs((current) => ({ ...current, [key]: value }))}
                />
              </View>
            ))}
            <Text style={styles.consentText}>
              By enabling alerts, you agree to receive automated Field IQ texts at this number. Consent is not a condition of purchase. Reply STOP to opt out.
            </Text>
            {alertMessage ? <Text style={styles.alertStatus}>{alertMessage}</Text> : null}
            <Pressable
              accessibilityRole="button"
              disabled={alertSending || !phone.trim()}
              onPress={() => void enableTextAlerts()}
              style={({ pressed }) => [styles.enableAlertsButton, (pressed || alertSending || !phone.trim()) && styles.pressed]}
            >
              <Text style={styles.enableAlertsButtonText}>{alertSending ? "Sending…" : "Enable & send test text"}</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>

      <Modal visible={selectedGame !== null} transparent animationType="slide" onRequestClose={() => setSelectedGame(null)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setSelectedGame(null)}>
          <Pressable style={styles.modalSheet} onPress={(event) => event.stopPropagation()}>
            <View style={styles.modalHandle} />
            <View style={styles.modalHeader}>
              <View>
                <Text style={styles.eyebrow}>
                  {selectedGame ? `${selectedGame.season - 1}–${selectedGame.season} GAME DATA` : "RECENT GAME DATA"}
                </Text>
                <Text style={styles.modalTitle}>
                  {selectedGame?.awayAbbreviation} vs {selectedGame?.homeAbbreviation}
                </Text>
              </View>
              <Pressable onPress={() => setSelectedGame(null)} style={styles.closeButton}>
                <Text style={styles.closeText}>×</Text>
              </Pressable>
            </View>
            <View style={styles.historyTabs}>
              <Pressable accessibilityRole="button" onPress={() => setHistoryView("overview")} style={[styles.historyTab, historyView === "overview" && styles.historyTabActive]}><Text style={[styles.historyTabText, historyView === "overview" && styles.historyTabTextActive]}>Overview</Text></Pressable>
              <Pressable accessibilityRole="button" onPress={() => setHistoryView("players")} style={[styles.historyTab, historyView === "players" && styles.historyTabActive]}><Text style={[styles.historyTabText, historyView === "players" && styles.historyTabTextActive]}>Player stats</Text></Pressable>
              <Pressable
                accessibilityRole="button"
                onPress={() => setHistoryView("recent")}
                style={[styles.historyTab, historyView === "recent" && styles.historyTabActive]}
              >
                <Text style={[styles.historyTabText, historyView === "recent" && styles.historyTabTextActive]}>
                  Recent form
                </Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                onPress={() => setHistoryView("headToHead")}
                style={[styles.historyTab, historyView === "headToHead" && styles.historyTabActive]}
              >
                <Text style={[styles.historyTabText, historyView === "headToHead" && styles.historyTabTextActive]}>
                  Head to head
                </Text>
              </Pressable>
            </View>
            <ScrollView style={styles.modalList}>
              {historyLoading ? (
                <ActivityIndicator color={colors.green} size="large" style={styles.loader} />
              ) : historyView === "overview" ? (
                <>
                  {selectedGame && [selectedGame.awayAbbreviation, selectedGame.homeAbbreviation].map((team) => { const cur=seasonSummaries[team]?.current; const prev=seasonSummaries[team]?.previous; return <View key={team} style={styles.recentTeamSection}><View style={styles.recentTeamHeader}><TeamBadge abbreviation={team}/><View style={styles.recentTeamHeading}><Text style={styles.recentTeamName}>{team} TEAM HISTORY</Text><Text style={styles.recentTeamSubhead}>Current season + prior-season baseline</Text></View></View>{cur && <Text style={styles.analysisLine}>{cur.season}: {cur.wins}-{cur.losses}{cur.ties ? "-" + cur.ties : ""} • Diff {cur.pointDifferential > 0 ? "+" : ""}{cur.pointDifferential}</Text>}{prev && <Text style={styles.analysisLine}>{prev.season}: {prev.wins}-{prev.losses}{prev.ties ? "-" + prev.ties : ""} • PF {prev.pointsFor} • PA {prev.pointsAgainst} • Diff {prev.pointDifferential > 0 ? "+" : ""}{prev.pointDifferential}</Text>}</View>})}
                  <Text style={styles.modalNote}>Prior-season history stays separate from current form. Recent games, team stats, head-to-head history, and the Field IQ prediction are generated together for matchup intelligence.</Text>
                </>
              ) : historyView === "players" ? (
                <>
                  <FilterChips values={[selectedGame?.season ?? 2026, (selectedGame?.season ?? 2026)-1]} selected={playerSeason} onSelect={(v)=>setPlayerSeason(Number(v))}/>
                  {selectedGame && [selectedGame.awayAbbreviation, selectedGame.homeAbbreviation].map((team)=>{const data=playerStats[team]?.[playerSeason]; const apiError=playerStatsErrors[team]?.[playerSeason]; const seasonLabel=data?.scope === "season_to_date" ? `Season to date (${playerSeason})` : data?.scope === "full_season" ? `Full season (${playerSeason})` : `Season ${playerSeason}`; return <View key={team} style={styles.recentTeamSection}><View style={styles.recentTeamHeader}><TeamBadge abbreviation={team}/><View style={styles.recentTeamHeading}><Text style={styles.recentTeamName}>{team} • {playerSeason} PLAYER LEADERS</Text><Text style={styles.recentTeamSubhead}>{seasonLabel}</Text></View></View>{apiError ? <Text style={styles.playerApiError}>Player data unavailable: {apiError}</Text> : (["passing","rushing","receiving","defense","kicking"] as const).map((kind)=>{const rows=data?.leaders[kind] ?? []; return <View key={kind} style={{marginTop:10}}><Text style={styles.pickLabel}>{kind.toUpperCase()}</Text>{rows.slice(0,5).map((p,idx)=><Text key={p.playerId+"-"+kind+"-"+idx} style={styles.analysisLine}>{p.playerName} • {p.position || "—"} • {kind==="passing" ? `${Math.round(p.passingYards ?? 0)} YDS • ${Math.round(p.passingTds ?? 0)} TD • ${Math.round(p.interceptions ?? 0)} INT` : kind==="rushing" ? `${Math.round(p.rushingYards ?? 0)} YDS • ${Math.round(p.carries ?? 0)} ATT • ${Math.round(p.rushingTds ?? 0)} TD` : kind==="receiving" ? `${Math.round(p.receivingYards ?? 0)} YDS • ${Math.round(p.receptions ?? 0)} REC • ${Math.round(p.receivingTds ?? 0)} TD` : kind==="defense" ? `${Math.round(p.defTacklesSolo ?? 0)} SOLO • ${Math.round(p.defSacks ?? 0)} SACK • ${Math.round(p.defInterceptions ?? 0)} INT` : `${Math.round(p.fgMade ?? 0)}/${Math.round(p.fgAtt ?? 0)} FG • ${Math.round(p.patMade ?? 0)}/${Math.round(p.patAtt ?? 0)} XP`}</Text>)}{!rows.length && <Text style={styles.emptyCompact}>No {kind} leaders recorded for {playerSeason}.</Text>}</View>})}</View>})}
                  <Text style={styles.modalNote}>2026 uses season-to-date player production. 2025 is retained as prior-season context. Pregame ML features continue to use only information available before kickoff.</Text>
                </>
              ) : historyView === "recent" ? (
                <>
                  {selectedGame && (
                    <RecentTeamSection
                      team={selectedGame.awayAbbreviation}
                      games={recentForm[selectedGame.awayAbbreviation] ?? []}
                    />
                  )}
                  {selectedGame && (
                    <RecentTeamSection
                      team={selectedGame.homeAbbreviation}
                      games={recentForm[selectedGame.homeAbbreviation] ?? []}
                    />
                  )}
                </>
              ) : (
                <>
                  {history.map((meeting) => <MeetingLine key={meeting.id} meeting={meeting} />)}
                  {history.length === 0 && <Text style={styles.empty}>No completed meetings found.</Text>}
                </>
              )}
            </ScrollView>
            <Text style={styles.modalNote}>
              {historyView === "overview" ? "Season records are generated from completed games only." : historyView === "players" ? "Player statistics come from the automated player coverage layer; official NFL references remain a separate validation layer." : historyView === "recent" ? "Completed games and weekly team statistics from the Field IQ dataset." : "Previous regular season and playoff meetings between these teams."}
            </Text>
          </Pressable>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.background },
  shell: { flex: 1, width: "100%", maxWidth: 1080, alignSelf: "center" },
  scroller: { flex: 1 },
  container: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 32 },
  header: { alignItems: "center", flexDirection: "row", justifyContent: "space-between", paddingHorizontal: 18, paddingVertical: 14 },
  brand: { color: colors.green, fontSize: 23, fontWeight: "900", letterSpacing: 1.5 },
  subtitle: { color: colors.muted, fontSize: 11, fontWeight: "600", marginTop: 2 },
  headerActions: { alignItems: "center", flexDirection: "row", gap: 8 },
  alertButton: { backgroundColor: colors.panelRaised, borderColor: "#2f6f4c", borderRadius: 18, borderWidth: 1, paddingHorizontal: 11, paddingVertical: 7 },
  alertButtonText: { color: colors.green, fontSize: 11, fontWeight: "900" },
  weekPill: { backgroundColor: colors.greenDark, borderColor: "#286945", borderRadius: 18, borderWidth: 1, paddingHorizontal: 11, paddingVertical: 7 },
  weekText: { color: colors.green, fontSize: 11, fontWeight: "800" },
  hero: { backgroundColor: colors.panelRaised, borderColor: "#27523d", borderRadius: 24, borderWidth: 1, marginBottom: 21, padding: 24 },
  heroCompact: { borderRadius: 20, padding: 18 },
  heroHeadingRow: { alignItems: "flex-start", flexDirection: "row", justifyContent: "space-between" },
  heroCopy: { flex: 1 },
  modelMark: { alignItems: "center", backgroundColor: colors.greenDark, borderColor: "#347957", borderRadius: 24, borderWidth: 1, height: 48, justifyContent: "center", marginLeft: 24, width: 48 },
  modelMarkText: { color: colors.green, fontSize: 14, fontWeight: "900", letterSpacing: 1 },
  eyebrow: { color: colors.green, fontSize: 11, fontWeight: "900", letterSpacing: 1.4, marginBottom: 8 },
  heroTitle: { color: colors.text, fontSize: 30, fontWeight: "900", lineHeight: 35, marginBottom: 10, maxWidth: 620 },
  heroTitleCompact: { fontSize: 25, lineHeight: 30 },
  heroBody: { color: "#acc2b6", fontSize: 14, lineHeight: 21, maxWidth: 760 },
  modelSummary: { alignItems: "stretch", backgroundColor: "#0b1712", borderColor: colors.border, borderRadius: 16, borderWidth: 1, flexDirection: "row", marginTop: 18, paddingHorizontal: 8, paddingVertical: 12 },
  summaryItem: { alignItems: "center", flex: 1, justifyContent: "center", minWidth: 0 },
  summaryDivider: { alignSelf: "stretch", backgroundColor: colors.border, width: 1 },
  summaryValue: { color: colors.text, fontSize: 18, fontWeight: "900" },
  summaryValueSmall: { color: colors.text, fontSize: 12, fontWeight: "900" },
  summaryLabel: { color: colors.muted, fontSize: 8, fontWeight: "900", letterSpacing: 0.7, marginTop: 4, textAlign: "center" },
  sourceInline: { alignItems: "center", flexDirection: "row" },
  liveDot: { backgroundColor: colors.green, borderRadius: 5, height: 9, marginRight: 8, width: 9 },
  demoDot: { backgroundColor: colors.gold, borderRadius: 5, height: 9, marginRight: 8, width: 9 },
  screenIntro: { marginBottom: 22, paddingTop: 8 },
  screenTitle: { color: colors.text, fontSize: 28, fontWeight: "900", marginBottom: 7 },
  sectionTitle: { color: colors.text, fontSize: 21, fontWeight: "800", marginBottom: 12 },
  resultsRow: { alignItems: "baseline", flexDirection: "row", justifyContent: "space-between", marginTop: 10 },
  resultCount: { color: colors.muted, fontSize: 12, fontWeight: "700" },
  loader: { marginVertical: 42 },
  card: { backgroundColor: colors.panel, borderColor: colors.border, borderRadius: 22, borderWidth: 1, marginBottom: 16, padding: 17 },
  cardTop: { alignItems: "center", flexDirection: "row", justifyContent: "space-between", marginBottom: 17 },
  nextGameLabel: { color: colors.green, fontSize: 8, fontWeight: "900", letterSpacing: 1 },
  kickoff: { color: colors.text, fontSize: 12, fontWeight: "800", marginTop: 4 },
  confidencePill: { backgroundColor: colors.greenDark, borderRadius: 15, paddingHorizontal: 10, paddingVertical: 6 },
  confidenceText: { color: colors.green, fontSize: 10, fontWeight: "800" },
  matchup: { alignItems: "center", flexDirection: "row", justifyContent: "space-between" },
  team: { alignItems: "center", flex: 1, minWidth: 0 },
  badge: { alignItems: "center", backgroundColor: colors.panelRaised, borderColor: "#2b4d3c", borderRadius: 22, borderWidth: 1, height: 45, justifyContent: "center", width: 58 },
  badgeText: { color: colors.text, fontSize: 13, fontWeight: "900" },
  teamName: { color: colors.text, fontSize: 13, fontWeight: "700", marginTop: 9, textAlign: "center" },
  probability: { color: colors.muted, fontSize: 25, fontWeight: "900", marginTop: 6 },
  winnerProbability: { color: colors.green, fontSize: 25, fontWeight: "900", marginTop: 6 },
  at: { color: colors.muted, fontSize: 14, fontWeight: "900", marginHorizontal: 8 },
  probabilityTrack: { backgroundColor: "#26372f", borderRadius: 4, flexDirection: "row", height: 7, marginTop: 16, overflow: "hidden", width: "100%" },
  awayProbabilityFill: { backgroundColor: "#71877b", height: "100%" },
  homeProbabilityFill: { backgroundColor: colors.green, height: "100%" },
  pick: { alignItems: "flex-end", borderTopColor: colors.border, borderTopWidth: 1, flexDirection: "row", justifyContent: "space-between", marginTop: 18, paddingTop: 15 },
  pickLabel: { color: colors.muted, fontSize: 9, fontWeight: "900", letterSpacing: 1.2 },
  pickWinner: { color: colors.green, fontSize: 16, fontWeight: "900", marginTop: 4 },
  edgeBlock: { alignItems: "flex-end" },
  edgeValue: { color: colors.text, fontSize: 16, fontWeight: "900", marginTop: 4 },
  factorRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, justifyContent: "center", marginTop: 13 },
  factor: { backgroundColor: "#17251f", borderRadius: 12, paddingHorizontal: 9, paddingVertical: 6 },
  factorText: { color: colors.muted, fontSize: 9, fontWeight: "700" },
  predictionHistory: { backgroundColor: "#0a1511", borderRadius: 13, marginTop: 13, padding: 12 },
  predictionHistoryLabel: { color: colors.muted, fontSize: 8, fontWeight: "900", letterSpacing: 1 },
  predictionHistoryValue: { color: colors.text, fontSize: 12, fontWeight: "800", marginTop: 5 },
  predictionHistoryScore: { color: colors.muted, fontSize: 11, marginTop: 2 },
  methodBlock: { borderTopColor: colors.border, borderTopWidth: 1, marginTop: 15, paddingTop: 14 },
  methodLabel: { color: colors.green, fontSize: 9, fontWeight: "900", letterSpacing: 1 },
  methodText: { color: "#acc2b6", fontSize: 12, lineHeight: 18, marginTop: 6 },
  previousGamesButton: { alignItems: "center", backgroundColor: colors.greenDark, borderColor: "#2f6f4c", borderRadius: 13, borderWidth: 1, flexDirection: "row", justifyContent: "space-between", marginTop: 13, paddingHorizontal: 14, paddingVertical: 12 },
  previousGamesButtonText: { color: colors.green, fontSize: 11, fontWeight: "900" },
  previousGamesArrow: { color: colors.green, fontSize: 17, fontWeight: "900" },
  secondaryMarketButton: { alignItems: "center", borderColor: colors.green, borderRadius: 13, borderWidth: 1, marginTop: 10, paddingVertical: 12 },
  secondaryMarketButtonText: { color: colors.green, fontSize: 12, fontWeight: "900" },
  extractedGame: { backgroundColor: "#0a1511", borderColor: colors.border, borderRadius: 12, borderWidth: 1, marginTop: 10, padding: 12 },
  manualPasteBox: { backgroundColor: "#07110d", borderColor: colors.border, borderRadius: 13, borderWidth: 1, color: colors.text, fontSize: 14, minHeight: 260, marginTop: 12, padding: 14 },
  screenshotButton: { alignItems: "center", backgroundColor: colors.green, borderRadius: 13, marginTop: 14, paddingVertical: 13 },
  screenshotButtonText: { color: colors.background, fontSize: 12, fontWeight: "900" },
  marketCard: { backgroundColor: colors.panel, borderColor: colors.border, borderRadius: 20, borderWidth: 1, marginBottom: 16, padding: 16 },
  marketRow: { alignItems: "center", flexDirection: "row", gap: 10, marginBottom: 14 },
  marketField: { flex: 1 },
  marketInput: { backgroundColor: "#0a1511", borderColor: colors.border, borderRadius: 13, borderWidth: 1, color: colors.text, flex: 1, fontSize: 16, fontWeight: "900", padding: 13, textAlign: "center" },
  marketInputWide: { backgroundColor: "#0a1511", borderColor: colors.border, borderRadius: 13, borderWidth: 1, color: colors.text, fontSize: 16, fontWeight: "900", padding: 13 },
  analysisPanel: { backgroundColor: colors.greenDark, borderColor: "#2f6f4c", borderRadius: 15, borderWidth: 1, marginTop: 4, padding: 14 },
  analysisWinner: { color: colors.green, fontSize: 20, fontWeight: "900", marginBottom: 8, marginTop: 4 },
  analysisLine: { color: colors.text, fontSize: 12, fontWeight: "700", marginTop: 4 },
  marketHint: { color: colors.muted, fontSize: 10, lineHeight: 15, marginTop: 10 },
  filterLabel: { color: colors.muted, fontSize: 10, fontWeight: "900", letterSpacing: 1.2, marginBottom: 8 },
  chips: { gap: 8, paddingBottom: 18 },
  chip: { backgroundColor: colors.panel, borderColor: colors.border, borderRadius: 18, borderWidth: 1, paddingHorizontal: 13, paddingVertical: 8 },
  chipActive: { backgroundColor: colors.green, borderColor: colors.green },
  chipText: { color: colors.muted, fontSize: 11, fontWeight: "800" },
  chipTextActive: { color: colors.background },
  scheduleCard: { backgroundColor: colors.panel, borderColor: colors.border, borderRadius: 20, borderWidth: 1, marginBottom: 13, padding: 16 },
  gameWeek: { color: colors.green, fontSize: 9, fontWeight: "900", letterSpacing: 1.2 },
  gameDate: { color: colors.text, fontSize: 13, fontWeight: "700", marginTop: 4 },
  upcomingPill: { backgroundColor: colors.greenDark, borderRadius: 12, paddingHorizontal: 9, paddingVertical: 6 },
  upcomingText: { color: colors.green, fontSize: 9, fontWeight: "900" },
  finalPill: { backgroundColor: "#263029", borderRadius: 12, paddingHorizontal: 9, paddingVertical: 6 },
  finalText: { color: colors.muted, fontSize: 9, fontWeight: "900" },
  scheduleTeams: { alignItems: "center", flexDirection: "row", justifyContent: "space-between" },
  scheduleTeam: { alignItems: "center", flex: 1, minWidth: 0 },
  scheduleTeamName: { color: colors.text, fontSize: 12, fontWeight: "700", marginTop: 7, textAlign: "center" },
  score: { color: colors.text, fontSize: 23, fontWeight: "900", marginTop: 5 },
  venue: { color: colors.muted, fontSize: 10, marginTop: 14, textAlign: "center" },
  lastMeeting: { backgroundColor: "#0a1511", borderColor: colors.border, borderRadius: 15, borderWidth: 1, marginTop: 15, padding: 13 },
  lastMeetingLabel: { color: colors.muted, fontSize: 9, fontWeight: "900", letterSpacing: 1.1 },
  lastMeetingResult: { color: colors.text, fontSize: 13, fontWeight: "800", marginTop: 7 },
  lastMeetingScore: { color: colors.muted, fontSize: 12, marginTop: 3 },
  historyButton: { alignItems: "center", borderColor: "#2f6f4c", borderRadius: 12, borderWidth: 1, marginTop: 12, paddingVertical: 10 },
  historyButtonText: { color: colors.green, fontSize: 11, fontWeight: "800" },
  pressed: { opacity: 0.65 },
  bottomNav: { backgroundColor: "#0a1511", borderTopColor: colors.border, borderTopWidth: 1, flexDirection: "row", paddingBottom: 5, paddingHorizontal: 8, paddingTop: 6 },
  navItem: { alignItems: "center", borderRadius: 14, flex: 1, paddingVertical: 7 },
  navItemActive: { backgroundColor: colors.greenDark },
  navIcon: { color: colors.muted, fontSize: 17, fontWeight: "900" },
  navText: { color: colors.muted, fontSize: 9, fontWeight: "800", marginTop: 2, textTransform: "uppercase" },
  navTextActive: { color: colors.green },
  disclaimer: { color: "#5f756a", fontSize: 10, lineHeight: 15, marginTop: 15, textAlign: "center" },
  empty: { color: colors.muted, fontSize: 13, paddingVertical: 32, textAlign: "center" },
  alertSheet: { backgroundColor: colors.panel, borderColor: colors.border, borderTopLeftRadius: 26, borderTopRightRadius: 26, borderWidth: 1, padding: 18 },
  alertTitleWrap: { flex: 1, paddingRight: 12 },
  alertIntro: { color: "#acc2b6", fontSize: 12, lineHeight: 18, marginBottom: 14 },
  phoneInput: { backgroundColor: "#0a1511", borderColor: colors.border, borderRadius: 13, borderWidth: 1, color: colors.text, fontSize: 16, marginBottom: 10, paddingHorizontal: 14, paddingVertical: 13 },
  alertOption: { alignItems: "center", borderBottomColor: colors.border, borderBottomWidth: 1, flexDirection: "row", justifyContent: "space-between", paddingVertical: 11 },
  alertOptionText: { color: colors.text, fontSize: 13, fontWeight: "700" },
  consentText: { color: colors.muted, fontSize: 9, lineHeight: 14, marginTop: 13 },
  alertStatus: { color: colors.green, fontSize: 11, fontWeight: "700", marginTop: 10 },
  enableAlertsButton: { alignItems: "center", backgroundColor: colors.green, borderRadius: 13, marginTop: 14, paddingVertical: 13 },
  enableAlertsButtonText: { color: colors.background, fontSize: 12, fontWeight: "900" },
  modalBackdrop: { backgroundColor: "rgba(0,0,0,0.68)", flex: 1, justifyContent: "flex-end" },
  modalSheet: { backgroundColor: colors.panel, borderColor: colors.border, borderTopLeftRadius: 26, borderTopRightRadius: 26, borderWidth: 1, maxHeight: "78%", padding: 18 },
  modalHandle: { alignSelf: "center", backgroundColor: "#455b50", borderRadius: 2, height: 4, marginBottom: 18, width: 42 },
  modalHeader: { alignItems: "center", flexDirection: "row", justifyContent: "space-between", marginBottom: 12 },
  modalTitle: { color: colors.text, fontSize: 25, fontWeight: "900" },
  closeButton: { alignItems: "center", backgroundColor: colors.panelRaised, borderRadius: 20, height: 40, justifyContent: "center", width: 40 },
  closeText: { color: colors.text, fontSize: 27, lineHeight: 29 },
  modalList: { maxHeight: 430 },
  historyTabs: { backgroundColor: "#0a1511", borderRadius: 14, flexDirection: "row", marginBottom: 8, padding: 4 },
  historyTab: { alignItems: "center", borderRadius: 11, flex: 1, paddingVertical: 10 },
  historyTabActive: { backgroundColor: colors.greenDark },
  historyTabText: { color: colors.muted, fontSize: 11, fontWeight: "800" },
  historyTabTextActive: { color: colors.green },
  meetingLine: { alignItems: "center", borderBottomColor: colors.border, borderBottomWidth: 1, flexDirection: "row", justifyContent: "space-between", paddingVertical: 14 },
  meetingDate: { color: colors.muted, fontSize: 10, fontWeight: "700" },
  meetingTeams: { color: colors.text, fontSize: 15, fontWeight: "800", marginTop: 5 },
  winnerBlock: { alignItems: "flex-end" },
  winnerLabel: { color: colors.muted, fontSize: 8, fontWeight: "900", letterSpacing: 1 },
  winnerName: { color: colors.green, fontSize: 15, fontWeight: "900", marginTop: 3 },
  recentTeamSection: { borderBottomColor: colors.border, borderBottomWidth: 1, paddingBottom: 8, paddingTop: 12 },
  recentTeamHeader: { alignItems: "center", flexDirection: "row", marginBottom: 8 },
  recentTeamHeading: { marginLeft: 11 },
  recentTeamName: { color: colors.text, fontSize: 14, fontWeight: "900" },
  recentTeamSubhead: { color: colors.muted, fontSize: 10, marginTop: 2 },
  recentGameLine: { borderTopColor: colors.border, borderTopWidth: 1, paddingVertical: 12 },
  recentGameTop: { alignItems: "center", flexDirection: "row", justifyContent: "space-between" },
  recentGameCopy: { flex: 1 },
  recentOpponent: { color: colors.text, fontSize: 14, fontWeight: "800", marginTop: 4 },
  resultPill: { alignItems: "center", borderRadius: 11, flexDirection: "row", gap: 7, paddingHorizontal: 10, paddingVertical: 7 },
  winPill: { backgroundColor: colors.greenDark },
  lossPill: { backgroundColor: "#30211f" },
  resultLetter: { fontSize: 12, fontWeight: "900" },
  winText: { color: colors.green },
  lossText: { color: "#f29b88" },
  recentScore: { color: colors.text, fontSize: 12, fontWeight: "900" },
  recentStats: { color: colors.muted, fontSize: 10, fontWeight: "700", marginTop: 7 },
  emptyCompact: { color: colors.muted, fontSize: 12, paddingVertical: 16, textAlign: "center" },
  playerApiError: { backgroundColor: "#30211f", borderColor: "#69443c", borderRadius: 12, borderWidth: 1, color: "#f6b4a6", fontSize: 11, lineHeight: 17, marginTop: 8, padding: 12 },
  modalNote: { color: colors.muted, fontSize: 9, marginTop: 14, textAlign: "center" },
});
