from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tech_icons import TECH_ICON_PATHS

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
JSON_PATH = ASSETS_DIR / "profile-data.json"
MAX_LANGUAGES = 6
# Markup/styling is left out of the language bar so it reflects programming languages.
EXCLUDED_LANGUAGES = {"HTML", "CSS", "SCSS", "Less", "Sass"}

USERNAME = os.getenv("PROFILE_USERNAME", "Haritha-Sivasankaran")
TIMEZONE_NAME = os.getenv("PROFILE_TIMEZONE", "Asia/Kolkata")
TOKEN = os.getenv("PROFILE_STATS_TOKEN", "").strip()

GRAPHQL_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    login
    name
    createdAt
    publicRepos: repositories(
      first: 100
      privacy: PUBLIC
      ownerAffiliations: OWNER
      isFork: false
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      totalCount
      nodes {
        name
        stargazerCount
        primaryLanguage {
          name
          color
        }
      }
    }
    privateRepos: repositories(
      first: 100
      privacy: PRIVATE
      ownerAffiliations: OWNER
      isFork: false
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      totalCount
      nodes {
        name
        primaryLanguage {
          name
          color
        }
      }
    }
    contributionsCollection(from: $from, to: $to) {
      hasAnyRestrictedContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            contributionLevel
            date
            weekday
          }
        }
      }
    }
  }
}
""".strip()

def current_datetime() -> datetime:
    if ZoneInfo is not None:
        # Newer runners ship tzdata without legacy aliases (e.g. Asia/Calcutta), so try the modern name too.
        for name in (TIMEZONE_NAME, "Asia/Kolkata"):
            try:
                return datetime.now(ZoneInfo(name))
            except Exception:
                continue
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))


def request_json(url: str, token: str | None = None, payload: dict | None = None) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "haritha-profile-overview",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")

    request = Request(url, headers=headers, data=body)
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def request_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "haritha-profile-overview",
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def fetch_public_repo_language_breakdown(login: str, token: str | None = None) -> list[dict]:
    if token:
        # Use /user/repos to fetch both public and private repositories for the authenticated user
        url = "https://api.github.com/user/repos?per_page=100&type=owner&sort=updated"
    else:
        url = f"https://api.github.com/users/{login}/repos?per_page=100&type=owner&sort=updated"

    repos = request_json(url, token=token)

    totals = Counter()
    for repo in repos:
        if repo.get("fork"):
            continue
        try:
            repo_languages = request_json(repo["languages_url"], token=token)
            for language, byte_count in repo_languages.items():
                if language not in EXCLUDED_LANGUAGES:
                    totals[language] += byte_count
        except Exception as e:
            # Handle potential API errors gracefully for individual repos
            print(f"Failed to fetch languages for {repo.get('name')}: {e}")

    if not totals:
        return []

    total_bytes = sum(totals.values()) or 1
    ranked = totals.most_common(MAX_LANGUAGES)
    return [
        {
            "name": language,
            "bytes": byte_count,
            "percent": round((byte_count / total_bytes) * 100, 2),
        }
        for language, byte_count in ranked
    ]


def fetch_graphql_profile(login: str, from_date: date, to_date: date, token: str) -> dict:
    payload = {
        "query": GRAPHQL_QUERY,
        "variables": {
            "login": login,
            "from": f"{from_date.isoformat()}T00:00:00Z",
            "to": f"{to_date.isoformat()}T23:59:59Z",
        },
    }
    response = request_json("https://api.github.com/graphql", token=token, payload=payload)
    if response.get("errors"):
        message = "; ".join(item.get("message", "Unknown GraphQL error") for item in response["errors"])
        raise RuntimeError(message)

    user = response["data"]["user"]
    public_repositories = user["publicRepos"]["nodes"]
    private_repositories = user["privateRepos"]["nodes"]
    all_repositories = public_repositories + private_repositories
    language_breakdown = fetch_public_repo_language_breakdown(login, token=token)

    contribution_days: list[dict] = []
    weekly_totals: list[dict] = []
    for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
        filtered_days = []
        for day in week["contributionDays"]:
            day_date = date.fromisoformat(day["date"])
            if from_date <= day_date <= to_date:
                contribution_days.append(day)
                filtered_days.append(day)
        if filtered_days:
            weekly_totals.append(
                {
                    "start": filtered_days[0]["date"],
                    "total": sum(day["contributionCount"] for day in filtered_days),
                }
            )

    contribution_days.sort(key=lambda d: d["date"])
    longest_streak = 0
    temp_streak = 0
    for day in contribution_days:
        if day["contributionCount"] > 0:
            temp_streak += 1
            if temp_streak > longest_streak:
                longest_streak = temp_streak
        else:
            temp_streak = 0

    weekday_counts = [0] * 7
    for day in contribution_days:
        day_date = date.fromisoformat(day["date"])
        w = day_date.weekday()
        weekday_counts[w] += day["contributionCount"]
    if sum(weekday_counts) == 0:
        weekday_counts = [10, 15, 25, 18, 12, 4, 2]

    # Prefer most-recently-updated private repo as "active" pipeline
    active_private = [r for r in private_repositories if r["name"].lower() != login.lower()]
    active_public  = [r for r in public_repositories  if r["name"].lower() != login.lower()]
    if active_private:
        top_repo_name = active_private[0]["name"]
        top_repo_lang = (active_private[0]["primaryLanguage"]["name"] if active_private[0].get("primaryLanguage") else "Java")
    elif active_public:
        top_repo_name = active_public[0]["name"]
        top_repo_lang = (active_public[0]["primaryLanguage"]["name"] if active_public[0].get("primaryLanguage") else "TypeScript")
    else:
        top_repo_name = "Portfolio"
        top_repo_lang = "TypeScript"

    # Second most recently updated private repo for "Current Focus" panel
    if len(active_private) >= 2:
        focus_repo_name = active_private[1]["name"]
        focus_repo_lang = (active_private[1]["primaryLanguage"]["name"] if active_private[1].get("primaryLanguage") else "Java")
    elif len(active_private) == 1:
        # Only one private repo — fall back to first public repo as secondary
        focus_repo_name = active_public[0]["name"] if active_public else top_repo_name
        focus_repo_lang = (active_public[0]["primaryLanguage"]["name"] if active_public and active_public[0].get("primaryLanguage") else top_repo_lang)
    else:
        focus_repo_name = top_repo_name
        focus_repo_lang = top_repo_lang

    private_commits = user["contributionsCollection"]["restrictedContributionsCount"]
    total_contributions = user["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    if total_contributions >= private_commits:
        public_contributions = total_contributions - private_commits
    else:
        public_contributions = total_contributions

    top_track_name = ""
    try:
        url = f"https://api.github.com/repos/{login}/{top_repo_name}/contents"
        contents = request_json(url, token=token)
        if isinstance(contents, list):
            files = [item["name"] for item in contents if item.get("type") == "file" and not item["name"].startswith(".")]
            code_files = [f for f in files if f.split(".")[-1] in ["py", "ipynb", "java", "js", "ts", "html", "css", "go", "rs"]]
            if code_files:
                top_track_name = code_files[0]
            elif files:
                top_track_name = files[0]
    except Exception as e:
        print(f"Failed to fetch repo contents: {e}")
    if not top_track_name:
        top_track_name = "transitpulse.py" if top_repo_name.lower() == "transitpulse" else "main.py"

    # Strictly private repo — never falls back to public
    private_repo_name = active_private[0]["name"] if active_private else ""
    private_repo_lang = (active_private[0]["primaryLanguage"]["name"] if active_private and active_private[0].get("primaryLanguage") else "Java") if active_private else ""

    return {
        "source_mode": "github-graphql",
        "username": user["login"],
        "name": user.get("name") or user["login"],
        "joined_year": date.fromisoformat(user["createdAt"][:10]).year,
        "public_repos": user["publicRepos"]["totalCount"],
        "private_repos": user["privateRepos"]["totalCount"],
        "stars_earned": sum(repo["stargazerCount"] for repo in public_repositories),
        "contributions_365d": total_contributions,
        "public_contributions": public_contributions,
        "private_contributions": private_commits,
        "active_days": sum(1 for day in contribution_days if day["contributionCount"] > 0),
        "peak_day": max((day["contributionCount"] for day in contribution_days), default=0),
        "restricted_contributions": private_commits,
        "has_restricted_contributions": user["contributionsCollection"]["hasAnyRestrictedContributions"],
        "weekly_totals": weekly_totals[-12:],
        "language_breakdown": language_breakdown,
        "longest_streak": longest_streak,
        "weekday_counts": weekday_counts,
        "top_repo_name": top_repo_name,
        "top_repo_lang": top_repo_lang,
        "top_track_name": top_track_name,
        "focus_repo_name": focus_repo_name,
        "focus_repo_lang": focus_repo_lang,
        "private_repo_name": private_repo_name,
        "private_repo_lang": private_repo_lang,
    }


def fetch_public_profile(login: str) -> dict:
    user = request_json(f"https://api.github.com/users/{login}")
    repos = request_json(
        f"https://api.github.com/users/{login}/repos?per_page=100&type=owner&sort=updated"
    )
    html = request_text(f"https://github.com/users/{login}/contributions")

    cells = {
        cell_id: {"date": day_date, "level": int(level)}
        for day_date, cell_id, level in re.findall(
            r'<td[^>]*data-date="([^"]+)"[^>]*id="([^"]+)"[^>]*data-level="(\d+)"[^>]*class="ContributionCalendar-day"[^>]*></td>',
            html,
        )
    }
    tooltips = re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>(.*?)</tool-tip>', html, re.S)

    contribution_days = []
    for cell_id, label in tooltips:
        info = cells.get(cell_id)
        if not info:
            continue
        plain_label = re.sub(r"<.*?>", "", label).strip()
        if plain_label.startswith("No contributions"):
            count = 0
        else:
            match = re.match(r"(\d[\d,]*) contribution", plain_label)
            count = int(match.group(1).replace(",", "")) if match else 0
        contribution_days.append(
            {
                "date": info["date"],
                "contributionCount": count,
                "contributionLevel": info["level"],
            }
        )

    contribution_days.sort(key=lambda item: item["date"])
    weekly_totals = []
    for index in range(0, len(contribution_days), 7):
        week = contribution_days[index : index + 7]
        if not week:
            continue
        weekly_totals.append(
            {
                "start": week[0]["date"],
                "total": sum(day["contributionCount"] for day in week),
            }
        )

    contribution_days.sort(key=lambda d: d["date"])
    longest_streak = 0
    temp_streak = 0
    for day in contribution_days:
        if day["contributionCount"] > 0:
            temp_streak += 1
            if temp_streak > longest_streak:
                longest_streak = temp_streak
        else:
            temp_streak = 0

    weekday_counts = [0] * 7
    for day in contribution_days:
        day_date = date.fromisoformat(day["date"])
        w = day_date.weekday()
        weekday_counts[w] += day["contributionCount"]
    if sum(weekday_counts) == 0:
        weekday_counts = [10, 15, 25, 18, 12, 4, 2]

    active_repos = [r for r in repos if r["name"].lower() != login.lower() and not r.get("fork")]
    if active_repos:
        top_repo_name = active_repos[0]["name"]
        top_repo_lang = active_repos[0].get("language") or "TypeScript"
    else:
        top_repo_name = "Portfolio"
        top_repo_lang = "TypeScript"

    top_track_name = ""
    try:
        url = f"https://api.github.com/repos/{login}/{top_repo_name}/contents"
        contents = request_json(url, token=None)
        if isinstance(contents, list):
            files = [item["name"] for item in contents if item.get("type") == "file" and not item["name"].startswith(".")]
            code_files = [f for f in files if f.split(".")[-1] in ["py", "ipynb", "java", "js", "ts", "html", "css", "go", "rs"]]
            if code_files:
                top_track_name = code_files[0]
            elif files:
                top_track_name = files[0]
    except Exception as e:
        print(f"Failed to fetch repo contents: {e}")
    if not top_track_name:
        top_track_name = "transitpulse.py" if top_repo_name.lower() == "transitpulse" else "main.py"

    return {
        "source_mode": "github-public",
        "username": user["login"],
        "name": user.get("name") or user["login"],
        "joined_year": date.fromisoformat(user["created_at"][:10]).year,
        "public_repos": user["public_repos"],
        "stars_earned": sum(repo["stargazers_count"] for repo in repos if not repo.get("fork")),
        "contributions_365d": sum(day["contributionCount"] for day in contribution_days),
        "active_days": sum(1 for day in contribution_days if day["contributionCount"] > 0),
        "peak_day": max((day["contributionCount"] for day in contribution_days), default=0),
        "restricted_contributions": 0,
        "has_restricted_contributions": False,
        "weekly_totals": weekly_totals[-12:],
        "language_breakdown": fetch_public_repo_language_breakdown(login),
        "longest_streak": longest_streak,
        "weekday_counts": weekday_counts,
        "top_repo_name": top_repo_name,
        "top_repo_lang": top_repo_lang,
        "top_track_name": top_track_name,
    }


def fetch_profile_data() -> dict:
    today = current_datetime().date()
    from_date = today - timedelta(days=364)

    if TOKEN:
        try:
            return fetch_graphql_profile(USERNAME, from_date, today, TOKEN)
        except (HTTPError, URLError, RuntimeError, KeyError, ValueError) as e:
            print(f"GraphQL fetch failed: {e}")

    # Fallback to existing JSON data to preserve token-synced numbers if run locally
    if JSON_PATH.exists():
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            required_keys = ["username", "name", "source_mode", "contributions_365d", "language_breakdown", "weekly_totals"]
            if all(k in data for k in required_keys):
                return data
        except Exception as e:
            print(f"Failed to read existing JSON profile data: {e}")

    return fetch_public_profile(USERNAME)


def format_number(value: int) -> str:
    return f"{value:,}"


CARD_THEMES = {
    "dark": dict(bg="#0d1117", bar="#010409", border="#30363d", line="#21262d", fg="#e6edf3",
                 muted="#8b949e", subtle="#6e7681", track="#21262d", accent="#3fb950",
                 chip="#161b22", glow1="#238636", glow2="#1f6feb", glow_op="0.34", dots="#30363d",
                 name1="#ffffff", name2="#7ee787", name3="#79c0ff", stat="#56d364"),
    "light": dict(bg="#ffffff", bar="#f6f8fa", border="#d0d7de", line="#eaeef2", fg="#1f2328",
                  muted="#59636e", subtle="#818b98", track="#eaeef2", accent="#1a7f37",
                  chip="#f6f8fa", glow1="#2da44e", glow2="#0969da", glow_op="0.15", dots="#d0d7de",
                  name1="#1f2328", name2="#1a7f37", name3="#0969da", stat="#1a7f37"),
}
LANGUAGE_COLORS = {
    "HTML": "#e34c26", "JavaScript": "#f1e05a", "TypeScript": "#3178c6", "Jupyter Notebook": "#da5b0b",
    "CSS": "#663399", "Java": "#b07219", "Python": "#3572a5", "Shell": "#89e051", "Go": "#00add8",
    "Vue": "#41b883", "Svelte": "#ff3e00", "SCSS": "#c6538c", "Kotlin": "#a97bff", "C++": "#f34b7d",
}
CARD_ROLE = "Systems Engineer @ TCS  ·  Full-Stack Developer"
CARD_TAGLINE = "Code that survives Monday traffic and Friday deploys."
# (label, Simple Icons slug, dark-theme colour, light-theme colour); None = use text colour
CARD_TECH = [
    # Backend & messaging
    ("Java", "openjdk", "#f89820", "#c26b00"),
    ("Spring Boot", "springboot", "#6db33f", "#4e9a2a"),
    ("Python", "python", "#5a9bd5", "#3776ab"),
    ("Node.js", "nodedotjs", "#5fa04e", "#3c873a"),
    ("Express", "express", None, None),
    ("Kafka", "apachekafka", None, None),
    ("RabbitMQ", "rabbitmq", "#ff6600", "#e65c00"),
    # Frontend
    ("React", "react", "#61dafb", "#087ea4"),
    ("Next.js", "nextdotjs", None, None),
    ("TypeScript", "typescript", "#4c8fd6", "#3178c6"),
    ("JavaScript", "javascript", "#f7df1e", "#c9a800"),
    ("Vue.js", "vuedotjs", "#4fc08d", "#3ba776"),
    ("Svelte", "svelte", "#ff3e00", "#ff3e00"),
    ("Tailwind", "tailwindcss", "#38bdf8", "#0891b2"),
    # Data, infra & tooling
    ("PostgreSQL", "postgresql", "#6b8cef", "#336791"),
    ("MongoDB", "mongodb", "#47a248", "#3f8f3f"),
    ("Docker", "docker", "#2496ed", "#1d63ed"),
    ("GH Actions", "githubactions", "#2088ff", "#2088ff"),
    ("Linux", "linux", None, None),
    ("Git", "git", "#f05032", "#e44c2c"),
    ("Jupyter", "jupyter", "#f37626", "#e46e1e"),
]


def build_profile_card_svg(profile: dict, theme: str) -> str:
    """Single window-style card: intro, stack, live activity and languages."""
    t = CARD_THEMES[theme]
    W, H = 1200, 654
    repos = profile["public_repos"] + profile.get("private_repos", 0)
    stats = [
        (format_number(profile["contributions_365d"]), "contributions"),
        (format_number(profile["active_days"]), "active days"),
        (f'{profile.get("longest_streak", 0)} days', "longest streak"),
        (format_number(repos), "repositories"),
    ]

    def label(x, y, text):
        return (f'<text x="{x}" y="{y}" class="mono" font-size="12" fill="{t["subtle"]}" '
                f'letter-spacing="1.5">{escape(text.upper())}</text>')

    tile_w, tile_h, cols = 76, 62, 7
    gap_x = (584 - cols * tile_w) / (cols - 1)
    stack_parts = []
    for i, (name, slug, dark_color, light_color) in enumerate(CARD_TECH):
        tx = 56 + (i % cols) * (tile_w + gap_x)
        ty = 302 + (i // cols) * (tile_h + 8)
        color = (dark_color if theme == "dark" else light_color) or t["fg"]
        stack_parts.append(
            f'<g class="rise" style="animation-delay:{0.6 + i * 0.03:.2f}s">'
            f'<rect x="{tx:.1f}" y="{ty}" width="{tile_w}" height="{tile_h}" rx="12" fill="{t["chip"]}" stroke="{t["border"]}"/>'
            f'<g transform="translate({tx + tile_w / 2 - 11:.1f} {ty + 10}) scale(0.9167)">'
            f'<path d="{TECH_ICON_PATHS[slug]}" fill="{color}"/></g>'
            f'<text x="{tx + tile_w / 2:.1f}" y="{ty + 50}" text-anchor="middle" class="mono" font-size="10.5" '
            f'fill="{t["muted"]}">{escape(name)}</text></g>'
        )
    stack_svg = "".join(stack_parts)
    dots_svg = "".join(
        f'<circle cx="{dx}" cy="{dy}" r="1.4" fill="{t["dots"]}" opacity="{max(0.0, 1 - (W - 40 - dx) / 380):.2f}"/>'
        for dx in range(780, W - 40, 22) for dy in range(70, 232, 22)
    )
    stat_svg = "".join(
        f'<g class="rise" style="animation-delay:{0.8 + i * 0.1:.2f}s">'
        f'<text x="{720 + (i % 2) * 220}" y="{336 + (i // 2) * 108}" class="sans" font-size="34" '
        f'font-weight="700" fill="{t["stat"]}">{escape(v)}</text>'
        f'<text x="{720 + (i % 2) * 220}" y="{360 + (i // 2) * 108}" class="sans" font-size="14" '
        f'fill="{t["muted"]}">{escape(l)}</text></g>'
        for i, (v, l) in enumerate(stats)
    )

    langs = [l for l in profile.get("language_breakdown", []) if l["name"] not in EXCLUDED_LANGUAGES and l["percent"] >= 1][:6]
    total = sum(l["percent"] for l in langs) or 1
    bar_x, bar_y, bar_w = 56, 574, W - 112
    x, lx, segments, legend = float(bar_x), 56, [], []
    for lang in langs:
        w = bar_w * lang["percent"] / total
        color = LANGUAGE_COLORS.get(lang["name"], t["muted"])
        segments.append(f'<rect x="{x:.1f}" y="{bar_y}" width="{max(w - 2, 1):.1f}" height="8" fill="{color}"/>')
        x += w
        text = f'{lang["name"]} {lang["percent"] / total * 100:.0f}%'
        legend.append(
            f'<circle cx="{lx + 5}" cy="{bar_y + 36}" r="5" fill="{color}"/>'
            f'<text x="{lx + 16}" y="{bar_y + 41}" class="mono" font-size="13" fill="{t["muted"]}">{escape(text)}</text>'
        )
        lx += 16 + int(len(text) * 7.9) + 28

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
  <title id="t">Haritha Sivasankaran — {escape(CARD_ROLE)}</title>
  <desc id="d">{escape(CARD_TAGLINE)} {escape(", ".join(f"{v} {l}" for v, l in stats))}.</desc>
  <style>
    .sans {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace; }}
    .cursor {{ animation: blink 1.1s steps(1) infinite; }}
    .pulse {{ animation: pulse 2.4s ease-in-out infinite; transform-origin: 62px 100px; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    @keyframes pulse {{ 0%,100% {{ opacity: .35; transform: scale(1); }} 50% {{ opacity: 0; transform: scale(2.2); }} }}
    .rise {{ animation: rise .8s cubic-bezier(.2,.7,.2,1) both; }}
    .grow {{ animation: grow 1.4s cubic-bezier(.65,0,.35,1) 1.2s both; transform-box: fill-box; transform-origin: left center; }}
    .breathe {{ animation: breathe 8s ease-in-out infinite; }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
    @keyframes breathe {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .55; }} }}
    @media (prefers-reduced-motion: reduce) {{ .cursor, .pulse, .rise, .grow, .breathe {{ animation: none; }} }}
  </style>
  <defs>
    <linearGradient id="name" gradientUnits="userSpaceOnUse" x1="54" y1="0" x2="600" y2="0"><stop offset="0" stop-color="{t["name1"]}"/><stop offset="0.55" stop-color="{t["name2"]}"/><stop offset="1" stop-color="{t["name3"]}"/></linearGradient>
    <clipPath id="win"><rect width="{W}" height="{H}" rx="14"/></clipPath>
    <radialGradient id="g1" cx="0.88" cy="0.05" r="0.55"><stop offset="0" stop-color="{t["glow1"]}" stop-opacity="{t["glow_op"]}"/><stop offset="1" stop-color="{t["glow1"]}" stop-opacity="0"/></radialGradient>
    <radialGradient id="g2" cx="0.02" cy="1" r="0.5"><stop offset="0" stop-color="{t["glow2"]}" stop-opacity="{t["glow_op"]}"/><stop offset="1" stop-color="{t["glow2"]}" stop-opacity="0"/></radialGradient>
    <clipPath id="lang"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="8" rx="4"/></clipPath>
  </defs>
  <g clip-path="url(#win)">
    <rect width="{W}" height="{H}" fill="{t["bg"]}"/>
    <rect class="breathe" width="{W}" height="{H}" fill="url(#g1)"/>
    <rect width="{W}" height="{H}" fill="url(#g2)"/>
    {dots_svg}
    <rect width="{W}" height="44" fill="{t["bar"]}"/>
    <line x1="0" y1="44.5" x2="{W}" y2="44.5" stroke="{t["line"]}"/>
    <circle cx="28" cy="22" r="6" fill="{t["border"]}"/><circle cx="48" cy="22" r="6" fill="{t["border"]}"/><circle cx="68" cy="22" r="6" fill="{t["border"]}"/>
    <text x="{W / 2}" y="27" text-anchor="middle" class="mono" font-size="13" fill="{t["subtle"]}">haritha@github: ~/profile</text>
  </g>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{t["border"]}"/>

  <g class="rise" style="animation-delay:.1s">
  <circle class="pulse" cx="62" cy="100" r="5" fill="{t["accent"]}"/>
  <circle cx="62" cy="100" r="5" fill="{t["accent"]}"/>
  <text x="78" y="105" class="mono" font-size="14" fill="{t["muted"]}">{escape(CARD_ROLE)}</text>
  </g>
  <text class="rise sans" style="animation-delay:.25s" x="54" y="168" font-size="54" font-weight="700" fill="url(#name)" letter-spacing="-1.2">Haritha Sivasankaran<tspan class="cursor" fill="{t["accent"]}">_</tspan></text>
  <text class="rise sans" style="animation-delay:.4s" x="56" y="212" font-size="24" fill="{t["fg"]}" opacity="0.82">{escape(CARD_TAGLINE)}</text>

  <line x1="56" y1="246.5" x2="{W - 56}" y2="246.5" stroke="{t["line"]}"/>
  <g class="rise" style="animation-delay:.55s">{label(56, 286, "Stack")}{label(720, 286, "Activity · last 12 months")}</g>
  {stack_svg}
  <line x1="680.5" y1="270" x2="680.5" y2="502" stroke="{t["line"]}"/>
  {stat_svg}

  <line x1="56" y1="526.5" x2="{W - 56}" y2="526.5" stroke="{t["line"]}"/>
  <g class="rise" style="animation-delay:1.1s">
  {label(56, 556, "Languages")}
  <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="8" rx="4" fill="{t["track"]}"/>
  </g>
  <g clip-path="url(#lang)"><g class="grow">{"".join(segments)}</g></g>
  <g class="rise" style="animation-delay:1.6s">{"".join(legend)}</g>
</svg>
"""


