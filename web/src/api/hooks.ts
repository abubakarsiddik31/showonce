import { useMutation, useQuery } from '@tanstack/react-query'

import { api } from './client'
import type { Job } from './schemas'

const POLL_MS = 1200

export const useHealth = () =>
  useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 15_000, retry: false })

export const useSamples = () => useQuery({ queryKey: ['samples'], queryFn: api.samples })

const finished = (job: Job | undefined) => job?.status === 'done' || job?.status === 'failed'

/** Poll a background job until it finishes. */
export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.job(jobId as string),
    enabled: jobId !== null,
    refetchInterval: (query) => (finished(query.state.data) ? false : POLL_MS),
  })
}

export const useStartLearn = () => useMutation({ mutationFn: api.learn })
export const useStartUpload = () => useMutation({ mutationFn: api.learnUpload })
export const useStartRun = () => useMutation({ mutationFn: api.run })
export const useChat = () => useMutation({ mutationFn: api.chat })
