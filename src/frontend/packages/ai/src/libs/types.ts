/** Worker-side lifecycle of an LLM job. */
export type LLMJobStatus = 'queued' | 'processing' | 'completed' | 'failed'

export interface LLMJob {
  id: string
  prompt: string
  response?: string | null
  status: LLMJobStatus
  error?: string | null
  created_by: string
  created_at: string
  updated_at: string
}

/** One status update from the LLM SSE stream. */
export interface LLMJobStatusEvent {
  job_id: string
  status: LLMJobStatus
}

export interface RecentLLMJob {
  id: string
  prompt: string
  created_at: string
}

// Chat types
export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  error?: string | null
  assistant_message_id?: string | null
  metadata: Record<string, unknown>
  tokens?: number | null
  model?: string | null
  created_at: string
  updated_at: string
}

export interface Conversation {
  id: string
  user_id: string
  title?: string | null
  system_prompt?: string | null
  model?: string | null
  temperature?: number | null
  max_tokens?: number | null
  created_at: string
  updated_at: string
  messages?: Message[]
}

export interface ConversationCreate {
  title?: string
  system_prompt?: string
  model?: string
  temperature?: number
  max_tokens?: number
}

export interface ChatRequest {
  conversation_id?: string
  message: string
  model?: string
  temperature?: number
  max_tokens?: number
  system_prompt?: string
}

export interface ChatResponse {
  conversation_id: string
  user_message: Message
  assistant_message: Message
}
