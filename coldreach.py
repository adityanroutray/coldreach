#!/usr/bin/env python3
"""
ColdReach — High-Performance Cold Outreach Lead Intelligence Engine
=====================================================================
Interactive CLI for scraping profiles across 7 platforms, enriching leads
with verified emails via DNS & SMTP, and exporting enriched datasets to CSV.

Platforms: Instagram, LinkedIn, GitHub, YouTube, Twitch, Linktree, Pinterest.

Author  : Adityan Routray <adityanroutray@gmail.com>
GitHub  : https://github.com/adityanroutray/coldreach
License : MIT
"""

import sys
import csv
import time
import os
import logging
from pathlib import Path

if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent))

from app import __version__, __author__, __repo__

_verbose = '--verbose' in sys.argv or '-V' in sys.argv
logging.basicConfig(
    level=logging.DEBUG if _verbose else logging.WARNING,
    format='%(name)s: %(message)s',
)

_args = [a for a in sys.argv[1:] if a not in ('--verbose', '-V')]
if _args:
    arg = _args[0].lower()
    if arg in ('--version', '-v', 'version'):
        print(f"ColdReach v{__version__} by {__author__}")
        sys.exit(0)
    elif arg in ('--help', '-h', 'help'):
        print(f"ColdReach v{__version__} — Lead Intelligence Engine")
        print()
        print("Usage: python coldreach.py [options]")
        print()
        print("Options:")
        print("  --version, -v    Show version")
        print("  --help, -h       Show this help")
        print("  --verbose, -V    Enable debug logging")
        print()
        print("Run without arguments to launch interactive workspace.")
        sys.exit(0)

# Load local environment configuration
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _key, _, _val = _line.partition('=')
                os.environ.setdefault(_key.strip(), _val.strip())

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from rich.text import Text
from rich.theme import Theme
from rich.rule import Rule

from app.scrapers.instagram import scrape_profile_no_login
from app.scrapers.stealth import random_delay, proxy_status

# ColdReach Modern Electric Blue / Orange Brand Palette
ACCENT = "#0A84FF"         # ScaleWeb / ColdReach Blue
ACCENT_ORANGE = "#FE6A06"  # ScaleWeb Accent Orange
ACCENT_DIM = "#004080"
ACCENT_LIGHT = "#5AC8FA"
ACCENT_MUTED = "#002040"

_GRAD_START = (10, 132, 255)   # Electric Blue
_GRAD_END = (254, 106, 6)      # ScaleWeb Orange

_LOGO_LINES = [
    " ██████   ██████  ██      ██████  ██████  ███████  █████   ██████ ██   ██",
    "██       ██    ██ ██      ██   ██ ██   ██ ██      ██   ██ ██      ██   ██",
    "██       ██    ██ ██      ██   ██ ██████  █████   ███████ ██      ███████",
    "██       ██    ██ ██      ██   ██ ██   ██ ██      ██   ██ ██      ██   ██",
    " ██████   ██████  ███████ ██████  ██   ██ ███████ ██   ██  ██████ ██   ██",
]

_session_stats = {"scraped": 0}

custom_theme = Theme({
    "prompt.choices": ACCENT,
    "prompt.default": "dim",
})
console = Console(theme=custom_theme)
Prompt.prompt_suffix = " "
Confirm.prompt_suffix = " "


def _update_env(key, value):
    env_path = Path(__file__).parent / '.env'
    lines = []
    found = False
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith(key + '='):
                    lines.append(f'{key}={value}\n')
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f'{key}={value}\n')
    with open(env_path, 'w') as f:
        f.writelines(lines)
    os.environ[key] = value


