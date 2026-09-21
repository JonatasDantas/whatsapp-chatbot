'use client'
import { useState } from 'react'
import { takeoverConversation } from '@/lib/api'
import type { ConversationStage } from '@/lib/types'

interface Props {
  phone: string
  stage: ConversationStage
  onSuccess: () => void
}

export default function TakeoverButton({ phone, stage, onSuccess }: Props) {
  const [loading, setLoading] = useState(false)
  const isTakenOver = stage === 'owner_takeover'

  async function handleClick() {
    if (!confirm('Assume this conversation? The AI will stop responding and the guest will be notified.')) return
    setLoading(true)
    try {
      await takeoverConversation(phone)
      onSuccess()
    } catch (err) {
      alert('Failed to take over conversation. Please try again.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={isTakenOver || loading}
      aria-disabled={isTakenOver || loading}
      className={`px-4 py-2 rounded font-medium text-sm transition-colors ${
        isTakenOver
          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
          : 'bg-amber-500 hover:bg-amber-600 text-white'
      }`}
    >
      {isTakenOver ? 'Owner Assumed' : loading ? 'Assuming...' : 'Assume Conversation'}
    </button>
  )
}
