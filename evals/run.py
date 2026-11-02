"""Conversation evaluation with explicit synthetic weather. --live-model calls configured provider."""
import argparse
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
from time import perf_counter,sleep
from app.agent import Service
from app.storage import Store
from app.providers import ModelConfig
from app.hubs import seed_examples

class EvaluationWeather:
    def fetch(self,request):
        rows=[]
        day=request.start
        while day<=request.end:
            rows.append(dict(date=day.isoformat(),snowfall_sum=10 if day.day==1 else 0,temperature_2m_max=36,temperature_2m_min=-15,precipitation_sum=0,wind_speed_10m_max=0))
            day+=timedelta(days=1)
        return dict(rows=rows,evidence=dict(source_id='fixture:evaluation',source='Synthetic evaluation data'))

class EvaluationFEMA:
    """Explicit synthetic county scores for repeatable model evaluations."""
    def fetch(self,county_fips):
        values={'17031':90,'26163':70,'27053':80,'12086':85,'48201':95,'48113':60,'08031':40,'99999':50}
        score=values[county_fips]
        return dict(county_fips=county_fips,county='Synthetic',state='XX',
                    scores=dict(winter=score,hurricane=score,inland_flood=score,coastal_flood=score),
                    evidence=dict(source_id='fixture:evaluation-fema',source='Synthetic FEMA evaluation data'))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live-model',action='store_true')
    p.add_argument('--report',type=Path)
    p.add_argument('--delay-seconds',type=float,default=0,help='Pause between cases to respect provider rate limits')
    args=p.parse_args()
    if args.delay_seconds<0:p.error('--delay-seconds must be nonnegative')
    cases=json.loads(Path(__file__).with_name('cases.json').read_text())
    config=ModelConfig.load().public() if args.live_model else dict(provider='demo',model='deterministic-parser',configured=True)
    results=[]
    with tempfile.TemporaryDirectory() as directory:
        service=Service(Store(directory+'/eval.db'),EvaluationWeather(),mode='live' if args.live_model else 'demo',fema=EvaluationFEMA())
        seed_examples(service.store)
        for identifier in ['siteA','siteB']:
            service.store.add_location(dict(id=identifier,latitude=40,longitude=-105,timezone='UTC',county_fips='99999'))
        conversation=None
        for case in cases:
            if results and args.delay_seconds:sleep(args.delay_seconds)
            if case.get('new_conversation'):conversation=None
            began=perf_counter()
            item=dict(message=case['message'],passed=False)
            try:
                response=service.chat(dict(message=case['message'],conversation_id=conversation))
                conversation=response['conversation_id']
                item['intent']=response['intent']
                item['planning']=response.get('planning')
                raw_plan=response.get('planning',{}).get('model_plan',{})
                item['raw_model_plan_matches_expected']=all(raw_plan.get(k)==case[k] for k in ('action','hazard','threshold') if k in case)
                assert response['intent']['action']==case['action'],'Wrong action'
                if 'hazard' in case:assert response['intent']['hazard']==case['hazard'],'Wrong hazard'
                if 'threshold' in case:assert response['intent']['threshold']==case['threshold'],'Wrong threshold'
                if 'locations' in case:assert set(response['intent']['location_ids'])==set(case['locations']),'Wrong locations'
                if response['cards']:
                    assert all(c['evidence']['source_id']=='fixture:evaluation' for c in response['cards']),'Missing evidence'
                    if case.get('hazard')=='heat':
                        assert all(c['exceedance_percent']==100 for c in response['cards']),'Wrong heat calculation'
                if response.get('risk_results'):
                    assert all(r['evidence']['source_id']=='fixture:evaluation-fema' for r in response['risk_results']),'Missing county evidence'
                if case.get('risk_count') is not None:
                    assert len(response.get('risk_results',[]))==case['risk_count'],'Wrong risk result count'
                    assert response['result_status']=='complete','Risk result incomplete'
                item['passed']=True
                print('PASS',case['message'])
            except Exception as exc:
                item['error']=str(exc)
                print('FAIL',case['message'],str(exc))
            item['latency_seconds']=round(perf_counter()-began,3)
            results.append(item)
    passed=sum(r['passed'] for r in results)
    report=dict(created_at=datetime.now(timezone.utc).isoformat(),model_config=config,weather='synthetic evaluation fixtures',hazards='synthetic county fixtures',passed=passed,total=len(cases),cases=results)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('Report:',args.report)
    print(f'{passed}/{len(cases)} passed | {config["provider"]} / {config["model"]} | synthetic weather')
    return passed!=len(cases)

if __name__=='__main__':raise SystemExit(main())