def enrich_profiles(profiles):
    if not profiles:
        return profiles

    if not Confirm.ask("\n[white][+] Enrich leads with verified email & intelligence?[/white]", default=True):
        return profiles

    from app.scrapers.enrichment import LeadEnricher
    hunter_key = os.environ.get('HUNTER_API_KEY', '').strip() or None
    enricher = LeadEnricher(hunter_api_key=hunter_key)

    console.print()
    emails_found = 0
    phones_found = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("[white]Running ColdReach intelligence pipeline...", total=len(profiles))
        enriched = []
        for p in profiles:
            had_email = bool(p.get('email'))
            had_phone = bool(p.get('phone'))

            result = enricher.enrich_lead(p)
            enriched.append(result)

            if result.get('email') and not had_email:
                emails_found += 1
            if result.get('phone') and not had_phone:
                phones_found += 1

            progress.advance(task)

    console.print()
    summary_parts = []
    if emails_found:
        summary_parts.append(f"[green]{emails_found} verified emails discovered[/green]")
    if phones_found:
        summary_parts.append(f"[green]{phones_found} direct phone lines found[/green]")
    if not summary_parts:
        summary_parts.append("[yellow]No new contact channels identified[/yellow]")

    scores = [e.get('lead_score', 0) for e in enriched]
    avg_score = sum(scores) // len(scores) if scores else 0
    summary_parts.append(f"[white]Avg Lead Quality Score: {avg_score}/100[/white]")

    console.print(Rule("[bold white]ColdReach Enrichment Summary[/bold white]", style=ACCENT_DIM, align="left"))
    console.print()
    for part in summary_parts:
        console.print(f"  {part}")
    console.print()

    email_leads = [e for e in enriched if e.get('email')]
    if email_leads:
        t = Table(show_header=True, box=box.MINIMAL_HEAVY_HEAD, border_style="dim", padding=(0, 1))
        t.add_column("Lead", style="white")
        t.add_column("Discovered Email", style="white")
        t.add_column("Confidence", style="green")
        t.add_column("Source", style="dim")
        t.add_column("SMTP Verified", style="yellow")

        for e in email_leads:
            name = e.get('full_name') or e.get('username', '?')
            email_score = e.get('email_score', 0)
            score_color = 'green' if email_score >= 70 else 'yellow' if email_score >= 40 else 'red'
            verified = 'Yes' if e.get('email_verified') else 'No'
            t.add_row(
                name[:25],
                e['email'],
                f"[{score_color}]{email_score}%[/{score_color}]",
                e.get('email_source', '?'),
                verified
            )
        console.print(t)

    return enriched


def _platform_header(name: str, subtitle: str = "Direct extraction"):
    console.print()
    console.print(Rule(
        f"[bold white]{name}[/bold white]  [dim]{subtitle}[/dim]",
        style=ACCENT_DIM,
        align="left"
    ))
    console.print()


def _profile_card(profile: dict):
    _session_stats["scraped"] += 1
    lines = []

    if profile.get('full_name'):
        lines.append(f"[bold white]{profile['full_name'][:50]}[/bold white]")

    stats = []
    if profile.get('follower_count'):
        stats.append(f"[white]{profile['follower_count']:,}[/white] [dim]followers[/dim]")
    if profile.get('following_count'):
        stats.append(f"[white]{profile['following_count']:,}[/white] [dim]following[/dim]")
    if stats:
        lines.append("  ·  ".join(stats))

    email = profile.get('email', '')
    if profile.get('bio'):
        bio = profile['bio'].replace('\n', ' ')
        if email:
            bio = bio.replace(email, '').strip(' |·-,')
        bio = bio[:80] + '...' if len(bio) > 80 else bio
        if bio:
            lines.append(f"[dim]{bio}[/dim]")

    if email:
        lines.append(f"[bold {ACCENT_ORANGE}]{email}[/bold {ACCENT_ORANGE}]")

    if profile.get('website'):
        lines.append(f"[dim]{profile['website']}[/dim]")

    if profile.get('phone'):
        lines.append(f"[dim]{profile['phone']}[/dim]")

    username = profile.get('username', '?')
    console.print(Panel(
        "\n".join(lines) if lines else "[dim]No profile attributes[/dim]",
        title=f"[bold white]@{username}[/bold white]",
        title_align="left",
        border_style=ACCENT_DIM,
        box=box.ROUNDED,
        padding=(0, 2),
        width=68
    ))


def _success_summary(successful: int, total: int, item_type: str = "profiles"):
    console.print()
    if successful == total:
        console.print(f"  [green]OK[/green] [white]{successful}/{total} {item_type} captured[/white]")
    elif successful > 0:
        console.print(f"  [yellow]DONE[/yellow] [white]{successful}/{total} {item_type} captured[/white]")
    else:
        console.print(f"  [red]FAIL[/red] [white]0/{total} {item_type} captured[/white]")
    console.print()


def _export_result(filename: str, count: int, item_type: str = "profiles"):
    console.print(f"  [green]Saved[/green] [white]{filename}[/white] [dim]({count} {item_type})[/dim]")
    console.print()


def _no_results():
    console.print()
    console.print("  [yellow]No profile records retrieved[/yellow]")
    console.print()


def _pause():
    console.print()
    console.print(Rule(style=ACCENT_MUTED))
    Prompt.ask("[dim]Press Enter to return to workspace[/dim]", default="")


