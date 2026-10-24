"""Script-only watchdog. Scheduler durably queues stdout for Telegram delivery."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import sys

# Cron uses Hermes' Python. Permit manual checks from the host's bare Python too.
if __name__ == '__main__':
    try:
        import requests
    except ImportError:
        import importlib.util
        spec = importlib.util.find_spec('hermes_cli')
        if spec and spec.origin:
            runtime = Path(spec.origin).resolve().parents[2] / 'venv/bin/python'
            if runtime.exists() and str(runtime) != sys.executable:
                os.execv(str(runtime), [str(runtime), __file__, *sys.argv[1:]])

from bo3_alert_core import due_matches, format_alert
from bo3_pipeline import collect_schedule, collect_detail


def save_json(path, data):
    temporary=path.with_suffix('.new')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    os.replace(temporary,path)


def run_once(state_dir, now=None, schedule_reader=collect_schedule, detail_reader=collect_detail):
    state_dir.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now(timezone.utc)
    sent_path=state_dir/'sent.json'
    sent=json.loads(sent_path.read_text()) if sent_path.exists() else {}
    matches=schedule_reader()
    save_json(state_dir/'last_schedule.json', {'checked_at':now.isoformat(),'matches':matches})
    output=[]
    for match in due_matches(matches,sent,now):
        detail=detail_reader(match['url'])
        # Exact metadata from the match page overrides list metadata; retain stars.
        updated=dict(match)
        for key in ('start','tournament','name','format','live'):
            if detail.get(key) is not None and detail.get(key) != '':updated[key]=detail[key]
        if not due_matches([updated],sent,now):continue
        output.append(format_alert(updated,detail.get('streams',[]),now))
        sent[match['url']]=now.isoformat()
    # Save only after all selected match pages were successfully processed.
    if output:save_json(sent_path,sent)
    save_json(state_dir/'health.json',{'last_success':datetime.now(timezone.utc).isoformat(),'matched':len(matches),'starred':sum(m['stars']>=1 for m in matches),'alerts':len(output)})
    return '\n\n──────────\n\n'.join(output)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--inspect',action='store_true',help='Fetch live schedule only, without alerts or dedupe changes')
    args=parser.parse_args()
    home=Path(os.environ.get('HERMES_HOME',str(Path.home()/'.hermes')))
    state_dir=home/'data/bo3-match-alerts'
    state_dir.mkdir(parents=True,exist_ok=True)
    with (state_dir/'watch.lock').open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        if args.inspect:
            print(json.dumps(collect_schedule(),ensure_ascii=False,indent=2))
            return
        output=run_once(state_dir)
        if output:print(output,flush=True)

if __name__=='__main__':main()
