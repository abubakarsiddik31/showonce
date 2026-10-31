import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { Step } from '../../api/schemas'
import { ChatPanel } from './ChatPanel'
import type { ChatMessage } from './conversation'

const step: Step = {
  object: 'red chips',
  action: 'open',
  target: 'red chips',
  text: 'open red chips',
  how: "I'll tear the seal off.",
}

const ask: ChatMessage = {
  id: 'm-1',
  from: 'robot',
  text: 'This is what I understood. Is that right?',
  steps: [step],
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
  it('shows what the robot understood and lets the person confirm it', async () => {
    const props = setup()
    expect(screen.getByText('open red chips')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /yes, that.s right/i }))
    expect(props.onConfirm).toHaveBeenCalledOnce()
  })

  it('moves to the text box on "Not quite"', async () => {
    const props = setup()
    await userEvent.click(screen.getByRole('button', { name: /not quite/i }))
    expect(props.onNotQuite).toHaveBeenCalledOnce()
    expect(screen.getByLabelText(/tell the robot what to change/i)).toHaveFocus()
  })

  it('sends what is typed and clears the box', async () => {
    const props = setup()
    const box = screen.getByLabelText(/tell the robot what to change/i)
    await userEvent.type(box, 'also open the yellow packet')
    await userEvent.click(screen.getByRole('button', { name: /send/i }))
    expect(props.onSend).toHaveBeenCalledWith('also open the yellow packet')
    expect(box).toHaveValue('')
  })

  it('does not send blank text or while the robot is thinking', async () => {
    const props = setup({ thinking: true })
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/tell the robot what to change/i), 'hello{enter}')
    expect(props.onSend).not.toHaveBeenCalled()
  })

  it('stops asking for confirmation once confirmed, and shows how it will do each step', () => {
    setup({
      confirmed: true,
      messages: [ask, { ...ask, id: 'm-2', text: 'Learned.', showHow: true }],
    })
    expect(screen.queryByRole('button', { name: /yes, that.s right/i })).toBeNull()
    expect(screen.getByText("I'll tear the seal off.")).toBeInTheDocument()
  })
})
