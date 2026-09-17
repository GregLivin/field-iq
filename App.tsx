import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { getPredictions } from "./src/services/fieldIqApi";
import { Prediction } from "./src/types";

const colors = {
  background: "#07100d",
  panel: "#101b17",
  panelSoft: "#14231d",
  green: "#55e896",
  greenDark: "#173e2a",
  text: "#f4fff8",
  muted: "#91a79c",
  border: "#24362e",
};

function TeamBadge({ abbreviation }: { abbreviation: string }) {
  return (
    <View style={styles.badge}>
      <Text style={styles.badgeText}>{abbreviation}</Text>
    </View>
  );
}

function PredictionCard({ prediction }: { prediction: Prediction }) {
  const homeIsWinner =
    prediction.homeWinProbability >= prediction.awayWinProbability;

  return (
    <View style={styles.card}>
      <View style={styles.cardTop}>
        <Text style={styles.kickoff}>{prediction.kickoff}</Text>
        <View style={styles.confidencePill}>
          <Text style={styles.confidenceText}>
            {prediction.confidence} confidence
          </Text>
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

export default function App() {
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [source, setSource] = useState<"live" | "demo">("demo");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function loadPredictions(isRefresh = false) {
    isRefresh ? setRefreshing(true) : setLoading(true);
    const result = await getPredictions();
    setPredictions(result.predictions);
    setSource(result.source);
    setLoading(false);
    setRefreshing(false);
  }

  useEffect(() => {
    void loadPredictions();
  }, []);

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" />
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => void loadPredictions(true)}
            tintColor={colors.green}
          />
        }
      >
        <View style={styles.header}>
          <View>
            <Text style={styles.brand}>FIELDIQ</Text>
            <Text style={styles.subtitle}>Smarter predictions. Better picks.</Text>
          </View>
          <View style={styles.weekPill}>
            <Text style={styles.weekText}>NFL • WEEK 2</Text>
          </View>
        </View>

        <View style={styles.hero}>
          <Text style={styles.eyebrow}>GAME WINNER MODEL</Text>
          <Text style={styles.heroTitle}>This week’s smartest picks</Text>
          <Text style={styles.heroBody}>
            Matchup probabilities built from team form, player availability,
            weather, efficiency, and historical performance.
          </Text>
          <View style={styles.sourceRow}>
            <View style={source === "live" ? styles.liveDot : styles.demoDot} />
            <Text style={styles.sourceText}>
              {source === "live" ? "Live NFL data" : "Demo data • API ready"}
            </Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>Predictions</Text>

        {loading ? (
          <ActivityIndicator
            color={colors.green}
            size="large"
            style={styles.loader}
          />
        ) : (
          predictions.map((prediction) => (
            <PredictionCard key={prediction.id} prediction={prediction} />
          ))
        )}

        <Text style={styles.disclaimer}>
          Predictions are estimates, not guarantees. FieldIQ is not affiliated
          with or endorsed by the NFL.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.background },
  container: { padding: 20, paddingBottom: 44 },
  header: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 24,
  },
  brand: {
    color: colors.green,
    fontSize: 25,
    fontWeight: "900",
    letterSpacing: 1.5,
  },
  subtitle: { color: colors.muted, fontSize: 12, marginTop: 2 },
  weekPill: {
    backgroundColor: colors.greenDark,
    borderColor: "#256442",
    borderRadius: 18,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  weekText: { color: colors.green, fontSize: 11, fontWeight: "800" },
  hero: {
    backgroundColor: colors.panelSoft,
    borderColor: colors.border,
    borderRadius: 24,
    borderWidth: 1,
    marginBottom: 28,
    padding: 22,
  },
  eyebrow: {
    color: colors.green,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 1.4,
    marginBottom: 9,
  },
  heroTitle: {
    color: colors.text,
    fontSize: 30,
    fontWeight: "900",
    lineHeight: 34,
    marginBottom: 10,
  },
  heroBody: { color: colors.muted, fontSize: 14, lineHeight: 21 },
  sourceRow: { alignItems: "center", flexDirection: "row", marginTop: 18 },
  liveDot: {
    backgroundColor: colors.green,
    borderRadius: 5,
    height: 9,
    marginRight: 8,
    width: 9,
  },
  demoDot: {
    backgroundColor: "#f2b84b",
    borderRadius: 5,
    height: 9,
    marginRight: 8,
    width: 9,
  },
  sourceText: { color: colors.muted, fontSize: 12, fontWeight: "700" },
  sectionTitle: {
    color: colors.text,
    fontSize: 21,
    fontWeight: "800",
    marginBottom: 12,
  },
  card: {
    backgroundColor: colors.panel,
    borderColor: colors.border,
    borderRadius: 22,
    borderWidth: 1,
    marginBottom: 16,
    padding: 18,
  },
  cardTop: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 18,
  },
  kickoff: { color: colors.muted, fontSize: 12, fontWeight: "700" },
  confidencePill: {
    backgroundColor: colors.greenDark,
    borderRadius: 12,
    paddingHorizontal: 9,
    paddingVertical: 5,
  },
  confidenceText: { color: colors.green, fontSize: 10, fontWeight: "800" },
  matchup: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  team: { alignItems: "center", flex: 1 },
  badge: {
    alignItems: "center",
    backgroundColor: "#1a2b24",
    borderColor: "#345244",
    borderRadius: 22,
    borderWidth: 1,
    height: 44,
    justifyContent: "center",
    marginBottom: 8,
    width: 62,
  },
  badgeText: { color: colors.text, fontSize: 14, fontWeight: "900" },
  teamName: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "700",
    marginBottom: 4,
    textAlign: "center",
  },
  probability: { color: colors.muted, fontSize: 23, fontWeight: "900" },
  winnerProbability: { color: colors.green, fontSize: 23, fontWeight: "900" },
  at: { color: colors.muted, fontSize: 15, fontWeight: "800", marginHorizontal: 8 },
  pick: {
    alignItems: "center",
    borderTopColor: colors.border,
    borderTopWidth: 1,
    marginTop: 18,
    paddingTop: 14,
  },
  pickLabel: {
    color: colors.muted,
    fontSize: 9,
    fontWeight: "900",
    letterSpacing: 1.2,
  },
  pickWinner: { color: colors.green, fontSize: 18, fontWeight: "900", marginTop: 3 },
  factorRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    marginTop: 12,
  },
  factor: {
    backgroundColor: "#0b1511",
    borderRadius: 10,
    margin: 3,
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  factorText: { color: colors.muted, fontSize: 9, fontWeight: "600" },
  loader: { marginVertical: 48 },
  disclaimer: {
    color: "#63766d",
    fontSize: 10,
    lineHeight: 15,
    marginTop: 10,
    textAlign: "center",
  },
});
