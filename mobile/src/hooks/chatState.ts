import type {
  ChatMessage,
  ConnectionDiagnostics,
  LocalConversation,
  TutorStreamEvent,
} from '../types/tutor';

export type TutorPhase = 'restoring' | 'connecting' | 'ready' | 'generating' | 'offline';

export interface TutorState {
  localConversationId: string;
  createdAt: string;
  updatedAt: string;
  sessionId: string | null;
  phase: TutorPhase;
  messages: ChatMessage[];
  activeAssistantId: string | null;
  errorMessage: string | null;
  errorCode: string | null;
  statusMessage: string | null;
  contextReset: boolean;
  serverContextValid: boolean;
  diagnostics: ConnectionDiagnostics;
}

export const initialTutorState: TutorState = {
  localConversationId: '', createdAt: '', updatedAt: '', sessionId: null,
  phase: 'restoring', messages: [], activeAssistantId: null,
  errorMessage: null, errorCode: null, statusMessage: null,
  contextReset: false, serverContextValid: true,
  diagnostics: {
    apiBaseUrl: '', apiUrlValid: true, backendReachable: null,
    backendVersion: null, ollamaReachable: null, sessionId: null,
    serverContextValid: true, streamingActive: false,
    lastConnectionMs: null, firstDeltaMs: null, totalGenerationMs: null,
  },
};

export type TutorAction =
  | { type: 'RESTORED'; conversation: LocalConversation; warning: string | null; apiBaseUrl: string; apiUrlValid: boolean }
  | { type: 'CONNECTING' }
  | { type: 'SESSION_READY'; sessionId: string; backendVersion?: string; connectionMs?: number }
  | { type: 'SESSION_REPLACED'; sessionId: string; message?: string }
  | { type: 'CONNECTION_FAILED'; message: string; code?: string }
  | { type: 'SEND_STARTED'; user: ChatMessage; assistant: ChatMessage; at: string }
  | { type: 'RETRY_STARTED'; assistantId: string; at: string }
  | { type: 'STREAM_EVENT'; assistantId: string; event: TutorStreamEvent }
  | { type: 'STREAM_FAILED'; assistantId: string; message: string; code?: string }
  | { type: 'STREAM_CANCELLED'; assistantId: string }
  | { type: 'PERFORMANCE_RECORDED'; firstDeltaMs: number | null; totalGenerationMs: number }
  | { type: 'DIAGNOSTICS_BACKEND'; reachable: boolean; version?: string; ms?: number }
  | { type: 'DIAGNOSTICS_OLLAMA'; reachable: boolean }
  | { type: 'NEW_CONVERSATION'; conversation: LocalConversation };

function updateMessage(messages: ChatMessage[], id: string, update: (message: ChatMessage) => ChatMessage): ChatMessage[] {
  return messages.map((message) => (message.id === id ? update(message) : message));
}

function withDiagnostics(state: TutorState): TutorState {
  return {
    ...state,
    diagnostics: {
      ...state.diagnostics,
      sessionId: state.sessionId,
      serverContextValid: state.serverContextValid,
      streamingActive: state.phase === 'generating',
    },
  };
}

export function conversationFromState(state: TutorState): LocalConversation {
  return {
    localConversationId: state.localConversationId,
    backendSessionId: state.sessionId,
    messages: state.messages,
    createdAt: state.createdAt,
    updatedAt: state.updatedAt,
    serverContextValid: state.serverContextValid,
  };
}

export function canStartGeneration(state: TutorState): boolean {
  return state.phase === 'ready' && state.sessionId !== null;
}

