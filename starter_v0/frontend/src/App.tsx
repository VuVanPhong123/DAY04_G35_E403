import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from 'react';
import type { ReactElement, ReactNode } from 'react';
import type { ChatMessage, ChatResponse, ToolEvent } from './types';

const prompts = [
  'Tin AI hôm nay có gì nổi bật?',
  'Lấy 5 tweet mới nhất của Sam Altman.',
  'Mọi người đang bàn gì về OpenAI trên Twitter?',
  'Tóm tắt URL này: https://openai.com/research/',
  'Tìm 3 paper arXiv mới về agent evaluation.',
];

const loadingSteps = [
  'Đang phân tích yêu cầu...',
  'Đang chọn nguồn phù hợp...',
  'Đang gọi công cụ và tổng hợp...',
];

interface ChatBody {
  message: string;
  history: ChatMessage[];
  session_id: string;
}

function makeSessionId() {
  return crypto.randomUUID();
}

function extractUrls(text: string) {
  return Array.from(new Set(text.match(/https?:\/\/[^\s)]+/g) || []));
}

function toolName(event: ToolEvent) {
  return event.tool || event.name || 'tool';
}

function renderInline(text: string) {
  const parts: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|\[[^\]]+\]\(https?:\/\/[^)]+\)|https?:\/\/[^\s)]+)/g;
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > cursor) parts.push(text.slice(cursor, index));
    const token = match[0];
    if (token.startsWith('**')) {
      parts.push(<strong key={`${token}-${index}`}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('[')) {
      const link = token.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);
      if (link) {
        parts.push(<a key={`${token}-${index}`} href={link[2]} target="_blank" rel="noreferrer">{link[1]}</a>);
      }
    } else {
      parts.push(<a key={`${token}-${index}`} href={token} target="_blank" rel="noreferrer">{token}</a>);
    }
    cursor = index + token.length;
  }
  if (cursor < text.length) parts.push(text.slice(cursor));
  return parts;
}

function renderMarkdown(text: string) {
  const lines = text.split(/\r?\n/);
  const blocks: ReactElement[] = [];
  let listItems: ReactElement[] = [];

  function flushList() {
    if (listItems.length) {
      blocks.push(<ul key={`ul-${blocks.length}`}>{listItems}</ul>);
      listItems = [];
    }
  }

  lines.forEach((raw, index) => {
    const line = raw.trim();
    if (!line) {
      flushList();
      return;
    }
    if (line.startsWith('## ')) {
      flushList();
      blocks.push(<h3 key={index}>{renderInline(line.slice(3))}</h3>);
      return;
    }
    if (line.startsWith('# ')) {
      flushList();
      blocks.push(<h3 key={index}>{renderInline(line.slice(2))}</h3>);
      return;
    }
    if (/^- /.test(line)) {
      listItems.push(<li key={index}>{renderInline(line.slice(2))}</li>);
      return;
    }
    flushList();
    blocks.push(<p key={index}>{renderInline(line)}</p>);
  });
  flushList();
  return <div className="markdown">{blocks}</div>;
}

function parseSseFrame(frame: string) {
  const lines = frame.split('\n');
  let event = 'message';
  const dataLines: string[] = [];
  lines.forEach((line) => {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart());
    }
  });
  if (!dataLines.length) return null;
  return { event, data: JSON.parse(dataLines.join('\n')) as unknown };
}

async function readStream(response: Response, onStatus: (message: string) => void) {
  if (!response.body) throw new Error('Streaming is not available');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalPayload: ChatResponse | null = null;

  function handleFrame(frame: string) {
    const parsed = parseSseFrame(frame);
    if (!parsed) return;
    if (parsed.event === 'status') {
      const data = parsed.data as { message?: string };
      if (data.message) onStatus(data.message);
      return;
    }
    if (parsed.event === 'error') {
      const data = parsed.data as { detail?: string; error?: string };
      throw new Error(data.detail || data.error || 'Stream failed');
    }
    if (parsed.event === 'final') {
      finalPayload = parsed.data as ChatResponse;
    }
  }

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
    let boundary = buffer.indexOf('\n\n');
    while (boundary >= 0) {
      handleFrame(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf('\n\n');
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) handleFrame(buffer);
  if (!finalPayload) throw new Error('Stream ended without a final answer');
  return finalPayload;
}

async function requestChatStream(body: ChatBody, onStatus: (message: string) => void) {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error('Stream request failed');
  }
  return readStream(response, onStatus);
}

async function requestChatJson(body: ChatBody) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json() as ChatResponse | { detail?: string; error?: string };
  if (!response.ok) {
    throw new Error('detail' in data ? data.detail || 'Request failed' : 'Request failed');
  }
  return data as ChatResponse;
}

function compactToolResult(result: Record<string, unknown> | undefined) {
  if (!result) return undefined;
  const itemCount = Array.isArray(result.items) ? result.items.length : undefined;
  return {
    tool: result.tool,
    status: result.error ? 'error' : 'success',
    message: result.message,
    item_count: result.item_count ?? itemCount,
    query: result.query,
    topic: result.topic,
    timeframe: result.timeframe,
  };
}

