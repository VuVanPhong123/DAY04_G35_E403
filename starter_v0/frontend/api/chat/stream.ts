import type { VercelRequest, VercelResponse } from '@vercel/node';

const TIMEOUT_MS = 90000;

function sendJson(res: VercelResponse, status: number, body: unknown) {
  res.status(status).setHeader('Content-Type', 'application/json');
  res.send(JSON.stringify(body));
}

function backendOrigin() {
  const origin = process.env.BACKEND_ORIGIN;
  if (!origin) {
    throw new Error('BACKEND_ORIGIN is not configured');
  }
  return origin.replace(/\/+$/, '');
}

function validBody(body: unknown) {
  if (!body || typeof body !== 'object') return false;
  const value = body as { message?: unknown; history?: unknown; session_id?: unknown };
  if (typeof value.message !== 'string' || !value.message.trim()) return false;
  if (value.message.length > 4000) return false;
  if (value.history !== undefined && !Array.isArray(value.history)) return false;
  if (value.session_id !== undefined && typeof value.session_id !== 'string') return false;
  return true;
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'POST') {
    return sendJson(res, 405, { error: 'method_not_allowed' });
  }
  if (!validBody(req.body)) {
    return sendJson(res, 400, { error: 'invalid_request' });
  }

  let origin: string;
  try {
    origin = backendOrigin();
  } catch {
    return sendJson(res, 500, { error: 'backend_not_configured' });
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const upstream = await fetch(`${origin}/api/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'ngrok-skip-browser-warning': 'true',
        ...(process.env.BACKEND_SHARED_SECRET ? { 'X-Internal-API-Key': process.env.BACKEND_SHARED_SECRET } : {}),
      },
      body: JSON.stringify(req.body),
      signal: controller.signal,
    });

    if (!upstream.ok || !upstream.body) {
      const text = await upstream.text().catch(() => '');
      return sendJson(res, upstream.status || 502, { error: 'stream_unavailable', detail: text.slice(0, 500) });
    }

    res.writeHead(upstream.status, {
      'Content-Type': upstream.headers.get('content-type') || 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
    });

    const reader = upstream.body.getReader();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value) res.write(Buffer.from(value));
    }
    res.end();
  } catch {
    if (!res.headersSent) {
      return sendJson(res, 502, { error: 'backend_unavailable' });
    }
    res.end();
  } finally {
    clearTimeout(timeout);
  }
}
