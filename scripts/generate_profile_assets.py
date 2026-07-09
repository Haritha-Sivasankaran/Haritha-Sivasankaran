from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
SVG_PATH = ASSETS_DIR / "profile-overview.svg"
WRAPPED_SVG_PATH = ASSETS_DIR / "profile-wrapped.svg"
BUILD_SVG_PATH = ASSETS_DIR / "profile-build.svg"
JSON_PATH = ASSETS_DIR / "profile-data.json"
MAX_LANGUAGES = 6

USERNAME = os.getenv("PROFILE_USERNAME", "Haritha-Sivasankaran")
TIMEZONE_NAME = os.getenv("PROFILE_TIMEZONE", "Asia/Calcutta")
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

LANGUAGE_COLORS = {
    "Python": "#60A5FA",
    "HTML": "#3B82F6",
    "JavaScript": "#3B82F6",
    "TypeScript": "#60A5FA",
    "CSS": "#8B5CF6",
    "Java": "#8B5CF6",
    "Jupyter Notebook": "#3B82F6",
    "React": "#60A5FA",
    "MySQL": "#22C55E",
}


def adjust_languages_with_private_stack(raw_breakdown: list[dict]) -> list[dict]:
    adjusted = []
    has_java = False
    for item in raw_breakdown:
        name = item["name"]
        adjusted_item = dict(item)
        if name.lower() == "java":
            adjusted_item["bytes"] = max(item.get("bytes", 0), 80000)
            has_java = True
        adjusted.append(adjusted_item)
        
    if not has_java:
        adjusted.append({"name": "Java", "bytes": 80000})
        
    total_bytes = sum(x["bytes"] for x in adjusted) or 1
    for x in adjusted:
        x["percent"] = (x["bytes"] / total_bytes) * 100
        
    adjusted.sort(key=lambda x: x["percent"], reverse=True)
    return adjusted


def process_code_activity_languages(raw_breakdown: list[dict]) -> list[dict]:
    exclude = {"html", "css", "scss"}
    filtered = []
    has_react = False
    react_bytes = 0
    python_bytes = 0
    
    for item in raw_breakdown:
        name = item["name"]
        if name.lower() in exclude:
            continue
        if name.lower() in ["javascript", "typescript"]:
            has_react = True
            react_bytes += item.get("bytes", 0)
        elif name.lower() in ["python", "jupyter notebook"]:
            python_bytes += item.get("bytes", 0)
        else:
            filtered.append(dict(item))
            
    # Add combined Python
    filtered.append({"name": "Python", "bytes": max(python_bytes, 100000)})
    
    # Add React
    filtered.append({"name": "React", "bytes": max(react_bytes, 70000)})
        
    # Ensure Java is present
    java_item = next((x for x in filtered if "java" in x["name"].lower() and "javascript" not in x["name"].lower()), None)
    if java_item:
        java_item["bytes"] = max(java_item.get("bytes", 0), 50000)
    else:
        filtered.append({"name": "Java", "bytes": 50000})
        
    total_bytes = sum(x["bytes"] for x in filtered) or 1
    for x in filtered:
        x["percent"] = (x["bytes"] / total_bytes) * 100
        
    boosted = []
    min_pct = 15.0
    for x in filtered:
        boosted.append({"name": x["name"], "percent": max(min_pct, x["percent"])})
        
    total_pct = sum(x["percent"] for x in boosted) or 1
    for x in boosted:
        x["percent"] = round((x["percent"] / total_pct) * 100, 2)
        
    boosted.sort(key=lambda x: x["percent"], reverse=True)
    return boosted


def current_datetime() -> datetime:
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo(TIMEZONE_NAME))
    return datetime.utcnow()


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


def get_contribution_note(profile: dict) -> str:
    if profile["source_mode"] == "github-graphql" and profile["has_restricted_contributions"]:
        return "public + private activity"
    if profile["source_mode"] == "github-graphql":
        return "token-synced activity"
    return "public activity only"


def get_source_tag(profile: dict) -> str:
    if profile["source_mode"] == "github-graphql" and profile["has_restricted_contributions"]:
        return "token sync + private"
    if profile["source_mode"] == "github-graphql":
        return "token sync"
    return "public sync"


def draw_window_controls(x: int, y: int) -> str:
    return f"""
    <circle cx="{x}" cy="{y}" r="3.5" fill="#EF4444" opacity="0.8" />
    <circle cx="{x + 12}" cy="{y}" r="3.5" fill="#F59E0B" opacity="0.8" />
    <circle cx="{x + 24}" cy="{y}" r="3.5" fill="#10B981" opacity="0.8" />
    """.strip()


def draw_micro_stat(x: int, y: int, label: str, value: str, accent: str) -> str:
    return f"""
    <g transform="translate({x}, {y})">
      <rect x="0" y="0" width="96" height="60" rx="18" fill="#070A13" stroke="#1E293B" stroke-width="1.2" />
      <circle cx="17" cy="18" r="4" fill="{accent}" />
      <text x="28" y="21" font-size="8.6" font-weight="700" fill="#64748B" letter-spacing="1.1" class="font-mono">{escape(label.upper())}</text>
      <text x="16" y="40" font-size="22" font-weight="800" fill="#F8FAFC" class="font-sans">{escape(value)}</text>
      <rect x="16" y="46" width="64" height="3" rx="1.5" fill="{accent}" opacity="0.85" />
    </g>
    """.strip()


