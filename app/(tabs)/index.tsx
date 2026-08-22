import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";

import { ScreenContainer } from "@/components/screen-container";
import { EvidenceBadge } from "@/components/synth/evidence-badge";

/**
 * Home Screen - NativeWind Example
 *
 * This template uses NativeWind (Tailwind CSS for React Native).
 * You can use familiar Tailwind classes directly in className props.
 *
 * Key patterns:
 * - Use `className` instead of `style` for most styling
 * - Theme colors: use tokens directly (bg-background, text-foreground, bg-primary, etc.); no dark: prefix needed
 * - Responsive: standard Tailwind breakpoints work on web
 * - Custom colors defined in tailwind.config.js
 */
export default function HomeScreen() {
  return (
    <ScreenContainer className="px-5">
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.eyebrowRow}>
          <Text style={styles.eyebrow}>NIKO THE GREAT — SYNTH NOW</Text>
          <View style={styles.liveDot} />
        </View>
        <Text style={styles.title}>Know the sound{`\n`}behind the song.</Text>
        <Text style={styles.subtitle}>Research gear, trace production evidence, and analyze authorized audio without confusing similarity with fact.</Text>

        <Pressable onPress={() => router.push("/analyze" as never)} style={({ pressed }) => [styles.primaryAction, pressed && styles.pressed]} accessibilityRole="button">
          <View style={styles.actionIcon}><Text style={styles.actionIconText}>⌁</Text></View>
          <View style={styles.actionCopy}><Text style={styles.actionTitle}>Analyze a sound</Text><Text style={styles.actionSub}>Upload an authorized clip or stem</Text></View>
          <Text style={styles.actionArrow}>›</Text>
        </Pressable>

        <View style={styles.sectionRow}><Text style={styles.sectionTitle}>The Synth Now standard</Text></View>
        <View style={styles.standardCard}>
          <EvidenceBadge kind="verified" />
          <Text style={styles.cardTitle}>Evidence first</Text>
          <Text style={styles.cardCopy}>Documented recording uses are shown separately from artist associations and audio similarity results.</Text>
        </View>
        <View style={styles.standardCard}>
          <EvidenceBadge kind="similarity" />
          <Text style={styles.cardTitle}>Sound-aware, not overconfident</Text>
          <Text style={styles.cardCopy}>Audio analysis returns transparent confidence signals. A separated stem with source bleed is always limited and labeled.</Text>
        </View>

        <View style={styles.sectionRow}><Text style={styles.sectionTitle}>Your library</Text><Text style={styles.sectionMeta}>Sign in to sync</Text></View>
        <View style={styles.emptyLibrary}><Text style={styles.emptyTitle}>No saved gear yet</Text><Text style={styles.emptyCopy}>Discover a synth, VST, preset, or verified song use, then save it for your next session.</Text></View>
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: { paddingTop: 18, paddingBottom: 34, gap: 16 },
  eyebrowRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  eyebrow: { color: "#4CD3A7", fontSize: 11, fontWeight: "900", letterSpacing: 1.4 },
  liveDot: { width: 7, height: 7, borderRadius: 9, backgroundColor: "#4CD3A7" },
  title: { color: "#F5FAFF", fontSize: 39, fontWeight: "900", letterSpacing: -1.4, lineHeight: 43, marginTop: 4 },
  subtitle: { color: "#A8B7CA", fontSize: 16, lineHeight: 23, maxWidth: 340 },
  primaryAction: { backgroundColor: "#3CC6FF", borderRadius: 24, padding: 18, flexDirection: "row", alignItems: "center", marginTop: 10 },
  pressed: { opacity: 0.86, transform: [{ scale: 0.98 }] },
  actionIcon: { backgroundColor: "#07111F", width: 42, height: 42, borderRadius: 21, alignItems: "center", justifyContent: "center" },
  actionIconText: { color: "#3CC6FF", fontSize: 24, fontWeight: "900" },
  actionCopy: { flex: 1, marginLeft: 12 }, actionTitle: { color: "#07111F", fontSize: 18, fontWeight: "900" },
  actionSub: { color: "#12314A", marginTop: 3, fontSize: 13, fontWeight: "600" }, actionArrow: { color: "#07111F", fontSize: 34, lineHeight: 34 },
  sectionRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", marginTop: 13 },
  sectionTitle: { color: "#F5FAFF", fontSize: 18, fontWeight: "800" }, sectionMeta: { color: "#A8B7CA", fontSize: 12, fontWeight: "700" },
  standardCard: { backgroundColor: "#10233B", borderColor: "#294766", borderWidth: 1, borderRadius: 20, padding: 16, gap: 9 },
  cardTitle: { color: "#F5FAFF", fontSize: 16, fontWeight: "800", marginTop: 2 }, cardCopy: { color: "#A8B7CA", fontSize: 14, lineHeight: 20 },
  emptyLibrary: { borderRadius: 18, padding: 18, backgroundColor: "#0C1B2D", borderWidth: 1, borderColor: "#203C59" },
  emptyTitle: { color: "#F5FAFF", fontSize: 16, fontWeight: "800" }, emptyCopy: { color: "#A8B7CA", fontSize: 14, lineHeight: 20, marginTop: 5 },
});
