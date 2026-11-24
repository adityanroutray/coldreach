"""
YouTube Channel Scraper — ColdReach
======================================
Scrapes public YouTube channel pages by parsing HTML and embedded JSON.
No API key required.
"""

import re
import logging
import requests
from typing import Dict, Optional
from urllib.parse import unquote

from app.scrapers.stealth import random_user_agent, get_requests_proxies
from app.scrapers.utils import extract_email, parse_abbreviated_number

logger = logging.getLogger(__name__)


def scrape_channel(channel_identifier: str) -> Optional[Dict]:
    """Fetch YouTube channel data. Accepts @handle, channel ID, or custom URL."""
    if channel_identifier.startswith('@'):
        url = f'https://www.youtube.com/{channel_identifier}'
    elif channel_identifier.startswith('UC') and len(channel_identifier) == 24:
        url = f'https://www.youtube.com/channel/{channel_identifier}'
    else:
        url = f'https://www.youtube.com/@{channel_identifier}'

    headers = {
        'User-Agent':      random_user_agent(),
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept':          'text/html,application/xhtml+xml',
    }
    cookies = {'CONSENT': 'PENDING+999'}

    try:
        r = requests.get(url, headers=headers, cookies=cookies, timeout=20, proxies=get_requests_proxies())
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            return None

        result = _extract_channel_data(r.text, channel_identifier)
        if result:
            return result

        # Retry with fresh UA
        headers['User-Agent'] = random_user_agent()
        r = requests.get(url, headers=headers, cookies=cookies, timeout=20, proxies=get_requests_proxies())
        return _extract_channel_data(r.text, channel_identifier) if r.status_code == 200 else None

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching YouTube channel {channel_identifier}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching YouTube channel {channel_identifier}: {e}")
        return None


def _extract_channel_data(html: str, identifier: str) -> Optional[Dict]:
    results = {}

    m = re.search(r'"channelMetadataRenderer":\{"title":"([^"]+)"', html)
    if m:
        results['channel_name'] = m.group(1)

    m = re.search(r'"description":"([^"]*)"', html)
    if m:
        try:
            results['description'] = m.group(1).encode('utf-8').decode('unicode_escape')
        except (UnicodeDecodeError, UnicodeEncodeError):
            results['description'] = m.group(1)

    for pattern in [
        r'"subscriberCountText":\{"simpleText":"([\d.,]+[KMB]?) subscribers?"',
        r'"subscriberCountText":\{"accessibility":\{"accessibilityData":\{"label":"([\d.,]+[KMB]?) subscribers?"',
    ]:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            results['subscriber_count'] = parse_abbreviated_number(m.group(1))
            break

    m = re.search(r'"canonicalChannelUrl":"https://www\.youtube\.com/@([^"]+)"', html)
    if m:
        results['handle'] = m.group(1)

    m = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', html)
    if m:
        results['channel_id'] = m.group(1)

    m = re.search(r'"businessEmailLabel":\{"content":"([^"]+)"', html)
    if m:
        results['business_email'] = m.group(1)
    else:
        results['business_email'] = extract_email(results.get('description', ''))

    links = []
    for m in re.finditer(r'"urlEndpoint":\{"url":"(https?://[^"]+)"', html):
        link = m.group(1)
        if 'youtube.com' not in link and 'google.com' not in link:
            clean = _clean_redirect_url(link)
            if clean and clean not in links:
                links.append(clean)
    results['links'] = links[:5]

    if 'channel_name' not in results:
        return None

    handle = results.get('handle', identifier.lstrip('@'))
    return {
        'username':      handle,
        'full_name':     results.get('channel_name', ''),
        'bio':           results.get('description', ''),
        'email':         results.get('business_email', ''),
        'follower_count':results.get('subscriber_count', 0),
        'website':       results['links'][0] if results.get('links') else '',
        'links':         results.get('links', []),
        'channel_id':    results.get('channel_id', ''),
        'platform':      'youtube',
        'profile_url':   f'https://www.youtube.com/@{handle}',
    }


def _clean_redirect_url(url: str) -> str:
    if 'youtube.com/redirect' in url:
        m = re.search(r'[?&]q=([^&]+)', url)
        if m:
            return unquote(m.group(1))
    return url