export default function App() {
  const [sessionId, setSessionId] = useState(() => sessionStorage.getItem('session_id') || makeSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    const raw = sessionStorage.getItem('messages');
    return raw ? JSON.parse(raw) as ChatMessage[] : [];
  });
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [toolEvents, setToolEvents] = useState<ToolEvent[]>([]);
  const [backendStatus, setBackendStatus] = useState('checking');
  const [loadingStep, setLoadingStep] = useState(0);
  const [streamStatus, setStreamStatus] = useState('');

  useEffect(() => {
    sessionStorage.setItem('session_id', sessionId);
    sessionStorage.setItem('messages', JSON.stringify(messages));
  }, [sessionId, messages]);

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setBackendStatus(data.status || data.backend?.status || 'unknown'))
      .catch(() => setBackendStatus('offline'));
  }, []);

  useEffect(() => {
    if (!loading) {
      setLoadingStep(0);
      setStreamStatus('');
      return undefined;
    }
    const timer = window.setInterval(() => {
      setLoadingStep((step) => Math.min(step + 1, loadingSteps.length - 1));
    }, 1800);
    return () => window.clearInterval(timer);
  }, [loading]);

  const sources = useMemo(() => {
    const fromAnswer = extractUrls(messages.filter((m) => m.role === 'assistant').map((m) => m.content).join('\n'));
    const fromTools = toolEvents.flatMap((event) => {
      const text = JSON.stringify(event.result || {});
      return extractUrls(text);
    });
    return Array.from(new Set([...fromAnswer, ...fromTools])).slice(0, 8);
  }, [messages, toolEvents]);

  async function submit(value = input) {
    const message = value.trim();
    if (!message || loading) return;
    setLoading(true);
    setError('');
    setStreamStatus('');
    setInput('');
    const nextMessages = [...messages, { role: 'user' as const, content: message }];
    const body = { message, history: messages.slice(-12), session_id: sessionId };
    setMessages(nextMessages);
    try {
      let chat: ChatResponse;
      try {
        chat = await requestChatStream(body, setStreamStatus);
      } catch {
        setStreamStatus('Đang chuyển sang chế độ thường...');
        chat = await requestChatJson(body);
      }
      setSessionId(chat.session_id);
      setToolEvents(chat.tool_events || []);
      setMessages([...nextMessages, { role: 'assistant', content: chat.answer || '(no answer)' }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
      setMessages(messages);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void submit();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  function clearConversation() {
    const next = makeSessionId();
    setSessionId(next);
    setMessages([]);
    setToolEvents([]);
    setError('');
    sessionStorage.setItem('session_id', next);
    sessionStorage.removeItem('messages');
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>Research Agent</h1>
          <p>Trợ lý nghiên cứu dùng web, Twitter/X, URL, policy nội bộ và arXiv để tổng hợp câu trả lời kèm dấu vết công cụ.</p>
        </div>
        <span className={`status ${backendStatus}`}>{backendStatus}</span>
      </header>

      <section className="workspace">
        <aside className="samples">
          {prompts.map((prompt) => (
            <button key={prompt} type="button" onClick={() => setInput(prompt)} disabled={loading}>
              {prompt}
            </button>
          ))}
        </aside>

        <section className="chat-panel">
          <div className="messages">
            {messages.length === 0 ? <div className="empty">Nhập một câu hỏi nghiên cứu để bắt đầu.</div> : null}
            {messages.map((message, index) => (
              <article key={`${message.role}-${index}`} className={`bubble ${message.role}`}>
                <span>{message.role === 'user' ? 'bạn' : 'trợ lý'}</span>
                {message.role === 'assistant' ? renderMarkdown(message.content) : <p>{message.content}</p>}
              </article>
            ))}
            {loading ? <article className="bubble assistant loading"><span>trợ lý</span><p>{streamStatus || loadingSteps[loadingStep]}</p></article> : null}
          </div>

          {error ? <div className="error">{error}</div> : null}

          <form className="composer" onSubmit={onSubmit}>
            <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKeyDown} maxLength={4000} />
            <div className="actions">
              <button type="button" className="secondary" onClick={clearConversation} disabled={loading}>Xóa hội thoại</button>
              <button type="submit" disabled={loading || !input.trim()}>{loading ? 'Đang gửi' : 'Gửi'}</button>
            </div>
          </form>
        </section>

        <aside className="trace">
          <h2>Dấu vết công cụ</h2>
          {toolEvents.length === 0 ? <p className="muted">Chưa có tool call.</p> : null}
          {toolEvents.map((event, index) => (
            <details key={`${toolName(event)}-${index}`}>
              <summary>
                <span>{toolName(event)}</span>
                <strong>{event.result && 'error' in event.result ? 'lỗi' : 'thành công'}</strong>
              </summary>
              <pre>{JSON.stringify({ args: event.args, result: compactToolResult(event.result) }, null, 2)}</pre>
            </details>
          ))}
          <h2>Nguồn</h2>
          {sources.length === 0 ? <p className="muted">Chưa có URL nguồn.</p> : null}
          {sources.map((url) => <a key={url} href={url} target="_blank" rel="noreferrer">{url}</a>)}
        </aside>
      </section>
    </main>
  );
}
