import AsyncStorage from '@react-native-async-storage/async-storage';

import type {
  ChatMessage,
  ChatMessageStatus,
  LocalConversation,
  MessageRole,
} from '../types/tutor';

export const CONVERSATION_STORAGE_KEY = '@ai-tutor-kz/active-conversation';
export const STORAGE_SCHEMA_VERSION = 1;

export interface StoredConversationEnvelope {
  version: typeof STORAGE_SCHEMA_VERSION;
  conversation: LocalConversation;
}

export interface StorageLike {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
}

export interface ConversationLoadResult {
  conversation: LocalConversation | null;
  warning: string | null;
}

const roles = new Set<MessageRole>(['user', 'assistant']);
const statuses = new Set<ChatMessageStatus>([
  'sending',
  'streaming',
  'complete',
  'cancelled',
  'interrupted',
  'error',
]);

function isIsoDate(value: unknown): value is string {
  return typeof value === 'string' && !Number.isNaN(Date.parse(value));
}

function parseMessage(value: unknown): ChatMessage | null {
  if (typeof value !== 'object' || value === null) return null;
  const candidate = value as Partial<ChatMessage>;
  if (
    typeof candidate.id !== 'string' ||
    !candidate.id ||
    !roles.has(candidate.role as MessageRole) ||
    typeof candidate.text !== 'string' ||
    !statuses.has(candidate.status as ChatMessageStatus) ||
    !isIsoDate(candidate.createdAt)
  ) {
    return null;
  }
  return candidate as ChatMessage;
}

export function parseStoredConversation(raw: string | null): ConversationLoadResult {
  if (raw === null) return { conversation: null, warning: null };
  try {
    const envelope = JSON.parse(raw) as Partial<StoredConversationEnvelope>;
    if (envelope.version !== STORAGE_SCHEMA_VERSION) {
      return {
        conversation: null,
        warning: 'Локальная история имела неподдерживаемую версию и была очищена.',
      };
    }
    const candidate = envelope.conversation as Partial<LocalConversation> | undefined;
    if (
      !candidate ||
      typeof candidate.localConversationId !== 'string' ||
      !candidate.localConversationId ||
      (candidate.backendSessionId !== null &&
        typeof candidate.backendSessionId !== 'string') ||
      !Array.isArray(candidate.messages) ||
      !isIsoDate(candidate.createdAt) ||
      !isIsoDate(candidate.updatedAt) ||
      typeof candidate.serverContextValid !== 'boolean'
    ) {
      throw new Error('Stored conversation has invalid fields.');
    }
    const messages = candidate.messages.map(parseMessage);
    if (messages.some((message) => message === null)) {
      throw new Error('Stored conversation contains an invalid message.');
    }

    let interrupted = false;
    const restoredMessages = (messages as ChatMessage[]).map((message) => {
      if (message.status !== 'streaming' && message.status !== 'sending') return message;
      interrupted = true;
      return {
        ...message,
        text: message.text || 'Ответ не был получен.',
        status: 'interrupted' as const,
      };
    });

    return {
      conversation: {
        localConversationId: candidate.localConversationId,
        backendSessionId: candidate.backendSessionId,
        messages: restoredMessages,
        createdAt: candidate.createdAt,
        updatedAt: candidate.updatedAt,
        serverContextValid: interrupted ? false : candidate.serverContextValid,
      },
      warning: interrupted ? 'Предыдущий ответ был прерван при закрытии приложения.' : null,
    };
  } catch {
    return {
      conversation: null,
      warning: 'Повреждённая локальная история была очищена.',
    };
  }
}

export function serializeConversation(conversation: LocalConversation): string {
  const envelope: StoredConversationEnvelope = {
    version: STORAGE_SCHEMA_VERSION,
    conversation,
  };
  return JSON.stringify(envelope);
}

export async function loadConversation(
  storage: StorageLike = AsyncStorage,
): Promise<ConversationLoadResult> {
  const raw = await storage.getItem(CONVERSATION_STORAGE_KEY);
  const result = parseStoredConversation(raw);
  if (raw !== null && result.conversation === null) {
    await storage.removeItem(CONVERSATION_STORAGE_KEY);
  }
  return result;
}

export async function saveConversation(
  conversation: LocalConversation,
  storage: StorageLike = AsyncStorage,
): Promise<void> {
  await storage.setItem(
    CONVERSATION_STORAGE_KEY,
    serializeConversation(conversation),
  );
}

export async function clearConversation(
  storage: StorageLike = AsyncStorage,
): Promise<void> {
  await storage.removeItem(CONVERSATION_STORAGE_KEY);
}
