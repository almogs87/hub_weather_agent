"""Diagnose weather access without keys or LLM calls. No data substitution."""
import argparse
from datetime import date
import json
from .weather import WeatherClient, WeatherRequest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--latitude',type=float,default=41.8781)
    parser.add_argument('--longitude',type=float,default=-87.6298)
    parser.add_argument('--timezone',default='America/Chicago')
    args=parser.parse_args()
    client=WeatherClient()
    for label,start,end in [('one_day',date(2025,1,1),date(2025,1,1)),('full_year',date(2025,1,1),date(2025,12,31))]:
        print('Checking '+label+'...',flush=True)
        try:
            result=client.fetch(WeatherRequest(args.latitude,args.longitude,start,end,args.timezone),refresh=True)
            print(json.dumps(dict(check=label,status='ok',days=len(result['rows']),source_id=result['evidence']['source_id'])),flush=True)
        except Exception as exc:
            print(json.dumps(dict(check=label,status='failed',error=str(exc))),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
