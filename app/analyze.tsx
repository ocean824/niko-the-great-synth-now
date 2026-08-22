import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";

import { ScreenContainer } from "@/components/screen-container";
import { selectAuthorizedAudio, uploadForAnalysis, type SelectedAudio } from "@/lib/audio-upload";

export default function AnalyzeScreen() {
  const [inputType, setInputType] = useState<"mix" | "stem">("mix");
  const [asset, setAsset] = useState<SelectedAudio | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  async function chooseAudio() {
    setMessage("");
    try {
      const selected = await selectAuthorizedAudio(inputType);
      if (selected) setAsset(selected);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Synth Now could not open that file.");
    }
  }

  async function submit() {
    if (!asset) return;
    setLoading(true);
    setMessage("");
    try {
      const job = await uploadForAnalysis(asset);
      router.replace({ pathname: "/analysis/[jobId]", params: { jobId: job.id } });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The analysis request could not be created.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <ScreenContainer edges={["top", "bottom", "left", "right"]} className="px-5">
      <ScrollView contentContainerStyle={styles.content}>
        <Pressable onPress={() => router.back()} style={({ pressed }) => [styles.back, pressed && styles.pressed]} accessibilityRole="button"><Text style={styles.backText}>‹ Back</Text></Pressable>
        <Text style={styles.eyebrow}>PRIVATE ANALYSIS</Text>
        <Text style={styles.title}>Choose an authorized sound.</Text>
        <Text style={styles.subtitle}>Upload only audio you own or have permission to analyze. Similarity results are not published production credits.</Text>
        <View style={styles.segmented}>
          {(["mix", "stem"] as const).map((option) => <Pressable key={option} onPress={() => { setInputType(option); setAsset(null); }} style={({ pressed }) => [styles.segment, inputType === option && styles.segmentActive, pressed && styles.pressed]}><Text style={[styles.segmentText, inputType === option && styles.segmentTextActive]}>{option === "mix" ? "Full mix" : "Separated stem"}</Text></Pressable>)}
        </View>
        <View style={styles.warning}><Text style={styles.warningTitle}>{inputType === "stem" ? "Separated stem caution" : "Full mix matching"}</Text><Text style={styles.warningCopy}>{inputType === "stem" ? "If source bleed is audible, Synth Now will cap the result as a similarity candidate and show an artifact warning." : "Full mixes can be evaluated for compatible recording-reference matching, but source evidence still governs historical claims."}</Text></View>
        <Pressable onPress={chooseAudio} style={({ pressed }) => [styles.pickButton, pressed && styles.pressed]} accessibilityRole="button"><Text style={styles.pickTitle}>{asset ? "Choose a different file" : "Choose audio file"}</Text><Text style={styles.pickSub}>{asset ? `${asset.name}${asset.size ? ` · ${Math.round(asset.size / 1024 / 1024)} MB` : ""}` : "Audio only · up to 25 MB"}</Text></Pressable>
        {message ? <Text style={styles.message}>{message}</Text> : null}
        <Pressable disabled={!asset || loading} onPress={submit} style={({ pressed }) => [styles.submit, (!asset || loading) && styles.disabled, pressed && styles.pressed]} accessibilityRole="button">
          {loading ? <ActivityIndicator color="#07111F" /> : <Text style={styles.submitText}>Start private analysis</Text>}
        </Pressable>
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: { paddingTop: 16, paddingBottom: 32, gap: 15 }, back: { alignSelf: "flex-start", paddingVertical: 8, paddingRight: 12 }, backText: { color: "#A8B7CA", fontSize: 15, fontWeight: "700" },
  eyebrow: { color: "#4CD3A7", fontSize: 11, fontWeight: "900", letterSpacing: 1.1, marginTop: 4 }, title: { color: "#F5FAFF", fontSize: 31, lineHeight: 36, fontWeight: "900", letterSpacing: -0.8 }, subtitle: { color: "#A8B7CA", fontSize: 15, lineHeight: 21 },
  segmented: { flexDirection: "row", gap: 8 }, segment: { flex: 1, paddingVertical: 13, alignItems: "center", borderRadius: 14, borderColor: "#294766", borderWidth: 1, backgroundColor: "#0C1B2D" }, segmentActive: { backgroundColor: "#1D4B68", borderColor: "#3CC6FF" }, segmentText: { color: "#A8B7CA", fontSize: 14, fontWeight: "800" }, segmentTextActive: { color: "#F5FAFF" },
  warning: { backgroundColor: "#281E0C", borderColor: "#80541A", borderWidth: 1, padding: 15, borderRadius: 18 }, warningTitle: { color: "#F6B64A", fontSize: 15, fontWeight: "900" }, warningCopy: { color: "#E7CFA8", lineHeight: 20, fontSize: 13, marginTop: 5 },
  pickButton: { backgroundColor: "#10233B", borderColor: "#3CC6FF", borderWidth: 1, borderStyle: "dashed", minHeight: 116, borderRadius: 20, padding: 18, justifyContent: "center" }, pickTitle: { color: "#F5FAFF", fontSize: 18, fontWeight: "900" }, pickSub: { color: "#A8B7CA", fontSize: 13, marginTop: 5 }, message: { color: "#FFB4BE", fontSize: 14, lineHeight: 20 },
  submit: { minHeight: 54, backgroundColor: "#3CC6FF", borderRadius: 17, alignItems: "center", justifyContent: "center", marginTop: 3 }, submitText: { color: "#07111F", fontWeight: "900", fontSize: 16 }, disabled: { opacity: 0.45 }, pressed: { opacity: 0.84, transform: [{ scale: 0.98 }] },
});
