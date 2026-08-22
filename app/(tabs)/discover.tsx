import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { EvidenceBadge } from "@/components/synth/evidence-badge";
import { ScreenContainer } from "@/components/screen-container";
import { synthNowApi, type PresetSummary } from "@/lib/synth-now-api";

export default function DiscoverScreen() {
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<PresetSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("Search verified gear, official presets, or product history.");

  async function search() {
    const term = query.trim();
    if (!term) return;
    setLoading(true);
    setMessage("");
    try {
      const response = await synthNowApi.listPresets(term);
      setItems(response.items);
      if (!response.items.length) setMessage("No matching records are available yet. Try a maker, product, era, or preset name.");
    } catch (error) {
      setItems([]);
      setMessage(error instanceof Error ? error.message : "Search is temporarily unavailable.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <ScreenContainer className="px-5">
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.eyebrow}>DISCOVER</Text>
        <Text style={styles.title}>Find the gear behind a sound.</Text>
        <Text style={styles.subtitle}>Start with a maker, synth, VST, preset, artist, or recording. Results retain their evidence label.</Text>
        <View style={styles.searchRow}>
          <TextInput value={query} onChangeText={setQuery} placeholder="Try “Juno”, “Minimoog”, or a preset" placeholderTextColor="#6E849D" style={styles.input} returnKeyType="search" onSubmitEditing={search} />
          <Pressable onPress={search} style={({ pressed }) => [styles.searchButton, pressed && styles.pressed]} accessibilityRole="button"><Text style={styles.searchText}>Search</Text></Pressable>
        </View>
        {loading ? <ActivityIndicator color="#3CC6FF" style={{ marginTop: 24 }} /> : null}
        {message ? <View style={styles.message}><Text style={styles.messageText}>{message}</Text></View> : null}
        {items.map((item) => (
          <View key={item.id} style={styles.resultCard}>
            <EvidenceBadge kind={item.evidenceLabel === "similarity" ? "similarity" : item.evidenceLabel === "official" ? "official" : "verified"} />
            <Text style={styles.resultName}>{item.name}</Text>
            <Text style={styles.resultMeta}>{[item.maker, item.product].filter(Boolean).join(" · ") || "Canonical Synth Now record"}</Text>
          </View>
        ))}
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: { paddingTop: 18, paddingBottom: 32, gap: 14 }, eyebrow: { color: "#4CD3A7", fontSize: 11, fontWeight: "900", letterSpacing: 1.2 },
  title: { color: "#F5FAFF", fontSize: 30, lineHeight: 35, fontWeight: "900", letterSpacing: -0.7 }, subtitle: { color: "#A8B7CA", fontSize: 15, lineHeight: 21 },
  searchRow: { flexDirection: "row", gap: 8, marginTop: 5 }, input: { flex: 1, minHeight: 50, color: "#F5FAFF", backgroundColor: "#10233B", borderColor: "#294766", borderWidth: 1, borderRadius: 15, paddingHorizontal: 14, fontSize: 14 },
  searchButton: { minHeight: 50, justifyContent: "center", paddingHorizontal: 15, backgroundColor: "#3CC6FF", borderRadius: 15 }, searchText: { color: "#07111F", fontWeight: "900" }, pressed: { opacity: 0.82 },
  message: { marginTop: 8, borderColor: "#294766", borderWidth: 1, borderRadius: 16, padding: 15, backgroundColor: "#0C1B2D" }, messageText: { color: "#A8B7CA", fontSize: 14, lineHeight: 20 },
  resultCard: { backgroundColor: "#10233B", borderWidth: 1, borderColor: "#294766", borderRadius: 18, padding: 15, gap: 8 }, resultName: { color: "#F5FAFF", fontSize: 17, fontWeight: "800" }, resultMeta: { color: "#A8B7CA", fontSize: 13 },
});