def draw_language_mix(language_breakdown: list[dict]) -> str:
    if not language_breakdown:
        return """
        <text x="744" y="306" font-size="15" fill="#94A3B8" class="font-sans">No public repo language data yet.</text>
        """.strip()

    visible_languages = language_breakdown[:5]
    breakdown_total = sum(item["percent"] for item in language_breakdown) or 1
    max_percent = max(item["percent"] for item in visible_languages) or 1
    bar_x = 744
    bar_y = 270
    bar_width = 276
    current_x = bar_x

    raw_widths = [bar_width * (item["percent"] / breakdown_total) for item in language_breakdown]
    segment_widths = [int(width) for width in raw_widths]
    remaining_pixels = bar_width - sum(segment_widths)
    remainders = sorted(
        enumerate(raw_widths),
        key=lambda item: item[1] - int(item[1]),
        reverse=True,
    )
    for index, _ in remainders[:remaining_pixels]:
        segment_widths[index] += 1

    segments = [
        f'<rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="10" rx="5" fill="#0A1220" stroke="#22324A" stroke-width="1.2" />'
    ]
    for item, width in zip(language_breakdown, segment_widths):
        if width <= 0:
            continue
        accent = LANGUAGE_COLORS.get(item["name"], "#94A3B8")
        segments.append(
            f'<rect x="{current_x}" y="{bar_y}" width="{width}" height="10" rx="5" fill="{accent}" />'
        )
        current_x += width

    rows = []
    for index, item in enumerate(visible_languages):
        y = 292 + index * 22
        accent = LANGUAGE_COLORS.get(item["name"], "#94A3B8")
        fill_width = min(126, 36 + int((item["percent"] / max_percent) * 92))
        rows.append(
            f"""
            <g>
              <circle cx="{bar_x + 4}" cy="{y - 4}" r="4" fill="{accent}" />
              <text x="{bar_x + 16}" y="{y}" font-size="10.5" font-weight="700" fill="#E2E8F0" class="font-sans">{escape(item["name"])}</text>
              <text x="{bar_x + 276}" y="{y}" font-size="10.5" font-weight="700" fill="#8FA5C4" class="font-mono" text-anchor="end">{item["percent"]:.2f}%</text>
              <rect x="{bar_x + 16}" y="{y + 5}" width="126" height="4" rx="2" fill="#101B32" />
              <rect x="{bar_x + 16}" y="{y + 5}" width="{fill_width}" height="4" rx="2" fill="{accent}" />
            </g>
            """.strip()
        )

    footer = ""
    if len(language_breakdown) > len(visible_languages):
        footer = (
            f'<text x="{bar_x}" y="394" font-size="9.8" font-weight="600" fill="#64748B" class="font-mono">'
            f'+{len(language_breakdown) - len(visible_languages)} more in the data snapshot</text>'
        )

    return "\n".join([*segments, *rows, footer])


def draw_spotify_language_mix(language_breakdown: list[dict]) -> str:
    if not language_breakdown:
        return '<text x="570" y="250" font-size="14" fill="#94A3B8" class="font-sans">No repository language data yet.</text>'
    
    visible_languages = language_breakdown[:6]
    breakdown_total = sum(item["percent"] for item in language_breakdown) or 1
    max_percent = max(item["percent"] for item in visible_languages) or 1
    bar_x = 570
    bar_y = 210
    bar_width = 450
    current_x = bar_x

    raw_widths = [bar_width * (item["percent"] / breakdown_total) for item in language_breakdown]
    segment_widths = [int(width) for width in raw_widths]
    remaining_pixels = bar_width - sum(segment_widths)
    remainders = sorted(
        enumerate(raw_widths),
        key=lambda item: item[1] - int(item[1]),
        reverse=True,
    )
    for index, _ in remainders[:remaining_pixels]:
        segment_widths[index] += 1

    segments = [
        f'<rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="10" rx="5" fill="#131326" />'
    ]
    
    colors = ["#3B82F6", "#6366F1", "#8B5CF6", "#A78BFA", "#EC4899", "#FFFFFF"]
    for i, (item, width) in enumerate(zip(language_breakdown, segment_widths)):
        if width <= 0:
            continue
        color = colors[min(i, len(colors) - 1)]
        segments.append(
            f'<rect x="{current_x}" y="{bar_y}" width="{width}" height="10" rx="5" fill="{color}" />'
        )
        current_x += width

    rows = []
    for index, item in enumerate(visible_languages):
        y = 246 + index * 24
        color = colors[min(index, len(colors) - 1)]
        fill_width = min(150, 40 + int((item["percent"] / max_percent) * 110))
        rows.append(
            f"""
            <g>
              <circle cx="{bar_x + 4}" cy="{y - 4}" r="4" fill="{color}" />
              <text x="{bar_x + 18}" y="{y}" font-size="11" font-weight="700" fill="#E2E8F0" class="font-sans">{escape(item["name"])}</text>
              <text x="{bar_x + 450}" y="{y}" font-size="11" font-weight="700" fill="#94A3B8" class="font-mono" text-anchor="end">{item["percent"]:.1f}%</text>
              <rect x="{bar_x + 180}" y="{y - 7}" width="150" height="4" rx="2" fill="#131326" />
              <rect x="{bar_x + 180}" y="{y - 7}" width="{fill_width}" height="4" rx="2" fill="{color}" />
            </g>
            """.strip()
        )
    return "\n".join([*segments, *rows])


def draw_spotify_build_tempo(weekly_totals: list[dict]) -> str:
    if not weekly_totals:
        return '<text x="80" y="480" font-size="14" fill="#94A3B8" class="font-sans">No build tempo data yet.</text>'
    
    chart_left = 100
    chart_right = 1000
    chart_top = 460
    chart_bottom = 515
    chart_height = chart_bottom - chart_top
    totals = [item["total"] for item in weekly_totals]
    max_total = max(totals) or 1
    step = (chart_right - chart_left) / (len(weekly_totals) - 1) if len(weekly_totals) > 1 else 0

    points = []
    for index, week in enumerate(weekly_totals):
        x = chart_left + step * index
        total = week["total"]
        normalized = total / max_total if max_total else 0
        y = chart_bottom - (normalized * chart_height) if total else chart_bottom - 2
        points.append((x, y, total, week["start"]))

    line_path = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y, _, _ in points)
    area_path = (
        f"M {points[0][0]:.2f} {chart_bottom:.2f} "
        + " L ".join(f"{x:.2f} {y:.2f}" for x, y, _, _ in points)
        + f" L {points[-1][0]:.2f} {chart_bottom:.2f} Z"
    )

    labels = []
    month_indices = {0, 3, 6, 9, len(points) - 1}
    for index, (x, y, total, start_date) in enumerate(points):
        accent = "#3B82F6" if index % 2 == 0 else "#8B5CF6"
        labels.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#040408" stroke="{accent}" stroke-width="2.5" />'
        )
        if total > 0:
            labels.append(
                f'<text x="{x:.2f}" y="{y - 10:.2f}" font-size="10" font-weight="700" text-anchor="middle" fill="#FFFFFF" class="font-mono">{total}</text>'
            )
        if index in month_indices:
            labels.append(
                f'<text x="{x:.2f}" y="534" font-size="10" font-weight="700" text-anchor="middle" fill="#94A3B8" class="font-mono">{date.fromisoformat(start_date).strftime("%b").upper()}</text>'
            )

    grid = [
        f'<line x1="80" y1="{chart_bottom}" x2="1020" y2="{chart_bottom}" stroke="#131326" stroke-width="1" />',
        f'<line x1="80" y1="{chart_top}" x2="1020" y2="{chart_top}" stroke="#131326" stroke-opacity="0.5" stroke-dasharray="4,4" />',
    ]

    return "\n".join([
        *grid,
        f'<path d="{area_path}" fill="url(#tempoFill)" opacity="0.15" />',
        f'<path d="{line_path}" fill="none" stroke="url(#bluePurpleGrad)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />',
        *labels
    ])


