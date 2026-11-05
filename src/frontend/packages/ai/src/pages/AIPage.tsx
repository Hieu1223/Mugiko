import { useEffect, useState, useCallback } from 'react'
import {
  Button,
  ErrorState,
  InlineNotice,
  Input,
  Link,
  LoadingState,
  PageTitle,
  Textarea,
  errorDetail,
  relativeDate,
  shortId,
  truncate,
  useDocumentTitle,
  useSearchParams,
  useToast,
  Select,
} from '@mugiko/common'
import {
  createLLMJob,
  getLLMJob,
  readRecentJobs,
  rememberJob,
  streamLLMJobStatus,
  createConversation,
  listConversations,
  getConversation,
  deleteConversation,
  addMessage,
  streamMessageProgress,
} from '../libs/llm'
import type {
  LLMJob,
  LLMJobStatus,
  RecentLLMJob,
  Conversation,
  Message,
} from '../libs/types'

const STATUS_LABELS: Record<LLMJobStatus, string> = {
  queued: 'Queued',
  processing: 'Processing',
  completed: 'Completed',
  failed: 'Failed',
}

export function AIPage() {
  useDocumentTitle('AI')
  const { toast } = useToast()
  const [params, setParams] = useSearchParams()
  const jobId = params.get('jobId')?.trim() || ''
  const conversationId = params.get('conversationId')?.trim() || ''

  // View mode: 'jobs' (old LLM jobs) or 'chat' (new chat)
  const [viewMode, setViewMode] = useState<'jobs' | 'chat'>(jobId ? 'jobs' : 'chat')

  // LLM Jobs state
  const [prompt, setPrompt] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [lookupId, setLookupId] = useState('')
  const [recent, setRecent] = useState<RecentLLMJob[]>([])
  const [job, setJob] = useState<LLMJob | null>(null)
  const [loadingJob, setLoadingJob] = useState(false)
  const [jobError, setJobError] = useState<string | null>(null)
  const [detailNonce, setDetailNonce] = useState(0)
  const [liveStatus, setLiveStatus] = useState<LLMJobStatus | null>(null)
  const [streamState, setStreamState] = useState<'idle' | 'live' | 'reconnecting'>('idle')

  // Chat state
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null)
  const [chatInput, setChatInput] = useState('')
  const [chatSending, setChatSending] = useState(false)
  const [chatError, setChatError] = useState<string | null>(null)
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null)
  const [streamAbort, setStreamAbort] = useState<AbortController | null>(null)
  const [newConvTitle, setNewConvTitle] = useState('')
  const [showNewConv, setShowNewConv] = useState(false)

  useEffect(() => {
    setRecent(readRecentJobs())
  }, [])

  // Load conversations for chat view
  useEffect(() => {
    if (viewMode === 'chat') {
      loadConversations()
    }
  }, [viewMode])

  const loadConversations = async () => {
    try {
      const convs = await listConversations(20)
      setConversations(convs)
      if (conversationId) {
        const conv = convs.find(c => c.id === conversationId)
        if (conv) {
          await loadConversation(conv.id)
        }
      } else if (convs.length > 0 && !activeConversation) {
        await loadConversation(convs[0].id)
      }
    } catch (err) {
      setChatError(errorDetail(err))
    }
  }

  const loadConversation = async (id: string) => {
    try {
      setChatError(null)
      const conv = await getConversation(id, 50)
      setActiveConversation(conv)
      setParams({ ...params, conversationId: conv.id }, { replace: true })
    } catch (err) {
      setChatError(errorDetail(err))
    }
  }

  const startNewConversation = async () => {
    if (!newConvTitle.trim()) {
      setChatError('Enter a conversation title.')
      return
    }
    setChatSending(true)
    setChatError(null)
    try {
      const conv = await createConversation({
        title: newConvTitle,
      })
      setNewConvTitle('')
      setShowNewConv(false)
      setConversations([conv, ...conversations])
      await loadConversation(conv.id)
    } catch (err) {
      setChatError(errorDetail(err))
    } finally {
      setChatSending(false)
    }
  }

  const handleChatSubmit = async () => {
    const text = chatInput.trim()
    if (!text || !activeConversation || chatSending || streamingMessageId) return

    setChatSending(true)
    setChatError(null)
    const userMessage = text
    setChatInput('')

    try {
      const created = await addMessage(activeConversation.id, 'user', userMessage)
      // Optimistically show the user message while the assistant streams.
      const optimistic: Message = {
        ...created,
        content: userMessage,
        status: 'queued',
      }
      setActiveConversation((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          messages: [...(prev.messages || []), optimistic],
        }
      })

      setStreamingMessageId(created.id)
      const controller = new AbortController()
      setStreamAbort(controller)

      // Stream progress via SSE; fall back to DB reconciliation on close/failure.
      streamMessageProgress(activeConversation.id, created.id, (data) => {
        let parsed: any = null
        try {
          parsed = JSON.parse(data)
        } catch {
          return
        }
        if (parsed.status === 'completed') {
          setStreamAbort(null)
          setStreamingMessageId(null)
          loadConversation(activeConversation!.id)
        } else if (parsed.status === 'failed') {
          setStreamAbort(null)
          setStreamingMessageId(null)
          setChatError(parsed.error || 'The assistant message failed.')
          setChatSending(false)
        }
      }, controller.signal)
        .catch((err) => {
          if (controller.signal.aborted) return
          // Stream closed without a terminal status — reconcile from the DB.
          setStreamAbort(null)
          reconcileStreamingMessage(activeConversation!.id, created.id)
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setStreamAbort(null)
            setStreamingMessageId(null)
          }
        })
    } catch (err) {
      setChatError(errorDetail(err))
      setChatInput(userMessage)
    } finally {
      setChatSending(false)
    }
  }

  const reconcileStreamingMessage = async (conversationId: string, messageId: string) => {
    // Poll the DB a few times for a terminal status before giving up.
    for (let i = 0; i < 6; i++) {
      await new Promise((r) => setTimeout(r, 1500))
      try {
        const conv = await getConversation(conversationId, 50)
        setActiveConversation(conv)
        const msg = (conv.messages || []).find((m) => m.id === messageId)
        if (msg && (msg.status === 'completed' || msg.status === 'failed')) {
          if (msg.status === 'failed') {
            setChatError(msg.error || 'The assistant message failed.')
          }
          return
        }
      } catch {
        // Keep retrying.
      }
    }
    setChatError('The assistant message did not reach a terminal status.')
  }

  const deleteConv = async (id: string) => {
    try {
      await deleteConversation(id)
      setConversations(conversations.filter(c => c.id !== id))
      if (activeConversation?.id === id) {
        const next = conversations.find(c => c.id !== id)
        if (next) {
          await loadConversation(next.id)
        } else {
          setActiveConversation(null)
          setParams({}, { replace: true })
        }
      }
      toast('Conversation deleted.', 'success')
    } catch (err) {
      setChatError(errorDetail(err))
    }
  }

  // LLM Jobs logic
  const status = liveStatus ?? job?.status ?? null
  const isWorking = status === 'queued' || status === 'processing'
  const visibleJob = job && job.id === jobId ? job : null

  useEffect(() => {
    if (!jobId) {
      setJob(null)
      setJobError(null)
      setLiveStatus(null)
      setLoadingJob(false)
      return
    }

    const controller = new AbortController()
    let alive = true
    setLoadingJob(true)
    setJobError(null)

    getLLMJob(jobId, controller.signal)
      .then((data) => {
        if (!alive) return
        setJob(data)
        setLiveStatus(data.status)
        setPrompt(data.prompt)
      })
      .catch((err) => {
        if (!alive || controller.signal.aborted) return
        setJobError(errorDetail(err))
      })
      .finally(() => {
        if (alive) setLoadingJob(false)
      })

    return () => {
      alive = false
      controller.abort()
    }
  }, [jobId, detailNonce])

  useEffect(() => {
    if (!jobId || !isWorking) {
      setStreamState('idle')
      return
    }

    const controller = new AbortController()
    let alive = true
    let retry = 0
    let timer: number | undefined

    const scheduleReconnect = () => {
      if (!alive) return
      setStreamState('reconnecting')
      timer = window.setTimeout(connect, Math.min(1000 * 2 ** retry, 15000))
      retry += 1
    }

    const connect = () => {
      if (!alive) return
      setStreamState(retry === 0 ? 'live' : 'reconnecting')

      streamLLMJobStatus(
        jobId,
        (event) => {
          if (!alive || event.job_id !== jobId) return
          retry = 0
          setStreamState('live')
          setLiveStatus(event.status)
          if (event.status === 'completed' || event.status === 'failed') {
            setDetailNonce((value) => value + 1)
          }
        },
        controller.signal,
      )
        .then(() => scheduleReconnect())
        .catch((err) => {
          if (!alive || controller.signal.aborted) return
          if (err instanceof DOMException && err.name === 'AbortError') return
          scheduleReconnect()
        })
    }

    connect()

    return () => {
      alive = false
      controller.abort()
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [jobId, isWorking])

  useEffect(() => {
    if (!jobId || !isWorking) return
    const timer = window.setInterval(() => setDetailNonce((value) => value + 1), 20000)
    return () => window.clearInterval(timer)
  }, [jobId, isWorking])

  const submitJob = async () => {
    const text = prompt.trim()
    if (!text) {
      setCreateError('Enter a prompt first.')
      return
    }

    setCreating(true)
    setCreateError(null)
    try {
      const created = await createLLMJob(text)
      setRecent(rememberJob(created))
      setJob(created)
      setLiveStatus(created.status)
      setDetailNonce(0)
      setParams({ jobId: created.id })
    } catch (err) {
      setCreateError(errorDetail(err))
    } finally {
      setCreating(false)
    }
  }

  const newJob = () => {
    setParams({}, { replace: true })
    setPrompt('')
    setJob(null)
    setJobError(null)
    setLiveStatus(null)
    setCreateError(null)
    setDetailNonce(0)
  }

  const loadById = () => {
    const id = lookupId.trim()
    if (!id) return
    setParams({ jobId: id })
    setLookupId('')
  }

  const copyResponse = async () => {
    if (!visibleJob?.response) return
    try {
      await navigator.clipboard.writeText(visibleJob.response)
      toast('Response copied.', 'success')
    } catch {
      toast('Could not copy the response.', 'error')
    }
  }

  return (
    <div className="page">
      <PageTitle
        title="AI"
        actions={
          <>
            <Select
              value={viewMode}
              onChange={(e) => setViewMode(e.target.value as "jobs" | "chat")}
              style={{ width: 140, marginRight: 12 }}
            >
              <option value="chat">Chat</option>
              <option value="jobs">LLM Jobs</option>
            </Select>
            {viewMode === 'jobs' && jobId && <Button onClick={newJob}>New job</Button>}
            {viewMode === 'chat' && (
              <Select
                value="nvidia/nemotron-3-ultra-550b-a55b"
                disabled
                style={{ width: 200, marginRight: 12 }}
              >
                <option value="nvidia/nemotron-3-ultra-550b-a55b">Nemotron 3 Ultra 550B</option>
              </Select>
            )}
          </>
        }
      />

      {viewMode === 'jobs' && (
        <>
          {!jobId && (
            <>
              <p className="muted">
                Send a prompt to the NIM worker. Jobs run in the background, and this page
                follows their status live.
              </p>

              <div className="stack">
                <Textarea
                  label="Prompt"
                  hint="The worker sends this to the configured NIM model."
                  rows={7}
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  disabled={creating}
                  placeholder="Explain the difference between は and が with examples."
                />
                {createError && (
                  <InlineNotice tone="error" onDismiss={() => setCreateError(null)}>
                    {createError}
                  </InlineNotice>
                )}
                <div className="form-row">
                  <Button
                    variant="primary"
                    loading={creating}
                    disabled={!prompt.trim()}
                    onClick={submitJob}
                  >
                    Generate
                  </Button>
                </div>
              </div>

              <hr />

              <h2>Load a job</h2>
              <div className="form-row">
                <Input
                  label="Job ID"
                  value={lookupId}
                  onChange={(event) => setLookupId(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') loadById()
                  }}
                  placeholder="00000000-0000-0000-0000-000000000000"
                />
                <Button onClick={loadById} disabled={!lookupId.trim()}>
                  Open
                </Button>
              </div>

              {recent.length > 0 && (
                <>
                  <h2>Recent jobs</h2>
                  <table>
                    <thead>
                      <tr>
                        <th>Job</th>
                        <th>Prompt</th>
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recent.map((item) => (
                        <tr key={item.id}>
                          <td>
                            <Link to={`/ai?jobId=${encodeURIComponent(item.id)}`}>
                              {shortId(item.id)}
                            </Link>
                          </td>
                          <td>{truncate(item.prompt, 80)}</td>
                          <td>{relativeDate(item.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </>
          )}

          {jobId && (
            <>
              {loadingJob && !visibleJob && <LoadingState label="Loading job" />}

              {jobError && (
                <ErrorState
                  message={jobError}
                  onRetry={() => setDetailNonce((value) => value + 1)}
                />
              )}

              {visibleJob && (
                <div className="llm-job">
                  <p className="llm-job__meta">
                    {status && (
                      <span className={`llm-status llm-status--${status}`}>
                        {STATUS_LABELS[status]}
                      </span>
                    )}
                    <span className="muted">Job {shortId(visibleJob.id)}</span>
                    {isWorking && (
                      <span className="muted">
                        {streamState === 'live'
                          ? 'Live updates'
                          : streamState === 'reconnecting'
                          ? 'Reconnecting…'
                          : 'Checking status'}
                      </span>
                    )}
                  </p>

                  <h2>Prompt</h2>
                  <pre className="llm-prompt">{visibleJob.prompt}</pre>

                  {isWorking && (
                    <p className="status" role="status">
                      {status === 'queued'
                        ? 'Queued. The worker will pick it up shortly.'
                        : 'Generating a response…'}
                    </p>
                  )}

                  {status === 'failed' && (
                    <ErrorState message={visibleJob.error || 'The LLM job failed.'} />
                  )}

                  {status === 'completed' && (
                    <>
                      <div className="llm-job__head">
                        <h2>Response</h2>
                        <Button
                          size="sm"
                          onClick={copyResponse}
                          disabled={!visibleJob.response}
                        >
                          Copy
                        </Button>
                      </div>
                      {loadingJob && !visibleJob.response ? (
                        <LoadingState label="Loading response" />
                      ) : visibleJob.response ? (
                        <pre className="llm-output">{visibleJob.response}</pre>
                      ) : (
                        <p className="muted">The job completed without a response.</p>
                      )}
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}

      {viewMode === 'chat' && (
        <div className="chat-page">
          {chatError && (
            <InlineNotice tone="error" onDismiss={() => setChatError(null)}>
              {chatError}
            </InlineNotice>
          )}

          <div className="chat-layout">
            {/* Sidebar */}
            <aside className="chat-sidebar">
              {showNewConv ? (
                <div className="new-conversation-form">
                  <h3>New Conversation</h3>
                  <Input
                    label="Title"
                    value={newConvTitle}
                    onChange={(e) => setNewConvTitle(e.target.value)}
                    placeholder="My conversation"
                    onKeyDown={(e) => e.key === 'Enter' && startNewConversation()}
                    autoFocus
                  />
                  <div className="form-row">
                    <Button variant="primary" onClick={startNewConversation} loading={chatSending}>
                      Create
                    </Button>
                    <Button onClick={() => setShowNewConv(false)}>Cancel</Button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="form-row">
                    <Button variant="primary" onClick={() => setShowNewConv(true)} disabled={chatSending}>
                      New Chat
                    </Button>
                  </div>
                  <ul className="conversation-list">
                    {conversations.map((conv) => (
                      <li
                        key={conv.id}
                        className={`conversation-item ${activeConversation?.id === conv.id ? 'active' : ''}`}
                        onClick={() => loadConversation(conv.id)}
                      >
                        <div className="conv-info">
                          <span className="conv-title">{conv.title || 'Untitled'}</span>
                          <span className="conv-date">{relativeDate(conv.updated_at)}</span>
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={(e) => {
                            e.stopPropagation()
                            deleteConv(conv.id)
                          }}
                        >
                          Delete
                        </Button>
                      </li>
                    ))}
                    {conversations.length === 0 && (
                      <li className="muted">No conversations yet. Click "New Chat" to start.</li>
                    )}
                  </ul>
                </>
              )}
            </aside>

            {/* Chat area */}
            <main className="chat-main">
              {activeConversation ? (
                <>
                  <div className="chat-header">
                    <h2>{activeConversation.title || 'Untitled'}</h2>
                    <div className="chat-meta">
                      <span className="muted">Model: Nemotron 3 Ultra 550B</span>
                    </div>
                  </div>

                  <div className="messages">
                    {activeConversation.messages?.map((msg) => (
                      <div key={msg.id} className={`message ${msg.role}`}>
                        <div className="message-role">{msg.role}</div>
                        <div className="message-content">{msg.content}</div>
                        {msg.metadata && Object.keys(msg.metadata).length > 0 && (
                          <div className="message-meta muted">
                            {JSON.stringify(msg.metadata)}
                          </div>
                        )}
                      </div>
                    ))}
                    {chatSending && <div className="message assistant sending">Thinking…</div>}
                  </div>

                  <div className="chat-input-area">
                    <Textarea
                      label=""
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault()
                          handleChatSubmit()
                        }
                      }}
                      rows={3}
                      placeholder="Type your message... (Shift+Enter for new line)"
                      disabled={chatSending || !activeConversation}
                    />
                    <div className="form-row">
                      <Button
                        variant="primary"
                        onClick={handleChatSubmit}
                        loading={chatSending}
                        disabled={!chatInput.trim() || chatSending || !activeConversation}
                      >
                        Send
                      </Button>
                    </div>
                  </div>
                </>
              ) : (
                <div className="chat-empty">
                  <h3>Welcome to AI Chat</h3>
                  <p className="muted">Create a new conversation to start chatting with the AI assistant.</p>
                  <Button variant="primary" onClick={() => setShowNewConv(true)} disabled={chatSending}>
                    New Conversation
                  </Button>
                </div>
              )}
            </main>
          </div>
        </div>
      )}
    </div>
  )
}