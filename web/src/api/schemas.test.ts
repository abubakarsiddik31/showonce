import { describe, expect, it } from 'vitest'

import { jobSchema } from './schemas'

describe('jobSchema', () => {
  it('accepts a running job without results', () => {
    const job = jobSchema.parse({ id: 'a1', kind: 'learn', status: 'running', stage: 'Watching' })
    expect(job.learn).toBeUndefined()
  })
  it('rejects an unknown status', () => {
    expect(() => jobSchema.parse({ id: 'a1', kind: 'run', status: 'weird', stage: '' })).toThrow()
  })
})
