const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? ''

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  // Get token from Amplify session
  const { fetchAuthSession } = await import('aws-amplify/auth')
  const session = await fetchAuthSession()
  const token = session.tokens?.idToken?.toString() ?? ''

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: token,
      ...(options?.headers ?? {}),
    },
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(`API error ${res.status}: ${err}`)
  }

  return res.json() as Promise<T>
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const fetcher = (url: string): Promise<any> => apiFetch<any>(url)

export async function takeoverConversation(phone: string): Promise<void> {
  await apiFetch(`/api/conversations/${encodeURIComponent(phone)}/takeover`, {
    method: 'POST',
  })
}