def build_svg(profile: dict) -> str:
    now = current_datetime()
    updated_label = now.strftime("%d %b %Y").upper()

    lang_breakdown = adjust_languages_with_private_stack(profile.get("language_breakdown", []))
    longest_streak = profile.get("longest_streak", 0)
    public_repos = profile.get("public_repos", 0)
    contributions_365d = profile.get("contributions_365d", 0)
    active_days = profile.get("active_days", 0)
    peak_day = profile.get("peak_day", 0)
    stars_earned = profile.get("stars_earned", 0)

    return f"""<svg width="1100" height="600" viewBox="0 0 1100 600" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">Developer Telemetry Report</title>
  <desc id="desc">A dark premium yearly developer stats report using only blue, purple, and white accents.</desc>
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&amp;family=Sora:wght@500;600;700;800&amp;display=swap');
      .font-sans {{ font-family: 'Sora', -apple-system, BlinkMacSystemFont, sans-serif; }}
      .font-mono {{ font-family: 'IBM Plex Mono', monospace; }}
    </style>
    <linearGradient id="pageBg" x1="0" y1="0" x2="1100" y2="600" gradientUnits="userSpaceOnUse">
      <stop stop-color="#040408" />
      <stop offset="0.55" stop-color="#07070F" />
      <stop offset="1" stop-color="#020205" />
    </linearGradient>
    <linearGradient id="cardBg" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="#0A0A15" />
      <stop offset="1" stop-color="#05050A" />
    </linearGradient>
    <linearGradient id="cardBorder" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="#3B82F6" stop-opacity="0.4" />
      <stop offset="0.5" stop-color="#8B5CF6" stop-opacity="0.25" />
      <stop offset="1" stop-color="#00E5FF" stop-opacity="0.1" />
    </linearGradient>
    <linearGradient id="bluePurpleGrad" x1="0" y1="0" x2="1" y2="0">
      <stop stop-color="#3B82F6" />
      <stop offset="1" stop-color="#8B5CF6" />
    </linearGradient>
    <linearGradient id="tempoFill" x1="0" y1="460" x2="0" y2="515" gradientUnits="userSpaceOnUse">
      <stop stop-color="#3B82F6" stop-opacity="0.2" />
      <stop offset="1" stop-color="#8B5CF6" stop-opacity="0" />
    </linearGradient>
    <pattern id="gridPattern" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M 32 0 H 0 V 32" fill="none" stroke="#1E1B4B" stroke-width="1.2" stroke-opacity="0.22" />
    </pattern>
    <filter id="blurGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="32" />
    </filter>
  </defs>

  <rect width="1100" height="600" rx="20" fill="url(#pageBg)" />
  <rect width="1100" height="600" rx="20" fill="url(#gridPattern)" />
  <circle cx="160" cy="180" r="180" fill="#3B82F6" opacity="0.10" filter="url(#blurGlow)" />
  <circle cx="940" cy="420" r="220" fill="#8B5CF6" opacity="0.10" filter="url(#blurGlow)" />
  <circle cx="550" cy="300" r="160" fill="#00E5FF" opacity="0.06" filter="url(#blurGlow)" />
  <rect x="1.5" y="1.5" width="1097" height="597" rx="18.5" stroke="#131326" stroke-width="1.4" />

  <text x="60" y="62" font-size="10.5" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">2026 ACTIVITY OVERVIEW</text>
  <text x="60" y="102" font-size="44" font-weight="800" fill="#FFFFFF" class="font-sans">your activity overview.</text>
  <text x="1040" y="62" font-size="9.5" font-weight="700" fill="#94A3B8" class="font-mono" text-anchor="end">LAST REFRESHED ON {escape(updated_label)}</text>

  <!-- CARD 1: ANNUAL ENERGY -->
  <rect x="60" y="140" width="465" height="240" rx="26" fill="url(#cardBg)" stroke="url(#cardBorder)" stroke-width="1.5" />
  <text x="80" y="174" font-size="9" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">01 / ANNUAL ENERGY</text>
  <text x="80" y="224" font-size="48" font-weight="800" fill="#FFFFFF" class="font-sans">{format_number(contributions_365d)}</text>
  <text x="80" y="250" font-size="14" font-weight="600" fill="#94A3B8" class="font-sans">total annual contributions</text>

  <!-- Grid of sub-stats inside Card 1 -->
  <g transform="translate(80, 275)">
    <text x="0" y="15" font-size="9" font-weight="700" fill="#94A3B8" class="font-mono">ACTIVE DAYS</text>
    <text x="0" y="38" font-size="20" font-weight="800" fill="#FFFFFF" class="font-sans">{active_days}</text>

    <text x="180" y="15" font-size="9" font-weight="700" fill="#94A3B8" class="font-mono">PEAK DAY</text>
    <text x="180" y="38" font-size="20" font-weight="800" fill="#FFFFFF" class="font-sans">{peak_day}</text>

    <text x="0" y="65" font-size="9" font-weight="700" fill="#94A3B8" class="font-mono">REPOSITORIES</text>
    <text x="0" y="88" font-size="20" font-weight="800" fill="#FFFFFF" class="font-sans">{public_repos}</text>

    <text x="180" y="65" font-size="9" font-weight="700" fill="#94A3B8" class="font-mono">STARS EARNED</text>
    <text x="180" y="88" font-size="20" font-weight="800" fill="#FFFFFF" class="font-sans">{stars_earned}</text>
  </g>

  <!-- CARD 2: CODE FREQUENCIES -->
  <rect x="550" y="140" width="490" height="240" rx="26" fill="url(#cardBg)" stroke="url(#cardBorder)" stroke-width="1.5" />
  <text x="570" y="174" font-size="9" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">02 / CODE FREQUENCIES</text>
  {draw_spotify_language_mix(lang_breakdown)}

  <!-- CARD 3: ACTIVITY TEMPO -->
  <rect x="60" y="405" width="980" height="140" rx="26" fill="url(#cardBg)" stroke="url(#cardBorder)" stroke-width="1.5" />
  <text x="80" y="434" font-size="9" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">03 / ACTIVITY TEMPO</text>
  {draw_spotify_build_tempo(profile["weekly_totals"])}

  <!-- FOOTER -->
  <line x1="60" y1="565" x2="1040" y2="565" stroke="#131326" stroke-width="1" />
  <text x="1040" y="582" font-size="9.5" font-weight="800" fill="#8B5CF6" letter-spacing="1" class="font-mono" text-anchor="end">SHIPPED IN 2026</text>
</svg>
""".strip()


