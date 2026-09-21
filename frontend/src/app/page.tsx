'use client'
import { useEffect, useState } from 'react'
import useSWR from 'swr'
import { useRouter } from 'next/navigation'
import { getCurrentUser, signOut } from 'aws-amplify/auth'
import ConversationsTable from '@/components/ConversationsTable'
import type { Conversation } from '@/lib/types'
import { fetcher } from '@/lib/api'

export default function DashboardPage() {
  const router = useRouter()
  const [authChecked, setAuthChecked] = useState(false)

  useEffect(() => {
    getCurrentUser()
      .then(() => setAuthChecked(true))
      .catch(() => router.push('/login'))
  }, [router])

  const { data, error, isLoading, mutate } = useSWR<{ conversations: Conversation[] }>(
    authChecked ? '/api/conversations' : null,
    fetcher,
    { refreshInterval: 5000 }
  )

  if (!authChecked || isLoading) {
    return <div className="flex min-h-screen items-center justify-center text-gray-500">Loading...</div>
  }

  if (error) {
    return <div className="p-8 text-red-600">Error loading conversations.</div>
  }

  const conversations = data?.conversations ?? []
  const qualified = conversations.filter(c => c.lead_status === 'qualified').length
  const pendingTakeover = conversations.filter(c => c.stage !== 'owner_takeover' && c.lead_status === 'qualified').length

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-3 flex justify-between items-center shadow-sm">
        <h1 className="text-lg font-semibold">Chácara Dashboard</h1>
        <div className="flex gap-4 items-center">
          <a href="/calendar" className="text-sm text-blue-600 hover:underline">Calendar</a>
          <button onClick={() => signOut().then(() => router.push('/login'))} className="text-sm text-gray-500 hover:text-gray-700">
            Sign out
          </button>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { label: 'Total Conversations', value: conversations.length },
            { label: 'Qualified Leads', value: qualified },
            { label: 'Awaiting Takeover', value: pendingTakeover },
          ].map(card => (
            <div key={card.label} className="bg-white rounded-lg shadow p-5">
              <p className="text-sm text-gray-500">{card.label}</p>
              <p className="text-3xl font-bold mt-1">{card.value}</p>
            </div>
          ))}
        </div>

        <ConversationsTable conversations={conversations} />
      </main>
    </div>
  )
}