def _gradient_line(text: str, row: int, total_rows: int) -> Text:
    t = Text()
    length = len(text.rstrip())
    row_shift = row / max(total_rows - 1, 1)

    for j, char in enumerate(text):
        if j < length and char != ' ':
            h_progress = j / max(length - 1, 1)
            progress = h_progress * 0.6 + row_shift * 0.4
            progress = max(0.0, min(1.0, progress))

            r = int(_GRAD_START[0] + (_GRAD_END[0] - _GRAD_START[0]) * progress)
            g = int(_GRAD_START[1] + (_GRAD_END[1] - _GRAD_START[1]) * progress)
            b = int(_GRAD_START[2] + (_GRAD_END[2] - _GRAD_START[2]) * progress)
            t.append(char, style=f"bold #{r:02x}{g:02x}{b:02x}")
        else:
            t.append(char)
    return t


def _gradient_bar() -> Text:
    width = min(console.width, 84)
    t = Text()
    for j in range(width):
        progress = j / max(width - 1, 1)
        r = int(_GRAD_START[0] + (_GRAD_END[0] - _GRAD_START[0]) * progress)
        g = int(_GRAD_START[1] + (_GRAD_END[1] - _GRAD_START[1]) * progress)
        b = int(_GRAD_START[2] + (_GRAD_END[2] - _GRAD_START[2]) * progress)
        t.append("▀", style=f"#{r:02x}{g:02x}{b:02x}")
    return t


def show_header():
    console.print()
    console.print(_gradient_bar(), justify="center")
    console.print()

    total = len(_LOGO_LINES)
    for i, line in enumerate(_LOGO_LINES):
        t = _gradient_line(line, i, total)
        console.print(t, justify="center")

    console.print()
    console.print(f"[dim]v{__version__}[/dim]  [bold white]Cold Outreach Lead Intelligence Engine[/bold white]  [dim]by {__author__}[/dim]", justify="center")
    console.print()
    console.print(_gradient_bar(), justify="center")

    ps = proxy_status()
    if ps == 'custom':
        proxy_str = "[green]● custom[/green]"
    elif ps == 'file':
        proxy_str = "[green]● rotating[/green]"
    elif ps == 'free':
        proxy_str = "[yellow]● free[/yellow]"
    else:
        proxy_str = "[dim]○ direct[/dim]"

    status = f"[dim]Repo:[/dim] [white]{__repo__}[/white]  ·  [dim]Proxy:[/dim] {proxy_str}"
    if _session_stats["scraped"] > 0:
        status += f"  ·  [dim]Scraped Leads:[/dim] [white]{_session_stats['scraped']}[/white]"
    console.print(status, justify="center")
    console.print()


def show_menu():
    console.print(Rule("[bold white]Intelligence Channels[/bold white]", style=ACCENT_DIM, align="left"))
    console.print()

    # 7-platform layout
    platforms_left = [
        ("1", "Instagram", "profiles & bios"),
        ("2", "LinkedIn", "voyager cookie"),
        ("3", "GitHub", "developers & repos"),
        ("4", "YouTube", "creators & channels"),
    ]
    platforms_right = [
        ("5", "Twitch", "streamers & socials"),
        ("6", "Link-in-Bio", "Linktree, Stan, Bio.link"),
        ("7", "Pinterest", "creators & merchants"),
    ]

    table = Table(show_header=False, box=None, padding=(0, 0), pad_edge=False, expand=False)
    table.add_column("", width=36)
    table.add_column("", width=36)

    max_rows = max(len(platforms_left), len(platforms_right))
    for i in range(max_rows):
        left = ""
        right = ""
        if i < len(platforms_left):
            n, name, desc = platforms_left[i]
            left = f"  [{ACCENT}][{n}][/{ACCENT}]  [bold white]{name}[/bold white]  [dim]{desc}[/dim]"
        if i < len(platforms_right):
            n, name, desc = platforms_right[i]
            right = f"  [{ACCENT}][{n}][/{ACCENT}]  [bold white]{name}[/bold white]  [dim]{desc}[/dim]"
        table.add_row(left, right)

    console.print(table)
    console.print()

    console.print(Rule("[bold white]Core Utilities[/bold white]", style=ACCENT_DIM, align="left"))
    console.print()

    tools_left = [
        ("8", "Bulk Scrape", "from file list"),
        ("9", "Exports", "browse CSV datasets"),
    ]
    tools_right = [
        ("10", "Settings", "proxies & cookies"),
        ("0", "Exit", "close ColdReach"),
    ]

    tools = Table(show_header=False, box=None, padding=(0, 0), pad_edge=False, expand=False)
    tools.add_column("", width=36)
    tools.add_column("", width=36)

    for i in range(max(len(tools_left), len(tools_right))):
        left = ""
        right = ""
        if i < len(tools_left):
            n, name, desc = tools_left[i]
            left = f"  [{ACCENT}][{n}][/{ACCENT}]  [bold white]{name}[/bold white]  [dim]{desc}[/dim]"
        if i < len(tools_right):
            n, name, desc = tools_right[i]
            right = f"  [{ACCENT}][{n}][/{ACCENT}]  [bold white]{name}[/bold white]  [dim]{desc}[/dim]"
        tools.add_row(left, right)

    console.print(tools)
    console.print()


