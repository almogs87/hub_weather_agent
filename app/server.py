"""Local single-user HTTP API and chat. Run: python -m app.server [--demo]."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from pydantic import ValidationError
from .agent import Service
from .winter import WinterProfile
from .providers import ModelConfig

STATIC=Path(__file__).parent/'static'

def dispatch(service,path,payload):
    if path=='/api/scenarios/compare':
        from .comparison import compare_networks
        return compare_networks(service,payload)
    if path=='/api/chat':return service.chat(payload)
    if path=='/api/hub-comparison':
        from .hub_comparison import compare_hubs
        return compare_hubs(service,payload)
    if path=='/api/scenarios/replay':return service.replay(payload)
    raise KeyError('Unknown endpoint')

def make_handler(service,port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,format,*args):
            # Do not log chat bodies, tokens or query strings.
            return
        def send_json(self,status,payload):
            raw=json.dumps(payload,ensure_ascii=True,allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            self.wfile.write(raw)
        def do_GET(self):
            if self.path=='/api/health':
                return self.send_json(200,dict(status='ok',mode=service.mode,llm_configured=ModelConfig.load().public()['configured'],model_config=ModelConfig.load().public(),weather_source=os.environ.get('WEATHER_SOURCE','auto'),chat_weather_source_selection=True,comparison_ui_version=2))
            if self.path=='/api/locations':return self.send_json(200,list(service.store.locations().values()))
            if self.path=='/api/comparison-options':
                from datetime import datetime,timezone
                from .storm_events import EVENT_TYPES
                from .hub_comparison import BANDS
                return self.send_json(200,dict(daily_hazards=BANDS,noaa_event_types=EVENT_TYPES,periods=[5,10,20,30],last_complete_year=datetime.now(timezone.utc).year-1,open_meteo_catalog_url='https://open-meteo.com/en/docs/historical-weather-api',catalog_note='The provider documents additional variables; only the daily hazards listed here are scored.'))
            if self.path=='/api/profile':return self.send_json(200,WinterProfile().describe())
            files={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/us-states.json':'us-states.json'}
            if self.path not in files:return self.send_json(404,dict(error='Not found'))
            path=STATIC/files[self.path]
            raw=path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type',{'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8','json':'application/json; charset=utf-8'}[path.suffix[1:]])
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            self.wfile.write(raw)
        def do_POST(self):
            # Local-only, same-origin application. Reject cross-site mutation requests.
            allowed={f'http://127.0.0.1:{port}',f'http://localhost:{port}'}
            if self.headers.get('Origin') and self.headers['Origin'] not in allowed:
                return self.send_json(403,dict(error='Origin not allowed'))
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return self.send_json(415,dict(error='Expected application/json'))
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=100000:raise ValueError('Request must be 1–100000 bytes')
                payload=json.loads(self.rfile.read(length))
                result=dispatch(service,self.path,payload)
                return self.send_json(200,result)
            except KeyError:
                return self.send_json(404,dict(error='Not found'))
            except (ValueError,ValidationError) as exc:
                return self.send_json(400,dict(error=str(exc),data_substituted=False))
            except HTTPError as exc:
                return self.send_json(502,dict(error='External provider rejected request',provider_status=exc.code,data_substituted=False))
            except (URLError,TimeoutError,OSError):
                return self.send_json(502,dict(error='External data/model connection failed; retry or check configuration',data_substituted=False))
            except RuntimeError as exc:
                return self.send_json(503,dict(error=str(exc),data_substituted=False))
    return Handler

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',type=int,default=8000)
    p.add_argument('--demo',action='store_true')
    args=p.parse_args()
    from .hubs import load_hubs
    from .storage import Store
    service=Service(store=Store(catalog=load_hubs()),mode='demo' if args.demo else 'live')
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(service,args.port))
    print(f'Open http://127.0.0.1:{args.port} | mode: {service.mode}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
