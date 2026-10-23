import { Pressable, StyleSheet, Text, View } from 'react-native';

interface Props {
  message: string;
  onRetry?: () => void;
}

export function ErrorBanner({ message, onRetry }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.text}>{message}</Text>
      {onRetry ? (
        <Pressable accessibilityRole="button" onPress={onRetry} style={styles.retry}>
          <Text style={styles.retryText}>Повторить</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: '#FFF0E8',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#E3B79E',
  },
  text: { flex: 1, color: '#703D26', fontSize: 13 },
  retry: { paddingHorizontal: 10, paddingVertical: 7, borderRadius: 8, backgroundColor: '#FFFFFF' },
  retryText: { color: '#2457D6', fontWeight: '700' },
});