export function tutorReducer(state: TutorState, action: TutorAction): TutorState {
  let next: TutorState;
  switch (action.type) {
    case 'RESTORED':
      next = {
        ...state,
        localConversationId: action.conversation.localConversationId,
        createdAt: action.conversation.createdAt,
        updatedAt: action.conversation.updatedAt,
        messages: action.conversation.messages,
        sessionId: action.conversation.backendSessionId,
        phase: 'connecting', activeAssistantId: null,
        statusMessage: action.warning,
        serverContextValid: action.conversation.serverContextValid,
        diagnostics: { ...state.diagnostics, apiBaseUrl: action.apiBaseUrl, apiUrlValid: action.apiUrlValid },
      };
      break;
    case 'CONNECTING':
      next = { ...state, phase: 'connecting', errorMessage: null, errorCode: null };
      break;
    case 'SESSION_READY':
      next = {
        ...state, sessionId: action.sessionId, phase: 'ready',
        errorMessage: null, errorCode: null, contextReset: false,
        diagnostics: {
          ...state.diagnostics, backendReachable: true,
          backendVersion: action.backendVersion ?? state.diagnostics.backendVersion,
          lastConnectionMs: action.connectionMs ?? state.diagnostics.lastConnectionMs,
        },
      };
      break;
    case 'SESSION_REPLACED':
      next = {
        ...state, sessionId: action.sessionId, phase: 'ready', activeAssistantId: null,
        errorMessage: null, errorCode: null,
        statusMessage: action.message ?? 'Создана новая AI-сессия. Предыдущие сообщения видны только локально.',
        contextReset: state.messages.length > 0,
        serverContextValid: state.messages.length === 0,
      };
      break;
    case 'CONNECTION_FAILED':
      next = {
        ...state, phase: 'offline', errorMessage: action.message,
        errorCode: action.code ?? null,
        diagnostics: { ...state.diagnostics, backendReachable: false },
      };
      break;
    case 'SEND_STARTED':
      if (!canStartGeneration(state)) return state;
      next = {
        ...state, phase: 'generating', activeAssistantId: action.assistant.id,
        errorMessage: null, errorCode: null, updatedAt: action.at,
        messages: [...state.messages, action.user, action.assistant],
      };
      break;
    case 'RETRY_STARTED':
      if (!canStartGeneration(state)) return state;
      next = {
        ...state, phase: 'generating', activeAssistantId: action.assistantId,
        errorMessage: null, errorCode: null, updatedAt: action.at,
        messages: updateMessage(state.messages, action.assistantId, (message) => ({ ...message, text: '', status: 'streaming' })),
      };
      break;
    case 'STREAM_EVENT':
      if (action.event.type === 'delta') {
        const deltaText = action.event.data.text;
        next = { ...state, messages: updateMessage(state.messages, action.assistantId, (message) => ({ ...message, text: message.text + deltaText, status: 'streaming' })) };
        break;
      }
      if (action.event.type === 'done') {
        next = { ...state, phase: 'ready', activeAssistantId: null, messages: updateMessage(state.messages, action.assistantId, (message) => ({ ...message, status: 'complete' })) };
        break;
      }
      if (action.event.type === 'error') {
        return tutorReducer(state, { type: 'STREAM_FAILED', assistantId: action.assistantId, message: action.event.data.message, code: action.event.data.code });
      }
      return state;
    case 'STREAM_FAILED':
      next = {
        ...state, phase: state.sessionId ? 'ready' : 'offline', activeAssistantId: null,
        errorMessage: action.message, errorCode: action.code ?? null,
        messages: updateMessage(state.messages, action.assistantId, (message) => ({ ...message, status: 'error' })),
      };
      break;
    case 'STREAM_CANCELLED':
      next = {
        ...state, phase: state.sessionId ? 'ready' : 'offline', activeAssistantId: null,
        messages: updateMessage(state.messages, action.assistantId, (message) => ({ ...message, text: message.text || 'Ответ остановлен.', status: 'cancelled' })),
      };
      break;
    case 'PERFORMANCE_RECORDED':
      next = { ...state, diagnostics: { ...state.diagnostics, firstDeltaMs: action.firstDeltaMs, totalGenerationMs: action.totalGenerationMs } };
      break;
    case 'DIAGNOSTICS_BACKEND':
      next = { ...state, diagnostics: { ...state.diagnostics, backendReachable: action.reachable, backendVersion: action.version ?? state.diagnostics.backendVersion, lastConnectionMs: action.ms ?? state.diagnostics.lastConnectionMs } };
      break;
    case 'DIAGNOSTICS_OLLAMA':
      next = { ...state, diagnostics: { ...state.diagnostics, ollamaReachable: action.reachable } };
      break;
    case 'NEW_CONVERSATION':
      next = {
        ...initialTutorState,
        localConversationId: action.conversation.localConversationId,
        createdAt: action.conversation.createdAt,
        updatedAt: action.conversation.updatedAt,
        messages: action.conversation.messages,
        sessionId: action.conversation.backendSessionId,
        phase: action.conversation.backendSessionId ? 'ready' : 'connecting',
        diagnostics: { ...state.diagnostics, sessionId: action.conversation.backendSessionId, serverContextValid: true, streamingActive: false },
      };
      break;
  }
  return withDiagnostics(next);
}
