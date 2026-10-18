"""Opt-in, idempotent educational content import; existing records stay intact."""
import json
from pathlib import Path

from . import admin
from .service import require_role


def pack():
    return json.loads((Path(__file__).resolve().parents[1] / 'content/learning-pack.json').read_text(encoding='utf-8'))


def summary(conn, user):
    require_role(user, 'hr')
    material = pack()
    entries = {(r['kind'],r['slug']) for r in conn.execute('SELECT kind,slug FROM learning_imports')}
    return {'title':material['title'], 'disclaimer':material['disclaimer'],
            'documents_count':len(material['documents']), 'courses_count':len(material['courses']),
            'imported_documents':sum(('document',d['slug']) in entries for d in material['documents']),
            'imported_courses':sum(('course',c['slug']) in entries for c in material['courses'])}


def import_pack(conn, user):
    require_role(user,'hr')
    material = pack()
    conn.execute('BEGIN IMMEDIATE')
    result = {'created_documents':0,'created_courses':0,'skipped_documents':0,'skipped_courses':0}
    for kind, plural, items in [('document','documents',material['documents']),('course','courses',material['courses'])]:
        for item in items:
            if conn.execute('SELECT entity_id FROM learning_imports WHERE kind=? AND slug=?',(kind,item['slug'])).fetchone():
                result['skipped_'+plural]+=1
                continue
            saved = admin.save_article(conn,user,item['data']) if kind == 'document' else admin.save_course(conn,user,item['data'])
            conn.execute('INSERT INTO learning_imports VALUES(?,?,?)',(kind,item['slug'],saved['id']))
            result['created_'+plural]+=1
    return result
