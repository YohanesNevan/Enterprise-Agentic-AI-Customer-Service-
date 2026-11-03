const passthroughHeaders = [
  'content-type',
  'x-role',
  'x-actor-type',
  'x-actor-id',
  'x-correlation-id',
]

export default async function handler(req, res) {
  const apiOrigin = process.env.API_ORIGIN?.replace(/\/$/, '')
  const apiBasicAuth = process.env.API_BASIC_AUTH

  if (!apiOrigin || !apiBasicAuth) {
    res.status(503).json({
      error_code: 'API_NOT_CONFIGURED',
      message: 'API backend belum dikonfigurasi untuk deployment ini.',
    })
    return
  }

  let origin
  try {
    origin = new URL(apiOrigin)
  } catch {
    res.status(503).json({ error_code: 'API_ORIGIN_INVALID', message: 'Origin API belum valid.' })
    return
  }
  if (origin.protocol !== 'https:' || origin.username || origin.password || origin.pathname !== '/' || origin.search || origin.hash) {
    res.status(503).json({ error_code: 'API_ORIGIN_INVALID', message: 'API_ORIGIN harus berupa origin HTTPS.' })
    return
  }

  const incoming = new URL(req.url, 'http://vercel.local')
  const apiPath = incoming.searchParams.get('path')
  if (!apiPath || !apiPath.startsWith('/') || apiPath.startsWith('//')) {
    res.status(400).json({ error_code: 'INVALID_API_PATH', message: 'Path API tidak valid.' })
    return
  }
  const allowedPath = ['/healthz', '/readyz'].includes(apiPath)
    || ['/v1', '/internal'].some((prefix) => apiPath === prefix || apiPath.startsWith(`${prefix}/`))
  if (!allowedPath) {
    res.status(404).json({ error_code: 'API_PATH_NOT_ALLOWED', message: 'Rute API tidak diizinkan.' })
    return
  }
  if (!['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method)) {
    res.status(405).json({ error_code: 'METHOD_NOT_ALLOWED', message: 'Metode HTTP tidak diizinkan.' })
    return
  }

  const upstreamQuery = new URLSearchParams(incoming.searchParams)
  upstreamQuery.delete('path')
  const query = upstreamQuery.toString()
  const headers = new Headers()
  for (const name of passthroughHeaders) {
    const value = req.headers[name]
    if (typeof value === 'string') headers.set(name, value)
  }
  headers.set('authorization', `Basic ${Buffer.from(apiBasicAuth).toString('base64')}`)

  let body
  if (!['GET', 'HEAD'].includes(req.method)) {
    body = req.body
    if (body && typeof body === 'object' && !Buffer.isBuffer(body)) {
      body = JSON.stringify(body)
      if (!headers.has('content-type')) headers.set('content-type', 'application/json')
    }
  }

  try {
    const upstream = await fetch(`${origin.origin}${apiPath}${query ? `?${query}` : ''}`, {
      method: req.method,
      headers,
      body,
      redirect: 'manual',
    })
    const contentType = upstream.headers.get('content-type')
    if (contentType) res.setHeader('content-type', contentType)
    res.setHeader('cache-control', 'no-store')
    const correlationId = upstream.headers.get('x-correlation-id')
    if (correlationId) res.setHeader('x-correlation-id', correlationId)
    res.status(upstream.status).send(Buffer.from(await upstream.arrayBuffer()))
  } catch {
    res.status(502).json({
      error_code: 'API_UNAVAILABLE',
      message: 'API backend tidak dapat dijangkau.',
    })
  }
}
