import { API_BASE, getAccessToken, refreshAccessToken } from './api'

export interface ToolEvent {
  name: string
  status: 'running' | 'done' | 'error'
  summary: string
}

export interface ChatHandlers {
  onThinking?: (summary: string) => void
  onToken?: (delta: string) => void
  onTool?: (t: ToolEvent) => void
  onMessage?: (m: { role: string; text: string; created_at: string } | null) => void
  onError?: (detail: string) => void
  onDone?: () => void
}

/**
 * POSTs a chat turn and consumes the `text/event-stream` response. Uses `fetch`
 * (not EventSource — we need an Authorization header). Retries once through a
 * token refresh on 401.
 */
export async function streamChat(
  conversationId: string,
  text: string,
  handlers: ChatHandlers,
  attempt = 0,
): Promise<void> {
  const token = getAccessToken()
  const resp = await fetch(
    `${API_BASE}/chat/conversations/${conversationId}/messages`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      credentials: 'include',
      body: JSON.stringify({ text }),
    },
  )

  if (resp.status === 401 && attempt === 0) {
    const fresh = await refreshAccessToken()
    if (fresh) return streamChat(conversationId, text, handlers, 1)
    handlers.onError?.('Your session expired. Please sign in again.')
    return
  }
  if (resp.status === 503) {
    handlers.onError?.('AI features are not configured on this server.')
    return
  }
  if (!resp.ok || !resp.body) {
    handlers.onError?.(`The request failed (${resp.status}).`)
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''
    for (const frame of frames) dispatch(frame, handlers)
  }
  if (buffer.trim()) dispatch(buffer, handlers)
}

function dispatch(frame: string, h: ChatHandlers) {
  let event = 'message'
  let data = ''
  for (const line of frame.split('\n')) {
    if (line.startsWith('event: ')) event = line.slice(7).trim()
    else if (line.startsWith('data: ')) data += line.slice(6)
  }
  if (!data) return
  let parsed: Record<string, unknown>
  try {
    parsed = JSON.parse(data)
  } catch {
    return
  }
  switch (event) {
    case 'thinking':
      h.onThinking?.(String(parsed.summary ?? ''))
      break
    case 'token':
      h.onToken?.(String(parsed.delta ?? ''))
      break
    case 'tool':
      h.onTool?.(parsed as unknown as ToolEvent)
      break
    case 'message':
      h.onMessage?.((parsed.message as never) ?? null)
      break
    case 'error':
      h.onError?.(String(parsed.detail ?? 'Something went wrong.'))
      break
    case 'done':
      h.onDone?.()
      break
  }
}
