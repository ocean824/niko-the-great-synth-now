import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";

import { ConfidenceCard } from "@/components/synth/confidence-card";
import { EvidenceBadge } from "@/components/synth/evidence-badge";
import { ScreenContainer } from "@/components/screen-container";
import { synthNowApi, type AnalysisStatus } from "@/lib/synth-now-api";

export default function AnalysisResultScreen() {
  const { jobId } = useLocalSearchParams<{ jobId: string }>();
  const [job, setJob] = useState<AnalysisStatus | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!jobId) return;
    try {
      setError("");
      setJob(await synthNowApi.getAnalysis(jobId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The analysis result is unavailable.");
    }
  }, [jobId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!job || !["awaiting_upload", "queued", "running"].includes(job.state)) return;
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [job, load]);

  const inProgress = !job || ["awaiting_upload", "queued", "running"].includes(job.state);
  const sourceBleed = job?.artifactFlags?.includes("source_bleed");

  return (
    <ScreenContainer edges={["top", "bottom", "left", "right"]} className="px-5">
      <ScrollView contentContainerStyle={styles.content}>
        <Pressable onPress={() => router.replace("/(tabs)")} style={({ pressed }) => [styles.back, pressed && styles.pressed]} accessibilityRole="button"><Text style={styles.backText}>‹ Today</Text></Pressable>
        <Text style={styles.eyebrow}>ANALYSIS RESULT</Text>
        {inProgress ? <View style={styles.progress}><ActivityIndicator color="#3CC6FF" /><Text style={styles.progressTitle}>{job?.state === "queued" ? "Your analysis is queued" : "Preparing your analysis"}</Text><Text style={styles.progressCopy}>Synth Now checks the private upload, runs the authorized analysis path, and keeps audio inference separate from historical production claims.</Text></View> : null}
        {error ? <View style={styles.error}><Text style={styles.errorText}>{error}</Text><Pressable onPress={load} style={({ pressed }) => [styles.retry, pressed && styles.pressed]}><Text style={styles.retryText}>Try again</Text></Pressable></View> : null}
        {job?.state === "completed" ? <>
          {sourceBleed ? <View style={styles.bleed}><EvidenceBadge kind="limited" /><Text style={styles.bleedTitle}>Approximate separated stem</Text><Text style={styles.bleedCopy}>Source bleed was detected. Any result below is a similarity candidate, not a confirmed original instrument, VST, or preset.</Text></View> : null}
          <EvidenceBadge kind={job.resultKind === "recording_match" ? "verified" : job.resultKind === "similarity_candidate" ? "similarity" : "official"} />
          <Text style={styles.resultTitle}>{job.resultKind === "recording_match" ? "Compatible recording match" : job.resultKind === "similarity_candidate" ? "Similarity candidate" : "No confident candidate"}</Text>
          <Text style={styles.resultCopy}>{job.historicalClaimAllowed ? "This response may link to an already verified evidence record." : "This response cannot create or verify a historical production claim. Open source-backed gear pages for documented uses."}</Text>
          {job.confidence ? <ConfidenceCard confidence={job.confidence} /> : null}
        </> : null}
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: { paddingTop: 16, paddingBottom: 32, gap: 15 }, back: { alignSelf: "flex-start", paddingVertical: 8, paddingRight: 12 }, backText: { color: "#A8B7CA", fontSize: 15, fontWeight: "700" }, eyebrow: { color: "#4CD3A7", fontSize: 11, letterSpacing: 1.1, fontWeight: "900" },
  progress: { backgroundColor: "#10233B", borderColor: "#294766", borderWidth: 1, borderRadius: 20, padding: 20, gap: 10 }, progressTitle: { color: "#F5FAFF", fontSize: 19, fontWeight: "900" }, progressCopy: { color: "#A8B7CA", fontSize: 14, lineHeight: 20 },
  bleed: { backgroundColor: "#281E0C", borderColor: "#80541A", borderWidth: 1, borderRadius: 20, padding: 16, gap: 8 }, bleedTitle: { color: "#F6B64A", fontSize: 17, fontWeight: "900" }, bleedCopy: { color: "#E7CFA8", lineHeight: 20, fontSize: 14 },
  resultTitle: { color: "#F5FAFF", fontSize: 27, fontWeight: "900", lineHeight: 32, marginTop: -6 }, resultCopy: { color: "#A8B7CA", fontSize: 15, lineHeight: 22 },
  error: { backgroundColor: "#351821", borderColor: "#8D3342", borderWidth: 1, borderRadius: 18, padding: 16, gap: 10 }, errorText: { color: "#FFB4BE", fontSize: 14, lineHeight: 20 }, retry: { alignSelf: "flex-start", paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10, backgroundColor: "#FF6B7D" }, retryText: { color: "#301019", fontWeight: "900", fontSize: 13 }, pressed: { opacity: 0.84, transform: [{ scale: 0.98 }] },
});
