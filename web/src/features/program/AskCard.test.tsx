import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { Question } from '../../api/schemas'
import { AskCard } from './AskCard'

const question: Question = {
  id: 'plan',
  prompt: 'Which one matches what you showed?',
  options: [
    {
      id: 'geometry',
      label: 'Tracked motion',
      steps: [
        { object: 'red mug', action: 'place_in', target: 'tray', text: 'put red mug in tray' },
      ],
    },
    {
      id: 'muse_spark',
      label: 'Video understanding',
      steps: [
        { object: 'blue mug', action: 'place_in', target: 'tray', text: 'put blue mug in tray' },
      ],
    },
  ],
}

describe('AskCard', () => {
  it('shows both plans and reports the choice', async () => {
    const onChoose = vi.fn()
    render(<AskCard question={question} chosen={null} onChoose={onChoose} />)
    expect(screen.getByText('Needs your call')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('radio', { name: /video understanding/i }))
    expect(onChoose).toHaveBeenCalledWith('muse_spark')
  })

  it('marks the chosen plan and says it was saved', () => {
    render(<AskCard question={question} chosen="geometry" onChoose={() => {}} />)
    expect(screen.getByRole('radio', { name: /tracked motion/i })).toHaveAttribute(
      'aria-checked',
      'true',
    )
    expect(screen.getByText(/will not ask again/i)).toBeInTheDocument()
  })
})
