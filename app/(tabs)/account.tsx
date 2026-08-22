import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { ScreenContainer } from "@/components/screen-container";

export default function AccountScreen() {
  return (
    <ScreenContainer className="px-5">
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.eyebrow}>ACCOUNT</Text>
        <Text style={styles.title}>Your access, on your terms.</Text>
        <View style={styles.card}><Text style={styles.cardTitle}>Subscription readiness</Text><Text style={styles.cardCopy}>Native subscriptions use approved iOS and Android product IDs. A secure Worker reconciles each provider event into one entitlement record.</Text><Pressable style={({ pressed }) => [styles.button, pressed && styles.pressed]} accessibilityRole="button"><Text style={styles.buttonText}>View plans when available</Text></Pressable></View>
        <View style={styles.row}><Text style={styles.rowTitle}>Privacy</Text><Text style={styles.rowCopy}>Authorized clips are private and follow a defined R2 retention policy.</Text></View>
        <View style={styles.row}><Text style={styles.rowTitle}>Email</Text><Text style={styles.rowCopy}>Transactional account and analysis messages send through a verified Synth Now domain via Resend.</Text></View>
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: { paddingTop: 18, paddingBottom: 32, gap: 14 }, eyebrow: { color: "#F6B64A", fontSize: 11, letterSpacing: 1.2, fontWeight: "900" },
  title: { color: "#F5FAFF", fontSize: 30, lineHeight: 35, fontWeight: "900", letterSpacing: -0.7 }, card: { backgroundColor: "#10233B", borderColor: "#294766", borderWidth: 1, borderRadius: 20, padding: 18, gap: 8, marginTop: 4 },
  cardTitle: { color: "#F5FAFF", fontSize: 18, fontWeight: "800" }, cardCopy: { color: "#A8B7CA", fontSize: 14, lineHeight: 20 }, button: { marginTop: 8, alignSelf: "flex-start", minHeight: 42, justifyContent: "center", backgroundColor: "#F6B64A", borderRadius: 12, paddingHorizontal: 14 }, buttonText: { color: "#281700", fontWeight: "900", fontSize: 13 }, pressed: { opacity: 0.82 },
  row: { backgroundColor: "#0C1B2D", borderColor: "#294766", borderWidth: 1, borderRadius: 18, padding: 16 }, rowTitle: { color: "#F5FAFF", fontSize: 15, fontWeight: "800" }, rowCopy: { color: "#A8B7CA", fontSize: 13, lineHeight: 19, marginTop: 5 },
});
