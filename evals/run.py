"""Conversation evaluation with explicit synthetic weather. --live-model calls configured provider."""
import argparse
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
from time import perf_counter
from app.agent import Service
from app.storage import Store
from app.providers import ModelConfig

class EvaluationWeather:
    def fetch(self,request):
        rows=[]
        day=request.start
        while day<=request.end:
            rows.append(dict(date=day.isoformat(),snowfall_sum=10 if day.day==1 else 0,temperature_2m_max=36,temperature_2m_min=-15,precipitation_sum=0,wind_speed_10m_max=0))
            day+=timedelta(days=1)
        return dict(rows=rows,evidence=dict(source_id='fixture:evaluation',source='Synthetic evaluation data'))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live-model',action='store_true')
    p.add_argument('--report',type=Path)
    args=p.parse_args()
    cases=json.loads(Path(__file__).with_name('cases.json').read_text())
    config=ModelConfig.load().public() if args.live_model else dict(provider='demo',model='deterministic-parser',configured=True)
    results=[]
    with tempfile.TemporaryDirectory() as directory:
        service=Service(Store(directory+'/eval.db'),EvaluationWeather(),mode='live' if args.live_model else 'demo')
        for identifier in ['siteA','siteB']:
            service.add_location(dict(id=identifier,latitude=40,longitude=-105,timezone='UTC'))
        conversation=None
        for case in cases:
            began=perf_counter()
            item=dict(message=case['message'],passed=False)
            try:
                response=service.chat(dict(message=case['message'],conversation_id=conversation))
                conversation=response['conversation_id']
                item['intent']=response['intent']
                assert response['intent']['action']==case['action'],'Wrong action'
                if 'hazard' in case:assert response['intent']['hazard']==case['hazard'],'Wrong hazard'
                if response['cards']:
                    assert all(c['evidence']['source_id']=='fixture:evaluation' for c in response['cards']),'Missing evidence'
                    if case.get('hazard')=='heat':
                        assert all(c['exceedance_percent']==100 for c in response['cards']),'Wrong heat calculation'
                item['passed']=True
                print('PASS',case['message'])
            except Exception as exc:
                item['error']=str(exc)
                print('FAIL',case['message'],str(exc))
            item['latency_seconds']=round(perf_counter()-began,3)
            results.append(item)
    passed=sum(r['passed'] for r in results)
    report=dict(created_at=datetime.now(timezone.utc).isoformat(),model_config=config,weather='synthetic evaluation fixtures',passed=passed,total=len(cases),cases=results)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('Report:',args.report)
    print(f'{passed}/{len(cases)} passed | {config["provider"]} / {config["model"]} | synthetic weather')
    return passed!=len(cases)

if __name__=='__main__':raise SystemExit(main())
