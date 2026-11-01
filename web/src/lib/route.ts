import { useCallback, useSyncExternalStore } from 'react'

export type Route = { page: 'home' } | { page: 'studio'; clip: string | null; upload: boolean }

/** `#/studio?clip=dishes_wash` opens the studio on a clip; anything else is the landing page. */
export function parseRoute(hash: string): Route {
  const [path = '', query = ''] = hash.replace(/^#/, '').split('?')
  if (path !== '/studio') return { page: 'home' }
  const params = new URLSearchParams(query)
  return { page: 'studio', clip: params.get('clip'), upload: params.get('upload') === '1' }
}

export function studioHref(options: { clip?: string; upload?: boolean } = {}): string {
  const params = new URLSearchParams()
  if (options.clip) params.set('clip', options.clip)
  if (options.upload) params.set('upload', '1')
  const query = params.toString()
  return `#/studio${query ? `?${query}` : ''}`
}

const subscribe = (notify: () => void) => {
  window.addEventListener('hashchange', notify)
  return () => window.removeEventListener('hashchange', notify)
}

/** The current page, kept in the URL hash so the back button and shared links just work. */
export function useRoute(): [Route, (href: string) => void] {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash)
  const go = useCallback((href: string) => {
    window.location.hash = href
    window.scrollTo({ top: 0 })
  }, [])
  // Parsing on every render is cheap, and the string snapshot keeps the store stable.
  return [parseRoute(hash), go]
}
