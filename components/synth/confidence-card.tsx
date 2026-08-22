import { StyleSheet, Text, View } from "react-native";

import type { AnalysisConfidence } from "@/lib/synth-now-api";

const labels: Record<keyof AnalysisConfidence, string> = {
  inputQuality: "Input quality",
  separationIntegrity: "Separation integrity",
  referenceCompatibility: "Reference match",
  candidateMargin: "Candidate margin",
  temporalConsensus: "Timing agreement",
};

export function ConfidenceCard({ confidence }: { confidence: AnalysisConfidence }) {
  return (
    <View style={styles.card}>
      <Text style={styles.title}>Analysis confidence</Text>
      <Text style={styles.copy}>Each signal is shown separately so a useful similarity does not look like a documented fact.</Text>
      <View style={styles.grid}>
        {(Object.keys(labels) as Array<keyof AnalysisConfidence>).map((key) => (
          <View key={key} style={styles.item}>
            <Text style={styles.label}>{labels[key]}</Text>
            <Text style={[styles.value, confidence[key] === "limited" && styles.limited]}>{confidence[key]}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: "#10233B", borderColor: "#294766", borderWidth: 1, borderRadius: 20, padding: 16, gap: 8 },
  title: { color: "#F5FAFF", fontSize: 17, fontWeight: "800" },
  copy: { color: "#A8B7CA", fontSize: 13, lineHeight: 19 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 4 },
  item: { width: "47%", borderTopColor: "#294766", borderTopWidth: 1, paddingTop: 9 },
  label: { color: "#A8B7CA", fontSize: 11, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.7 },
  value: { color: "#4CD3A7", fontSize: 14, fontWeight: "800", marginTop: 2, textTransform: "capitalize" },
  limited: { color: "#F6B64A" },
});
