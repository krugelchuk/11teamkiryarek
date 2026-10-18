"""Explicit, repeatable preparation of a separate fictional presentation database."""
import argparse
from contextlib import closing
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import initialize, connect
from app import learning, service, branches


def prepare(db):
    initialize(db, seed_demo=True)
    with closing(connect(db)) as conn, conn:
        if conn.execute("SELECT value FROM settings WHERE key='demo_mode'").fetchone()[0] != '1':
            raise ValueError('Use a separate demo database. Existing organization data is not modified.')
        hr = conn.execute("SELECT id FROM users WHERE email='hr@demo.local' AND role='hr'").fetchone()
        worker = conn.execute("SELECT id FROM users WHERE email='employee@demo.local' AND role='employee'").fetchone()
        if not hr or not worker:
            raise ValueError('This database has no standard demo accounts. Choose a new demo database.')
        actor = service.profile(conn, hr['id'])
        branches.prepare_demo(conn)
        conn.commit()
        result = learning.import_pack(conn, actor)
        conn.commit()
        assigned = 0
        for item in conn.execute("SELECT entity_id FROM learning_imports WHERE kind='course'").fetchall():
            cid = item['entity_id']
            if not conn.execute('SELECT 1 FROM enrollments WHERE user_id=? AND course_id=?', (worker['id'], cid)).fetchone():
                service.assign_course(conn, actor, {'user_id': worker['id'], 'course_id': cid})
                conn.commit()
                assigned += 1
        return {**result, 'assigned_courses': assigned}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=Path, default=Path(__file__).resolve().parents[1] / 'data/demo.db')
    args = parser.parse_args()
    print(prepare(args.db))