def _get_delay_range(fallback=(1.0, 2.5)):
    try:
        d_min = float(os.environ.get('CR_DELAY_MIN', str(fallback[0])))
        d_max = float(os.environ.get('CR_DELAY_MAX', str(fallback[1])))
        return (d_min, d_max) if d_max >= d_min >= 0 else fallback
    except ValueError:
        return fallback


def _standard_scrape_loop(scraper_func, items, label_prefix="@", delay_range=None):
    if delay_range is None:
        delay_range = _get_delay_range()
    profiles = []

    for i, item in enumerate(items, 1):
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
            progress.add_task(f"[white]Extracting {label_prefix}{item}  [dim]({i}/{len(items)})[/dim]", total=None)
            try:
                prev_level = logging.getLogger().level
                if not _verbose:
                    logging.getLogger().setLevel(logging.CRITICAL)
                profile = scraper_func(item)
                if not _verbose:
                    logging.getLogger().setLevel(prev_level)

                if profile:
                    profiles.append(profile)
                    progress.stop()
                    _profile_card(profile)
                else:
                    progress.stop()
                    console.print(f"  [red]✗[/red] [dim]{label_prefix}{item} — not found[/dim]")
            except RuntimeError:
                progress.stop()
                console.print(f"  [bold red]✗ {label_prefix}{item} — rate limited[/bold red]")
                break
            except Exception as e:
                progress.stop()
                console.print(f"  [red]✗[/red] [dim]{label_prefix}{item} — {str(e)[:80]}[/dim]")

        if i < len(items):
            random_delay(*delay_range)

    return profiles


def _standard_export(profiles, total, platform_name, item_type="profiles"):
    if profiles:
        _success_summary(len(profiles), total, item_type)
        profiles = enrich_profiles(profiles)
        if Confirm.ask("[+] Export enriched dataset to CSV?", default=True):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"coldreach_{platform_name}_{timestamp}.csv"
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if profiles:
                    writer = csv.DictWriter(f, fieldnames=profiles[0].keys())
                    writer.writeheader()
                    writer.writerows(profiles)
            _export_result(filename, len(profiles), item_type)
    else:
        _no_results()


def _collect_usernames(platform_name, prompt_label="Username", strip_at=False):
    console.print(f"[white]Enter {platform_name} targets (one per line)[/white]")
    console.print("[dim]Press Enter on empty line when complete[/dim]")
    console.print()

    items = []
    while True:
        entry = Prompt.ask(prompt_label, default="")
        if not entry:
            break
        if strip_at:
            entry = entry.replace('@', '')
        entry = entry.strip()
        if entry:
            items.append(entry)
            prefix = "@" if strip_at else ""
            console.print(f"[green]✓[/green] Added {prefix}{entry}")

    if not items:
        console.print("[yellow]No targets provided[/yellow]")
    return items


def scrape_instagram_interactive():
    _platform_header("Instagram", "No login required")
    usernames = _collect_usernames("Instagram", strip_at=True)
    if not usernames:
        return
    console.print()
    profiles = _standard_scrape_loop(scrape_profile_no_login, usernames, label_prefix="@", delay_range=(1.5, 4.0))
    _standard_export(profiles, len(usernames), "instagram")


