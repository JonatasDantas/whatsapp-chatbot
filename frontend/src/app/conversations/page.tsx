'use client'
import { useEffect, useState, Suspense } from 'react'
import useSWR from 'swr'
import { useRouter, useSearchParams } from 'next/navigation'
import { getCurrentUser } from 'aws-amplify/auth'
import ChatView from '@/components/ChatView'
import TakeoverButton from '@/components/TakeoverButton'
import type { Conversation, Message } from '@/lib/types'
import { fetcher } from '@/lib/api'

function ConversationContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const phone = searchParams.get('phone') ?? ''
  const encodedPhone = encodeURIComponent(phone)
  const [authChecked, setAuthChecked] = useState(false)

  useEffect(() => {
    getCurrentUser()
      .then(() => setAuthChecked(true))
      .catch(() => router.push('/login'))
  }, [router])

  const { data: convData, mutate: mutateConv } = useSWR<{ conversation: Conversation }>(
    authChecked && phone ? `/api/conversations/${encodedPhone}` : null,
    fetcher,
    { refreshInterval: 5000 }
  )

  const { data: msgData } = useSWR<{ messages: Message[] }>(
    authChecked && phone ? `/api/conversations/${encodedPhone}/messages` : null,
    fetcher,
    { refreshInterval: 5000 }
  )

  if (!authChecked) return null

  const conv = convData?.conversation
  const messages = msgData?.messages ?? []

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b px-6 py-3 flex items-center gap-4 shadow-sm">
        <button onClick={() => router.push('/')} className="text-sm text-blue-600 hover:underline">
          ← Back
        </button>
        <h1 className="text-lg font-semibold">{phone}</h1>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-6 grid grid-cols-3 gap-6">
        {/* Conversation metadata */}
        <aside className="col-span-1 bg-white rounded-lg shadow p-4 space-y-3 h-fit">
          <h2 className="font-semibold text-gray-700">Details</h2>
          {conv ? (
            <dl className="text-sm space-y-2">
              {[
                ['Stage', conv.stage],
                ['Lead', conv.lead_status],
                ['Check-in', conv.checkin],
                ['Check-out', conv.checkout],
                ['Guests', conv.guests],
                ['Purpose', conv.purpose],
                ['Price Est.', conv.price_estimate ? `R$ ${conv.price_estimate}` : '—'],
                ['Rules Accepted', conv.rules_accepted ? 'Yes' : 'No'],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <dt className="text-gray-400">{label}</dt>
                  <dd className="font-medium">{value ?? '—'}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-gray-400 text-sm">Loading...</p>
          )}

          {conv && (
            <div className="pt-2">
              <TakeoverButton
                phone={phone}
                stage={conv.stage}
                onSuccess={() => mutateConv()}
              />
            </div>
          )}
        </aside>

        {/* Chat messages */}
        <section className="col-span-2 bg-white rounded-lg shadow">
          <div className="border-b px-4 py-3">
            <h2 className="font-semibold text-gray-700">Messages ({messages.length})</h2>
          </div>
          <ChatView messages={messages} />
        </section>
      </main>
    </div>
  )
}

export default function ConversationPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-gray-500">Loading...</div>}>
      <ConversationContent />
    </Suspense>
  )
}
