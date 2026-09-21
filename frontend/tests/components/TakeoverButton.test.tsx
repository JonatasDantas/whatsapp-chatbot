import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import TakeoverButton from '@/components/TakeoverButton'

vi.mock('@/lib/api', () => ({
  takeoverConversation: vi.fn().mockResolvedValue(undefined),
}))

describe('TakeoverButton', () => {
  it('renders button when not in takeover stage', () => {
    render(<TakeoverButton phone="+5511999999999" stage="qualification" onSuccess={() => {}} />)
    expect(screen.getByRole('button', { name: /assume/i })).toBeDefined()
  })

  it('shows disabled state when already in owner_takeover', () => {
    render(<TakeoverButton phone="+5511999999999" stage="owner_takeover" onSuccess={() => {}} />)
    const btn = screen.getByRole('button')
    expect(btn.hasAttribute('disabled') || btn.getAttribute('aria-disabled') === 'true').toBe(true)
  })

  it('calls onSuccess after confirmation', async () => {
    const onSuccess = vi.fn()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<TakeoverButton phone="+5511999999999" stage="qualification" onSuccess={onSuccess} />)
    fireEvent.click(screen.getByRole('button', { name: /assume/i }))
    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce())
  })

  it('does nothing if user cancels confirmation', async () => {
    const onSuccess = vi.fn()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<TakeoverButton phone="+5511999999999" stage="qualification" onSuccess={onSuccess} />)
    fireEvent.click(screen.getByRole('button', { name: /assume/i }))
    await waitFor(() => expect(onSuccess).not.toHaveBeenCalled())
  })
})
