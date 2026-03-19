import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ConversationsTable from '@/components/ConversationsTable'
import type { Conversation } from '@/lib/types'

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}))

const mockConversations: Conversation[] = [
  {
    phone_number: '+5511999999999',
    name: 'Ana Lima',
    stage: 'qualification',
    checkin: '2026-04-10',
    checkout: '2026-04-12',
    guests: 4,
    purpose: 'anniversary',
    customer_profile: null,
    rules_accepted: true,
    price_estimate: 1200,
    lead_status: 'qualified',
    owner_notified: false,
    created_at: '2026-03-01T00:00:00Z',
    updated_at: '2026-03-02T00:00:00Z',
  },
]

describe('ConversationsTable', () => {
  it('renders conversation phone number', () => {
    render(<ConversationsTable conversations={mockConversations} />)
    expect(screen.getByText('+5511999999999')).toBeDefined()
  })

  it('renders stage badge', () => {
    render(<ConversationsTable conversations={mockConversations} />)
    expect(screen.getByText('qualification')).toBeDefined()
  })

  it('renders lead status', () => {
    render(<ConversationsTable conversations={mockConversations} />)
    expect(screen.getByText('qualified')).toBeDefined()
  })

  it('renders empty state when no conversations', () => {
    render(<ConversationsTable conversations={[]} />)
    expect(screen.getByText(/no conversations/i)).toBeDefined()
  })
})