def scrape_linkedin_interactive():
    from app.scrapers.linkedin import scrape_linkedin_profile

    cookie = os.environ.get('LINKEDIN_COOKIE', '').strip()
    if not cookie:
        console.print()
        console.print(Rule("[bold yellow]LinkedIn Session Required[/bold yellow]", style="yellow", align="left"))
        console.print()
        console.print("  [white]1.[/white] Open Chrome > linkedin.com (logged in)")
        console.print("  [white]2.[/white] DevTools (F12) > Application > Cookies > linkedin.com")
        console.print("  [white]3.[/white] Copy the value of [bold]li_at[/bold]")
        console.print("  [white]4.[/white] Configure via Settings (Option 10) or .env: [bold]LINKEDIN_COOKIE=...[/bold]")
        console.print()
        return

    _platform_header("LinkedIn", "Voyager API")
    console.print("[white]Enter LinkedIn handles or profile URLs (one per line)[/white]")
    console.print("[dim]Press Enter on empty line when complete[/dim]")
    console.print()

    usernames = []
    while True:
        entry = Prompt.ask("Username/URL", default="")
        if not entry:
            break
        entry = entry.strip().rstrip('/')
        if '/in/' in entry:
            entry = entry.split('/in/')[-1]
        entry = entry.lstrip('@').strip()
        if entry:
            usernames.append(entry)
            console.print(f"[green]✓[/green] Added {entry}")

    if not usernames:
        return

    console.print()
    profiles = _standard_scrape_loop(scrape_linkedin_profile, usernames, label_prefix="", delay_range=(3.0, 6.0))
    _standard_export(profiles, len(usernames), "linkedin")


def scrape_github_interactive():
    from app.scrapers.github import scrape_profile
    _platform_header("GitHub", "REST API")
    usernames = _collect_usernames("GitHub")
    if not usernames:
        return
    console.print()
    profiles = _standard_scrape_loop(scrape_profile, usernames, label_prefix="", delay_range=(0.5, 1.5))
    _standard_export(profiles, len(usernames), "github")


def scrape_youtube_interactive():
    from app.scrapers.youtube import scrape_channel
    _platform_header("YouTube", "Public Channels")

    console.print("[white]Enter YouTube channel handles (e.g. @MrBeast) or Channel IDs[/white]")
    console.print("[dim]Press Enter on empty line when complete[/dim]")
    console.print()

    channels = []
    while True:
        channel = Prompt.ask("Channel", default="")
        if not channel:
            break
        channel = channel.strip()
        if channel:
            channels.append(channel)
            console.print(f"[green]✓[/green] Added {channel}")

    if not channels:
        return

    console.print()
    profiles = _standard_scrape_loop(scrape_channel, channels, label_prefix="", delay_range=(1.0, 2.5))
    _standard_export(profiles, len(channels), "youtube", "channels")


def scrape_twitch_interactive():
    from app.scrapers.twitch import scrape_profile
    _platform_header("Twitch", "Public GQL")
    usernames = _collect_usernames("Twitch")
    if not usernames:
        return
    console.print()
    profiles = _standard_scrape_loop(scrape_profile, usernames, label_prefix="", delay_range=(0.5, 1.5))
    _standard_export(profiles, len(usernames), "twitch")


def scrape_linktree_interactive():
    from app.scrapers.linktree import scrape_linktree, scrape_all
    _platform_header("Link-in-Bio", "Linktree, Stan, Bio.link")

    console.print("  [1] Linktree only (linktr.ee)")
    console.print("  [2] Auto-detect across platforms")
    console.print()
    platform_choice = Prompt.ask("[>] Selection", choices=["1", "2"], default="1")

    scraper_map = {"1": (scrape_linktree, "linktree"), "2": (scrape_all, "linkbio")}
    scraper_func, platform_name = scraper_map[platform_choice]

    console.print()
    usernames = _collect_usernames("link-in-bio")
    if not usernames:
        return

    console.print()
    profiles = _standard_scrape_loop(scraper_func, usernames, label_prefix="", delay_range=(0.5, 1.5))

    if profiles:
        _success_summary(len(profiles), len(usernames))
        profiles = enrich_profiles(profiles)
        if Confirm.ask("[+] Export enriched dataset to CSV?", default=True):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"coldreach_{platform_name}_{timestamp}.csv"

            export_profiles = []
            for p in profiles:
                flat = {k: v for k, v in p.items() if k not in ['links', 'socials']}
                if p.get('socials'):
                    for platform, handle in p['socials'].items():
                        flat[f'social_{platform}'] = handle
                export_profiles.append(flat)

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if export_profiles:
                    all_keys = set()
                    for p in export_profiles:
                        all_keys.update(p.keys())
                    writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
                    writer.writeheader()
                    writer.writerows(export_profiles)
            _export_result(filename, len(profiles))
    else:
        _no_results()


