"""Reproducible author-defined question set. No live personnel data or database needed."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.assistant import answer


def evaluate():
    pack = json.loads((ROOT/'content/learning-pack.json').read_text(encoding='utf-8'))
    cases = json.loads((ROOT/'content/assistant-eval.json').read_text(encoding='utf-8'))['cases']
    articles = [{**item['data'], 'id':index+1000, 'slug':item['slug']} for index,item in enumerate(pack['documents'])]
    by_id = {article['id']:article['slug'] for article in articles}
    results = []
    for case in cases:
        visible = [article for article in articles if case['role'] in article['roles']]
        response = answer(case['question'],visible,{'id':7,'vacation_balance':18})
        actual = ['profile' if source['url']=='/api/profile' else by_id.get(source['id']) for source in response['sources']]
        expected = case['expected_source']
        passed = not response['found'] if expected is None else response['found'] and expected in actual
        results.append({**case,'passed':bool(passed),'found':response['found'],'actual_sources':actual,'mode':response['mode']})
    positive = [result for result in results if result['expected_source'] is not None]
    negative = [result for result in results if result['expected_source'] is None]
    return {'dataset':'author_defined_educational_30_questions','mode':'extractive','total':len(results),
            'passed':sum(result['passed'] for result in results), 'positive_passed':sum(result['passed'] for result in positive),
            'positive_total':len(positive),'refusals_passed':sum(result['passed'] for result in negative),'refusals_total':len(negative),
            'false_answers':sum(result['found'] for result in negative),'results':results}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    old=os.environ.get('JANAMEN_AI_PROVIDER')
    os.environ['JANAMEN_AI_PROVIDER']='disabled'
    try:
        report=evaluate()
    finally:
        if old is None: os.environ.pop('JANAMEN_AI_PROVIDER',None)
        else: os.environ['JANAMEN_AI_PROVIDER']=old
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in report.items() if key!='results'},ensure_ascii=False))
    for result in report['results']:
        if not result['passed']: print('MISS',result['id'],result['question'],'expected',result['expected_source'],'got',result['actual_sources'])


if __name__=='__main__': main()
