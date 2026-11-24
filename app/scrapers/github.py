"""
GitHub Profile Scraper — ColdReach
=====================================
Fetches public GitHub user profiles via the GitHub REST API.

Limitations:
  - 60 unauthenticated requests/hour
  - Set GITHUB_TOKEN in .env to increase to 5000/hour
"""

import logging
import requests
from typing import Dict, Optional

from app.scrapers.stealth import get_requests_proxies, random_user_agent
from app.scrapers.utils import extract_email

logger = logging.getLogger(__name__)


def scrape_profile(username: str) -> Optional[Dict]:
    """Fetch GitHub public profile data for a username."""
    import os
    token = os.environ.get('GITHUB_TOKEN', '').strip()

    headers = {
        'Accept':     'application/vnd.github.v3+json',
        'User-Agent': random_user_agent(),
    }
    if token:
        headers['Authorization'] = f'token {token}'

    try:
        r = requests.get(
            f'https://api.github.com/users/{username}',
            headers=headers,
            timeout=15,
            proxies=get_requests_proxies()
        )

        if r.status_code == 404:
            logger.error(f"GitHub user @{username} not found")
            return None
        if r.status_code == 403:
            logger.error("GitHub API rate limit exceeded (60/hour without token)")
            return None
        if r.status_code != 200:
            logger.error(f"GitHub API error {r.status_code} for @{username}")
            return None

        data = r.json()
        bio = data.get('bio') or ''

        if not any([data.get('name'), bio, data.get('email'),
                    data.get('blog'), data.get('company'), data.get('twitter_username')]):
            return None

        return {
            'username':       data.get('login', username),
            'full_name':      data.get('name') or '',
            'bio':            bio,
            'email':          data.get('email') or extract_email(bio),
            'company':        (data.get('company') or '').lstrip('@'),
            'location':       data.get('location') or '',
            'website':        data.get('blog') or '',
            'twitter':        data.get('twitter_username') or '',
            'follower_count': data.get('followers', 0),
            'following_count':data.get('following', 0),
            'public_repos':   data.get('public_repos', 0),
            'is_hireable':    data.get('hireable') or False,
            'platform':       'github',
            'profile_url':    data.get('html_url', f'https://github.com/{username}'),
        }

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching GitHub @{username}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching GitHub @{username}: {e}")
        return None
