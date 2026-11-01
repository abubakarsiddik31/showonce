import { Landing } from './features/landing/Landing'
import { Studio } from './features/studio/Studio'
import { useRoute } from './lib/route'

/** Two pages: the landing page that carries the message, and the studio where the work is done. */
export default function App() {
  const [route, go] = useRoute()
  return route.page === 'studio' ? (
    // A new key starts the story again from scratch whenever another clip is opened.
    <Studio key={route.clip ?? 'default'} clip={route.clip} upload={route.upload} go={go} />
  ) : (
    <Landing go={go} />
  )
}
