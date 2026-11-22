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

from tagline_font import TAGLINE_FONT_WOFF2_B64
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
    """Terminal-style card that 'types' itself out: whoami, motto, stack, stats."""
    t = CARD_THEMES[theme]
    W = 1200
    X0 = 56            # left text edge
    CW = 9.0           # monospace character width (enforced with textLength)
    TYPE = 0.055       # seconds per typed character
    PROMPT = "➜  ~/profile"
    CMD_X = X0 + (len(PROMPT) + 1) * CW
    parts: list[str] = []

    def show(begin: float) -> str:
        return f'<set attributeName="opacity" to="1" begin="{begin:.2f}s" fill="freeze"/>'

    def fade(begin: float, dur: float = 0.35) -> str:
        return (f'<animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" '
                f'dur="{dur}s" fill="freeze"/>')

    def command(y: float, cmd: str, start: float, cid: str) -> float:
        """Prompt + a command typed character by character. Returns the time typing ends."""
        n = len(cmd)
        end = start + n * TYPE
        widths = ";".join(f"{i * CW:.1f}" for i in range(n + 1))
        xs = ";".join(f"{CMD_X + i * CW:.1f}" for i in range(n + 1))
        parts.append(
            f'<g opacity="0">{show(start - 0.25)}'
            f'<text x="{X0}" y="{y}" class="mono" font-size="15" textLength="{len(PROMPT) * CW:.0f}" lengthAdjust="spacing">'
            f'<tspan fill="{t["accent"]}">➜</tspan><tspan fill="{t["name3"]}">  ~/profile</tspan></text></g>'
            f'<clipPath id="{cid}"><rect x="{CMD_X}" y="{y - 16}" width="0" height="22">'
            f'<animate attributeName="width" values="{widths}" calcMode="discrete" begin="{start:.2f}s" '
            f'dur="{n * TYPE + 0.001:.3f}s" fill="freeze"/></rect></clipPath>'
            f'<text x="{CMD_X}" y="{y}" class="mono" font-size="15" fill="{t["fg"]}" clip-path="url(#{cid})" '
            f'textLength="{n * CW:.0f}" lengthAdjust="spacing">{escape(cmd)}</text>'
            f'<rect x="{CMD_X}" y="{y - 14}" width="{CW:.0f}" height="18" fill="{t["accent"]}" opacity="0">'
            f'{show(start - 0.25)}'
            f'<animate attributeName="x" values="{xs}" calcMode="discrete" begin="{start:.2f}s" '
            f'dur="{n * TYPE + 0.001:.3f}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0" begin="{end + 0.12:.2f}s" fill="freeze"/></rect>'
        )
        return end

    # 1. whoami -> name + role
    end = command(96, "whoami", 0.6, "c1")
    parts.append(
        f'<g opacity="0">{fade(end + 0.2)}'
        f'<text x="{X0 - 2}" y="160" class="sans" font-size="54" font-weight="700" fill="url(#name)" '
        f'letter-spacing="-1.2">Haritha Sivasankaran</text>'
        f'<text x="{X0}" y="192" class="mono" font-size="14" fill="{t["muted"]}">{escape(CARD_ROLE)}</text></g>'
    )

    # 2. cat motto.txt -> tagline
    end = command(244, "cat motto.txt", end + 0.9, "c2")
    parts.append(
        f'<g opacity="0">{fade(end + 0.2)}'
        f'<text x="{X0}" y="280" class="tagline" font-size="24" fill="{t["name2"]}" letter-spacing="-0.3">{escape(CARD_TAGLINE)}</text></g>'
    )

    # 3. ls ~/stack -> coloured listing with logos, 7 per row
    end = command(332, "ls ~/stack", end + 0.8, "c3")
    col_w = (W - 2 * X0) / 7
    for row in range(3):
        items = []
        for col in range(7):
            i = row * 7 + col
            if i >= len(CARD_TECH):
                break
            name, slug, dark_color, light_color = CARD_TECH[i]
            color = (dark_color if theme == "dark" else light_color) or t["fg"]
            x = X0 + col * col_w
            y = 372 + row * 34
            items.append(
                f'<g transform="translate({x:.1f} {y - 15}) scale(0.75)"><path d="{TECH_ICON_PATHS[slug]}" fill="{color}"/></g>'
                f'<text x="{x + 26:.1f}" y="{y}" class="mono" font-size="15" fill="{color}">{escape(name.lower().replace(" ", "-"))}</text>'
            )
        parts.append(f'<g opacity="0">{fade(end + 0.2 + row * 0.12, 0.25)}{"".join(items)}</g>')

    # 4. ./stats.sh -> git-style stat bars (left) + language bars (right)
    end = command(500, "./stats.sh --since 1y", end + 1.0, "c4")
    repos = profile["public_repos"] + profile.get("private_repos", 0)
    stats = [
        ("contributions", profile["contributions_365d"]),
        ("active days", profile["active_days"]),
        ("longest streak", profile.get("longest_streak", 0)),
        ("repositories", repos),
    ]
    top = max(v for _, v in stats) or 1
    out_t = end + 0.25
    for i, (label, value) in enumerate(stats):
        y = 540 + i * 28
        plus = max(1, round(28 * (value / top) ** 0.5))
        parts.append(
            f'<g opacity="0">{fade(out_t + i * 0.12, 0.25)}'
            f'<text x="{X0}" y="{y}" class="mono" font-size="15" fill="{t["muted"]}">{escape(label.ljust(15))}</text>'
            f'<text x="{X0 + 150}" y="{y}" class="mono" font-size="15" fill="{t["muted"]}">|</text>'
            f'<text x="{X0 + 210}" y="{y}" text-anchor="end" class="mono" font-size="15" font-weight="700" fill="{t["fg"]}">{format_number(value)}</text>'
            f'<text x="{X0 + 224}" y="{y}" class="mono" font-size="15" fill="{t["accent"]}">{"+" * plus}</text></g>'
        )

    langs = [l for l in profile.get("language_breakdown", [])
             if l["name"] not in EXCLUDED_LANGUAGES and l["percent"] >= 1][:5]
    total = sum(l["percent"] for l in langs) or 1
    LX, BAR_X, BAR_W = 640, 800, 260
    for i, lang in enumerate(langs):
        y = 540 + i * 28
        share = lang["percent"] / total
        color = LANGUAGE_COLORS.get(lang["name"], t["muted"])
        name = "Jupyter" if lang["name"] == "Jupyter Notebook" else lang["name"]
        parts.append(
            f'<g opacity="0">{fade(out_t + 0.3 + i * 0.12, 0.25)}'
            f'<text x="{LX}" y="{y}" class="mono" font-size="15" fill="{t["fg"]}">{escape(name)}</text>'
            f'<rect x="{BAR_X}" y="{y - 11}" width="{BAR_W}" height="10" rx="2" fill="{t["track"]}"/>'
            f'<rect x="{BAR_X}" y="{y - 11}" width="0" height="10" rx="2" fill="{color}">'
            f'<animate attributeName="width" from="0" to="{BAR_W * share:.1f}" begin="{out_t + 0.4 + i * 0.12:.2f}s" '
            f'dur="0.8s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines="0.2 0.7 0.2 1"/></rect>'
            f'<text x="{BAR_X + BAR_W + 14}" y="{y}" class="mono" font-size="15" fill="{t["muted"]}">{share * 100:.0f}%</text></g>'
        )

    # 5. idle prompt with blinking cursor
    rows = max(len(stats), len(langs))
    final_y = 540 + rows * 28 + 22
    final_t = out_t + 0.3 + rows * 0.12 + 0.9
    parts.append(
        f'<g opacity="0">{show(final_t)}'
        f'<text x="{X0}" y="{final_y}" class="mono" font-size="15" textLength="{len(PROMPT) * CW:.0f}" lengthAdjust="spacing">'
        f'<tspan fill="{t["accent"]}">➜</tspan><tspan fill="{t["name3"]}">  ~/profile</tspan></text>'
        f'<rect class="cursor" x="{CMD_X}" y="{final_y - 14}" width="{CW:.0f}" height="18" fill="{t["accent"]}"/></g>'
    )

    H = final_y + 44
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
  <title id="t">Haritha Sivasankaran — {escape(CARD_ROLE)}</title>
  <desc id="d">{escape(CARD_TAGLINE)} Stack: {escape(", ".join(n for n, *_ in CARD_TECH))}. {escape(", ".join(f"{format_number(v)} {l}" for l, v in stats))}.</desc>
  <style>
    .sans {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace; }}
    @font-face {{ font-family: "JBM Tagline"; font-style: italic; font-weight: 500; src: url(data:font/woff2;base64,{TAGLINE_FONT_WOFF2_B64}) format("woff2"); }}
    .tagline {{ font-family: "JBM Tagline", ui-monospace, Menlo, Consolas, monospace; font-style: italic; font-weight: 500; }}
    .cursor {{ animation: blink 1.05s steps(1) infinite; }}
    .breathe {{ animation: breathe 8s ease-in-out infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    @keyframes breathe {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .55; }} }}
    @media (prefers-reduced-motion: reduce) {{ .cursor, .breathe {{ animation: none; }} }}
  </style>
  <defs>
    <linearGradient id="name" gradientUnits="userSpaceOnUse" x1="54" y1="0" x2="600" y2="0"><stop offset="0" stop-color="{t["name1"]}"/><stop offset="0.55" stop-color="{t["name2"]}"/><stop offset="1" stop-color="{t["name3"]}"/></linearGradient>
    <clipPath id="win"><rect width="{W}" height="{H}" rx="14"/></clipPath>
    <radialGradient id="g1" cx="0.92" cy="0.0" r="0.5"><stop offset="0" stop-color="{t["glow1"]}" stop-opacity="{t["glow_op"]}"/><stop offset="1" stop-color="{t["glow1"]}" stop-opacity="0"/></radialGradient>
    <radialGradient id="g2" cx="0.0" cy="1" r="0.45"><stop offset="0" stop-color="{t["glow2"]}" stop-opacity="{t["glow_op"]}"/><stop offset="1" stop-color="{t["glow2"]}" stop-opacity="0"/></radialGradient>
  </defs>
  <g clip-path="url(#win)">
    <rect width="{W}" height="{H}" fill="{t["bg"]}"/>
    <rect class="breathe" width="{W}" height="{H}" fill="url(#g1)"/>
    <rect width="{W}" height="{H}" fill="url(#g2)"/>
    <rect width="{W}" height="44" fill="{t["bar"]}"/>
    <line x1="0" y1="44.5" x2="{W}" y2="44.5" stroke="{t["line"]}"/>
    <circle cx="28" cy="22" r="6" fill="#ff5f57"/><circle cx="48" cy="22" r="6" fill="#febc2e"/><circle cx="68" cy="22" r="6" fill="#28c840"/>
    <text x="{W / 2}" y="27" text-anchor="middle" class="mono" font-size="13" fill="{t["subtle"]}">haritha — zsh</text>
  </g>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{t["border"]}"/>
  {"".join(parts)}
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
