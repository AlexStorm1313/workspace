"""Pure match alert decisions and formatting; no network, clock or file I/O."""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit


def _utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Timezone-aware timestamps are required')
    return value.astimezone(timezone.utc)


def canonical_match_url(url):
    """Normalize bo3.gg match identity, removing tracking, fragments and slash."""
    parts = urlsplit(url)
    host = (parts.hostname or '').lower().removeprefix('www.')
    if (parts.scheme not in {'http', 'https'} or host != 'bo3.gg'
            or parts.username is not None or parts.password is not None
            or parts.port not in {None, 80, 443}
            or not parts.path.startswith('/matches/')
            or not parts.path[len('/matches/'):].strip('/')):
        raise ValueError('Expected an http(s) bo3.gg match URL')
    return urlunsplit(('https', host, parts.path.rstrip('/'), '', ''))


def mark_sent(sent, url, now):
    """Copy state and record first successful send; never expire or overwrite it."""
    result = dict(sent)
    result.setdefault(canonical_match_url(url), _utc(now).isoformat().replace('+00:00', 'Z'))
    return result


def due_matches(matches, sent, now):
    """Select eligible matches once per canonical URL, preserving input order."""
    now = _utc(now)
    seen = set(sent)
    result = []
    for match in matches:
        key = canonical_match_url(match['url'])
        if (match['stars'] >= 2 and not match['live'] and key not in seen
                and now <= _utc(match['start']) <= now + timedelta(minutes=10)):
            result.append(match)
            seen.add(key)
    return result


def format_alert(match, streams, now):
    """Render Telegram-ready standard Markdown with compact match and stream sections."""
    from math import ceil
    start = _utc(match['start'])
    seconds = max(0, ceil((start - _utc(now)).total_seconds()))
    hours, remaining = divmod(seconds, 3600)
    minutes, seconds_left = divmod(remaining, 60)
    if hours:
        countdown = f'{hours}h' + (f' {minutes}m' if minutes else '')
    else:
        countdown = ' '.join(part for part in (
            f'{minutes}m' if minutes else '',
            f'{seconds_left}s' if seconds_left else '') if part)
    timing = f'⏳ Starts in **{countdown}**' if countdown else '⏳ **Starting now**'
    stars = match['stars']
    stream_lines = []
    seen = set()
    allowed_hosts = {'twitch.tv', 'www.twitch.tv', 'm.twitch.tv',
                     'youtube.com', 'www.youtube.com', 'm.youtube.com',
                     'youtu.be', 'www.youtu.be', 'kick.com', 'www.kick.com'}
    for stream in streams:
        url = stream.get('url', '')
        try:
            parts = urlsplit(url)
            if (parts.scheme not in {'http', 'https'} or parts.hostname not in allowed_hosts
                    or parts.username is not None or parts.password is not None
                    or parts.port not in {None, 80, 443} or not parts.path.strip('/')):
                continue
        except (ValueError, TypeError, AttributeError):
            continue
        key = (parts.hostname.removeprefix('www.').removeprefix('m.'),
               parts.path.rstrip('/'), parts.query)
        if key in seen:
            continue
        seen.add(key)
        clean_url = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ''))
        stream_lines.append(f"• [{stream.get('label') or 'Stream'}]({clean_url}) · {stream.get('language') or 'unknown'}")
        if len(stream_lines) == 6:
            break
    return '\n'.join([
        f"🎮 **{match['name']}**",
        f"{'⭐' * stars} · **{match['format'].upper()}**",
        '',
        f"🏆 **{match['tournament']}**",
        timing,
        f"🕒 {start.isoformat(sep=' ').replace('+00:00', ' UTC')}",
        '',
        '📺 **Streams**',
        *(stream_lines or ['Streams not yet listed — check match details below.']),
        '',
        f"📊 [Match details on BO3.gg]({match['url']})",
    ])

