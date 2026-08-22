import { ScrollView, StyleSheet, Text, View } from "react-native";

import { ScreenContainer } from "@/components/screen-container";

export default function LibraryScreen() {
  return (
    <ScreenContainer className="px-5">
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.eyebrow}>YOUR LIBRARY</Text>
        <Text style={styles.title}>Keep the sounds that matter.</Text>
        <Text style={styles.subtitle}>Saved gear, presets, songs, and analysis jobs appear here after cloud sync is connected to your account.</Text>
        <View style={styles.emptyCard}>
          <Text style={styles.emptyTitle}>Library sync is ready for your account</Text>
          <Text style={styles.emptyCopy}>The mobile client is prepared for a Neon-backed library. Sign-in and the Worker API will safely sync saved records without storing private audio locally as a permanent library item.</Text>
        </View>
        <View style={styles.rule}><Text style={styles.ruleTitle}>What syncs</Text><Text style={styles.ruleCopy}>Saved canonical gear and preset IDs, collections, and completed job metadata. Raw audio stays private under its R2 retention policy.</Text></View>
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: { paddingTop: 18, paddingBottom: 32, gap: 14 }, eyebrow: { color: "#A78BFA", fontSize: 11, letterSpacing: 1.2, fontWeight: "900" },
  title: { color: "#F5FAFF", fontSize: 30, lineHeight: 35, fontWeight: "900", letterSpacing: -0.7 }, subtitle: { color: "#A8B7CA", fontSize: 15, lineHeight: 21 },
  emptyCard: { backgroundColor: "#10233B", borderColor: "#A78BFA", borderWidth: 1, borderRadius: 20, padding: 18, marginTop: 6 }, emptyTitle: { color: "#F5FAFF", fontSize: 18, fontWeight: "800" }, emptyCopy: { color: "#A8B7CA", fontSize: 14, lineHeight: 20, marginTop: 7 },
  rule: { backgroundColor: "#0C1B2D", borderColor: "#294766", borderWidth: 1, borderRadius: 18, padding: 16 }, ruleTitle: { color: "#4CD3A7", fontWeight: "900", fontSize: 13, textTransform: "uppercase", letterSpacing: 0.8 }, ruleCopy: { color: "#A8B7CA", fontSize: 14, lineHeight: 20, marginTop: 6 },
});
