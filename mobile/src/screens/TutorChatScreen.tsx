import { useCallback, useRef, useState } from 'react';
import {
  Alert,
  FlatList,
  KeyboardAvoidingView,
  NativeScrollEvent,
  NativeSyntheticEvent,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ChatMessage } from '../components/ChatMessage';
import { Composer } from '../components/Composer';
import { ConnectionDiagnostics } from '../components/ConnectionDiagnostics';
import { ErrorBanner } from '../components/ErrorBanner';
import { StatusBanner } from '../components/StatusBanner';
import { StreamingIndicator } from '../components/StreamingIndicator';
import { useTutorSession } from '../hooks/useTutorSession';

export function TutorChatScreen() {
  const {
    state, retryConnection, sendMessage, retryMessage, cancelGeneration,
    newConversation, testConnection, testOllama,
  } = useTutorSession();
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const listRef = useRef<FlatList>(null);
  const nearBottomRef = useRef(true);

  const onScroll = useCallback((event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent;
    nearBottomRef.current =
      contentSize.height - (contentOffset.y + layoutMeasurement.height) < 100;
  }, []);

  const status =
    state.phase === 'restoring'
      ? 'Восстановление истории…'
      : state.phase === 'connecting'
      ? 'Подключение…'
      : state.phase === 'offline'
        ? 'Backend недоступен'
        : state.phase === 'generating'
          ? 'Ответ формируется'
          : 'Подключено';

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.container}
      >
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>AI Tutor</Text>
            <Text style={[styles.status, state.phase === 'offline' && styles.offline]}>{status}</Text>
          </View>
          <View style={styles.headerActions}>
            <Pressable accessibilityRole="button" onPress={() => setShowDiagnostics((visible) => !visible)} style={styles.headerButton}>
              <Text style={styles.headerButtonText}>Диагностика</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => {
                if (state.messages.length === 0) void newConversation();
                else Alert.alert('Начать новый чат?', 'Текущая локальная история будет удалена.', [
                  { text: 'Отмена', style: 'cancel' },
                  { text: 'Новый чат', style: 'destructive', onPress: () => void newConversation() },
                ]);
              }}
              style={styles.headerButton}
            >
              <Text style={styles.headerButtonText}>Новый чат</Text>
            </Pressable>
          </View>
        </View>

        {showDiagnostics ? (
          <ConnectionDiagnostics diagnostics={state.diagnostics} onTestConnection={() => void testConnection()} onTestOllama={() => void testOllama()} />
        ) : null}

        {state.statusMessage ? <StatusBanner message={state.statusMessage} /> : null}

        {state.errorMessage ? (
          <ErrorBanner
            message={state.errorMessage}
            onRetry={state.phase === 'offline' ? () => void retryConnection() : undefined}
          />
        ) : null}

        <FlatList
          ref={listRef}
          data={state.messages}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => <ChatMessage message={item} onRetry={(id) => void retryMessage(id)} />}
          contentContainerStyle={styles.messages}
          keyboardShouldPersistTaps="handled"
          onScroll={onScroll}
          scrollEventThrottle={100}
          onContentSizeChange={() => {
            if (nearBottomRef.current) listRef.current?.scrollToEnd({ animated: true });
          }}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Text style={styles.emptyTitle}>Задайте учебный вопрос</Text>
              <Text style={styles.emptyText}>
                Ответ локальной модели будет появляться здесь постепенно.
              </Text>
            </View>
          }
          ListFooterComponent={
            state.phase === 'generating' ? <StreamingIndicator /> : null
          }
        />

        <Composer
          isGenerating={state.phase === 'generating'}
          isReady={state.phase === 'ready'}
          onSend={sendMessage}
          onStop={cancelGeneration}
        />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#F3F5F9' },
  container: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 18,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#CBD2DF',
  },
  title: { color: '#172033', fontSize: 22, fontWeight: '700' },
  status: { color: '#34714E', fontSize: 12, marginTop: 2 },
  offline: { color: '#A23A3A' },
  headerActions: { flexDirection: 'row', gap: 6 },
  headerButton: { paddingHorizontal: 8, paddingVertical: 7, borderRadius: 8, backgroundColor: '#EDF1F8' },
  headerButtonText: { color: '#345077', fontSize: 11, fontWeight: '700' },
  messages: { flexGrow: 1, paddingHorizontal: 12, paddingVertical: 10 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 28 },
  emptyTitle: { color: '#172033', fontSize: 18, fontWeight: '700', textAlign: 'center' },
  emptyText: { color: '#687286', fontSize: 14, lineHeight: 20, textAlign: 'center', marginTop: 8 },
});