def scrape_pinterest_interactive():
    from app.scrapers.pinterest import scrape_profile
    _platform_header("Pinterest", "Public profiles")
    usernames = _collect_usernames("Pinterest")
    if not usernames:
        return
    console.print()
    profiles = _standard_scrape_loop(scrape_profile, usernames, label_prefix="", delay_range=(1.0, 2.5))
    _standard_export(profiles, len(usernames), "pinterest")


def scrape_from_file():
    _platform_header("Bulk Pipeline", "File ingestion")
    console.print()

    filename = Prompt.ask("[>] Target filename", default="targets.txt")
    try:
        usernames = []
        if filename.lower().endswith('.csv'):
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    username = row.get('username', '') or row.get('Username', '') or row.get('handle', '') or row.get('Handle', '')
                    if not username:
                        first_col = list(row.values())[0] if row else ''
                        username = first_col
                    username = username.strip().replace('@', '')
                    if username:
                        usernames.append(username)
        else:
            with open(filename, 'r', encoding='utf-8') as f:
                usernames = [line.strip().replace('@', '') for line in f if line.strip()]

        if not usernames:
            console.print(f"\n[red]✗ No records identified in {filename}[/red]")
            return

        console.print(f"\n[white]Loaded {len(usernames)} targets from {filename}[/white]")
        console.print()
        console.print(f"[bold {ACCENT}]Select platform channel:[/bold {ACCENT}]")
        console.print("  [1] Instagram")
        console.print("  [2] LinkedIn")
        console.print("  [3] GitHub")
        console.print("  [4] YouTube")
        console.print("  [5] Twitch")
        console.print("  [6] Linktree")
        console.print("  [7] Pinterest")
        console.print()

        platform_choice = Prompt.ask("[>] Platform", choices=["1", "2", "3", "4", "5", "6", "7"], default="1")
        platform_map = {
            "1": ("instagram", "Instagram"),
            "2": ("linkedin", "LinkedIn"),
            "3": ("github", "GitHub"),
            "4": ("youtube", "YouTube"),
            "5": ("twitch", "Twitch"),
            "6": ("linktree", "Linktree"),
            "7": ("pinterest", "Pinterest"),
        }
        platform_key, platform_name = platform_map[platform_choice]

        if platform_key == "instagram":
            from app.scrapers.instagram import scrape_profile_no_login as scraper_func
        elif platform_key == "linkedin":
            cookie = os.environ.get('LINKEDIN_COOKIE', '').strip()
            if not cookie:
                console.print("[red]✗ LINKEDIN_COOKIE not configured in .env[/red]")
                return
            from app.scrapers.linkedin import scrape_linkedin_profile as scraper_func
        elif platform_key == "github":
            from app.scrapers.github import scrape_profile as scraper_func
        elif platform_key == "youtube":
            from app.scrapers.youtube import scrape_channel as scraper_func
        elif platform_key == "twitch":
            from app.scrapers.twitch import scrape_profile as scraper_func
        elif platform_key == "linktree":
            from app.scrapers.linktree import scrape_linktree as scraper_func
        elif platform_key == "pinterest":
            from app.scrapers.pinterest import scrape_profile as scraper_func

        console.print()
        console.print(f"[white]Extracting {len(usernames)} {platform_name} records...[/white]")
        if not Confirm.ask("Execute batch?", default=True):
            return

        console.print()
        profiles = []
        successful = 0

        for i, username in enumerate(usernames, 1):
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
                progress.add_task(f"[white]@{username}  [dim]({i}/{len(usernames)})[/dim]", total=None)
                try:
                    profile = scraper_func(username)
                    if profile:
                        profiles.append(profile)
                        successful += 1
                        cnt = profile.get('follower_count', 0) or profile.get('subscriber_count', 0) or 0
                        progress.stop()
                        console.print(f"  [green]✓[/green] @{username}  [dim]{cnt:,} followers[/dim]")
                    else:
                        progress.stop()
                        console.print(f"  [red]✗[/red] [dim]@{username}[/dim]")
                except Exception:
                    progress.stop()
                    console.print(f"  [red]✗[/red] [dim]@{username}[/dim]")

            if i < len(usernames):
                random_delay(*_get_delay_range((1.5, 4.0)))

        console.print()
        if profiles:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            export_filename = f"coldreach_bulk_{platform_key}_{timestamp}.csv"
            with open(export_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=profiles[0].keys())
                writer.writeheader()
                writer.writerows(profiles)
            _success_summary(successful, len(usernames))
            _export_result(export_filename, successful)
        else:
            _no_results()

    except FileNotFoundError:
        console.print(f"\n[red]✗ Error: File '{filename}' not found[/red]")
    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")


