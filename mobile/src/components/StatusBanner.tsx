import { StyleSheet, Text, View } from 'react-native';

export function StatusBanner({ message }: { message: string }) {
  return (
    <View style={styles.container}>
      <Text style={styles.text}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { paddingHorizontal: 14, paddingVertical: 9, backgroundColor: '#EAF1FF', borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#AFC2E8' },
  text: { color: '#29466F', fontSize: 13, lineHeight: 18 },
});
