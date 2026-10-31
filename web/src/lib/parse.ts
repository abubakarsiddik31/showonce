/** "red mug" or "mug: red ceramic mug" per line -> { name: prompt }. */
export function parseLines(text: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    if (!line) continue
    const [name, ...rest] = line.split(':')
    const key = (name ?? '').trim()
    if (key) out[key] = rest.join(':').trim() || key
  }
  return out
}
