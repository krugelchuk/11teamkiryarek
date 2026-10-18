import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Alert, Spinner, ErrorState } from '../components/ui';
import { errMsg, useAsync } from '../hooks/useAsync';
import { api } from '../api/endpoints';
import Setup from './Setup';
import Brand from '../components/Brand';
import LoginScene from '../components/LoginScene';
import Icon from '../components/Icon';

export default function Login() {
  const { login, sessionExpired } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setup = useAsync(() => api.setupStatus(), []);

  if (setup.loading && !setup.data) return <div className="boot"><Spinner label="Проверяем настройки…" /></div>;
  if (setup.error && !setup.data) return <div className="boot"><ErrorState error={setup.error} onRetry={setup.reload} /></div>;
  if (setup.data?.setup_required) return <Setup />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login login--scene">
      <div className="login-side">
        <Brand large />
        <div className="login-story">
          <span className="login-eyebrow"><span />ПРОСТРАНСТВО ВАШЕЙ КОМАНДЫ</span>
          <h2>Ваш следующий шаг.<br /><span>Начинается здесь.</span></h2>
          <p>Рабочие вопросы становятся проще, когда профиль, заявки и обучение — рядом.</p>
        </div>
        <LoginScene />
        <div className="login-side-footer"><span>Профиль</span><span>Заявки</span><span>Обучение</span><span>AI-помощник</span></div>
      </div>

      <div className="login-form-side">
      <div className="login-form-meta"><span>QADAM11</span><span>КАБИНЕТ СОТРУДНИКА</span></div>
      <form className="login-card" onSubmit={submit} aria-busy={busy}>
        <div className="login-welcome-icon"><Icon name="lock" size={27} /></div>
        <span className="login-form-eyebrow">РАДЫ ВАС ВИДЕТЬ</span>
        <h1>Вход в кабинет</h1>
        <p className="muted login-form-description">Войдите, чтобы всё важное для работы было под рукой.</p>

        {sessionExpired && <Alert kind="info">Сессия завершена. Войдите снова.</Alert>}
        {error && <Alert>{error}</Alert>}

        <label className="field">
          <span>Email</span>
          <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@company.kz" spellCheck={false} autoCapitalize="none" />
        </label>
        <label className="field">
          <span>Пароль</span>
          <div className="login-password-field">
            <input type={showPassword ? 'text' : 'password'} autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Введите пароль" />
            <button type="button" className="login-password-toggle" onClick={() => setShowPassword(value => !value)} aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'} aria-pressed={showPassword}><Icon name="eye" size={22} /></button>
          </div>
        </label>
        <button className="btn btn-primary btn-block" disabled={busy}>
          <span>{busy ? 'Входим…' : 'Войти'}</span>{!busy && <Icon name="arrow" size={22} />}
        </button>

        <p className="login-access-note">Нет доступа? Учётную запись создаёт HR вашей организации. Обратитесь к администратору.</p>
        {setup.data?.demo_mode && <Alert kind="info">Запущен демонстрационный режим. Тестовые аккаунты описаны в инструкции проекта.</Alert>}
      </form>
      <div className="login-form-footer"><Icon name="lock" size={15} /><span>Доступ к данным в соответствии с вашей ролью</span></div>
      </div>
    </div>
  );
}
