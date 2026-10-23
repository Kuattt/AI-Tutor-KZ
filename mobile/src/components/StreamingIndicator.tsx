import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

export function StreamingIndicator() {
  return (
    <View style={styles.container}>
      <ActivityIndicator size="small" color="#2457D6" />
      <Text style={styles.text}>Репетитор отвечает…</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 5 },
  text: { color: '#5F687A', fontSize: 13 },
});
