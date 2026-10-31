import { z } from 'zod'

export const actionSchema = z.enum(['place_in', 'stack_on'])
export type Action = z.infer<typeof actionSchema>

export const stepSchema = z.object({
  object: z.string(),
  action: actionSchema,
  target: z.string(),
  text: z.string().default(''),
})
export type Step = z.infer<typeof stepSchema>

export const sampleSchema = z.object({
  id: z.string(),
  name: z.string(),
  videoUrl: z.string(),
  objects: z.array(z.string()),
  containers: z.array(z.string()),
  durationS: z.number(),
})
export type Sample = z.infer<typeof sampleSchema>

const optionSchema = z.object({ id: z.string(), label: z.string(), steps: z.array(stepSchema) })
export const questionSchema = z.object({
  id: z.string(),
  prompt: z.string(),
  options: z.array(optionSchema),
})
export type Question = z.infer<typeof questionSchema>

export const learnResultSchema = z.object({
  sampleId: z.string(),
  videoUrl: z.string(),
  width: z.number(),
  height: z.number(),
  durationS: z.number(),
  source: z.enum(['geometry', 'muse_spark']),
  steps: z.array(stepSchema),
  questions: z.array(questionSchema),
  discrepancies: z.array(z.string()),
  rests: z.array(
    z.object({
      object: z.string(),
      startS: z.number(),
      endS: z.number(),
      x: z.number(),
      y: z.number(),
    }),
  ),
  moves: z.array(
    z.object({
      object: z.string(),
      startS: z.number(),
      endS: z.number(),
      fromX: z.number(),
      fromY: z.number(),
      toX: z.number(),
      toY: z.number(),
    }),
  ),
  containers: z.array(
    z.object({ name: z.string(), x1: z.number(), y1: z.number(), x2: z.number(), y2: z.number() }),
  ),
})
export type LearnResult = z.infer<typeof learnResultSchema>
export type Move = LearnResult['moves'][number]

export const runResultSchema = z.object({
  videoUrl: z.string(),
  success: z.boolean(),
  seed: z.number(),
  checks: z.array(z.object({ step: z.string(), ok: z.boolean(), detail: z.string() })),
  stepTimesS: z.array(z.number()),
  perceptionErrorMm: z.record(z.string(), z.number()),
})
export type RunResult = z.infer<typeof runResultSchema>

export const jobSchema = z.object({
  id: z.string(),
  kind: z.enum(['learn', 'run']),
  status: z.enum(['queued', 'running', 'done', 'failed']),
  stage: z.string(),
  error: z.string().nullable().optional(),
  learn: learnResultSchema.nullable().optional(),
  run: runResultSchema.nullable().optional(),
})
export type Job = z.infer<typeof jobSchema>

export const jobRefSchema = z.object({ jobId: z.string() })
export const healthSchema = z.object({ ok: z.boolean(), metaKey: z.boolean() })
