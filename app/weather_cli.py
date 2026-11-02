"""Analyze user-supplied coordinates; no preset facility selection."""
import argparse
from datetime import date
import json
import sys
from .weather import WeatherClient, WeatherRequest, HAZARDS, exposure, trend

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--latitude',type=float,required=True)
    p.add_argument('--longitude',type=float,required=True)
    p.add_argument('--timezone',required=True)
    p.add_argument('--start',type=date.fromisoformat,default=date(2011,1,1))
    p.add_argument('--end',type=date.fromisoformat,default=date(2025,12,31))
    p.add_argument('--hazard',choices=HAZARDS,default='snow')
    p.add_argument('--threshold',type=float)
    p.add_argument('--refresh',action='store_true')
    args=p.parse_args()
    try:
        request=WeatherRequest(args.latitude,args.longitude,args.start,args.end,args.timezone)
        data=WeatherClient().fetch(request,args.refresh)
        result=exposure(data['rows'],args.start,args.end,args.hazard,args.threshold)
        result['trend']=trend(result['annual'],args.start.year,args.end.year)
        result['evidence']=data['evidence']
        print(json.dumps(result,indent=2,ensure_ascii=True,allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps(dict(status='error',error=str(exc),data_substituted=False)),file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
