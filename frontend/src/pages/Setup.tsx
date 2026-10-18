import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/endpoints';
import { useAuth } from '../auth/AuthContext';
import { Alert } from '../components/ui';
import { errMsg } from '../hooks/useAsync';
import Brand from '../components/Brand';

export default function Setup() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      await api.setup({ name, company, email, password });
      await login(email, password);
      navigate('/admin', { replace: true });
    } catch (e) { setError(errMsg(e)); }
    finally { setBusy(false); }
  }
  return <div className="login">
    <div className="login-side"><Brand large />
      <h2>Начните со своей организации</h2><p>Создайте первого HR-администратора. Затем добавьте сотрудников, курсы и документы базы знаний в кабинете.</p>
      <p>В новой базе нет заранее заданных людей, заявок или ответов.</p></div>
    <form className="login-card form" onSubmit={submit}>
      <h1>Первоначальная настройка</h1><p className="muted">Эта форма доступна только до создания первого аккаунта.</p>
      {error && <Alert>{error}</Alert>}
      <label className="field"><span>Ваше имя</span><input required maxLength={150} value={name} onChange={e => setName(e.target.value)} /></label>
      <label className="field"><span>Компания</span><input required maxLength={150} value={company} onChange={e => setCompany(e.target.value)} /></label>
      <label className="field"><span>Email HR</span><input required type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} /></label>
      <label className="field"><span>Пароль · минимум 10 символов</span><input required type="password" autoComplete="new-password" minLength={10} maxLength={256} value={password} onChange={e => setPassword(e.target.value)} /></label>
      <button className="btn btn-primary" disabled={busy}>{busy ? 'Создаём…' : 'Создать рабочее пространство'}</button>
    </form></div>;
}
