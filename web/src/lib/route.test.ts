import { describe, expect, it } from 'vitest'

import { parseRoute, studioHref } from './route'

describe('routes', () => {
  it('shows the landing page by default and for unknown paths', () => {
    expect(parseRoute('')).toEqual({ page: 'home' })
    expect(parseRoute('#/')).toEqual({ page: 'home' })
    expect(parseRoute('#/nowhere')).toEqual({ page: 'home' })
  })

  it('opens the studio, optionally on a clip or with the upload dialog', () => {
    expect(parseRoute('#/studio')).toEqual({ page: 'studio', clip: null, upload: false })
    expect(parseRoute('#/studio?clip=dishes_wash')).toEqual({
      page: 'studio',
      clip: 'dishes_wash',
      upload: false,
    })
    expect(parseRoute('#/studio?upload=1')).toMatchObject({ upload: true })
  })

  it('builds links that parse back to the same place', () => {
    expect(parseRoute(studioHref({ clip: 'chips_open' }))).toMatchObject({ clip: 'chips_open' })
    expect(studioHref()).toBe('#/studio')
    expect(parseRoute(studioHref({ upload: true }))).toMatchObject({ upload: true })
  })
})
