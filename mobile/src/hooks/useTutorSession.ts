import { randomUUID } from 'expo-crypto';
import { useCallback, useEffect, useReducer, useRef } from 'react';

import { TutorApiError } from '../api/client';
import {
  checkBackendHealth,
  checkOllamaHealth,
  createTutorSession,
  deleteTutorSession,
  getTutorSession,
  streamTutorMessage,
} from '../api/tutorApi';
import { environment } from '../config/environment';
import {
  clearConversation,
  loadConversation,
  saveConversation,
} from '../storage/conversationStorage';
import type { ChatMessage, LocalConversation, TutorStreamEvent } from '../types/tutor';
import {
  canStartGeneration,
  conversationFromState,
  initialTutorState,
  tutorReducer,
  type TutorState,
} from './chatState';
import { recoverBackendSession } from './sessionRecovery';

function makeMessageId(role: 'user' | 'assistant'): string {
  return `${role}-${randomUUID()}`;
}

function newLocalConversation(now = new Date().toISOString()): LocalConversation {
  return {
    localConversationId: randomUUID(), backendSessionId: null, messages: [],
    createdAt: now, updatedAt: now, serverContextValid: true,
  };
}

export function userMessageForError(error: unknown): string {
  if (!(error instanceof TutorApiError)) return 'Произошла неизвестная ошибка.';
  switch (error.code) {
    case 'INVALID_BACKEND_URL':
      return 'Адрес backend настроен неверно. Проверьте EXPO_PUBLIC_API_BASE_URL.';
    case 'NETWORK_ERROR':
      return 'Backend недоступен. Проверьте адрес и запущен ли FastAPI.';
    case 'BACKEND_UNHEALTHY':
      return 'Backend отвечает, но сообщает о проблеме состояния.';
    case 'REQUEST_TIMEOUT':
    case 'LLM_TIMEOUT':
      return 'Время ожидания ответа истекло. Автоматический повтор не выполнялся.';
    case 'OLLAMA_UNAVAILABLE':
      return 'Backend работает, но локальный сервис Ollama недоступен.';
    case 'MODEL_NOT_AVAILABLE':
      return 'Backend работает, но локальная модель сейчас недоступна.';
    case 'SESSION_NOT_FOUND':
      return 'Серверная сессия истекла или была удалена.';
    case 'MALFORMED_SSE':
    case 'LLM_RESPONSE_ERROR':
      return 'Сервер вернул повреждённый поток ответа.';
    case 'STREAM_INTERRUPTED':
      return 'Соединение прервалось до завершения ответа.';
    case 'CANCELLED':
      return 'Ответ остановлен пользователем.';
    default:
      return 'Не удалось получить ответ репетитора.';
  }
}

function developmentLog(event: string, details: Record<string, unknown> = {}) {
  if (__DEV__) console.info(`[tutor] ${event}`, details);
}

