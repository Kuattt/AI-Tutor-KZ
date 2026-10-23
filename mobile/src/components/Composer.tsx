import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

interface Props {
  isGenerating: boolean;
  isReady: boolean;
  onSend: (text: string) => Promise<boolean>;
  onStop: () => void;
}

export function Composer({ isGenerating, isReady, onSend, onStop }: Props) {
  const [text, setText] = useState('');
  const canSend = isReady && text.trim().length > 0;

  async function submit() {
    if (!canSend) return;
    const sent = await onSend(text);
    if (sent) setText('');
  }

  return (
    <View style={styles.container}>
      <TextInput
        accessibilityLabel="Сообщение ученика"
        multiline
        placeholder="Напишите вопрос…"
        placeholderTextColor="#7A8498"
        value={text}
        onChangeText={setText}
        style={styles.input}
        editable={isReady || isGenerating}
        maxLength={10_000}
      />
      {isGenerating ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Остановить ответ"
          onPress={onStop}
          style={[styles.button, styles.stopButton]}
        >
          <Text style={styles.buttonText}>Стоп</Text>
        </Pressable>
      ) : (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Отправить сообщение"
          disabled={!canSend}
          onPress={() => void submit()}
          style={[styles.button, !canSend && styles.disabledButton]}
        >
          <Text style={styles.buttonText}>Отправить</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#CCD2DE',
    backgroundColor: '#FFFFFF',
  },
  input: {
    flex: 1,
    minHeight: 44,
    maxHeight: 120,
    borderWidth: 1,
    borderColor: '#CBD2DF',
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingTop: 10,
    paddingBottom: 10,
    color: '#172033',
    fontSize: 16,
  },
  button: {
    minHeight: 44,
    justifyContent: 'center',
    borderRadius: 12,
    paddingHorizontal: 14,
    backgroundColor: '#2457D6',
  },
  stopButton: { backgroundColor: '#B43A3A' },
  disabledButton: { opacity: 0.4 },
  buttonText: { color: '#FFFFFF', fontSize: 14, fontWeight: '700' },
});
