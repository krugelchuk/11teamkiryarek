import { useState } from 'react';
import { integrationApi, type EnterpriseIntegration, type IntegrationPreview } from '../api/integrations';
import { Alert, ErrorState, PageHeader, Spinner } from '../components/ui';
import { errMsg, useAsync } from '../hooks/useAsync';
import { fmtDateTime } from '../lib/format';
import Icon from '../components/Icon';
import '../integrations.css';

export default function Integrations() {
  const catalog = useAsync(() => integrationApi.list(), []);
  return <>
    <PageHeader title="Корпоративные системы" subtitle="Место для будущего обмена кадровыми данными и документами" />
    <section className="integration-intro">
      <span className="integration-eyebrow">QADAM11 · РАЗВИТИЕ ПЛАТФОРМЫ</span>
      <h2>Один кабинет.<br /><span>Связь с системами компании.</span></h2>
      <p>Кадровая система станет источником официальных данных, а документооборот — следующим шагом после согласования заявки.</p>
      <div className="integration-flow" aria-label="План будущего обмена"><span>1С:ЗУП<small>Профиль и остаток</small></span><span aria-hidden="true">→</span><strong>Qadam11<small>Кабинет и заявка</small></strong><span aria-hidden="true">→</span><span>Documentolog<small>Документ и подпись</small></span></div>
    </section>
    {catalog.loading ? <Spinner /> : catalog.error ? <ErrorState error={catalog.error} onRetry={catalog.reload} /> : catalog.data && <>
      <div className="integration-disclaimer" role="note"><Icon name="link" size={22} /><div><strong>Демонстрация будущих интеграций</strong><p>{catalog.data.notice}</p></div></div>
      <div className="enterprise-integrations">{catalog.data.items.map(item => <IntegrationCard key={item.id} item={item} />)}</div>
      <section className="integration-roadmap"><h2>Следующий шаг после прототипа</h2><p>Получить доступ к тестовым средам компании, согласовать поля и маршруты документов, затем заменить заглушки настоящими адаптерами. Основной кабинет, заявки и обучение продолжат работать через тот же сервер.</p></section>
    </>}
  </>;
}

function IntegrationCard({item}: {item: EnterpriseIntegration}) {
  const [preview, setPreview] = useState<IntegrationPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function showPreview() {
    setBusy(true); setError(null);
    try { setPreview(await integrationApi.preview(item.id)); }
    catch (err) { setError(errMsg(err)); } finally { setBusy(false); }
  }
  return <section className="card enterprise-integration">
    <div className="integration-card-heading"><span className={`integration-monogram ${item.id === '1c-zup' ? 'integration-onec' : ''}`} aria-hidden="true">{item.id === '1c-zup' ? '1C' : 'D'}</span><span className="integration-stub-label">ЗАГЛУШКА · НЕ ПОДКЛЮЧЕНО</span></div>
    <h2>{item.title}</h2><p className="integration-caption">{item.caption}</p><p className="integration-description">{item.description}</p>
    <span className="integration-direction">{item.direction}</span>
    <h3>Какие данные будут передаваться</h3><ul className="integration-fields">{item.fields.map(field => <li key={field}>{field}</li>)}</ul>
    <p className="integration-next-step">{item.next_step}</p>
    <button className="btn btn-secondary" onClick={() => void showPreview()} disabled={busy} aria-expanded={!!preview}>{busy ? 'Готовим пример…' : preview ? 'Обновить пример обмена' : 'Посмотреть пример обмена'} <Icon name="arrow" size={18} /></button>
    {error && <Alert>{error}</Alert>}
    {preview && <div className="integration-preview" role="region" aria-label={`Пример обмена ${item.title}`}>
      <strong>Пример получен от локальной заглушки</strong><p>{preview.notice}</p>
      <ol>{preview.steps.map(step => <li key={step}>{step}</li>)}</ol>
      <details className="integration-json"><summary>Данные запроса и ответа</summary><h4>Запрос</h4><pre>{JSON.stringify(preview.request, null, 2)}</pre><h4>Ответ заглушки</h4><pre>{JSON.stringify(preview.response, null, 2)}</pre></details>
      <small>Пример сформирован: {fmtDateTime(preview.generated_at)} · Внешних вызовов: 0 · Данные не сохранены</small>
      <button className="integration-hide" onClick={() => setPreview(null)}>Скрыть пример</button>
    </div>}
  </section>;
}
