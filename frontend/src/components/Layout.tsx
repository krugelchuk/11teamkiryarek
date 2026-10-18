import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { ROLE_LABEL, initials } from '../lib/format';
import type { Role } from '../api/types';
import Icon from './Icon';
import Brand from './Brand';
import WorkspaceBackdrop from './WorkspaceBackdrop';
import { errMsg } from '../hooks/useAsync';

interface NavItem {
  to: string;
  label: string;
  icon: string;
  roles?: Role[];
  badge?: 'unread';
}

const NAV: NavItem[] = [
  { to: '/', label: 'Главная', icon: 'home' },
  { to: '/requests', label: 'Мои заявки', icon: 'doc' },
  { to: '/branches', label: 'Команда на карте', icon: 'map' },
  { to: '/approvals', label: 'Согласование', icon: 'check', roles: ['manager', 'hr'] },
  { to: '/academy', label: 'Jana Academy', icon: 'book' },
  { to: '/assistant', label: 'AI Jana', icon: 'spark' },
  { to: '/notifications', label: 'Уведомления', icon: 'bell', badge: 'unread' },
  { to: '/admin', label: 'Управление данными', icon: 'doc', roles: ['hr'] },
  { to: '/integrations', label: 'Корпоративные системы', icon: 'link', roles: ['hr'] },
];

export default function Layout() {
  const { user, logout, unread } = useAuth();
  const [open, setOpen] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const loc = useLocation();

  useEffect(() => {
    setOpen(false);
    window.scrollTo(0, 0);
  }, [loc.pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  if (!user) return null;
  const items = NAV.filter((n) => !n.roles || n.roles.includes(user.role));

  async function signOut() {
    setLoggingOut(true);
    setLogoutError(null);
    try {
      await logout();
    } catch (error) {
      setLogoutError(errMsg(error));
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <div className="shell">
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <Brand />
          <button className="icon-btn sidebar-close-btn" onClick={() => setOpen(false)} aria-label="Закрыть меню">
            ✕
          </button>
        </div>
        <div className="nav-caption">РАБОЧЕЕ ПРОСТРАНСТВО</div>
        <nav className="nav" aria-label="Основное меню">
          {items.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === '/'}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setOpen(false)}
            >
              <span className="nav-icon" aria-hidden>
                <Icon name={n.icon} />
              </span>
              <span>{n.label}</span>
              {n.badge === 'unread' && unread > 0 && <span className="nav-badge">{unread > 99 ? '99+' : unread}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="user-chip">
            <span className="avatar">{initials(user.name)}</span>
            <div className="user-meta">
              <strong>{user.name}</strong>
              <span>{ROLE_LABEL[user.role]}</span>
            </div>
          </div>
          {logoutError && <p role="alert" className="small">Не удалось выйти: {logoutError}</p>}
          <button className="btn btn-ghost-dark" onClick={() => void signOut()} disabled={loggingOut}>
            {loggingOut ? 'Выходим…' : 'Выйти'}
          </button>
        </div>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}

      <div className="main">
        <WorkspaceBackdrop />
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setOpen(true)} aria-label="Открыть меню">
            <Icon name="menu" />
          </button>
          <span className="topbar-title">{user.company} <span className="topbar-separator">/</span> Личный кабинет</span>
          <NavLink to="/notifications" className="bell" aria-label={`Уведомления: ${unread} непрочитанных`}>
            <Icon name="bell" size={22} />{unread > 0 && <span className="bell-dot">{unread > 99 ? '99+' : unread}</span>}
          </NavLink>
          <span className="role-pill">{ROLE_LABEL[user.role]}</span>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