def build_wrapped_svg(profile: dict) -> str:
    now = current_datetime()
    updated_label = now.strftime("%d %b %Y").upper()

    lang_breakdown = process_code_activity_languages(adjust_languages_with_private_stack(profile.get("language_breakdown", [])))
    top_langs = [l["name"] for l in lang_breakdown[:3]]
    while len(top_langs) < 3:
        top_langs.append("TypeScript")

    # Dynamic Archetype Logic based on top language stack
    lang_set = {l.lower() for l in top_langs}
    if "java" in lang_set or "react" in lang_set:
        archetype_title = "The Architect"
        archetype_sub = "Full Stack Engineer"
        archetype_desc1 = "Designing reliable Spring Boot backend layers"
        archetype_desc2 = "integrated with React frontend nodes."
    elif "jupyter notebook" in lang_set or "python" in lang_set:
        archetype_title = "The Alchemist"
        archetype_sub = "Tenacious Creator"
        archetype_desc1 = "Melting analytical data models with clean"
        archetype_desc2 = "web structures to synthesize results."
    elif "typescript" in lang_set or "javascript" in lang_set:
        archetype_title = "The Artisan"
        archetype_sub = "Frontend Crafter"
        archetype_desc1 = "Sculpting fluid user interfaces and polished"
        archetype_desc2 = "interactive node structures."
    else:
        archetype_title = "The Pioneer"
        archetype_sub = "System Builder"
        archetype_desc1 = "Venturing into backend scripts and local"
        archetype_desc2 = "services for seamless system operations."

    # Dynamic Peak Rhythm Logic
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_counts = profile.get("weekday_counts", [10, 15, 25, 18, 12, 4, 2])
    max_idx = weekday_counts.index(max(weekday_counts))
    peak_weekday_name = weekday_names[max_idx]

    if max_idx in [0, 1]:
        rhythm_title = "Early Week Flow"
    elif max_idx in [2, 3]:
        rhythm_title = "Midweek Peak"
    elif max_idx == 4:
        rhythm_title = "Friday Release"
    else:
        rhythm_title = "Weekend Shift"

    max_count = max(weekday_counts) or 1
    bar_heights = [int((count / max_count) * 50) for count in weekday_counts]

    bar_elements = []
    colors = ["#3B82F6", "#3B82F6", "url(#bluePurpleGrad)", "#8B5CF6", "#8B5CF6", "#3B82F6", "#3B82F6"]
    opacities = ["0.4", "0.6", "1.0", "0.7", "0.5", "0.3", "0.2"]
    day_labels = ["M", "T", "W", "T", "F", "S", "S"]
    
    for i in range(7):
        h = max(2, bar_heights[i])
        y_val = 50 - h
        x_val = i * 20
        # Highlight actual peak day with bluePurpleGrad and 1.0 opacity
        if i == max_idx:
            color = "url(#bluePurpleGrad)"
            opacity = "1.0"
            text_fill = "#FFFFFF"
        else:
            color = colors[i]
            opacity = opacities[i]
            text_fill = "#94A3B8"
        bar_elements.append(
            f'<rect x="{x_val}" y="{y_val}" width="12" height="{h}" rx="3" fill="{color}" opacity="{opacity}" />'
            f'\n    <text x="{x_val + 6}" y="62" font-size="8" font-weight="700" fill="{text_fill}" text-anchor="middle" class="font-mono">{day_labels[i]}</text>'
        )
    bar_chart_svg = "\n    ".join(bar_elements)

    # Dynamic Top Coding Track Logic using real active repository name and language
    top_repo_name = profile.get("top_repo_name", "dspy")
    top_repo_lang = profile.get("top_repo_lang", "Python")
    track_name = profile.get("top_track_name")
    
    if not track_name:
        lang_exts = {
            "python": ".py",
            "jupyter notebook": ".ipynb",
            "java": ".java",
            "javascript": ".js",
            "typescript": ".ts",
            "html": ".html",
            "css": ".css",
            "go": ".go",
            "rust": ".rs",
        }
        ext = lang_exts.get(top_repo_lang.lower(), ".py")
        clean_repo = top_repo_name.lower().replace("-", "_").replace(" ", "_")
        if clean_repo == "dspy":
            track_name = "dspy_pipeline.py"
        elif clean_repo == "headroom":
            track_name = "headroom.js" if ext == ".js" else f"headroom{ext}"
        else:
            if len(clean_repo) > 20:
                track_name = f"main{ext}"
            else:
                track_name = f"{clean_repo}{ext}"

    # Calculate dynamic font size to prevent overlapping the cassette graphic
    track_len = len(track_name)
    if track_len <= 18:
        track_font_size = 24
    elif track_len <= 26:
        track_font_size = 18
    else:
        track_font_size = 15

    album_name = f"Repository: {top_repo_name}"

    total_contribs = profile.get("contributions_365d", 400)
    updates_count = max(42, int(total_contribs * 0.35))

    return f"""<svg width="1100" height="600" viewBox="0 0 1100 600" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">Developer Wrapped Report</title>
  <desc id="desc">A dark premium yearly developer stats report using only blue, purple, and white accents.</desc>
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&amp;family=Sora:wght@500;600;700;800&amp;display=swap');
      .font-sans {{ font-family: 'Sora', -apple-system, BlinkMacSystemFont, sans-serif; }}
      .font-mono {{ font-family: 'IBM Plex Mono', monospace; }}
    </style>
    <linearGradient id="pageBg" x1="0" y1="0" x2="1100" y2="600" gradientUnits="userSpaceOnUse">
      <stop stop-color="#040408" />
      <stop offset="0.55" stop-color="#07070F" />
      <stop offset="1" stop-color="#020205" />
    </linearGradient>
    <linearGradient id="cardBg" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="#0A0A15" />
      <stop offset="1" stop-color="#05050A" />
    </linearGradient>
    <linearGradient id="cardBorder" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="#3B82F6" stop-opacity="0.4" />
      <stop offset="0.5" stop-color="#8B5CF6" stop-opacity="0.25" />
      <stop offset="1" stop-color="#00E5FF" stop-opacity="0.1" />
    </linearGradient>
    <radialGradient id="auraGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#8B5CF6" stop-opacity="0.32" />
      <stop offset="70%" stop-color="#3B82F6" stop-opacity="0.08" />
      <stop offset="100%" stop-color="#0A0A15" stop-opacity="0" />
    </radialGradient>
    <linearGradient id="bluePurpleGrad" x1="0" y1="0" x2="1" y2="0">
      <stop stop-color="#3B82F6" />
      <stop offset="1" stop-color="#8B5CF6" />
    </linearGradient>
    <pattern id="gridPattern" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M 32 0 H 0 V 32" fill="none" stroke="#1E1B4B" stroke-width="1.2" stroke-opacity="0.22" />
    </pattern>
    <filter id="blurGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="32" />
    </filter>
  </defs>

  <rect width="1100" height="600" rx="20" fill="url(#pageBg)" />
  <rect width="1100" height="600" rx="20" fill="url(#gridPattern)" />
  <circle cx="160" cy="180" r="180" fill="#3B82F6" opacity="0.10" filter="url(#blurGlow)" />
  <circle cx="940" cy="420" r="220" fill="#8B5CF6" opacity="0.10" filter="url(#blurGlow)" />
  <circle cx="550" cy="300" r="160" fill="#00E5FF" opacity="0.06" filter="url(#blurGlow)" />
  <rect x="1.5" y="1.5" width="1097" height="597" rx="18.5" stroke="#131326" stroke-width="1.4" />

  <text x="60" y="62" font-size="10.5" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">2026 DEVELOPER WRAPPED</text>
  <text x="60" y="102" font-size="44" font-weight="800" fill="#FFFFFF" class="font-sans">your year in code.</text>
  <text x="1040" y="62" font-size="9.5" font-weight="700" fill="#94A3B8" class="font-mono" text-anchor="end">LAST REFRESHED ON {escape(updated_label)}</text>

  <!-- CARD 1: TOP LANGUAGES -->
  <rect x="60" y="140" width="310" height="240" rx="26" fill="url(#cardBg)" stroke="url(#cardBorder)" stroke-width="1.5" />
  <text x="80" y="174" font-size="9" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">01 / TOP LANGUAGES</text>
  
  <text x="80" y="218" font-size="13" font-weight="700" fill="#8B5CF6" class="font-mono">#1</text>
  <text x="105" y="218" font-size="16" font-weight="800" fill="#FFFFFF" class="font-sans">{escape(top_langs[0])}</text>
  
  <text x="80" y="258" font-size="13" font-weight="700" fill="#6366F1" class="font-mono">#2</text>
  <text x="105" y="258" font-size="16" font-weight="800" fill="#E2E8F0" class="font-sans">{escape(top_langs[1])}</text>
  
  <text x="80" y="298" font-size="13" font-weight="700" fill="#3B82F6" class="font-mono">#3</text>
  <text x="105" y="298" font-size="16" font-weight="800" fill="#E2E8F0" class="font-sans">{escape(top_langs[2])}</text>

  <!-- CARD 2: CODING AURA -->
  <rect x="395" y="140" width="310" height="240" rx="26" fill="url(#cardBg)" stroke="url(#cardBorder)" stroke-width="1.5" />
  <rect x="396.5" y="141.5" width="307" height="237" rx="24.5" fill="url(#auraGlow)" />
  <text x="415" y="174" font-size="9" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">02 / CODING AURA</text>
  <text x="415" y="230" font-size="28" font-weight="800" fill="#FFFFFF" class="font-sans">Deep Sync &amp;</text>
  <text x="415" y="265" font-size="28" font-weight="800" fill="#8B5CF6" class="font-sans">Flow State</text>
  <text x="415" y="305" font-size="11" font-weight="600" fill="#94A3B8" class="font-sans">responsive interfaces &amp; backend streams</text>

  <!-- CARD 3: DEVELOPER STYLE -->
  <rect x="730" y="140" width="310" height="240" rx="26" fill="url(#cardBg)" stroke="url(#cardBorder)" stroke-width="1.5" />
  <text x="750" y="174" font-size="9" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">03 / DEVELOPER STYLE</text>
  <text x="750" y="230" font-size="32" font-weight="800" fill="#FFFFFF" class="font-sans">{escape(archetype_title)}</text>
  <text x="750" y="260" font-size="12" font-weight="600" fill="#3B82F6" class="font-sans">{escape(archetype_sub)}</text>
  <text x="750" y="295" font-size="12" font-weight="500" fill="#94A3B8" class="font-sans">
    <tspan x="750" dy="0">{escape(archetype_desc1)}</tspan>
    <tspan x="750" dy="18">{escape(archetype_desc2)}</tspan>
  </text>

  <!-- CARD 4: PEAK RHYTHM -->
  <rect x="60" y="405" width="465" height="140" rx="26" fill="url(#cardBg)" stroke="url(#cardBorder)" stroke-width="1.5" />
  <text x="80" y="434" font-size="9" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">04 / PEAK RHYTHM</text>
  
  <text x="80" y="468" font-size="9.5" font-weight="700" fill="#94A3B8" class="font-mono">WEEKLY MOMENTUM</text>
  <text x="80" y="502" font-size="28" font-weight="800" fill="#FFFFFF" class="font-sans">{escape(rhythm_title)}</text>
  <text x="80" y="522" font-size="11" font-weight="600" fill="#3B82F6" class="font-sans">{escape(peak_weekday_name)} is peak commit time</text>

  <g transform="translate(340, 435)">
    {bar_chart_svg}
  </g>

  <!-- CARD 5: TOP CODING TRACK -->
  <rect x="550" y="405" width="490" height="140" rx="26" fill="url(#cardBg)" stroke="url(#cardBorder)" stroke-width="1.5" />
  <text x="580" y="434" font-size="9" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">05 / TOP CODING TRACK</text>

  <text x="580" y="465" font-size="{track_font_size}" font-weight="800" fill="#FFFFFF" class="font-sans">{escape(track_name)}</text>
  <text x="580" y="487" font-size="11" font-weight="600" fill="#8B5CF6" class="font-sans">{updates_count} updates | {escape(album_name)}</text>

  <!-- Playback Controls -->
  <g transform="translate(895, 475)">
    <!-- Shuffle -->
    <path d="M -44 -4 L -40 -4 L -34 4 L -30 4" stroke="#94A3B8" stroke-width="1.2" stroke-linecap="round" />
    <path d="M -44 4 L -40 4 L -37 1 M -33 -3 L -30 -4" stroke="#94A3B8" stroke-width="1.2" stroke-linecap="round" />
    <path d="M -32 2 L -30 4 L -32 6" fill="none" stroke="#94A3B8" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" />
    <path d="M -32 -6 L -30 -4 L -32 -2" fill="none" stroke="#94A3B8" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" />

    <!-- Prev -->
    <path d="M -20 0 L -12 6 L -12 -6 Z" fill="#94A3B8" />
    <rect x="-22" y="-6" width="2" height="12" fill="#94A3B8" />

    <!-- Play/Pause -->
    <circle cx="2" cy="0" r="13" fill="#FFFFFF" />
    <rect x="-2" y="-4.5" width="2.2" height="9" fill="#040408" />
    <rect x="3.2" y="-4.5" width="2.2" height="9" fill="#040408" />

    <!-- Next -->
    <path d="M 18 0 L 26 6 L 26 -6 Z" fill="#94A3B8" />
    <rect x="26" y="-6" width="2" height="12" fill="#94A3B8" />

    <!-- Repeat -->
    <path d="M 38 -4 A 5 5 0 1 1 38 4" fill="none" stroke="#94A3B8" stroke-width="1.2" stroke-linecap="round" />
    <path d="M 36 -6 L 39 -4 L 36 -2" fill="none" stroke="#94A3B8" stroke-width="1.2" stroke-linecap="round" />
  </g>

  <!-- Heart/Like Icon -->
  <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" fill="#8B5CF6" fill-opacity="0.85" transform="translate(805, 473) scale(0.65)" />

  <!-- Progress Bar & Sound Wave Equalizer -->
  <g transform="translate(580, 514)">
    <rect x="0" y="0" width="280" height="4" rx="2" fill="#131326" />
    <rect x="0" y="0" width="190" height="4" rx="2" fill="url(#bluePurpleGrad)" />
    <circle cx="190" cy="2" r="4.5" fill="#FFFFFF" />
  </g>

  <!-- Sound Equalizer Graphic overlay -->
  <g fill-opacity="0.75" transform="translate(780, 498)">
    <rect x="0" y="4" width="2" height="8" rx="1" fill="#8B5CF6" />
    <rect x="4" y="0" width="2" height="12" rx="1" fill="#3B82F6" />
    <rect x="8" y="7" width="2" height="5" rx="1" fill="#00E5FF" />
    <rect x="12" y="2" width="2" height="10" rx="1" fill="#8B5CF6" />
    <rect x="16" y="9" width="2" height="3" rx="1" fill="#3B82F6" />
    <rect x="20" y="5" width="2" height="7" rx="1" fill="#00E5FF" />
    <rect x="24" y="1" width="2" height="11" rx="1" fill="#8B5CF6" />
    <rect x="28" y="8" width="2" height="4" rx="1" fill="#3B82F6" />
  </g>

  <!-- Turntable Deck Aura Glow -->
  <circle cx="980" cy="475" r="46" fill="url(#auraGlow)" opacity="0.6" />

  <!-- Spinning Vinyl Record -->
  <g transform="translate(980, 475)">
    <circle cx="0" cy="0" r="30" fill="#0D0D18" stroke="#1E1E38" stroke-width="1.5" />
    <circle cx="0" cy="0" r="24" fill="none" stroke="#16162B" stroke-width="1" />
    <circle cx="0" cy="0" r="18" fill="none" stroke="#16162B" stroke-width="1" />
    <circle cx="0" cy="0" r="12" fill="none" stroke="#16162B" stroke-width="1" />
    <circle cx="0" cy="0" r="9" fill="#8B5CF6" />
    <circle cx="0" cy="0" r="2.5" fill="#040408" />
  </g>

  <!-- FOOTER -->
  <line x1="60" y1="565" x2="1040" y2="565" stroke="#131326" stroke-width="1" />
  <text x="1040" y="582" font-size="9.5" font-weight="800" fill="#8B5CF6" letter-spacing="1" class="font-mono" text-anchor="end">SHIPPED IN 2026</text>
</svg>"""


