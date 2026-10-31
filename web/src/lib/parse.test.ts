import { describe, expect, it } from 'vitest'

import { parseLines } from '../lib/parse'

describe('parseLines', () => {
  it('uses the name as the prompt unless one is given', () => {
    expect(parseLines('red mug\nblue mug: blue ceramic mug\n\n')).toEqual({
      'red mug': 'red mug',
      'blue mug': 'blue ceramic mug',
    })
  })
})
