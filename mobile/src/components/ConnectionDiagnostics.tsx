import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { ConnectionDiagnostics as Diagnostics } from '../types/tutor';

interface Props {
  diagnostics: Diagnostics;
  onTestConnection: () => void;
  onTestOllama: () => void;
}

function yesNo(value: boolean | null): string {
  return value === null ? 'не проверено' : value ? 'да' : 'нет';
}

export function ConnectionDiagnostics({ diagnostics, onTestConnection, onTestOllama }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Диагностика подключения</Text>
      <Text style={styles.line}>API: {diagnostics.apiBaseUrl || 'не задан'}</Text>
      <Text style={styles.line}>Адрес корректен: {yesNo(diagnostics.apiUrlValid)}</Text>
      <Text style={styles.line}>Backend доступен: {yesNo(diagnostics.backendReachable)}</Text>
      <Text style={styles.line}>Версия backend: {diagnostics.backendVersion ?? 'не сообщается'}</Text>
      <Text style={styles.line}>Сессия: {diagnostics.sessionId ?? 'нет'}</Text>
      <Text style={styles.line}>Серверный контекст: {yesNo(diagnostics.serverContextValid)}</Text>
      <Text style={styles.line}>Генерация активна: {yesNo(diagnostics.streamingActive)}</Text>
      <Text style={styles.line}>Ollama доступна: {yesNo(diagnostics.ollamaReachable)}</Text>
      <Text style={styles.line}>
        Время подключения: {diagnostics.lastConnectionMs === null ? '—' : `${diagnostics.lastConnectionMs} мс`}
      </Text>
      <Text style={styles.line}>
        Первый фрагмент / всего: {diagnostics.firstDeltaMs === null ? '—' : `${diagnostics.firstDeltaMs} мс`} / {diagnostics.totalGenerationMs === null ? '—' : `${diagnostics.totalGenerationMs} мс`}
      </Text>
      <View style={styles.actions}>
        <Pressable accessibilityRole="button" onPress={onTestConnection} style={styles.button}>
          <Text style={styles.buttonText}>Проверить backend</Text>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={onTestOllama} style={styles.secondaryButton}>
          <Text style={styles.secondaryButtonText}>Проверить модель</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 14, backgroundColor: '#EEF3FF', borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#B8C7E8' },
  heading: { color: '#172033', fontSize: 14, fontWeight: '700', marginBottom: 6 },
  line: { color: '#465169', fontSize: 12, lineHeight: 18 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10 },
  button: { backgroundColor: '#2457D6', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8 },
  buttonText: { color: '#FFFFFF', fontSize: 12, fontWeight: '700' },
  secondaryButton: { backgroundColor: '#FFFFFF', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, borderWidth: 1, borderColor: '#9DB0D7' },
  secondaryButtonText: { color: '#2457D6', fontSize: 12, fontWeight: '700' },
});
