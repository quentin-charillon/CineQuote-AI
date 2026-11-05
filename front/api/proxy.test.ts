import { afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'

import proxy from './proxy'

describe('Vercel API proxy', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    delete process.env.RENDER_API_URL
    delete process.env.PROXY_SHARED_SECRET
  })

  it('fails closed when server-only configuration is missing', async () => {
    const response = await proxy.fetch(new Request('https://cinequote.example/api/proxy?path=health'))
    expect(response.status).toBe(503)
  })

  it('routes API traffic before the SPA fallback', () => {
    const config = JSON.parse(readFileSync(new URL('../vercel.json', import.meta.url), 'utf8')) as {
      rewrites: Array<{ source: string; destination: string }>
    }
    expect(config.rewrites).toEqual([
      { source: '/api/:path*', destination: '/api/proxy' },
      { source: '/(.*)', destination: '/index.html' },
    ])
  })

  it('preserves status, cookies, retry headers and request context', async () => {
    process.env.RENDER_API_URL = 'https://cinequote-api.onrender.com/'
    process.env.PROXY_SHARED_SECRET = 'test-proxy-secret'
    const fetchMock = vi.fn().mockResolvedValue(new Response('{"detail":"limited"}', {
      status: 429,
      headers: { 'Content-Type': 'application/json', 'Retry-After': '60', 'Set-Cookie': 'cinequote_session=abc; HttpOnly; Secure' },
    }))
    vi.stubGlobal('fetch', fetchMock)

    const response = await proxy.fetch(new Request('https://cinequote.example/api/proxy?path=auth%2Flogin&next=1', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Cookie: 'old=value', Origin: 'https://cinequote.example', 'X-Forwarded-For': '203.0.113.9' },
      body: '{}',
    }))

    expect(response.status).toBe(429)
    expect(response.headers.get('retry-after')).toBe('60')
    expect(response.headers.get('set-cookie')).toContain('HttpOnly')
    const [url, init] = fetchMock.mock.calls[0] as [URL, RequestInit]
    expect(url.toString()).toBe('https://cinequote-api.onrender.com/auth/login?next=1')
    const headers = init.headers as Headers
    expect(headers.get('cookie')).toBe('old=value')
    expect(headers.get('origin')).toBe('https://cinequote.example')
    expect(headers.get('x-forwarded-for')).toBe('203.0.113.9')
    expect(headers.get('x-cinequote-proxy-secret')).toBe('test-proxy-secret')
  })

  it('rejects a missing or unsafe upstream path', async () => {
    process.env.RENDER_API_URL = 'https://cinequote-api.onrender.com'
    process.env.PROXY_SHARED_SECRET = 'test-proxy-secret'
    expect((await proxy.fetch(new Request('https://cinequote.example/api/proxy'))).status).toBe(400)
    expect((await proxy.fetch(new Request('https://cinequote.example/api/proxy?path=..%2Fadmin'))).status).toBe(400)
  })
})
