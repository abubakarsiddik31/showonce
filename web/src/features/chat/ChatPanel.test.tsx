import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ChatPanel } from './ChatPanel'
import type { ChatMessage } from './conversation'

const ask: ChatMessage = {
  id: 'm-1',
  from: 'robot',
  text: 'I saw you tear open the red bag of chips. Did I get it right?',
  asks: true,
}

function setup(overrides: Partial<Parameters<typeof ChatPanel>[0]> = {}) {
  const props = {
    messages: [ask],
    confirmed: false,
    thinking: false,
    onSend: vi.fn(),
    onConfirm: vi.fn(),
    onNotQuite: vi.fn(),
    ...overrides,
  }
  render(<ChatPanel {...props} />)
  return props
}

describe('ChatPanel', () => {
  it('speaks first, in words, and waits for the person to say it is right', async () => {
    const props = setup()
    expect(screen.getByText(/tear open the red bag of chips/)).toBeInTheDocument()
    expect(props.onConfirm).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: /yes, that.s right/i }))
    expect(props.onConfirm).toHaveBeenCalledOnce()
  })

  it('moves to the text box on "Not quite"', async () => {
    const props = setup()
    await userEvent.click(screen.getByRole('button', { name: /not quite/i }))
    expect(props.onNotQuite).toHaveBeenCalledOnce()
    expect(screen.getByLabelText(/tell the robot what to change/i)).toHaveFocus()
  })

  it('lets the person say more instead of answering, and clears the box', async () => {
    const props = setup()
    const box = screen.getByLabelText(/tell the robot what to change/i)
    await userEvent.type(box, 'I also wanted the yellow packet left alone')
    await userEvent.click(screen.getByRole('button', { name: /send/i }))
    expect(props.onSend).toHaveBeenCalledWith('I also wanted the yellow packet left alone')
    expect(box).toHaveValue('')
  })

  it('does not send blank text or while the robot is thinking', async () => {
    const props = setup({ thinking: true })
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/tell the robot what to change/i), 'hello{enter}')
    expect(props.onSend).not.toHaveBeenCalled()
  })

  it('does not offer the yes/no buttons after a message that only invites more talk', () => {
    setup({
      messages: [
        ask,
        { id: 'm-2', from: 'person', text: 'Not quite.' },
        {
          id: 'm-3',
          from: 'robot',
          text: 'Tell me what is different.',
          asks: false,
        },
      ],
    })
    expect(screen.queryByRole('button', { name: /yes, that.s right/i })).toBeNull()
  })

  it('stops asking once confirmed', () => {
    setup({ confirmed: true })
    expect(screen.queryByRole('button', { name: /yes, that.s right/i })).toBeNull()
  })
})