export function useTutorSession() {
  const [state, dispatch] = useReducer(tutorReducer, initialTutorState);
  const stateRef = useRef<TutorState>(state);
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  const hydratedRef = useRef(false);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const persist = useCallback(async (conversation: LocalConversation) => {
    try {
      await saveConversation(conversation);
    } catch (error) {
      developmentLog('conversation_persist_failed', { error: String(error) });
    }
  }, []);

  const connect = useCallback(async (conversation: LocalConversation) => {
    dispatch({ type: 'CONNECTING' });
    try {
      const recovery = await recoverBackendSession(
        conversation.backendSessionId,
        conversation.serverContextValid,
        conversation.messages.length > 0,
        {
          checkHealth: checkBackendHealth,
          getSession: getTutorSession,
          createSession: () => createTutorSession({ language: 'auto' }),
        },
      );
      if (!mountedRef.current) return;
      if (recovery.reused) {
        dispatch({
          type: 'SESSION_READY', sessionId: recovery.sessionId,
          backendVersion: recovery.backendVersion ?? undefined,
          connectionMs: recovery.connectionMs,
        });
      } else if (recovery.contextLost) {
        dispatch({ type: 'SESSION_REPLACED', sessionId: recovery.sessionId });
      } else {
        dispatch({
          type: 'SESSION_READY', sessionId: recovery.sessionId,
          backendVersion: recovery.backendVersion ?? undefined,
          connectionMs: recovery.connectionMs,
        });
      }
      await persist({
        ...conversation,
        backendSessionId: recovery.sessionId,
        serverContextValid: !recovery.contextLost,
        updatedAt: new Date().toISOString(),
      });
      developmentLog(recovery.reused ? 'session_reused' : 'session_created', {
        sessionId: recovery.sessionId, contextLost: recovery.contextLost,
      });
    } catch (error) {
      if (!mountedRef.current) return;
      const code = error instanceof TutorApiError ? error.code : 'UNKNOWN';
      dispatch({ type: 'CONNECTION_FAILED', message: userMessageForError(error), code });
      developmentLog('session_recovery_failed', { code });
    }
  }, [persist]);

  useEffect(() => {
    mountedRef.current = true;
    void (async () => {
      let loaded: Awaited<ReturnType<typeof loadConversation>>;
      try {
        loaded = await loadConversation();
      } catch {
        loaded = { conversation: null, warning: 'Не удалось прочитать локальную историю.' };
      }
      if (!mountedRef.current) return;
      const conversation = loaded.conversation ?? newLocalConversation();
      hydratedRef.current = true;
      dispatch({
        type: 'RESTORED', conversation, warning: loaded.warning,
        apiBaseUrl: environment.apiBaseUrl, apiUrlValid: environment.apiUrlValid,
      });
      await connect(conversation);
    })();
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, [connect]);

  useEffect(() => {
    if (!hydratedRef.current || state.phase === 'restoring' || state.phase === 'connecting' || state.phase === 'generating') return;
    void persist(conversationFromState(state));
  }, [persist, state]);

  const executeStream = useCallback(async (sessionId: string, text: string, assistantId: string) => {
    const controller = new AbortController();
    abortRef.current = controller;
    const startedAt = performance.now();
    let firstDeltaAt: number | null = null;
    try {
      await streamTutorMessage(sessionId, { message: text, mode: 'auto' }, {
        signal: controller.signal,
        onEvent: (event: TutorStreamEvent) => {
          if (!mountedRef.current) return;
          if (event.type === 'delta' && firstDeltaAt === null) {
            firstDeltaAt = performance.now();
            developmentLog('first_delta_received', { latencyMs: Math.round(firstDeltaAt - startedAt) });
          }
          dispatch({ type: 'STREAM_EVENT', assistantId, event });
        },
      });
      const total = Math.round(performance.now() - startedAt);
      dispatch({
        type: 'PERFORMANCE_RECORDED',
        firstDeltaMs: firstDeltaAt === null ? null : Math.round(firstDeltaAt - startedAt),
        totalGenerationMs: total,
      });
      developmentLog('stream_completed', { totalMs: total });
    } catch (error) {
      if (!mountedRef.current) return;
      if (error instanceof TutorApiError && error.code === 'CANCELLED') {
        dispatch({ type: 'STREAM_CANCELLED', assistantId });
      } else {
        const code = error instanceof TutorApiError ? error.code : 'UNKNOWN';
        dispatch({ type: 'STREAM_FAILED', assistantId, message: userMessageForError(error), code });
        if (code === 'SESSION_NOT_FOUND') {
          const created = await createTutorSession({ language: 'auto' });
          if (mountedRef.current) dispatch({ type: 'SESSION_REPLACED', sessionId: created.session_id });
        }
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, []);

  const sendMessage = useCallback(async (text: string): Promise<boolean> => {
    const current = stateRef.current;
    const trimmed = text.trim();
    if (!trimmed || abortRef.current !== null || !canStartGeneration(current) || !current.sessionId) return false;
    const now = new Date().toISOString();
    const user: ChatMessage = { id: makeMessageId('user'), role: 'user', text: trimmed, status: 'complete', createdAt: now };
    const assistant: ChatMessage = { id: makeMessageId('assistant'), role: 'assistant', text: '', status: 'streaming', createdAt: now };
    dispatch({ type: 'SEND_STARTED', user, assistant, at: now });
    await persist({ ...conversationFromState(current), messages: [...current.messages, user, assistant], updatedAt: now });
    void executeStream(current.sessionId, trimmed, assistant.id);
    return true;
  }, [executeStream, persist]);

  const retryMessage = useCallback(async (assistantId: string) => {
    const current = stateRef.current;
    if (!canStartGeneration(current) || abortRef.current) return;
    const index = current.messages.findIndex((message) => message.id === assistantId);
    const user = index > 0 ? current.messages[index - 1] : null;
    const assistant = current.messages[index];
    if (!user || user.role !== 'user' || !assistant || assistant.role !== 'assistant' || !['error', 'interrupted'].includes(assistant.status)) return;

    try {
      const created = await createTutorSession({ language: 'auto' });
      if (current.sessionId) void deleteTutorSession(current.sessionId).catch(() => undefined);
      dispatch({ type: 'SESSION_REPLACED', sessionId: created.session_id, message: 'Для безопасного повтора создана новая AI-сессия. Старый контекст не использован.' });
      const now = new Date().toISOString();
      dispatch({ type: 'RETRY_STARTED', assistantId, at: now });
      const messages = current.messages.map((message) => message.id === assistantId ? { ...message, text: '', status: 'streaming' as const } : message);
      await persist({ ...conversationFromState(current), backendSessionId: created.session_id, serverContextValid: false, messages, updatedAt: now });
      void executeStream(created.session_id, user.text, assistantId);
    } catch (error) {
      dispatch({ type: 'CONNECTION_FAILED', message: userMessageForError(error), code: error instanceof TutorApiError ? error.code : 'UNKNOWN' });
    }
  }, [executeStream, persist]);

  const cancelGeneration = useCallback(() => abortRef.current?.abort(), []);

  const newConversation = useCallback(async () => {
    abortRef.current?.abort();
    const oldSessionId = stateRef.current.sessionId;
    if (oldSessionId) await deleteTutorSession(oldSessionId).catch(() => undefined);
    await clearConversation().catch(() => undefined);
    const conversation = newLocalConversation();
    try {
      const created = await createTutorSession({ language: 'auto' });
      conversation.backendSessionId = created.session_id;
      dispatch({ type: 'NEW_CONVERSATION', conversation });
      await persist(conversation);
    } catch (error) {
      dispatch({ type: 'NEW_CONVERSATION', conversation });
      dispatch({ type: 'CONNECTION_FAILED', message: userMessageForError(error), code: error instanceof TutorApiError ? error.code : 'UNKNOWN' });
    }
  }, [persist]);

  const retryConnection = useCallback(async () => {
    const current = conversationFromState(stateRef.current);
    await connect(current);
  }, [connect]);

  const testConnection = useCallback(async () => {
    const started = performance.now();
    try {
      const health = await checkBackendHealth();
      dispatch({ type: 'DIAGNOSTICS_BACKEND', reachable: true, version: health.version, ms: Math.round(performance.now() - started) });
    } catch {
      dispatch({ type: 'DIAGNOSTICS_BACKEND', reachable: false, ms: Math.round(performance.now() - started) });
    }
  }, []);

  const testOllama = useCallback(async () => {
    try {
      await checkOllamaHealth();
      dispatch({ type: 'DIAGNOSTICS_OLLAMA', reachable: true });
    } catch {
      dispatch({ type: 'DIAGNOSTICS_OLLAMA', reachable: false });
    }
  }, []);

  return { state, retryConnection, sendMessage, retryMessage, cancelGeneration, newConversation, testConnection, testOllama };
}