def write_outputs(profile: dict) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for theme in CARD_THEMES:
        (ASSETS_DIR / f"profile-card-{theme}.svg").write_text(build_profile_card_svg(profile, theme), encoding="utf-8")

    metadata = {
        "username": profile["username"],
        "name": profile["name"],
        "source_mode": profile["source_mode"],
        "generated_at": current_datetime().isoformat(),
        "timezone": TIMEZONE_NAME,
        "contributions_365d": profile["contributions_365d"],
        "public_contributions": profile.get("public_contributions", profile["contributions_365d"]),
        "private_contributions": profile.get("private_contributions", profile.get("restricted_contributions", 0)),
        "active_days": profile["active_days"],
        "peak_day": profile["peak_day"],
        "public_repos": profile["public_repos"],
        "private_repos": profile.get("private_repos", 0),
        "stars_earned": profile["stars_earned"],
        "joined_year": profile["joined_year"],
        "has_restricted_contributions": profile["has_restricted_contributions"],
        "restricted_contributions": profile["restricted_contributions"],
        "language_breakdown": profile["language_breakdown"],
        "weekly_totals": profile["weekly_totals"],
        "longest_streak": profile.get("longest_streak", 0),
        "weekday_counts": profile.get("weekday_counts", []),
        "top_repo_name": profile.get("top_repo_name", "dspy"),
        "top_repo_lang": profile.get("top_repo_lang", "Python"),
        "top_track_name": profile.get("top_track_name", "main.py"),
        "focus_repo_name": profile.get("focus_repo_name", ""),
        "focus_repo_lang": profile.get("focus_repo_lang", ""),
    }
    JSON_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def update_readme_cache_buster() -> None:
    readme_path = ROOT / "README.md"
    if not readme_path.exists():
        return
    content = readme_path.read_text(encoding="utf-8")
    timestamp = int(current_datetime().timestamp())

    new_content = re.sub(
        r'(srcset|src)="\./assets/profile-card-(dark|light)\.svg(?:\?[^"]+)?"',
        lambda m: f'{m.group(1)}="./assets/profile-card-{m.group(2)}.svg?t={timestamp}"',
        content
    )
    readme_path.write_text(new_content, encoding="utf-8")


def main() -> None:
    profile = fetch_profile_data()
    write_outputs(profile)
    update_readme_cache_buster()


if __name__ == "__main__":
    main()
