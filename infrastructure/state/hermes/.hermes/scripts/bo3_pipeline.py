"""Read live bo3.gg pages through Hermes' configured browser, never archives."""
import json
from datetime import datetime
from urllib.parse import urlsplit

SESSION = 'bo3-match-alerts'


def run_browser(body):
    from tools.browser_use_cli import browser_exec
    result = browser_exec('# Read BO3 live match source\n' + body,
                          session=SESSION, task_id='bo3-match-alerts', timeout_s=110)
    if isinstance(result, str):
        result = json.loads(result)
    if not result.get('success'):
        raise RuntimeError('BO3 browser failed: ' + str(result.get('stderr') or result.get('error') or result))
    lines = result.get('output', '').splitlines()
    for line in reversed(lines):
        if line.startswith('BO3_DATA='):
            return json.loads(line.removeprefix('BO3_DATA='))
    raise RuntimeError('BO3 browser returned no validated data')


NAVIGATE = '''
import json,time
cdp('Emulation.setTimezoneOverride', timezoneId='UTC')
if page_info().get('url') in ('', 'about:blank'):
    new_tab(URL)
else:
    goto_url(URL)
for attempt in range(80):
    if js(READY): break
    time.sleep(.5)
else:
    raise RuntimeError('BO3 page did not load: ' + str(page_info()))
'''


def collect_schedule():
    code = 'URL="https://bo3.gg/matches/current"\nREADY=\'document.querySelectorAll("a.c-global-match-link .team-name").length > 0\'\n' + NAVIGATE
    code += '''
value=js("""(() => {
 const events={};
 for(const s of document.querySelectorAll('script[type="application/ld+json"]')) {
   try {const data=JSON.parse(s.textContent); for(const e of (Array.isArray(data)?data:[data])) if(e.url&&e.startDate) events[e.url]=e;} catch{}
 }
 return [...document.querySelectorAll('a.c-global-match-link')].map(e=>{
   const row=e.closest('.table-row'); const url=e.href;
   const teams=[...e.querySelectorAll('.team-name')].map(x=>x.textContent.trim());
   const time=e.querySelector('.time')?.textContent.trim();
   const date=url.match(/-(\\d{2})-(\\d{2})-(\\d{4})$/);
   const start=events[url]?.startDate || (date && /^\\d{2}:\\d{2}$/.test(time||'') ? `${date[3]}-${date[2]}-${date[1]}T${time}:00+00:00` : null);
   return {url,name:teams.join(' vs '),stars:e.querySelectorAll('.o-icon--star-1.filled').length,live:!!e.querySelector('.o-label--live'),format:e.querySelector('.bo-type')?.textContent.trim()||'',tournament:row?.querySelector('.tournament-name')?.textContent.trim()||'',start};
 }).filter(m=>m.name&&m.start);
})()""")
if not value: raise RuntimeError('BO3 schedule parsed no timestamped matches')
print('BO3_DATA='+json.dumps(value,ensure_ascii=False))
'''
    return run_browser(code)


def collect_detail(url):
    if not url.startswith('https://bo3.gg/matches/') or urlsplit(url).netloc != 'bo3.gg':
        raise ValueError('Not a BO3 match URL')
    ready = """!!document.querySelector('h1') && [...document.querySelectorAll('script[type="application/ld+json"]')].some(s=>s.textContent.includes('startDate'))"""
    code = 'URL=' + repr(url) + '\nREADY=' + repr(ready) + '\n' + NAVIGATE
    code += '''
meta=js("""(()=>{
 let events=[];for(const s of document.querySelectorAll('script[type="application/ld+json"]')){try{let d=JSON.parse(s.textContent);events.push(...(Array.isArray(d)?d:[d]))}catch{}}
 const e=events.find(x=>x['@type']==='SportsEvent')||{};
 return {start:e.startDate||null,tournament:e.organizer?.name||document.querySelector('.tournament-name')?.textContent.trim()||'',name:e.name||'',live:!!document.querySelector('.c-match .o-label--live'),streams:[]};
})()""")
# Streams may populate shortly after the main SSR document.
for _ in range(12):
 if js('!!document.querySelector(".c-nav-streams__item")'):break
 time.sleep(.25)
js('document.querySelector(".c-nav-streams__footer .show-more")?.click()')
time.sleep(.25)
count=js('document.querySelectorAll(".c-nav-streams__item").length')
from urllib.parse import urlsplit,parse_qs
for index in range(min(count,12)):
 label=js(f"(()=>{{let b=document.querySelectorAll('.c-nav-streams__item')[{index}];b.click();return {{label:b.querySelector('.caster__title')?.textContent.trim()||'Stream',language:b.querySelector('.language')?.textContent.trim()||''}}}})()")
 time.sleep(.25)
 src=js('document.querySelector(".c-widget-streams iframe")?.src||""')
 parsed=urlsplit(src); q=parse_qs(parsed.query); link=None
 if parsed.hostname=='player.kick.com' and parsed.path.strip('/'):
  link='https://kick.com/'+parsed.path.strip('/')
 elif parsed.hostname=='player.twitch.tv' and q.get('channel'):
  link='https://www.twitch.tv/'+q['channel'][0]
 elif parsed.hostname in ('www.youtube.com','youtube.com','www.youtube-nocookie.com') and parsed.path.startswith('/embed/'):
  video=parsed.path.split('/embed/')[1].split('/')[0]
  if video: link='https://www.youtube.com/watch?v='+video
 if link and not any(s['url']==link for s in meta['streams']):
  meta['streams'].append(dict(label,url=link))
meta['streams'].sort(key=lambda s: s['language'].lower()!='english')
if not meta['start']: raise RuntimeError('BO3 match has no exact start timestamp')
print('BO3_DATA='+json.dumps(meta,ensure_ascii=False))
'''
    return run_browser(code)
