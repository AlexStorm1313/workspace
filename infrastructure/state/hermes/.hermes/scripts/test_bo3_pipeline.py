import unittest
import bo3_pipeline as p

class LiveSourceTests(unittest.TestCase):
    def test_real_schedule_and_streams(self):
        rows = p.collect_schedule()
        self.assertGreater(len(rows), 0)
        rated = [m for m in rows if m['stars'] >= 1]
        self.assertGreater(len(rated), 0)
        for match in rated:
            self.assertTrue(match['url'].startswith('https://bo3.gg/matches/'))
            self.assertIsNotNone(p.datetime.fromisoformat(match['start']).tzinfo)
        detail = p.collect_detail(rated[0]['url'])
        self.assertIsInstance(detail['streams'], list)
        self.assertTrue(detail['start'])
        self.assertTrue(detail['tournament'])
        self.assertGreater(len(detail['streams']), 0)
        for stream in detail['streams']:
            self.assertRegex(stream['url'], r'^https://(www\.)?(twitch\.tv|youtube\.com|kick\.com)/')
        print('LIVE VERIFIED:', len(rows), 'matches;', len(rated), 'starred;', detail)

if __name__ == '__main__':
    unittest.main()
