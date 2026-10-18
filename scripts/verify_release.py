"""Acceptance across two actual Python processes. Never changes the running database."""
import argparse
from datetime import timedelta
import json
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from app.database import today
from test_api import Client


def start(db):
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    process = subprocess.Popen([sys.executable, '-X', 'utf8', str(ROOT / 'server.py'), '--port', str(port), '--db', str(db)],
                               cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    base = f'http://127.0.0.1:{port}'
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError('Server exited during startup: ' + process.stderr.read().decode('utf-8', errors='replace'))
            try:
                with urllib.request.urlopen(base + '/api/health', timeout=.5) as response:
                    if response.status == 200:
                        return process, base
            except OSError:
                time.sleep(.1)
        raise RuntimeError('Server startup timed out')
    except BaseException:
        stop(process)
        raise


def stop(process):
    if process.poll() is None:
        process.terminate()
    try:
        process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workdir', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.workdir:
        args.workdir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    report = {'status':'passed', 'mode':'empty_database_no_demo', 'checks':[]}
    def checked(label, condition):
        if not condition:
            raise AssertionError(label)
        report['checks'].append(label)
    with tempfile.TemporaryDirectory(prefix='janamen-release-', dir=args.workdir) as folder:
        db = Path(folder) / 'acceptance.db'
        password = secrets.token_urlsafe(24)
        process, base = start(db)
        first_pid = process.pid
        try:
            hr = Client(base)
            checked('fresh_setup_required', hr.call('GET','/api/setup/status')[1]['setup_required'])
            checked('no_demo_mode', not hr.call('GET','/api/setup/status')[1]['demo_mode'])
            checked('bootstrap_hr', hr.call('POST','/api/setup', {'name':'Проверка HR','email':'hr@acceptance.test','password':password,'company':'Проверка запуска'})[0] == 201)
            def login(client, email):
                status, result, _ = client.call('POST','/api/auth/login', {'email':email,'password':password})
                checked('login_' + result.get('user',{}).get('role','failed'), status == 200)
                client.csrf = result['csrf_token']
                return result['user']
            login(hr, 'hr@acceptance.test')
            def add(name, email, role, manager=None):
                status, user, _ = hr.call('POST','/api/admin/users', {'name':name,'email':email,'password':password,'company':'Проверка запуска','role':role,'manager_id':manager,'vacation_balance':18})
                checked('create_' + role, status == 201)
                return user
            boss = add('Проверка руководителя','manager@acceptance.test','manager')
            worker = add('Проверка сотрудника','worker@acceptance.test','employee',boss['id'])
            employee, manager = Client(base), Client(base)
            login(employee, worker['email']); login(manager, boss['email'])
            checked('readonly_profile', employee.call('PATCH','/api/profile', {'vacation_balance':99})[0] == 404)
            start_date = today() + timedelta(days=30)
            status, record, _ = employee.call('POST','/api/requests', {'type':'vacation','start_date':str(start_date),'end_date':str(start_date+timedelta(days=2))})
            checked('create_vacation', status == 201)
            rid = record['id']
            checked('employee_cannot_approve', employee.call('POST',f'/api/requests/{rid}/decision', {'decision':'approved'})[0] == 403)
            checked('manager_approves', manager.call('POST',f'/api/requests/{rid}/decision', {'decision':'approved','comment':'Принято'})[0] == 200)
            checked('no_double_approval', manager.call('POST',f'/api/requests/{rid}/decision', {'decision':'approved'})[0] == 409)
            checked('balance_deducted_once', employee.call('GET','/api/profile')[1]['vacation_balance'] == 15)
            checked('history_stored', len(employee.call('GET',f'/api/requests/{rid}')[1]['history']) == 2)
            notes = employee.call('GET','/api/notifications')[1]['items']
            checked('status_notification', any(n['entity_id'] == rid and n['type'] == 'request_status' for n in notes))
            bid = '70000001088185194'
            checked('real_astana_catalog', len(hr.call('GET','/api/branches')[1]['items']) == 13)
            checked('hr_assigns_branch', hr.call('PATCH',f"/api/admin/users/{worker['id']}/branch", {'branch_id':bid})[0] == 200)
            checked('employee_cannot_change_branch', employee.call('PATCH',f"/api/admin/users/{worker['id']}/branch", {'branch_id':None})[0] == 403)
            checked('hr_sets_branch_minimum', hr.call('PATCH',f'/api/admin/branches/{bid}', {'min_staff':1})[0] == 200)
            calendar = manager.call('GET',f'/api/branches/{bid}?from={start_date}&to={start_date}')[1]
            checked('approved_leave_in_calendar', calendar['calendar'][0]['remaining'] == 0 and calendar['calendar'][0]['approved'] == 1)
            # Start a second real process with the same on-disk database.
            stop(process)
            process, base = start(db)
            second_pid = process.pid
            employee.base = base
            hr.base = base
            checked('new_python_process', first_pid != second_pid)
            checked('session_survives_restart', employee.call('GET','/api/auth/me')[0] == 200)
            checked('balance_survives_restart', employee.call('GET','/api/profile')[1]['vacation_balance'] == 15)
            checked('request_survives_restart', employee.call('GET',f'/api/requests/{rid}')[1]['status'] == 'approved')
            checked('notifications_survive_restart', len(employee.call('GET','/api/notifications')[1]['items']) == len(notes))
            checked('branch_assignment_survives_restart', employee.call('GET','/api/profile')[1]['branch_id'] == bid)
            checked('branch_minimum_survives_restart', hr.call('GET',f'/api/branches/{bid}')[1]['branch']['min_staff'] == 1)
            employee.call('POST','/api/auth/logout', {})
            checked('logout_revokes_session', employee.call('GET','/api/auth/me')[0] == 401)
        finally:
            stop(process)
    report['duration_seconds'] = round(time.monotonic()-started,3)
    report['check_count'] = len(report['checks'])
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
