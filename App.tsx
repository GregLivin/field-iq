import { StatusBar } from "expo-status-bar";
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
  useWindowDimensions,
  View,
} from "react-native";

import {
  getMatchupHistory,
  getPredictions,
  getSchedule,
} from "./src/services/fieldIqApi";
import { MatchupMeeting, Prediction, ScheduleGame } from "./src/types";

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

type Tab = "picks" | "schedule" | "matchups";

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

function PredictionCard({ prediction }: { prediction: Prediction }) {
  const homeIsWinner = prediction.homeWinProbability >= prediction.awayWinProbability;
  return (
    <View style={styles.card}>
      <View style={styles.cardTop}>
        <Text style={styles.kickoff}>{prediction.kickoff}</Text>
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
      <View style={styles.pick}>
        <Text style={styles.pickLabel}>FIELDIQ PICK</Text>
        <Text style={styles.pickWinner}>{prediction.predictedWinner}</Text>
      </View>
      <View style={styles.factorRow}>
        {prediction.factors.slice(0, 3).map((factor) => (
          <View key={factor} style={styles.factor}>
            <Text style={styles.factorText}>{factor}</Text>
          </View>
        ))}
      </View>
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
  const [history, setHistory] = useState<MatchupMeeting[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

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

  async function openHistory(game: ScheduleGame) {
    setSelectedGame(game);
    setHistory([]);
    setHistoryLoading(true);
    const result = await getMatchupHistory(game.awayAbbreviation, game.homeAbbreviation);
    setHistory(result?.meetings ?? []);
    setHistoryLoading(false);
  }

  const title = activeTab === "picks" ? "Predictions" : activeTab === "schedule" ? "NFL Schedule" : "Matchup History";

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" />
      <View style={styles.shell}>
        <View style={styles.header}>
          <View>
            <Text style={styles.brand}>FIELDIQ</Text>
            {!compact && <Text style={styles.subtitle}>Smarter predictions. Better picks.</Text>}
          </View>
          <View style={styles.weekPill}>
            <Text style={styles.weekText}>NFL {season} • W{week}</Text>
          </View>
        </View>

        <ScrollView
          style={styles.scroller}
          contentContainerStyle={styles.container}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={() => void loadData(true)} tintColor={colors.green} />
          }
        >
          {activeTab === "picks" && (
            <>
              <View style={[styles.hero, compact && styles.heroCompact]}>
                <Text style={styles.eyebrow}>GAME WINNER MODEL</Text>
                <Text style={[styles.heroTitle, compact && styles.heroTitleCompact]}>This week’s smartest picks</Text>
                <Text style={styles.heroBody}>
                  Probabilities built from team form, player availability, weather, efficiency, and history.
                </Text>
                <View style={styles.sourceRow}>
                  <View style={source === "live" ? styles.liveDot : styles.demoDot} />
                  <Text style={styles.sourceText}>{source === "live" ? `Daily data • ${model}` : "Demo data"}</Text>
                </View>
              </View>
              <Text style={styles.sectionTitle}>{title}</Text>
              {loading ? <ActivityIndicator color={colors.green} size="large" style={styles.loader} /> :
                predictions.map((prediction) => <PredictionCard key={prediction.id} prediction={prediction} />)}
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
            Predictions are estimates, not guarantees. FieldIQ is not affiliated with or endorsed by the NFL.
          </Text>
        </ScrollView>

        <View style={styles.bottomNav}>
          {(["picks", "schedule", "matchups"] as Tab[]).map((tab) => (
            <Pressable
              accessibilityRole="button"
              key={tab}
              onPress={() => setActiveTab(tab)}
              style={[styles.navItem, activeTab === tab && styles.navItemActive]}
            >
              <Text style={[styles.navIcon, activeTab === tab && styles.navTextActive]}>
                {tab === "picks" ? "◎" : tab === "schedule" ? "▦" : "↔"}
              </Text>
              <Text style={[styles.navText, activeTab === tab && styles.navTextActive]}>{tab}</Text>
            </Pressable>
          ))}
        </View>
      </View>

      <Modal visible={selectedGame !== null} transparent animationType="slide" onRequestClose={() => setSelectedGame(null)}>
        <Pressable style={styles.modalBackdrop} onPress={() => setSelectedGame(null)}>
          <Pressable style={styles.modalSheet} onPress={(event) => event.stopPropagation()}>
            <View style={styles.modalHandle} />
            <View style={styles.modalHeader}>
              <View>
                <Text style={styles.eyebrow}>LAST FIVE MEETINGS</Text>
                <Text style={styles.modalTitle}>
                  {selectedGame?.awayAbbreviation} vs {selectedGame?.homeAbbreviation}
                </Text>
              </View>
              <Pressable onPress={() => setSelectedGame(null)} style={styles.closeButton}>
                <Text style={styles.closeText}>×</Text>
              </Pressable>
            </View>
            <ScrollView style={styles.modalList}>
              {historyLoading ? <ActivityIndicator color={colors.green} size="large" style={styles.loader} /> :
                history.map((meeting) => <MeetingLine key={meeting.id} meeting={meeting} />)}
              {!historyLoading && history.length === 0 && <Text style={styles.empty}>No completed meetings found.</Text>}
            </ScrollView>
            <Text style={styles.modalNote}>Regular season and playoff meetings in the FieldIQ dataset.</Text>
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
  container: { paddingHorizontal: 16, paddingTop: 10, paddingBottom: 32 },
  header: { alignItems: "center", flexDirection: "row", justifyContent: "space-between", paddingHorizontal: 18, paddingVertical: 12 },
  brand: { color: colors.green, fontSize: 23, fontWeight: "900", letterSpacing: 1.5 },
  subtitle: { color: colors.muted, fontSize: 12, marginTop: 2 },
  weekPill: { backgroundColor: colors.greenDark, borderColor: "#286945", borderRadius: 18, borderWidth: 1, paddingHorizontal: 11, paddingVertical: 7 },
  weekText: { color: colors.green, fontSize: 11, fontWeight: "800" },
  hero: { backgroundColor: colors.panelRaised, borderColor: colors.border, borderRadius: 24, borderWidth: 1, marginBottom: 26, padding: 24 },
  heroCompact: { borderRadius: 20, padding: 18 },
  eyebrow: { color: colors.green, fontSize: 11, fontWeight: "900", letterSpacing: 1.4, marginBottom: 8 },
  heroTitle: { color: colors.text, fontSize: 32, fontWeight: "900", lineHeight: 36, marginBottom: 10 },
  heroTitleCompact: { fontSize: 27, lineHeight: 31 },
  heroBody: { color: colors.muted, fontSize: 14, lineHeight: 21 },
  sourceRow: { alignItems: "center", flexDirection: "row", marginTop: 17 },
  liveDot: { backgroundColor: colors.green, borderRadius: 5, height: 9, marginRight: 8, width: 9 },
  demoDot: { backgroundColor: colors.gold, borderRadius: 5, height: 9, marginRight: 8, width: 9 },
  sourceText: { color: colors.muted, fontSize: 12, fontWeight: "700" },
  screenIntro: { marginBottom: 22, paddingTop: 8 },
  screenTitle: { color: colors.text, fontSize: 28, fontWeight: "900", marginBottom: 7 },
  sectionTitle: { color: colors.text, fontSize: 21, fontWeight: "800", marginBottom: 12 },
  resultsRow: { alignItems: "baseline", flexDirection: "row", justifyContent: "space-between", marginTop: 10 },
  resultCount: { color: colors.muted, fontSize: 12, fontWeight: "700" },
  loader: { marginVertical: 42 },
  card: { backgroundColor: colors.panel, borderColor: colors.border, borderRadius: 22, borderWidth: 1, marginBottom: 16, padding: 17 },
  cardTop: { alignItems: "center", flexDirection: "row", justifyContent: "space-between", marginBottom: 17 },
  kickoff: { color: colors.muted, fontSize: 12, fontWeight: "700" },
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
  pick: { alignItems: "center", borderTopColor: colors.border, borderTopWidth: 1, marginTop: 18, paddingTop: 15 },
  pickLabel: { color: colors.muted, fontSize: 9, fontWeight: "900", letterSpacing: 1.2 },
  pickWinner: { color: colors.green, fontSize: 16, fontWeight: "900", marginTop: 4 },
  factorRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, justifyContent: "center", marginTop: 13 },
  factor: { backgroundColor: "#17251f", borderRadius: 12, paddingHorizontal: 9, paddingVertical: 6 },
  factorText: { color: colors.muted, fontSize: 9, fontWeight: "700" },
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
  modalBackdrop: { backgroundColor: "rgba(0,0,0,0.68)", flex: 1, justifyContent: "flex-end" },
  modalSheet: { backgroundColor: colors.panel, borderColor: colors.border, borderTopLeftRadius: 26, borderTopRightRadius: 26, borderWidth: 1, maxHeight: "78%", padding: 18 },
  modalHandle: { alignSelf: "center", backgroundColor: "#455b50", borderRadius: 2, height: 4, marginBottom: 18, width: 42 },
  modalHeader: { alignItems: "center", flexDirection: "row", justifyContent: "space-between", marginBottom: 12 },
  modalTitle: { color: colors.text, fontSize: 25, fontWeight: "900" },
  closeButton: { alignItems: "center", backgroundColor: colors.panelRaised, borderRadius: 20, height: 40, justifyContent: "center", width: 40 },
  closeText: { color: colors.text, fontSize: 27, lineHeight: 29 },
  modalList: { maxHeight: 430 },
  meetingLine: { alignItems: "center", borderBottomColor: colors.border, borderBottomWidth: 1, flexDirection: "row", justifyContent: "space-between", paddingVertical: 14 },
  meetingDate: { color: colors.muted, fontSize: 10, fontWeight: "700" },
  meetingTeams: { color: colors.text, fontSize: 15, fontWeight: "800", marginTop: 5 },
  winnerBlock: { alignItems: "flex-end" },
  winnerLabel: { color: colors.muted, fontSize: 8, fontWeight: "900", letterSpacing: 1 },
  winnerName: { color: colors.green, fontSize: 15, fontWeight: "900", marginTop: 3 },
  modalNote: { color: colors.muted, fontSize: 9, marginTop: 14, textAlign: "center" },
});
