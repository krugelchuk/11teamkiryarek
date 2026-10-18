import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api } from '../api/endpoints';
import type { AssistantAnswer, AssistantSource, KnowledgeDoc } from '../api/types';
import { ErrorState, Modal, PageHeader, Spinner } from '../components/ui';
import { errMsg, useAsync } from '../hooks/useAsync';


type Msg =
  | { id: number; role: 'user'; text: string }
  | { id: number; role: 'bot'; text: string; found: boolean; sources: AssistantSource[]; mode: AssistantAnswer['mode']; notice?: string }
  | { id: number; role: 'error'; text: string; question: string };

export default function Assistant() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [doc, setDoc] = useState<{ title: string; src: AssistantSource | { id: number; title: string; url: string } } | null>(null);
  const seq = useRef(0);
  const endRef = useRef<HTMLDivElement>(null);
  const kb = useAsync(() => api.knowledge(), []);
  const connection = useAsync(() => api.assistantStatus(), []);
  const suggestions = kb.data?.items.slice(0, 4).map(article => article.title) ?? [];

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [msgs, busy]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setInput('');
    setMsgs((m) => [...m, { id: ++seq.current, role: 'user', text: q }]);
    setBusy(true);
    try {
      const r = await api.ask(q);
      setMsgs((m) => [...m, { id: ++seq.current, role: 'bot', text: r.answer, found: r.found, sources: r.sources ?? [], mode: r.mode, notice: r.notice }]);
    } catch (e) {
      setMsgs((m) => [...m, { id: ++seq.current, role: 'error', text: errMsg(e), question: q }]);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(input);
  }

  return (
    <>
      <PageHeader title="AI Jana" subtitle="HR-помощник ищет в доступных вам документах и показывает источник" />
      <div className="grid-chat">
        <section className="card chat">
          <div className="mode-note">
            {connection.data?.note ?? 'Ответы опираются на доступные документы. Источники можно открыть под каждым подтверждённым ответом.'} Помощник не принимает кадровых решений.
          </div>
          <div className="chat-log" aria-live="polite">
            {msgs.length === 0 && (
              <div className="chat-empty">
                <p>Задайте типовой HR-вопрос или выберите подсказку:</p>
                <div className="chips">
                  {suggestions.map((s) => (
                    <button key={s} className="chip" onClick={() => void ask(s)} disabled={busy}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {msgs.map((m) => (
              <div key={m.id} className={`msg msg-${m.role}`}>
                {m.role === 'user' && <div className="bubble">{m.text}</div>}
                {m.role === 'bot' && (
                  <div className={`bubble ${m.found || m.mode === 'conversation' ? '' : 'bubble-nf'}`}>
                    <div className="muted small">{m.mode === 'grounded_llm' ? 'Модель · проверенные цитаты' : m.mode === 'conversation' ? 'AI Jana · подсказка' : 'Локальный поиск по документам'}</div>
                    {m.notice && <div className="muted small" role="status">{m.notice}</div>}
                    {m.found || m.mode === 'conversation' ? (
                      <div className="pre-text">{m.text}</div>
                    ) : (
                      <>
                        <strong>Надёжного ответа в базе знаний нет</strong>
                        <div className="pre-text">{m.text}</div>
                        <div className="muted small">Помощник не отвечает без источника. Лучше уточнить вопрос у HR — напишите в HR-отдел вашей компании.</div>
                      </>
                    )}
                    {m.sources.length > 0 && (
                      <div className="sources">
                        <span className="muted small">Источники:</span>
                        {m.sources.map((s) => {
                          const displayTitle = s.title?.trim() || 'Документ базы знаний';
                          return (
                            <button key={s.id} className="source" onClick={() => setDoc({ title: displayTitle, src: s })}>
                              📄 {displayTitle}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
                {m.role === 'error' && (
                  <div className="bubble bubble-err">
                    {m.text}
                    <div>
                      <button className="btn btn-secondary btn-sm" onClick={() => void ask(m.question)} disabled={busy}>
                        Повторить вопрос
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
            {busy && (
              <div className="msg msg-bot">
                <div className="bubble typing">Ищу в базе знаний…</div>
              </div>
            )}
            <div ref={endRef} />
          </div>
          {msgs.length > 0 && (
            <div className="chips chips-inline">
              {suggestions.map((s) => (
                <button key={s} className="chip chip-sm" onClick={() => void ask(s)} disabled={busy}>
                  {s}
                </button>
              ))}
            </div>
          )}
          <form className="chat-input" onSubmit={onSubmit}>
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Спросите про отпуск, обучение, документы…" maxLength={500} aria-label="Ваш вопрос" />
            <button className="btn btn-primary" disabled={busy || !input.trim()}>
              Отправить
            </button>
          </form>
        </section>

        <aside className="card">
          <h2>База знаний</h2>
          <p className="muted small">Документы, доступные вашей роли.</p>
          {kb.loading && !kb.data ? (
            <Spinner />
          ) : kb.error && !kb.data ? (
            <ErrorState error={kb.error} onRetry={kb.reload} />
          ) : (kb.data?.items.length ?? 0) === 0 ? (
            <p className="muted">Документов нет.</p>
          ) : (
            <ul className="list">
              {kb.data!.items.map((d) => (
                <li key={d.id} className="list-item col">
                  <button className="link-btn" onClick={() => setDoc({ title: d.title, src: { id: d.id, title: d.title, url: `/api/knowledge/${d.id}` } })}>
                    {d.title}
                  </button>
                  <span className="muted small">{d.summary}</span>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>

      {doc && <DocModal title={doc.title} url={doc.src.url} onClose={() => setDoc(null)} />}
    </>
  );
}

function DocModal({ title, url, onClose }: { title: string; url: string; onClose: () => void }) {
  const q = useAsync<KnowledgeDoc>(() => api.sourceDoc(url), [url]);
  const modalTitle = title?.trim() || q.data?.title || 'Источник документа';
  return (
    <Modal title={modalTitle} onClose={onClose} wide>
      {q.loading && !q.data ? (
        <Spinner />
      ) : q.error ? (
        <ErrorState error={q.error} onRetry={q.reload} />
      ) : q.data ? (
        <div>
          {q.data.summary && <p className="muted small" style={{ marginBottom: 14 }}>{q.data.summary}</p>}
          <div className="pre-text">{q.data.content || 'Содержимое документа пусто.'}</div>
        </div>
      ) : null}
    </Modal>
  );
}
