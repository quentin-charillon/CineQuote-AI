/** Same-origin Vercel proxy. RENDER_API_URL and PROXY_SHARED_SECRET stay server-side. */
export default {
  async fetch(request: Request): Promise<Response> {
    const backend = process.env.RENDER_API_URL?.replace(/\/$/, '')
    const proxySecret = process.env.PROXY_SHARED_SECRET
    if (!backend || !proxySecret) {
      return Response.json({ detail: 'API proxy is not configured' }, { status: 503 })
    }

    const incoming = new URL(request.url)
    const upstreamPath = incoming.pathname.replace(/^\/api/, '') || '/'
    const upstream = new URL(`${upstreamPath}${incoming.search}`, backend)
    const headers = new Headers()
    for (const name of ['accept', 'content-type', 'cookie', 'origin', 'user-agent', 'x-forwarded-for']) {
      const value = request.headers.get(name)
      if (value) headers.set(name, value)
    }
    headers.set('x-cinequote-proxy-secret', proxySecret)

    try {
      return await fetch(upstream, {
        method: request.method,
        headers,
        body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
        redirect: 'manual',
        // Required by Node when streaming a request body.
        duplex: 'half',
      } as RequestInit & { duplex: 'half' })
    } catch {
      return Response.json({ detail: 'The API is temporarily unavailable' }, { status: 502 })
    }
  },
}
