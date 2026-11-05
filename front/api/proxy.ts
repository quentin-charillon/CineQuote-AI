/** Same-origin Vercel proxy. RENDER_API_URL and PROXY_SHARED_SECRET stay server-side. */
const BODYLESS_STATUSES = new Set([101, 204, 205, 304])

function createClientResponse(upstream: Response, requestMethod: string): Response {
  const headers = new Headers(upstream.headers)

  // fetch transparently decodes compressed upstream responses. Forwarding the
  // original transport metadata would make the browser decode that body again.
  headers.delete('content-encoding')
  headers.delete('content-length')
  headers.delete('transfer-encoding')

  const hasBody = requestMethod !== 'HEAD' && !BODYLESS_STATUSES.has(upstream.status)
  return new Response(hasBody ? upstream.body : null, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers,
  })
}

export default {
  async fetch(request: Request): Promise<Response> {
    const backend = process.env.RENDER_API_URL?.replace(/\/$/, '')
    const proxySecret = process.env.PROXY_SHARED_SECRET
    if (!backend || !proxySecret) {
      return Response.json({ detail: 'API proxy is not configured' }, { status: 503 })
    }

    const incoming = new URL(request.url)
    const forwardedPath = incoming.searchParams.get('path')
    if (!forwardedPath) {
      return Response.json({ detail: 'API path is missing' }, { status: 400 })
    }
    const segments = forwardedPath.split('/')
    if (segments.some((segment) => segment === '.' || segment === '..' || segment.includes('\\') || /[\u0000-\u001f]/.test(segment))) {
      return Response.json({ detail: 'API path is invalid' }, { status: 400 })
    }

    incoming.searchParams.delete('path')
    const upstream = new URL(`/${segments.filter(Boolean).join('/')}`, backend)
    upstream.search = incoming.searchParams.toString()
    const headers = new Headers()
    for (const name of ['accept', 'content-type', 'cookie', 'origin', 'user-agent', 'x-forwarded-for']) {
      const value = request.headers.get(name)
      if (value) headers.set(name, value)
    }
    headers.set('x-cinequote-proxy-secret', proxySecret)

    try {
      const response = await fetch(upstream, {
        method: request.method,
        headers,
        body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
        redirect: 'manual',
        duplex: 'half',
      } as RequestInit & { duplex: 'half' })
      return createClientResponse(response, request.method)
    } catch {
      return Response.json({ detail: 'The API is temporarily unavailable' }, { status: 502 })
    }
  },
}
