"""Analyze user-supplied coordinates; no preset facility selection."""
import argparse
from datetime import date
import json
import sys
from .weather import WeatherRequest, HAZARDS, exposure, trend
from .weather_sources import WeatherSources

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
    p.add_argument('--source',choices=['auto','open-meteo','noaa'],default=None)
    args=p.parse_args()
    try:
        request=WeatherRequest(args.latitude,args.longitude,args.start,args.end,args.timezone)
        data=WeatherSources(source=args.source).fetch(request,args.refresh,hazard=args.hazard)
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
