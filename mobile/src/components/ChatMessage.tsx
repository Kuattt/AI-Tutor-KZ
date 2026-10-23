import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { ChatMessage as ChatMessageModel } from '../types/tutor';
import { TutorMarkdown } from './TutorMarkdown';

interface Props {
  message: ChatMessageModel;
  onRetry?: (messageId: string) => void;
}

export function ChatMessage({ message, onRetry }: Props) {
  const isUser = message.role === 'user';
  const statusLabel =
    message.status === 'cancelled'
      ? 'Остановлено'
      : message.status === 'interrupted'
        ? 'Ответ был прерван'
      : message.status === 'error'
        ? 'Ошибка ответа'
        : null;

  return (
    <View style={[styles.row, isUser ? styles.userRow : styles.assistantRow]}>
      <View style={[styles.bubble, isUser ? styles.userBubble : styles.assistantBubble]}>
        {isUser ? (
          <Text style={[styles.text, styles.userText]}>{message.text || '…'}</Text>
        ) : (
          <TutorMarkdown text={message.text} streaming={message.status === 'streaming'} />
        )}
        {statusLabel ? <Text style={styles.status}>{statusLabel}</Text> : null}
        {!isUser && ['error', 'interrupted'].includes(message.status) && onRetry ? (
          <Pressable accessibilityRole="button" onPress={() => onRetry(message.id)}>
            <Text style={styles.retry}>Повторить</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { width: '100%', marginVertical: 5 },
  userRow: { alignItems: 'flex-end' },
  assistantRow: { alignItems: 'flex-start' },
  bubble: { maxWidth: '86%', borderRadius: 16, paddingHorizontal: 14, paddingVertical: 10 },
  userBubble: { backgroundColor: '#2457D6', borderBottomRightRadius: 4 },
  assistantBubble: { backgroundColor: '#FFFFFF', borderBottomLeftRadius: 4 },
  text: { color: '#172033', fontSize: 16, lineHeight: 23 },
  userText: { color: '#FFFFFF' },
  status: { color: '#7D4A4A', fontSize: 12, marginTop: 5 },
  retry: { color: '#2457D6', fontSize: 13, fontWeight: '700', marginTop: 7 },
});
