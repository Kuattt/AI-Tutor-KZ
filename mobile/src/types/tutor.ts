export type TutorMode =
  | 'auto'
  | 'direct_explanation'
  | 'guided_solving'
  | 'answer_reveal_allowed';

export type MessageRole = 'user' | 'assistant';

export interface SessionMessage {
  role: MessageRole;
  content: string;
  created_at: string;
}

export interface CreateSessionRequest {
  language?: 'auto' | 'ru' | 'kk' | 'mixed';
  grade?: number | null;
}

export interface SessionCreatedResponse {
  session_id: string;
  created_at: string;
  mode: Exclude<TutorMode, 'auto'>;
}

export interface TutorSession {
  session_id: string;
  created_at: string;
  updated_at: string;
  mode: Exclude<TutorMode, 'auto'>;
  message_count: number;
  messages: SessionMessage[];
  metadata: Record<string, unknown>;
}

export interface TutorMessageRequest {
  message: string;
  mode?: TutorMode;
}

export interface ApiErrorData {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiErrorResponse {
  error: ApiErrorData;
}

export type TutorStreamEvent =
  | {
      type: 'start';
      data: { session_id: string; mode: Exclude<TutorMode, 'auto'> };
    }
  | { type: 'delta'; data: { text: string } }
  | {
      type: 'metadata';
      data: {
        mode: Exclude<TutorMode, 'auto'>;
        policy_reason: string;
        duration_seconds: number;
        first_token_seconds: number | null;
        prompt_tokens: number | null;
        generated_tokens: number | null;
      };
    }
  | { type: 'done'; data: { finish_reason: string } }
  | { type: 'error'; data: ApiErrorData };

export type ChatMessageStatus =
  | 'sending'
  | 'streaming'
  | 'complete'
  | 'cancelled'
  | 'interrupted'
  | 'error';

export interface ChatMessage {
  id: string;
  role: MessageRole;
  text: string;
  status: ChatMessageStatus;
  createdAt: string;
}

export interface LocalConversation {
  localConversationId: string;
  backendSessionId: string | null;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
  serverContextValid: boolean;
}

export interface ConnectionDiagnostics {
  apiBaseUrl: string;
  apiUrlValid: boolean;
  backendReachable: boolean | null;
  backendVersion: string | null;
  ollamaReachable: boolean | null;
  sessionId: string | null;
  serverContextValid: boolean;
  streamingActive: boolean;
  lastConnectionMs: number | null;
  firstDeltaMs: number | null;
  totalGenerationMs: number | null;
}
