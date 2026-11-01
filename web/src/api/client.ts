import type { z } from 'zod'

import {
  chatReplySchema,
  healthSchema,
  jobRefSchema,
  jobSchema,
  sampleSchema,
  type Step,
} from './schemas'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null
    const detail = typeof body?.detail === 'string' ? body.detail : response.statusText
    throw new ApiError(response.status, detail)
  }
  return schema.parse(await response.json())
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  health: () => request('/api/health', healthSchema),
  samples: () => request('/api/samples', sampleSchema.array()),
  job: (id: string) => request(`/api/jobs/${id}`, jobSchema),
  learn: (sampleId: string) =>
    request('/api/learn', jobRefSchema, json({ sampleId })).then((r) => r.jobId),
  learnUpload: (form: FormData) =>
    request('/api/learn/upload', jobRefSchema, { method: 'POST', body: form }).then((r) => r.jobId),
  chat: (body: {
    sampleId: string
    messages: Array<{ role: 'person' | 'robot'; text: string }>
    steps: Step[]
  }) => request('/api/chat', chatReplySchema, json(body)),
  run: (body: { sampleId: string; steps: Step[]; seed: number; oracle: boolean; slip: boolean }) =>
    request('/api/run', jobRefSchema, json(body)).then((r) => r.jobId),
}
