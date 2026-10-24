"""Behavioral tests for the pure match-alert core; no network or messages."""
import copy
from datetime import datetime, timezone
import unittest

import bo3_alert_core as core

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


def match(**changes):
    result = dict(url='https://bo3.gg/matches/alpha-beta', name='Alpha vs Beta',
                  start='2026-10-23T12:05:00Z', stars=2, live=False,
                  tournament='Example Cup', format='BO3')
    result.update(changes)
    return result


class DueMatchesTests(unittest.TestCase):
    def test_inclusive_window_and_offset_instants(self):
        rows = [match(url=f'https://bo3.gg/matches/{i}', start=start)
                for i, start in enumerate([
                    '2026-10-23T11:59:59.999999Z',
                    '2026-10-23T12:00:00Z',
                    '2026-10-23T14:05:00+02:00',
                    '2026-10-23T12:10:00Z',
                    '2026-10-23T12:10:00.000001Z'])]
        self.assertEqual(core.due_matches(rows, {}, NOW), rows[1:4])

    def test_only_filled_star_nonlive_unsent_matches_are_due(self):
        rows = [match(stars=0), match(stars=1), match(live=True),
                match(url='https://bo3.gg/matches/already-sent'),
                match(url='https://bo3.gg/matches/eligible', stars=2),
                match(url='https://bo3.gg/matches/three-stars', stars=3)]
        sent = {rows[3]['url']: '2026-10-22T01:00:00Z'}
        before = copy.deepcopy((rows, sent))
        self.assertEqual(core.due_matches(rows, sent, NOW), rows[4:])
        self.assertEqual((rows, sent), before)


class StateTests(unittest.TestCase):
    def test_canonical_identity_rejects_non_match_urls(self):
        for url in ['javascript:alert(1)', 'https://evil.test/matches/a',
                    'https://bo3.gg/', 'https://bo3.gg/matches/',
                    'https://someone@bo3.gg/matches/a',
                    'https://bo3.gg:9999/matches/a']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                core.canonical_match_url(url)

    def test_canonical_state_prevents_rescheduled_and_repeated_alerts(self):
        row = match(url='http://WWW.BO3.GG/matches/alpha-beta/?ref=home#streams')
        key = 'https://bo3.gg/matches/alpha-beta'
        self.assertEqual(core.canonical_match_url(row['url']), key)
        original = {'https://bo3.gg/matches/other': '2026-10-22T00:00:00Z'}
        sent = core.mark_sent(original, row['url'], NOW)
        self.assertEqual(sent[key], '2026-10-23T12:00:00Z')
        self.assertNotIn(key, original)
        self.assertEqual(core.mark_sent(sent, key, '2026-10-24T00:00:00Z'), sent)
        rescheduled = match(start='2026-10-24T12:05:00Z')
        self.assertEqual(core.due_matches([rescheduled], sent, '2026-10-24T12:00:00Z'), [])
        self.assertEqual(core.due_matches([row, match()], {}, NOW), [row])


class FormatAlertTests(unittest.TestCase):
    def test_exact_start_preserves_fractional_seconds(self):
        text = core.format_alert(match(start='2026-10-23T12:05:00.123456Z'), [], NOW)
        self.assertIn('2026-10-23 12:05:00.123456 UTC', text)

    def test_empty_streams_show_complete_utc_alert_and_explicit_fallback(self):
        row = match(start='2026-10-23T14:05:30+02:00')
        before = copy.deepcopy(row)
        text = core.format_alert(row, [], NOW)
        self.assertTrue(text.startswith('🎮 **Alpha vs Beta**\n⭐⭐ · **BO3**\n\n'))
        for field in ['🏆 **Example Cup**', '⏳ Starts in **5m 30s**',
                      '🕒 2026-10-23 12:05:30 UTC', '📺 **Streams**',
                      'Streams not yet listed', '[Match details on BO3.gg]', row['url']]:
            self.assertIn(field, text)
        self.assertEqual(row, before)

    def test_streams_are_unique_real_provider_links_capped_at_six(self):
        urls = ['https://www.twitch.tv/channel', 'https://www.youtube.com/watch?v=abc',
                'https://youtu.be/def', 'http://kick.com/channel',
                'https://m.youtube.com/@channel/live', 'https://twitch.tv/another',
                'https://kick.com/not-shown']
        invalid = ['javascript:alert(1)', 'ftp://twitch.tv/channel',
                   'https://twitch.tv.evil.test/channel', 'https://evil.test/twitch.tv',
                   'https://twitch.tv@evil.test/channel', 'https://evil@twitch.tv/channel',
                   'https://twitch.tv/', 'https://youtube.com/', 'not a url',
                   'https://twitch.tv:invalid/channel']
        streams = [dict(label='INVALID', url=url, language='xx') for url in invalid]
        streams += [dict(label=f'Feed {i}', url=url, language='en') for i, url in enumerate(urls)]
        streams.insert(len(invalid) + 1,
                       dict(label='DUPLICATE', url=urls[0] + '#player', language='en'))
        before = copy.deepcopy(streams)
        text = core.format_alert(match(), streams, NOW)
        for i, url in enumerate(urls[:6]):
            self.assertIn(f'• [Feed {i}]({url}) · en', text)
        self.assertNotIn(urls[6], text)
        self.assertNotIn('INVALID', text)
        self.assertNotIn('DUPLICATE', text)
        self.assertNotIn('not yet listed', text)
        self.assertEqual(text.count('https://www.twitch.tv/channel'), 1)
        self.assertEqual(streams, before)


if __name__ == '__main__':
    unittest.main()
