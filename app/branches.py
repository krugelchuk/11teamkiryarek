"""Public branch locations and strictly scoped HR staffing views."""
import json
from datetime import date, timedelta
from pathlib import Path

from . import service as svc
from .database import audit, today

CATALOG = Path(__file__).resolve().parents[1] / 'fixtures/astana_branches.json'


def initialize(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS branches (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, address TEXT NOT NULL,
          district TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
          source_url TEXT NOT NULL, checked_at TEXT NOT NULL,
          min_staff INTEGER CHECK(min_staff IS NULL OR min_staff >= 0)
        );
        CREATE TABLE IF NOT EXISTS employee_branches (
          user_id INTEGER PRIMARY KEY REFERENCES users(id),
          branch_id TEXT NOT NULL REFERENCES branches(id)
        );
        CREATE INDEX IF NOT EXISTS members_branch ON employee_branches(branch_id);
    ''')
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    for item in catalog['items']:
        conn.execute('''INSERT INTO branches(id,name,address,district,lat,lon,source_url,checked_at)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,address=excluded.address,district=excluded.district,
            lat=excluded.lat,lon=excluded.lon,source_url=excluded.source_url,checked_at=excluded.checked_at''',
            (item['id'], 'Jana Post', item['address'], item['district'], item['lat'], item['lon'],
             'https://2gis.kz/astana/firm/' + item['id'], catalog['checked_at']))


def dates(query):
    start = svc.parse_date(query.get('from', [str(today())])[0], 'from')
    default_end = start + timedelta(days=min(13, (date.max - start).days))
    end = svc.parse_date(query.get('to', [str(default_end)])[0], 'to')
    if end < start or (end - start).days > 61:
        svc.fail(400, 'validation_error', 'Выберите период от 1 до 62 календарных дней')
    return [str(start + timedelta(days=i)) for i in range((end - start).days + 1)]


def scope(user):
    if user['role'] == 'hr':
        return '1=1', (), 'Все сотрудники филиала'
    if user['role'] == 'manager':
        return '(u.manager_id=? OR u.id=?)', (user['id'], user['id']), 'Вы и ваши прямые подчинённые'
    return 'u.id=?', (user['id'],), 'Только ваши данные'


def members(conn, user, branch_id=None):
    where, params, _ = scope(user)
    if branch_id is not None:
        where += ' AND eb.branch_id=?'
        params += (branch_id,)
    return [dict(row) for row in conn.execute('''SELECT u.id,u.name,u.role,u.position,u.department,
        eb.branch_id FROM users u JOIN employee_branches eb ON eb.user_id=u.id
        WHERE ''' + where + ' ORDER BY u.name,u.id', params)]


def leave_rows(conn, user, days, branch_id=None):
    where, params, _ = scope(user)
    if branch_id is not None:
        where += ' AND eb.branch_id=?'
        params += (branch_id,)
    return [dict(row) for row in conn.execute('''SELECT r.id,r.user_id,r.start_date,r.end_date,r.status,
        eb.branch_id FROM requests r JOIN users u ON u.id=r.user_id
        JOIN employee_branches eb ON eb.user_id=u.id WHERE ''' + where + '''
        AND r.status IN ('approved','pending') AND r.start_date<=? AND r.end_date>=? ORDER BY r.start_date,r.id''',
        params + (days[-1], days[0]))]


def coverage(people, leaves, days, threshold):
    result = []
    for day in days:
        approved = {r['user_id'] for r in leaves if r['status'] == 'approved' and r['start_date'] <= day <= r['end_date']}
        pending = {r['user_id'] for r in leaves if r['status'] == 'pending' and r['start_date'] <= day <= r['end_date']}
        remaining = len(people) - len(approved)
        result.append({'date': day, 'approved': len(approved), 'pending': len(pending), 'remaining': remaining,
                       'shortage': threshold is not None and remaining < threshold})
    return result


def listing(conn, user, query):
    days = dates(query)
    people, leaves = members(conn, user), leave_rows(conn, user, days)
    own = conn.execute('SELECT branch_id FROM employee_branches WHERE user_id=?', (user['id'],)).fetchone()
    items = []
    for row in conn.execute('SELECT * FROM branches ORDER BY address'):
        item = dict(row)
        # A whole-branch threshold must never be applied to a manager's partial team.
        threshold = item['min_staff'] if user['role'] == 'hr' else None
        item['min_staff'] = threshold
        scoped = [p for p in people if p['branch_id'] == item['id']]
        calendar = coverage(scoped, [r for r in leaves if r['branch_id'] == item['id']], days, threshold)
        item.update(member_count=len(scoped), min_remaining=min(d['remaining'] for d in calendar),
                    max_approved=max(d['approved'] for d in calendar),
                    max_pending=max(d['pending'] for d in calendar),
                    shortage_days=sum(d['shortage'] for d in calendar), is_mine=bool(own and own[0] == item['id']))
        items.append(item)
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    return {'items': items, 'from': days[0], 'to': days[-1], 'scope': scope(user)[2],
            'demo_mode': conn.execute("SELECT value FROM settings WHERE key='demo_mode'").fetchone()[0] == '1',
            'notice': catalog['notice'], 'source_url': catalog['source_url']}


def detail(conn, user, branch_id, query):
    branch = conn.execute('SELECT * FROM branches WHERE id=?', (branch_id,)).fetchone()
    if not branch:
        svc.fail(404, 'not_found', 'Филиал не найден')
    days = dates(query)
    people, leaves = members(conn, user, branch_id), leave_rows(conn, user, days, branch_id)
    item = dict(branch)
    if user['role'] != 'hr':
        item['min_staff'] = None
    return {'branch': item, 'members': people, 'leaves': leaves, 'days': days,
            'calendar': coverage(people, leaves, days, item['min_staff']), 'scope': scope(user)[2]}


def employee(conn, user, branch_id, uid):
    if not any(p['id'] == uid for p in members(conn, user, branch_id)):
        svc.fail(404, 'not_found', 'Сотрудник не найден')
    person = svc.profile(conn, uid)
    courses = svc.courses(conn, person)['items']
    requests = svc.list_requests(conn, person)['items']
    return {'profile': person, 'courses': courses, 'requests': requests}


def assign(conn, user, uid, data):
    svc.require_role(user, 'hr')
    svc.fields(data, {'branch_id'})
    svc.profile(conn, uid)
    bid = data.get('branch_id')
    if bid is None:
        conn.execute('DELETE FROM employee_branches WHERE user_id=?', (uid,))
    elif not isinstance(bid, str) or not conn.execute('SELECT 1 FROM branches WHERE id=?', (bid,)).fetchone():
        svc.fail(400, 'validation_error', 'Выберите филиал из справочника')
    else:
        conn.execute('''INSERT INTO employee_branches VALUES(?,?) ON CONFLICT(user_id)
            DO UPDATE SET branch_id=excluded.branch_id''', (uid, bid))
    audit(conn, user['id'], 'branch_assigned', 'user', uid)
    return svc.profile(conn, uid)


def configure(conn, user, bid, data):
    svc.require_role(user, 'hr')
    svc.fields(data, {'min_staff'})
    value = data.get('min_staff')
    if value is not None and (type(value) is not int or not 0 <= value <= 10000):
        svc.fail(400, 'validation_error', 'Минимум сотрудников: целое число от 0 до 10000 или null')
    if not conn.execute('UPDATE branches SET min_staff=? WHERE id=?', (value, bid)).rowcount:
        svc.fail(404, 'not_found', 'Филиал не найден')
    audit(conn, user['id'], 'branch_threshold', 'branch', int(bid))
    return {'ok': True}


def prepare_demo(conn):
    """One-time, clearly fictional placement; never replace an HR edit on restart."""
    marker = 'astana_demo_placements_v1'
    if conn.execute('SELECT 1 FROM settings WHERE key=?', (marker,)).fetchone():
        return
    for email, bid in [('employee@demo.local', '70000001088185194'), ('manager@demo.local', '70000001088185194'),
                       ('hr@demo.local', '70000001088245648'), ('other@demo.local', '70000001110597258'),
                       ('other-manager@demo.local', '70000001110597258')]:
        conn.execute('''INSERT OR IGNORE INTO employee_branches SELECT id,? FROM users WHERE email=?''', (bid, email))
    conn.execute('INSERT INTO settings VALUES(?,?)', (marker, '1'))
