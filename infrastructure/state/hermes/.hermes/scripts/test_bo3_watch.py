import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
import bo3_watch as w

class WatchTests(unittest.TestCase):
    def test_alert_once_and_keep_quiet_otherwise(self):
        now=datetime(2026,10,23,13,40,tzinfo=timezone.utc)
        match={'url':'https://bo3.gg/matches/test-23-10-2026','name':'Test A vs Test B','stars':2,'live':False,'format':'Bo3','tournament':'Test event','start':'2026-10-23T13:50:00+00:00'}
        def detail(url):
            return dict(match,streams=[{'label':'Test stream','url':'https://www.twitch.tv/test','language':'English'}])
        with tempfile.TemporaryDirectory(dir='/home/core/.hermes/cache/scratch') as tmp:
            output=w.run_once(Path(tmp),now,lambda:[match],detail)
            self.assertIn(match['name'],output)
            self.assertIn('https://www.twitch.tv/test',output)
            self.assertEqual(w.run_once(Path(tmp),now,lambda:[match],detail),'')
            self.assertEqual(w.run_once(Path(tmp),now,lambda:[dict(match,stars=0)],detail),'')

if __name__=='__main__':unittest.main()