def build_build_svg(profile: dict) -> str:
    now = current_datetime()
    updated_label = now.strftime("%d %b %Y").upper()

    track_name = "build_pipeline_run.sh"
    top_repo_name = profile.get("top_repo_name", "TransitPulse")
    album_name = f"Active Project: {top_repo_name}"

    track_len = len(track_name)
    if track_len <= 20:
        track_font_size = 20
    elif track_len <= 28:
        track_font_size = 17
    else:
        track_font_size = 14

    private_commits = profile.get("private_contributions", profile.get("restricted_contributions", 0))
    if private_commits == 0:
        private_commits = 842
    public_commits = profile.get("public_contributions", profile.get("contributions_365d", 0))
    total_commits = profile.get("contributions_365d", public_commits + private_commits)
    private_repos_count = profile.get("private_repos", 0)

    lang_breakdown = adjust_languages_with_private_stack(profile.get("language_breakdown", []))

    # Categorize languages into stacks dynamically
    frontend_languages = []
    backend_languages = []
    data_languages = []

    frontend_percent = 0.0
    backend_percent = 0.0
    data_percent = 0.0

    for lang in lang_breakdown:
        name = lang["name"]
        pct = lang["percent"]
        name_lower = name.lower()
        if name_lower in ["react", "typescript", "html", "css", "javascript", "vue", "svelte"]:
            frontend_languages.append(name)
            frontend_percent += pct
        elif name_lower in ["java", "python", "go", "rust", "c++", "c#", "php", "ruby"]:
            backend_languages.append(name)
            backend_percent += pct
        else:
            data_languages.append(name)
            data_percent += pct

    # Scale percentages to sum to 100%
    total_pct = frontend_percent + backend_percent + data_percent
    if total_pct > 0:
        frontend_percent = round((frontend_percent / total_pct) * 100, 1)
        backend_percent = round((backend_percent / total_pct) * 100, 1)
        data_percent = round(100.0 - frontend_percent - backend_percent, 1)
    else:
        frontend_percent, backend_percent, data_percent = 25.0, 55.0, 20.0

    frontend_header = "React + Next.js"
    backend_header = "Java + Node.js"
    data_header = "SQL + Mongo"

    # Dynamic Card 4 labels from real profile data
    top_repo_lang = profile.get("top_repo_lang", "Java")
    deploy_label = f"Shipping: {top_repo_name} via {top_repo_lang}"
    if len(deploy_label) > 34:
        deploy_label = f"Shipping via {top_repo_lang} runtime"
    badge_lang = top_repo_lang.upper()[:12]

    # Strictly private repo for Card 4 Column 1 — never a public fallback
    pvt_card_name = profile.get("private_repo_name", "") or "Obsidian"
    pvt_card_lang = profile.get("private_repo_lang", "") or "Java"
    pvt_card_badge = pvt_card_lang.upper()[:12]

    # Pre-compute badge geometry for Card 4 Column 1
    badge1_w = min(len(pvt_card_badge) * 7 + 16, 80)
    badge1_cx = 90 + badge1_w // 2
    badge2_x = 90 + badge1_w + 8
    badge2_cx = badge2_x + 32

    # Private stats for Card 4 Column 2 — live from GitHub Action token sync
    private_commits_val = profile.get("private_contributions", profile.get("restricted_contributions", 0))
    total_commits_val = profile.get("contributions_365d", 0) or private_commits_val
    pvt_ratio = min(private_commits_val / max(total_commits_val, 1), 1.0)
    pvt_bar_fill = int(pvt_ratio * 440)
    pvt_pct = int(pvt_ratio * 100)
    pvt_label_x = 530 + len(format_number(private_commits_val)) * 16 + 6

    return f"""<svg width="1100" height="600" viewBox="0 0 1100 600" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">Tech Stack Mix</title>
  <desc id="desc">A presentation of the developer tech stack using blue, purple, and white accents.</desc>
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&amp;family=Sora:wght@500;600;700;800&amp;display=swap');
      .font-sans {{ font-family: 'Sora', -apple-system, BlinkMacSystemFont, sans-serif; }}
      .font-mono {{ font-family: 'IBM Plex Mono', monospace; }}
    </style>
    <linearGradient id="pageBg" x1="0" y1="0" x2="1100" y2="600" gradientUnits="userSpaceOnUse">
      <stop stop-color="#040408" />
      <stop offset="0.55" stop-color="#07070F" />
      <stop offset="1" stop-color="#020205" />
    </linearGradient>
    <linearGradient id="cardBg" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="#0A0A15" />
      <stop offset="1" stop-color="#05050A" />
    </linearGradient>
    <linearGradient id="cardBorder" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="#3B82F6" stop-opacity="0.4" />
      <stop offset="0.5" stop-color="#8B5CF6" stop-opacity="0.25" />
      <stop offset="1" stop-color="#00E5FF" stop-opacity="0.1" />
    </linearGradient>
    <linearGradient id="playProgress" x1="0" y1="0" x2="1" y2="0">
      <stop stop-color="#3B82F6" />
      <stop offset="1" stop-color="#8B5CF6" />
    </linearGradient>
    <pattern id="gridPattern" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M 32 0 H 0 V 32" fill="none" stroke="#1E1B4B" stroke-width="1.2" stroke-opacity="0.22" />
    </pattern>
    <filter id="blurGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="32" />
    </filter>
  </defs>

  <rect width="1100" height="600" rx="20" fill="url(#pageBg)" />
  <rect width="1100" height="600" rx="20" fill="url(#gridPattern)" />
  <circle cx="160" cy="180" r="180" fill="#3B82F6" opacity="0.10" filter="url(#blurGlow)" />
  <circle cx="940" cy="420" r="220" fill="#8B5CF6" opacity="0.10" filter="url(#blurGlow)" />
  <circle cx="550" cy="300" r="160" fill="#00E5FF" opacity="0.06" filter="url(#blurGlow)" />
  <rect x="1.5" y="1.5" width="1097" height="597" rx="18.5" stroke="#131326" stroke-width="1.4" />

  <text x="60" y="62" font-size="10.5" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">2026 WORKSPACE TELEMETRY</text>
  <text x="60" y="102" font-size="44" font-weight="800" fill="#FFFFFF" class="font-sans">your tech stack mix.</text>
  <text x="1040" y="62" font-size="9.5" font-weight="700" fill="#94A3B8" class="font-mono" text-anchor="end">LAST REFRESHED ON {escape(updated_label)}</text>

  <!-- CARD 1: FRONTEND -->
  <rect x="60" y="160" width="310" height="230" rx="26" fill="url(#cardBg)" stroke="url(#cardBorder)" stroke-width="1.5" />
  <text x="90" y="194" font-size="9" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">01 / UI &amp; LAYOUTS</text>
  <text x="90" y="240" font-size="30" font-weight="800" fill="#FFFFFF" class="font-sans">{escape(frontend_header)}</text>
  <text x="90" y="266" font-size="11.5" font-weight="700" fill="#8B5CF6" class="font-mono" letter-spacing="1">FRONTEND CORE | {frontend_percent}%</text>
  <text x="90" y="302" font-size="12" font-weight="500" fill="#94A3B8" class="font-sans">
    <tspan x="90" dy="0" fill="#F1F5F9">• React &amp; HTML components</tspan>
    <tspan x="90" dy="22" fill="#94A3B8">• Responsive styling layout</tspan>
    <tspan x="90" dy="22" fill="#94A3B8">• Interactive user interfaces</tspan>
  </text>

  <!-- CARD 2: BACKEND -->
  <rect x="395" y="160" width="310" height="230" rx="26" fill="url(#cardBg)" stroke="url(#cardBorder)" stroke-width="1.5" />
  <text x="425" y="194" font-size="9" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">02 / SERVICES &amp; ROUTING</text>
  <text x="425" y="240" font-size="30" font-weight="800" fill="#FFFFFF" class="font-sans">{escape(backend_header)}</text>
  <text x="425" y="266" font-size="11.5" font-weight="700" fill="#8B5CF6" class="font-mono" letter-spacing="1">BACKEND RUNTIME | {backend_percent}%</text>
  <text x="425" y="302" font-size="12" font-weight="500" fill="#94A3B8" class="font-sans">
    <tspan x="425" dy="0" fill="#F1F5F9">• Spring Boot microservices</tspan>
    <tspan x="425" dy="22" fill="#94A3B8">• Apache Kafka integration</tspan>
    <tspan x="425" dy="22" fill="#94A3B8">• RESTful API architectures</tspan>
  </text>

  <!-- CARD 3: OPERATIONS -->
  <rect x="730" y="160" width="310" height="230" rx="26" fill="url(#cardBg)" stroke="url(#cardBorder)" stroke-width="1.5" />
  <text x="760" y="194" font-size="9" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">03 / STABILIZATION &amp; DATA</text>
  <text x="760" y="240" font-size="30" font-weight="800" fill="#FFFFFF" class="font-sans">{escape(data_header)}</text>
  <text x="760" y="266" font-size="11.5" font-weight="700" fill="#8B5CF6" class="font-mono" letter-spacing="1">DATA &amp; DELIVERY | {data_percent}%</text>
  <text x="760" y="302" font-size="12" font-weight="500" fill="#94A3B8" class="font-sans">
    <tspan x="760" dy="0" fill="#F1F5F9">• Jupyter Notebook analysis</tspan>
    <tspan x="760" dy="22" fill="#94A3B8">• SQL database integrations</tspan>
    <tspan x="760" dy="22" fill="#94A3B8">• Docker containerization</tspan>
  </text>

  <!-- CARD 4: PRIVATE WORKSPACE CONSOLE -->
  <rect x="60" y="415" width="980" height="125" rx="26" fill="url(#cardBg)" stroke="url(#cardBorder)" stroke-width="1.5" />

  <!-- Subtle vertical divider -->
  <line x1="490" y1="432" x2="490" y2="528" stroke="#1E1B4B" stroke-width="1" stroke-opacity="0.6" />

  <!-- COLUMN 1: LOCKED IN — active private repo -->

  <!-- Pulsing lock aura -->
  <circle cx="96" cy="447" r="5" fill="#8B5CF6" opacity="0.2">
    <animate attributeName="r" values="5;10;5" dur="2.5s" repeatCount="indefinite" />
    <animate attributeName="opacity" values="0.2;0;0.2" dur="2.5s" repeatCount="indefinite" />
  </circle>
  <circle cx="96" cy="447" r="3.5" fill="#8B5CF6" />

  <!-- LOCKED IN pill -->
  <rect x="105" y="440" width="66" height="14" rx="7" fill="#8B5CF6" fill-opacity="0.15" stroke="#8B5CF6" stroke-opacity="0.5" stroke-width="1" />
  <text x="138" y="450.5" font-size="7" font-weight="800" fill="#8B5CF6" letter-spacing="1.2" class="font-mono" text-anchor="middle">LOCKED IN</text>

  <text x="178" y="450" font-size="9" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">/ PRIVATE REPO</text>

  <!-- Private repo name -->
  <text x="90" y="477" font-size="22" font-weight="800" fill="#FFFFFF" class="font-sans">{escape(pvt_card_name)}</text>

  <!-- Language badge -->
  <rect x="90" y="490" width="{badge1_w}" height="15" rx="7" fill="#3B82F6" fill-opacity="0.15" stroke="#3B82F6" stroke-opacity="0.4" stroke-width="1" />
  <text x="{badge1_cx}" y="500.5" font-size="7.5" font-weight="800" fill="#3B82F6" letter-spacing="1" class="font-mono" text-anchor="middle">{escape(pvt_card_badge)}</text>

  <!-- PRIVATE badge -->
  <rect x="{badge2_x}" y="490" width="52" height="15" rx="7" fill="#8B5CF6" fill-opacity="0.15" stroke="#8B5CF6" stroke-opacity="0.4" stroke-width="1" />
  <text x="{badge2_cx}" y="500.5" font-size="7.5" font-weight="800" fill="#8B5CF6" letter-spacing="1" class="font-mono" text-anchor="middle">PRIVATE</text>

  <!-- COLUMN 2: PRIVATE GRIND — real pvt commit stats -->

  <text x="530" y="450" font-size="9" font-weight="800" fill="#8B5CF6" letter-spacing="2" class="font-mono">PRIVATE GRIND</text>

  <!-- Hero number: private commits -->
  <text x="530" y="480" font-size="26" font-weight="800" fill="#FFFFFF" class="font-sans">{format_number(private_commits_val)}</text>
  <text x="{pvt_label_x}" y="480" font-size="11" font-weight="600" fill="#8B5CF6" class="font-mono">pvt commits</text>

  <!-- Pvt vs total ratio bar -->
  <rect x="530" y="488" width="440" height="5" rx="2.5" fill="#131326" />
  <rect x="530" y="488" width="{pvt_bar_fill}" height="5" rx="2.5" fill="url(#playProgress)" />

  <!-- Ratio micro-text -->
  <text x="530" y="508" font-size="10" font-weight="600" fill="#94A3B8" class="font-mono">deep in {escape(pvt_card_name)} · {pvt_pct}% of total work</text>

  <!-- FOOTER -->
  <line x1="60" y1="565" x2="1040" y2="565" stroke="#131326" stroke-width="1" />
  <text x="1040" y="582" font-size="9.5" font-weight="800" fill="#8B5CF6" letter-spacing="1" class="font-mono" text-anchor="end">SHIPPED IN 2026</text>
</svg>"""


def write_outputs(profile: dict) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text(build_svg(profile), encoding="utf-8")
    WRAPPED_SVG_PATH.write_text(build_wrapped_svg(profile), encoding="utf-8")
    BUILD_SVG_PATH.write_text(build_build_svg(profile), encoding="utf-8")

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
        r'src="\./assets/profile-overview\.svg(?:\?[^"]+)?"',
        f'src="./assets/profile-overview.svg?t={timestamp}"',
        content
    )
    new_content = re.sub(
        r'src="\./assets/profile-build\.svg(?:\?[^"]+)?"',
        f'src="./assets/profile-build.svg?t={timestamp}"',
        new_content
    )
    new_content = re.sub(
        r'src="\./assets/profile-wrapped\.svg(?:\?[^"]+)?"',
        f'src="./assets/profile-wrapped.svg?t={timestamp}"',
        new_content
    )
    readme_path.write_text(new_content, encoding="utf-8")


def main() -> None:
    profile = fetch_profile_data()
    write_outputs(profile)
    update_readme_cache_buster()


if __name__ == "__main__":
    main()
