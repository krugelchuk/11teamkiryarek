"""Learning content, question set and source-validated model adapter tests."""
import io
import json
import os
import unittest
from unittest.mock import patch

import test_admin
from app.assistant import answer
from app.learning import pack
from app.model import validate_quotes, ProviderUnavailable
from scripts.evaluate_assistant import evaluate


class LearningTests(unittest.TestCase):
    setUp = test_admin.ManagedDataTests.setUp
    tearDown = test_admin.ManagedDataTests.tearDown
    sign_in = test_admin.ManagedDataTests.sign_in
    employee = test_admin.ManagedDataTests.employee
    article = test_admin.ManagedDataTests.article

    def test_explicit_import_is_idempotent_and_preserves_existing_content(self):
        self.assertEqual(self.hr.call('GET','/api/knowledge')[1]['items'], [])
        original, _ = self.article(title='Собственный документ организации')
        employee, _ = self.employee()
        self.assertEqual(employee.call('POST','/api/admin/learning-pack/import',{})[0],403)
        self.assertEqual(employee.call('GET','/api/admin/learning-pack')[0],403)
        status, result, _ = self.hr.call('POST','/api/admin/learning-pack/import',{})
        self.assertEqual(status,201)
        self.assertEqual((result['created_documents'],result['created_courses']),(12,2))
        result=self.hr.call('POST','/api/admin/learning-pack/import',{})[1]
        self.assertEqual((result['created_documents'],result['created_courses']),(0,0))
        self.assertEqual((result['skipped_documents'],result['skipped_courses']),(12,2))
        self.assertEqual(len(self.hr.call('GET','/api/admin/knowledge')[1]['items']),13)
        self.assertEqual(self.hr.call('GET',f"/api/knowledge/{original['id']}")[1]['title'],'Собственный документ организации')

    def test_import_is_atomic_if_a_course_is_invalid(self):
        broken=pack()
        broken['courses'][0]['data']['duration_minutes']=0
        with patch('app.learning.pack',return_value=broken):
            self.assertEqual(self.hr.call('POST','/api/admin/learning-pack/import',{})[0],400)
        self.assertEqual(self.hr.call('GET','/api/knowledge')[1]['items'],[])
        self.assertEqual(self.hr.call('GET','/api/admin/courses')[1]['items'],[])
        self.assertEqual(self.hr.call('GET','/api/admin/learning-pack')[1]['imported_documents'],0)

    def test_pack_roles_and_both_courses_from_assignment_to_completion(self):
        self.hr.call('POST','/api/admin/learning-pack/import',{})
        employee, worker=self.employee()
        manager, _=self.employee('lead@example.test','manager')
        self.assertEqual(len(employee.call('GET','/api/knowledge')[1]['items']),9)
        self.assertEqual(len(manager.call('GET','/api/knowledge')[1]['items']),10)
        self.assertEqual(len(self.hr.call('GET','/api/knowledge')[1]['items']),12)
        courses=self.hr.call('GET','/api/admin/courses')[1]['items']
        self.assertEqual({course['correct_index'] for course in courses},{0,2})
        for course in courses:
            self.assertEqual(self.hr.call('POST','/api/admin/assignments',{'user_id':worker['id'],'course_id':course['id']})[0],201)
            details=employee.call('GET',f"/api/courses/{course['id']}")[1]
            self.assertEqual(len(details['lessons']),3)
            self.assertNotIn('correct_index',details['quiz'])
            for lesson in details['lessons']:
                employee.call('POST',f"/api/courses/{course['id']}/lessons/{lesson['id']}/complete",{})
            wrong=(course['correct_index']+1)%len(course['options'])
            self.assertFalse(employee.call('POST',f"/api/courses/{course['id']}/quiz",{'answer_index':wrong})[1]['passed'])
            self.assertEqual(employee.call('POST',f"/api/courses/{course['id']}/quiz",{'answer_index':course['correct_index']})[1]['course']['progress'],100)
        notes=employee.call('GET','/api/notifications')[1]['items']
        self.assertEqual(sum(n['type']=='course_completed' for n in notes),2)


