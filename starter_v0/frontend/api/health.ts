import type { VercelRequest, VercelResponse } from '@vercel/node';

function sendJson(res: VercelResponse, status: number, body: unknown) {
  res.status(status).setHeader('Content-Type', 'application/json');
  res.send(JSON.stringify(body));
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'GET') {
    return sendJson(res, 405, { error: 'method_not_allowed' });
  }
  const origin = process.env.BACKEND_ORIGIN?.replace(/\/+$/, '');
  if (!origin) {
    return sendJson(res, 200, { status: 'offline', backend: 'not_configured' });
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const upstream = await fetch(`${origin}/health`, { signal: controller.signal });
    const data = await upstream.json().catch(() => ({}));
    return sendJson(res, 200, { status: upstream.ok ? 'online' : 'offline', backend: data });
  } catch {
    return sendJson(res, 200, { status: 'offline' });
  } finally {
    clearTimeout(timeout);
  }
}

