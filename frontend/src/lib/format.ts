import type { CourseStatus, RequestStatus, Role } from '../api/types';

export const ROLE_LABEL: Record<Role, string> = {
  employee: 'Сотрудник',
  manager: 'Руководитель',
  hr: 'HR / администратор',
};

export const STATUS_LABEL: Record<RequestStatus, string> = {
  pending: 'На согласовании',
  approved: 'Одобрена',
  rejected: 'Отклонена',
  cancelled: 'Отменена',
};

export const COURSE_STATUS_LABEL: Record<CourseStatus, string> = {
  assigned: 'Назначен',
  in_progress: 'В процессе',
  completed: 'Пройден',
};

export const TYPE_LABEL: Record<string, string> = { vacation: 'Отпуск' };

/** YYYY-MM-DD -> 02.11.2026 (без сдвига часовых поясов) */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (m && iso.length <= 10) return `${m[3]}.${m[2]}.${m[1]}`;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('ru-RU');
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function fmtPeriod(start: string, end: string): string {
  return start === end ? fmtDate(start) : `${fmtDate(start)} — ${fmtDate(end)}`;
}

export function todayISO(): string {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${dd}`;
}

/** Календарные дни включительно (упрощение MVP, как на backend). */
export function inclusiveDays(start: string, end: string): number | null {
  if (!start || !end) return null;
  const a = Date.parse(`${start}T00:00:00Z`);
  const b = Date.parse(`${end}T00:00:00Z`);
  if (Number.isNaN(a) || Number.isNaN(b) || b < a) return null;
  return Math.round((b - a) / 86400000) + 1;
}

export function plural(n: number, one: string, few: string, many: string): string {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return many;
  if (b > 1 && b < 5) return few;
  if (b === 1) return one;
  return many;
}

export const daysWord = (n: number) => `${n} ${plural(n, 'день', 'дня', 'дней')}`;

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('');
}
