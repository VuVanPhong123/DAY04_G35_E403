import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from 'react';
import type { ChatMessage, ChatResponse, ToolEvent } from './types';

const prompts = [
  'Tin AI hom nay co gi noi bat?',
  'Lay 5 tweet moi nhat cua Sam Altman.',
  'Moi nguoi dang ban gi ve OpenAI tren Twitter?',
  'Tom tat URL nay: https://openai.com/research/',
  'Tim 3 paper arXiv moi ve agent evaluation.',
];

function makeSessionId() {
  return crypto.randomUUID();
}

function extractUrls(text: string) {
  return Array.from(new Set(text.match(/https?:\/\/[^\s)]+/g) || []));
}

function toolName(event: ToolEvent) {
  return event.tool || event.name || 'tool';
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
    setInput('');
    const nextMessages = [...messages, { role: 'user' as const, content: message }];
    setMessages(nextMessages);
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, history: messages.slice(-12), session_id: sessionId }),
      });
      const data = await response.json() as ChatResponse | { detail?: string; error?: string };
      if (!response.ok) {
        throw new Error('detail' in data ? data.detail || 'Request failed' : 'Request failed');
      }
      const chat = data as ChatResponse;
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
          <p>Searches web, social posts, URLs, company policy, and arXiv sources, then answers with a visible tool trace.</p>
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
            {messages.length === 0 ? <div className="empty">Start with a research question.</div> : null}
            {messages.map((message, index) => (
              <article key={`${message.role}-${index}`} className={`bubble ${message.role}`}>
                <span>{message.role}</span>
                <p>{message.content}</p>
              </article>
            ))}
            {loading ? <article className="bubble assistant"><span>assistant</span><p>Working...</p></article> : null}
          </div>

          {error ? <div className="error">{error}</div> : null}

          <form className="composer" onSubmit={onSubmit}>
            <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKeyDown} maxLength={4000} />
            <div className="actions">
              <button type="button" className="secondary" onClick={clearConversation} disabled={loading}>Clear</button>
              <button type="submit" disabled={loading || !input.trim()}>{loading ? 'Sending' : 'Send'}</button>
            </div>
          </form>
        </section>

        <aside className="trace">
          <h2>Tool Trace</h2>
          {toolEvents.length === 0 ? <p className="muted">No tool calls yet.</p> : null}
          {toolEvents.map((event, index) => (
            <details key={`${toolName(event)}-${index}`}>
              <summary>
                <span>{toolName(event)}</span>
                <strong>{event.result && 'error' in event.result ? 'error' : 'success'}</strong>
              </summary>
              <pre>{JSON.stringify({ args: event.args, result: event.result }, null, 2)}</pre>
            </details>
          ))}
          <h2>Sources</h2>
          {sources.length === 0 ? <p className="muted">No URLs returned yet.</p> : null}
          {sources.map((url) => <a key={url} href={url} target="_blank" rel="noreferrer">{url}</a>)}
        </aside>
      </section>
    </main>
  );
}

