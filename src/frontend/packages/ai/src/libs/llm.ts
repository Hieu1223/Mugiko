import { apiFetch, streamServerEvents } from '@mugiko/common'
import type { LLMJob, LLMJobStatusEvent, RecentLLMJob, Conversation, ConversationCreate, Message, ChatRequest, ChatResponse } from './types'

export const RECENT_JOBS_KEY = 'mugiko.llm.jobs'
const RECENT_LIMIT = 8

export async function createLLMJob(prompt: string): Promise<LLMJob> {
  return apiFetch<LLMJob>('/llm-jobs', { method: 'POST', body: { prompt } })
}

export async function getLLMJob(id: string, signal?: AbortSignal): Promise<LLMJob> {
  return apiFetch<LLMJob>(`/llm-jobs/${id}`, { signal })
}

/**
 * Follow LLM job status changes until the worker reaches a terminal status.
 * The server closes the stream after `completed` or `failed`.
 */
export async function streamLLMJobStatus(
  id: string,
  onStatus: (event: LLMJobStatusEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  await streamServerEvents(`/llm-jobs/${id}/status`, { signal }, (event) => {
    if (event.event !== 'status') return
    const parsed = parseStatusEvent<LLMJobStatusEvent>(event.data)
    if (parsed) onStatus(parsed)
  })
}

function parseStatusEvent<T>(data: string): T | null {
  try {
    return JSON.parse(data) as T
  } catch {
    return null
  }
}

export function readRecentJobs(): RecentLLMJob[] {
  try {
    const raw = window.localStorage.getItem(RECENT_JOBS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isRecentJob).slice(0, RECENT_LIMIT)
  } catch {
    return []
  }
}

export function rememberJob(job: LLMJob): RecentLLMJob[] {
  const entry: RecentLLMJob = {
    id: job.id,
    prompt: job.prompt,
    created_at: job.created_at,
  }
  const next = [entry, ...readRecentJobs().filter((item) => item.id !== job.id)].slice(
    0,
    RECENT_LIMIT,
  )
  try {
    window.localStorage.setItem(RECENT_JOBS_KEY, JSON.stringify(next))
  } catch {
    // Storage can be unavailable in private mode; recent jobs are optional.
  }
  return next
}

function isRecentJob(value: unknown): value is RecentLLMJob {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return (
    typeof record.id === 'string' &&
    typeof record.prompt === 'string' &&
    typeof record.created_at === 'string'
  )
}

// Chat API functions
export async function createConversation(payload: ConversationCreate): Promise<Conversation> {
  return apiFetch<Conversation>('/ai/conversations', { method: 'POST', body: payload })
}

export async function listConversations(limit = 20): Promise<Conversation[]> {
  return apiFetch<Conversation[]>(`/ai/conversations?limit=${limit}`)
}

export async function getConversation(id: string, messageLimit = 50, signal?: AbortSignal): Promise<Conversation> {
  return apiFetch<Conversation>(`/ai/conversations/${id}?message_limit=${messageLimit}`, { signal })
}

export async function deleteConversation(id: string): Promise<void> {
  return apiFetch<void>(`/ai/conversations/${id}`, { method: 'DELETE' })
}

export async function chatCompletion(payload: ChatRequest): Promise<ChatResponse> {
  return apiFetch<ChatResponse>('/ai/chat/completions', { method: 'POST', body: payload })
}

export async function addMessage(conversationId: string, role: string, content: string): Promise<Message> {
  return apiFetch<Message>(`/ai/conversations/${conversationId}/messages`, { method: 'POST', body: { role, content } })
}

export async function streamMessageProgress(
  conversationId: string,
  messageId: string,
  onEvent: (data: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  await streamServerEvents(`/ai/conversations/${conversationId}/messages/${messageId}/progress`, { signal }, (event) => {
    onEvent(event.data)
  })
}
