import { StyleSheet, Text, View } from "react-native";

type BadgeKind = "verified" | "official" | "similarity" | "limited";

const labels: Record<BadgeKind, string> = {
  verified: "Verified recording use",
  official: "Official source",
  similarity: "Similarity candidate",
  limited: "Limited by source bleed",
};

export function EvidenceBadge({ kind }: { kind: BadgeKind }) {
  return (
    <View style={[styles.badge, styles[kind]]} accessibilityLabel={labels[kind]}>
      <Text style={styles.text}>{labels[kind]}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: { alignSelf: "flex-start", borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5 },
  text: { color: "#06131F", fontSize: 12, fontWeight: "800" },
  verified: { backgroundColor: "#4CD3A7" },
  official: { backgroundColor: "#8BD3FF" },
  similarity: { backgroundColor: "#A78BFA" },
  limited: { backgroundColor: "#F6B64A" },
});
