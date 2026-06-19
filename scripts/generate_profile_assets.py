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
JSON_PATH = ASSETS_DIR / "profile-data.json"

USERNAME = os.getenv("PROFILE_USERNAME", "Haritha-Sivasankaran")
TIMEZONE_NAME = os.getenv("PROFILE_TIMEZONE", "Asia/Calcutta")
TOKEN = os.getenv("PROFILE_STATS_TOKEN", "").strip()

GRAPHQL_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    login
    name
    createdAt
    repositories(
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
    "HTML": "#F97316",
    "JavaScript": "#FACC15",
    "TypeScript": "#38BDF8",
    "CSS": "#7C3AED",
    "Java": "#FB923C",
    "Jupyter Notebook": "#F59E0B",
    "MySQL": "#22C55E",
}


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
    repositories = user["repositories"]["nodes"]

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

    language_counts = Counter(
        repo["primaryLanguage"]["name"]
        for repo in repositories
        if repo.get("primaryLanguage") and repo["primaryLanguage"].get("name")
    )

    return {
        "source_mode": "github-graphql",
        "username": user["login"],
        "name": user.get("name") or user["login"],
        "joined_year": date.fromisoformat(user["createdAt"][:10]).year,
        "public_repos": user["repositories"]["totalCount"],
        "stars_earned": sum(repo["stargazerCount"] for repo in repositories),
        "contributions_365d": user["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "active_days": sum(1 for day in contribution_days if day["contributionCount"] > 0),
        "peak_day": max((day["contributionCount"] for day in contribution_days), default=0),
        "restricted_contributions": user["contributionsCollection"]["restrictedContributionsCount"],
        "has_restricted_contributions": user["contributionsCollection"]["hasAnyRestrictedContributions"],
        "weekly_totals": weekly_totals[-12:],
        "language_counts": language_counts,
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

    language_counts = Counter(
        repo["language"]
        for repo in repos
        if not repo.get("fork") and repo.get("language")
    )

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
        "language_counts": language_counts,
    }


def fetch_profile_data() -> dict:
    today = current_datetime().date()
    from_date = today - timedelta(days=364)

    if TOKEN:
        try:
            return fetch_graphql_profile(USERNAME, from_date, today, TOKEN)
        except (HTTPError, URLError, RuntimeError, KeyError, ValueError):
            pass

    return fetch_public_profile(USERNAME)


def format_number(value: int) -> str:
    return f"{value:,}"


def draw_metric_card(x: int, y: int, label: str, value: str, accent: str, note: str = "") -> str:
    note_text = (
        f'<text x="{x + 22}" y="{y + 96}" font-size="13" fill="#94A3B8">{escape(note)}</text>'
        if note
        else ""
    )
    return f"""
    <g>
      <rect x="{x}" y="{y}" width="220" height="112" rx="22" fill="#101827" stroke="#1E293B" />
      <rect x="{x + 18}" y="{y + 18}" width="8" height="32" rx="4" fill="{accent}" />
      <text x="{x + 38}" y="{y + 36}" font-size="13" fill="#94A3B8" letter-spacing="0.4">{escape(label.upper())}</text>
      <text x="{x + 22}" y="{y + 74}" font-size="34" font-weight="700" fill="#F8FAFC">{escape(value)}</text>
      {note_text}
    </g>
    """.strip()


def draw_language_rows(language_counts: Counter) -> str:
    if not language_counts:
        return """
        <text x="592" y="178" font-size="16" fill="#94A3B8">No public repo language data yet.</text>
        """.strip()

    top_languages = language_counts.most_common(4)
    max_count = max(count for _, count in top_languages) or 1
    rows = []
    for index, (language, count) in enumerate(top_languages):
        y = 180 + index * 46
        bar_width = int(240 * (count / max_count))
        accent = LANGUAGE_COLORS.get(language, "#94A3B8")
        repo_label = "repo" if count == 1 else "repos"
        rows.append(
            f"""
            <g>
              <circle cx="604" cy="{y - 6}" r="7" fill="{accent}" />
              <text x="620" y="{y}" font-size="18" font-weight="600" fill="#E2E8F0">{escape(language)}</text>
              <text x="940" y="{y}" font-size="15" text-anchor="end" fill="#94A3B8">{count} {repo_label}</text>
              <rect x="620" y="{y + 12}" width="240" height="8" rx="4" fill="#172033" />
              <rect x="620" y="{y + 12}" width="{bar_width}" height="8" rx="4" fill="{accent}" />
            </g>
            """.strip()
        )
    return "\n".join(rows)


def draw_weekly_chart(weekly_totals: list[dict]) -> str:
    if not weekly_totals:
        return """
        <text x="56" y="446" font-size="16" fill="#94A3B8">Contribution chart will appear after your first tracked activity.</text>
        """.strip()

    chart = []
    chart_left = 64
    chart_bottom = 482
    bar_width = 58
    gap = 22
    bar_max_height = 116
    totals = [item["total"] for item in weekly_totals]
    max_total = max(totals) or 1
    accents = ["#2563EB", "#38BDF8", "#F97316", "#EC4899"]

    for index, week in enumerate(weekly_totals):
        x = chart_left + index * (bar_width + gap)
        height = max(8, int((week["total"] / max_total) * bar_max_height)) if week["total"] else 8
        y = chart_bottom - height
        color = accents[index % len(accents)]
        label_date = date.fromisoformat(week["start"])
        show_month = index in {0, 4, 8, len(weekly_totals) - 1}
        month_label = label_date.strftime("%b") if show_month else ""
        value_label = (
            f'<text x="{x + (bar_width / 2)}" y="{y - 10}" font-size="13" text-anchor="middle" fill="#CBD5E1">{week["total"]}</text>'
            if week["total"] > 0
            else ""
        )
        chart.append(
            f"""
            <g>
              <rect x="{x}" y="{y}" width="{bar_width}" height="{height}" rx="18" fill="{color}" opacity="0.95" />
              {value_label}
              <text x="{x + (bar_width / 2)}" y="508" font-size="12" text-anchor="middle" fill="#64748B">{month_label}</text>
            </g>
            """.strip()
        )

    return "\n".join(chart)


def build_svg(profile: dict) -> str:
    now = current_datetime()
    cards = [
        draw_metric_card(
            44,
            112,
            "365d contributions",
            format_number(profile["contributions_365d"]),
            "#2563EB",
            "actual GitHub contribution calendar",
        ),
        draw_metric_card(
            278,
            112,
            "active days",
            format_number(profile["active_days"]),
            "#EC4899",
            "days with at least one contribution",
        ),
        draw_metric_card(
            44,
            242,
            "public repos",
            format_number(profile["public_repos"]),
            "#F97316",
            f"building since {profile['joined_year']}",
        ),
        draw_metric_card(
            278,
            242,
            "stars earned",
            format_number(profile["stars_earned"]),
            "#7C3AED",
            f"peak day: {format_number(profile['peak_day'])}",
        ),
    ]

    source_tag = "GitHub GraphQL live sync" if profile["source_mode"] == "github-graphql" else "GitHub public sync"
    updated_label = now.strftime("%d %b %Y | %I:%M %p")

    return f"""<svg width="1100" height="540" viewBox="0 0 1100 540" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">Live GitHub profile overview for {escape(profile["name"])}</title>
  <desc id="desc">Automatically refreshed GitHub stats showing contributions, repositories, stars, languages, and recent weekly activity.</desc>
  <defs>
    <linearGradient id="hero" x1="40" y1="24" x2="1060" y2="520" gradientUnits="userSpaceOnUse">
      <stop stop-color="#0F172A" />
      <stop offset="0.5" stop-color="#111827" />
      <stop offset="1" stop-color="#050816" />
    </linearGradient>
  </defs>

  <rect x="10" y="10" width="1080" height="520" rx="30" fill="url(#hero)" stroke="#1E293B" />
  <rect x="38" y="34" width="132" height="34" rx="17" fill="#111C31" stroke="#22304A" />
  <text x="60" y="56" font-size="13" font-weight="700" fill="#60A5FA" letter-spacing="1.4">DEV PULSE</text>
  <text x="38" y="94" font-size="36" font-weight="700" fill="#F8FAFC">{escape(profile["name"])}</text>
  <text x="38" y="118" font-size="16" fill="#94A3B8">full-stack energy, live GitHub signal, zero mock stats</text>

  <rect x="822" y="34" width="230" height="34" rx="17" fill="#111C31" stroke="#22304A" />
  <text x="842" y="56" font-size="12" font-weight="600" fill="#E2E8F0">{escape(source_tag)}</text>
  <text x="822" y="92" font-size="13" fill="#64748B">last refresh: {escape(updated_label)}</text>

  {"".join(cards)}

  <rect x="546" y="112" width="510" height="242" rx="26" fill="#101827" stroke="#1E293B" />
  <text x="592" y="148" font-size="24" font-weight="700" fill="#F8FAFC">Stack Snapshot</text>
  <text x="592" y="170" font-size="14" fill="#94A3B8">based on your public repos, not a guessed tech stack</text>
  {draw_language_rows(profile["language_counts"])}

  <rect x="38" y="382" width="1018" height="118" rx="26" fill="#101827" stroke="#1E293B" />
  <text x="56" y="418" font-size="24" font-weight="700" fill="#F8FAFC">Shipping Rhythm</text>
  <text x="56" y="440" font-size="14" fill="#94A3B8">real weekly contributions from the last 12 weeks</text>
  <line x1="56" y1="482" x2="1028" y2="482" stroke="#1E293B" />
  {draw_weekly_chart(profile["weekly_totals"])}
</svg>
""".strip()


def write_outputs(profile: dict) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text(build_svg(profile), encoding="utf-8")

    metadata = {
        "username": profile["username"],
        "name": profile["name"],
        "source_mode": profile["source_mode"],
        "generated_at": current_datetime().isoformat(),
        "timezone": TIMEZONE_NAME,
        "contributions_365d": profile["contributions_365d"],
        "active_days": profile["active_days"],
        "peak_day": profile["peak_day"],
        "public_repos": profile["public_repos"],
        "stars_earned": profile["stars_earned"],
        "joined_year": profile["joined_year"],
        "has_restricted_contributions": profile["has_restricted_contributions"],
        "restricted_contributions": profile["restricted_contributions"],
        "language_counts": dict(profile["language_counts"]),
        "weekly_totals": profile["weekly_totals"],
    }
    JSON_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main() -> None:
    profile = fetch_profile_data()
    write_outputs(profile)


if __name__ == "__main__":
    main()