def settings_menu():
    _platform_header("Settings", "Engine Configuration")

    ps = proxy_status()
    current_proxy = os.environ.get('CR_PROXY', '')
    free_enabled = os.environ.get('CR_FREE_PROXY', '').lower() in ('1', 'true', 'yes')
    proxy_file = os.environ.get('CR_PROXY_FILE', '')
    delay_min = os.environ.get('CR_DELAY_MIN', '1.0')
    delay_max = os.environ.get('CR_DELAY_MAX', '2.5')
    li_cookie = os.environ.get('LINKEDIN_COOKIE', '').strip()

    proxy_str = f"[green]{ps}[/green]" if ps != 'none' else "[red]direct[/red]"
    if current_proxy:
        proxy_str += f"  [dim]{current_proxy[:40]}[/dim]"
    elif proxy_file:
        proxy_str += f"  [dim]{proxy_file[:40]}[/dim]"

    console.print(f"  [dim]Proxy Layer:[/dim]    {proxy_str}")
    console.print(f"  [dim]Free Pool:[/dim]      [green]on[/green]" if free_enabled else f"  [dim]Free Pool:[/dim]      [dim]off[/dim]")
    console.print(f"  [dim]Jitter Delay:[/dim]   [white]{delay_min}s - {delay_max}s[/white]")
    console.print(f"  [dim]LinkedIn Cookie:[/dim] [green]active[/green]" if li_cookie else f"  [dim]LinkedIn Cookie:[/dim] [dim]unconfigured[/dim]")
    console.print(f"  [dim]Session Stats:[/dim]   [white]{_session_stats['scraped']}[/white] [dim]leads extracted[/dim]")
    console.print()

    console.print(Rule("[bold white]Proxy Management[/bold white]", style=ACCENT_DIM, align="left"))
    console.print()
    console.print(f"  [{ACCENT}][1][/{ACCENT}]  Set dedicated proxy URL")
    console.print(f"  [{ACCENT}][2][/{ACCENT}]  Set proxy pool file")
    console.print(f"  [{ACCENT}][3][/{ACCENT}]  Toggle free anonymous pool")
    console.print(f"  [{ACCENT}][4][/{ACCENT}]  Test active connection")
    console.print(f"  [{ACCENT}][5][/{ACCENT}]  Reset proxy to direct")
    console.print()

    console.print(Rule("[bold white]Configuration & Storage[/bold white]", style=ACCENT_DIM, align="left"))
    console.print()
    console.print(f"  [{ACCENT}][6][/{ACCENT}]  Set scrape delay jitter")
    console.print(f"  [{ACCENT}][7][/{ACCENT}]  Save LinkedIn li_at cookie")
    console.print(f"  [{ACCENT}][8][/{ACCENT}]  Clean exported CSV files")
    console.print(f"  [{ACCENT}][0][/{ACCENT}]  Return to workspace")
    console.print()

    choice = Prompt.ask(f"[{ACCENT}]>[/{ACCENT}]", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8"], default="0")
    import httpx as _httpx

    if choice == '1':
        url = Prompt.ask("[>] Proxy URL (e.g. http://user:pass@host:port)")
        if url.strip():
            _update_env('CR_PROXY', url.strip())
            console.print("[green]✓ Dedicated proxy configured[/green]")
    elif choice == '2':
        filepath = Prompt.ask("[>] Path to proxy file")
        if filepath.strip():
            if os.path.exists(filepath.strip()):
                _update_env('CR_PROXY_FILE', filepath.strip())
                console.print("[green]✓ Proxy pool file configured[/green]")
            else:
                console.print(f"[red]✗ File not found: {filepath.strip()}[/red]")
    elif choice == '3':
        if free_enabled:
            _update_env('CR_FREE_PROXY', 'false')
            console.print("[yellow]✓ Free proxy pool disabled[/yellow]")
        else:
            _update_env('CR_FREE_PROXY', 'true')
            console.print("[green]✓ Free proxy pool enabled[/green]")
    elif choice == '4':
        console.print("[white]Testing network egress...[/white]")
        from app.scrapers.stealth import get_proxy
        px = get_proxy()
        if not px:
            try:
                resp = _httpx.get('https://httpbin.org/ip', timeout=10)
                ip = resp.json().get('origin', '?')
                console.print(f"[green]✓ Direct egress functional. Egress IP: {ip}[/green]")
            except Exception as e:
                console.print(f"[red]✗ Direct connection error: {e}[/red]")
        else:
            proxy_url = px if px.startswith('http') else f'http://{px}'
            try:
                resp = _httpx.get('https://httpbin.org/ip', proxy=proxy_url, timeout=10, verify=False)
                ip = resp.json().get('origin', '?')
                console.print(f"[green]✓ Proxy verified! External IP: {ip}[/green]")
            except Exception as e:
                console.print(f"[red]✗ Proxy unreachable: {e}[/red]")
    elif choice == '5':
        _update_env('CR_PROXY', '')
        _update_env('CR_FREE_PROXY', 'false')
        _update_env('CR_PROXY_FILE', '')
        os.environ.pop('CR_PROXY', None)
        os.environ.pop('CR_PROXY_FILE', None)
        console.print("[yellow]✓ Reset to direct connection[/yellow]")
    elif choice == '6':
        new_min = Prompt.ask("[>] Min delay (s)", default=delay_min)
        new_max = Prompt.ask("[>] Max delay (s)", default=delay_max)
        try:
            fmin, fmax = float(new_min), float(new_max)
            if fmin >= 0 and fmax >= fmin:
                _update_env('CR_DELAY_MIN', str(fmin))
                _update_env('CR_DELAY_MAX', str(fmax))
                console.print(f"[green]✓ Jitter set to {fmin}s - {fmax}s[/green]")
            else:
                console.print("[red]✗ Invalid range[/red]")
        except ValueError:
            console.print("[red]✗ Must be numeric[/red]")
    elif choice == '7':
        cookie = Prompt.ask("[>] Paste LinkedIn li_at value", default="")
        if cookie.strip():
            _update_env('LINKEDIN_COOKIE', cookie.strip())
            console.print("[green]✓ LinkedIn session updated[/green]")
    elif choice == '8':
        csv_files = list(Path('.').glob('coldreach_*.csv'))
        if not csv_files:
            console.print("[yellow]No ColdReach CSV datasets found[/yellow]")
        else:
            if Confirm.ask(f"[>] Delete {len(csv_files)} exported CSV files?", default=False):
                for f in csv_files:
                    f.unlink()
                console.print(f"[green]✓ Cleaned {len(csv_files)} exports[/green]")


def view_exports():
    _platform_header("Datasets", "Exported Lead Data")
    csv_files = list(Path('.').glob('coldreach_*.csv'))
    if not csv_files:
        console.print("  [yellow]No exported lead datasets found yet[/yellow]")
        return

    csv_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    table = Table(box=box.MINIMAL_HEAVY_HEAD, border_style="dim", padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("Dataset File", style="white")
    table.add_column("Size", style="white", justify="right")
    table.add_column("Generated", style="dim")

    for i, file in enumerate(csv_files[:10], 1):
        size = file.stat().st_size / 1024
        mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(file.stat().st_mtime))
        table.add_row(str(i), file.name, f"{size:.1f} KB", mtime)

    console.print(table)
    console.print(f"  [dim]{len(csv_files)} datasets total[/dim]")
    console.print()


def main():
    console.clear()
    show_header()

    while True:
        show_menu()
        try:
            choice = Prompt.ask(
                f"[{ACCENT}]>[/{ACCENT}]",
                choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
                default="1",
                show_choices=False
            )

            if choice == '0':
                console.clear()
                console.print()
                console.print(Rule(style=ACCENT_DIM))
                console.print(
                    f"  [bold {ACCENT}]ColdReach[/bold {ACCENT}]  "
                    f"[dim]Lead Intelligence Engine · {__repo__}[/dim]"
                )
                console.print()
                break

            console.clear()

            if choice == '1':
                scrape_instagram_interactive()
            elif choice == '2':
                scrape_linkedin_interactive()
            elif choice == '3':
                scrape_github_interactive()
            elif choice == '4':
                scrape_youtube_interactive()
            elif choice == '5':
                scrape_twitch_interactive()
            elif choice == '6':
                scrape_linktree_interactive()
            elif choice == '7':
                scrape_pinterest_interactive()
            elif choice == '8':
                scrape_from_file()
            elif choice == '9':
                view_exports()
            elif choice == '10':
                settings_menu()

            _pause()
            console.clear()
            show_header()

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Workspace closed.[/yellow]")
            break
        except EOFError:
            break
        except Exception as e:
            console.print(f"\n[red]✗ Engine error: {e}[/red]")


if __name__ == '__main__':
    main()
