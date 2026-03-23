import axios from 'axios'
import type { KiprisQuota, SearchResponse, SSEEvent } from './types'

const api = axios.create({ baseURL: '/api/v1' })

export async function searchStream(
  description: string,
  onEvent: (event: SSEEvent) => void,
): Promise<SearchResponse> {
  const response = await fetch('/api/v1/search/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description }),
  })

  if (!response.ok) {
    throw new Error(`Search failed: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult: SearchResponse | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data: ')) continue

      const jsonStr = trimmed.slice(6)
      if (!jsonStr) continue

      try {
        const event: SSEEvent = JSON.parse(jsonStr)
        onEvent(event)
        if (event.type === 'result' && event.data) {
          finalResult = event.data
        }
      } catch {
        // skip malformed events
      }
    }
  }

  if (!finalResult) throw new Error('No result received')
  return finalResult
}

export async function getKiprisQuota(): Promise<KiprisQuota> {
  const { data } = await api.get<KiprisQuota>('/search/kipris-quota')
  return data
}
