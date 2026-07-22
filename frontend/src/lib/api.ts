const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ApiOptions {
  method?: string
  headers?: Record<string, string>
  body?: any
}

export async function api(path: string, options: ApiOptions = {}) {
  const { method = 'GET', headers = {}, body } = options

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(errorData.detail || `API error: ${res.status}`)
  }

  // Handle 204 No Content
  if (res.status === 204) return null

  return res.json()
}
