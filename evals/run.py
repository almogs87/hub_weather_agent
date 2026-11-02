"""Conversation evaluation with explicit synthetic weather. --live-model uses real LLM."""
import argparse
from datetime import timedelta
import json
from pathlib import Path
import tempfile
from app.agent import Service
from app.storage import Store

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
    args=p.parse_args()
    cases=json.loads(Path(__file__).with_name('cases.json').read_text())
    failures=0
    with tempfile.TemporaryDirectory() as directory:
        service=Service(Store(directory+'/eval.db'),EvaluationWeather(),mode='live' if args.live_model else 'demo')
        for identifier in ['siteA','siteB']:
            service.add_location(dict(id=identifier,latitude=40,longitude=-105,timezone='UTC'))
        conversation=None
        for case in cases:
            try:
                response=service.chat(dict(message=case['message'],conversation_id=conversation))
                conversation=response['conversation_id']
                assert response['intent']['action']==case['action'],'Wrong action'
                if 'hazard' in case:assert response['intent']['hazard']==case['hazard'],'Wrong hazard'
                if response['cards']:
                    assert all(c['evidence']['source_id']=='fixture:evaluation' for c in response['cards']),'Missing evidence'
                    if case.get('hazard')=='heat':
                        assert all(c['exceedance_percent']==100 for c in response['cards']),'Wrong heat calculation'
                print('PASS',case['message'])
            except Exception as exc:
                failures+=1
                print('FAIL',case['message'],str(exc))
    print(f'{len(cases)-failures}/{len(cases)} passed | model: {"live" if args.live_model else "demo parser"} | synthetic weather')
    return bool(failures)

if __name__=='__main__':raise SystemExit(main())
