import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ChatView from '@/components/ChatView'
import type { Message } from '@/lib/types'

const messages: Message[] = [
  {
    phone_number: '+5511999999999',
    timestamp: '2026-03-01T10:00:00Z',
    role: 'user',
    message: 'Olá, tem disponibilidade?',
    message_type: 'text',
  },
  {
    phone_number: '+5511999999999',
    timestamp: '2026-03-01T10:00:05Z',
    role: 'assistant',
    message: 'Sim, temos disponibilidade!',
    message_type: 'text',
  },
]

describe('ChatView', () => {
  it('renders user message', () => {
    render(<ChatView messages={messages} />)
    expect(screen.getByText('Olá, tem disponibilidade?')).toBeDefined()
  })

  it('renders assistant message', () => {
    render(<ChatView messages={messages} />)
    expect(screen.getByText('Sim, temos disponibilidade!')).toBeDefined()
  })

  it('renders empty state for no messages', () => {
    render(<ChatView messages={[]} />)
    expect(screen.getByText(/no messages/i)).toBeDefined()
  })
})
