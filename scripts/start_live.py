"""Portable hidden-key launcher for the local weather analyst."""
import argparse
import getpass
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent

def local_groq_key():
    """Use the first Groq key from the private local Markdown file, if present."""
    path=ROOT/'keys.local.md'
    if not path.is_file():return None
    match=re.search(r'\bgsk_[A-Za-z0-9]{20,}\b',path.read_text(encoding='utf-8'))
    return match.group(0) if match else None

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider',choices=['groq','openai'],default='groq')
    parser.add_argument('--model',default=None)
    parser.add_argument('--weather-source',choices=['auto','open-meteo','noaa'],default='auto')
    parser.add_argument('--action',choices=['serve','evaluate'],default='serve')
    parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args(argv)
    if not 1<=args.port<=65535:parser.error('--port must be between 1 and 65535')
    model=args.model or ('openai/gpt-oss-20b' if args.provider=='groq' else None)
    if not model:parser.error('--model is required for OpenAI')
    variable='GROQ_API_KEY' if args.provider=='groq' else 'OPENAI_API_KEY'
    environment=os.environ.copy()
    if args.provider=='groq':
        try:key=local_groq_key()
        except (OSError,UnicodeError) as exc:
            print(f'Could not read keys.local.md: {exc}',file=sys.stderr);return 1
        if key:environment[variable]=key
    if not environment.get(variable):
        try:key=getpass.getpass(f'Enter your {args.provider} API key (hidden): ').strip()
        except (EOFError,KeyboardInterrupt):print('\nCancelled.',file=sys.stderr);return 1
        if not key:print('No key entered.',file=sys.stderr);return 1
        environment[variable]=key
    environment.update(LLM_PROVIDER=args.provider,LLM_MODEL=model,WEATHER_SOURCE=args.weather_source)
    if args.action=='evaluate':
        safe_model=re.sub(r'[^A-Za-z0-9_.-]+','-',model)
        command=[sys.executable,'-m','evals.run','--live-model','--delay-seconds','10','--report',f'eval-results/{args.provider}-{safe_model}.json']
    else:
        command=[sys.executable,'-m','app.server','--port',str(args.port)]
    print(f'Provider: {args.provider} | Model: {model} | Weather: {args.weather_source}',flush=True)
    try:return subprocess.run(command,cwd=ROOT,env=environment,check=False).returncode
    except KeyboardInterrupt:return 130

if __name__=='__main__':raise SystemExit(main())