class AssistantQualityTests(unittest.TestCase):
    def setUp(self):
        self.article={'id':81,'title':'Оформление отпуска','summary':'Как оформить отпуск',
                      'content':'Оформить отпуск можно в разделе «Мои заявки». Выберите даты и отправьте заявку.'}
        self.own={'id':9,'vacation_balance':18}

    def test_educational_question_set_sources_and_refusals(self):
        with patch.dict(os.environ,{'JANAMEN_AI_PROVIDER':'disabled'}):
            report=evaluate()
        self.assertEqual(report['passed'],30,[r for r in report['results'] if not r['passed']])
        self.assertEqual(report['false_answers'],0)

    def test_quote_validation_rejects_unknown_source_and_invented_text(self):
        valid={'found':True,'excerpts':[{'source_id':81,'quote':'Оформить отпуск можно в разделе «Мои заявки».'}]}
        self.assertEqual(validate_quotes(valid,[self.article])[0]['source_id'],81)
        for excerpts in ([{'source_id':99,'quote':valid['excerpts'][0]['quote']}],
                         [{'source_id':81,'quote':'Всем сотрудникам автоматически положено 99 дней.'}],[]):
            with self.assertRaises(ProviderUnavailable):
                validate_quotes({'found':True,'excerpts':excerpts},[self.article])

    def response(self, selection, status='completed'):
        return io.BytesIO(json.dumps({'status':status,'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(selection,ensure_ascii=False)}]}]},ensure_ascii=False).encode())

    def test_model_transport_shape_no_profile_and_only_verified_quote(self):
        selected={'found':True,'excerpts':[{'source_id':81,'quote':'Оформить отпуск можно в разделе «Мои заявки».'}]}
        env={'JANAMEN_AI_PROVIDER':'openai','OPENAI_API_KEY':'unit-test-not-a-real-key','OPENAI_MODEL':'test-model'}
        with patch.dict(os.environ,env), patch('app.model.urllib.request.urlopen',return_value=self.response(selected)) as transport:
            result=answer('Как оформить отпуск?', [self.article],self.own)
        self.assertTrue(result['found']); self.assertEqual(result['mode'],'grounded_llm')
        self.assertEqual(result['answer'],selected['excerpts'][0]['quote'])
        request=transport.call_args.args[0]
        payload=json.loads(request.data)
        self.assertFalse(payload['store'])
        self.assertTrue(payload['text']['format']['strict'])
        sent=json.loads(payload['input'])
        self.assertEqual(set(sent),{'question','documents'})
        self.assertNotIn('vacation_balance',payload['input'])

    def test_model_failure_or_fake_citation_falls_back_transparently(self):
        env={'JANAMEN_AI_PROVIDER':'openai','OPENAI_API_KEY':'unit-test-not-a-real-key','OPENAI_MODEL':'test-model'}
        with patch.dict(os.environ,env), patch('app.model.urllib.request.urlopen',side_effect=TimeoutError):
            result=answer('Как оформить отпуск?',[self.article],self.own)
        self.assertEqual(result['mode'],'extractive'); self.assertIn('notice',result)
        self.assertEqual(result['answer'],self.article['content'])
        fake={'found':True,'excerpts':[{'source_id':81,'quote':'Придуманное правило, которого нет в источнике.'}]}
        with patch.dict(os.environ,env), patch('app.model.urllib.request.urlopen',return_value=self.response(fake)):
            result=answer('Как оформить отпуск?',[self.article],self.own)
        self.assertNotIn('Придуманное правило',result['answer'])
        self.assertEqual(result['mode'],'extractive')

    def test_own_profile_never_sent_to_model_and_model_can_refuse(self):
        env={'JANAMEN_AI_PROVIDER':'openai','OPENAI_API_KEY':'unit-test-not-a-real-key','OPENAI_MODEL':'test-model'}
        with patch.dict(os.environ,env), patch('app.model.urllib.request.urlopen') as transport:
            result=answer('Сколько у меня осталось дней отпуска?',[self.article],self.own)
            transport.assert_not_called()
            self.assertIn('18',result['answer'])
        with patch.dict(os.environ,env), patch('app.model.urllib.request.urlopen',return_value=self.response({'found':False,'excerpts':[]})):
            result=answer('Как оформить отпуск?',[self.article],self.own)
        self.assertFalse(result['found']); self.assertEqual(result['sources'],[])
