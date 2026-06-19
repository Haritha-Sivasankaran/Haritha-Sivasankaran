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


def fetch_public_repo_language_breakdown(login: str, token: str | None = None) -> list[dict]:
    repos = request_json(
        f"https://api.github.com/users/{login}/repos?per_page=100&type=owner&sort=updated",
        token=token,
    )

    totals = Counter()
    for repo in repos:
        if repo.get("fork"):
            continue
        repo_languages = request_json(repo["languages_url"], token=token)
        for language, byte_count in repo_languages.items():
            totals[language] += byte_count

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
    repositories = user["repositories"]["nodes"]
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
        "language_breakdown": language_breakdown,
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


def draw_micro_stat(x: int, y: int, label: str, value: str, accent: str) -> str:
    return f"""
    <g>
      <rect x="{x}" y="{y}" width="92" height="56" rx="18" fill="#111B2E" />
      <rect x="{x + 12}" y="{y + 12}" width="6" height="30" rx="3" fill="{accent}" />
      <text x="{x + 28}" y="{y + 23}" font-size="11" font-weight="600" fill="#94A3B8" letter-spacing="0.6">{escape(label.upper())}</text>
      <text x="{x + 28}" y="{y + 44}" font-size="24" font-weight="700" fill="#F8FAFC">{escape(value)}</text>
    </g>
    """.strip()


def draw_language_mix(language_breakdown: list[dict]) -> str:
    if not language_breakdown:
        return """
        <text x="524" y="256" font-size="16" fill="#94A3B8">No public repo language data yet.</text>
        """.strip()

    breakdown_total = sum(item["percent"] for item in language_breakdown) or 1
    bar_x = 524
    bar_y = 246
    bar_width = 476
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

    segments = [f'<rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="14" rx="7" fill="#172033" />']
    for item, width in zip(language_breakdown, segment_widths):
        accent = LANGUAGE_COLORS.get(item["name"], "#94A3B8")
        segments.append(
            f'<rect x="{current_x}" y="{bar_y}" width="{width}" height="14" rx="7" fill="{accent}" />'
        )
        current_x += width

    tiles = []
    tile_width = 166
    tile_height = 38
    gap_x = 12
    gap_y = 12
    start_y = 280

    for index, item in enumerate(language_breakdown):
        column = index % 3
        row = index // 3
        x = 524 + column * (tile_width + gap_x)
        y = start_y + row * (tile_height + gap_y)
        accent = LANGUAGE_COLORS.get(item["name"], "#94A3B8")
        tiles.append(
            f"""
            <g>
              <rect x="{x}" y="{y}" width="{tile_width}" height="{tile_height}" rx="16" fill="#111B2E" />
              <rect x="{x + 12}" y="{y + 10}" width="7" height="18" rx="3" fill="{accent}" />
              <text x="{x + 29}" y="{y + 16}" font-size="10.5" font-weight="600" fill="#94A3B8">{escape(item["name"])}</text>
              <text x="{x + 29}" y="{y + 32}" font-size="19" font-weight="700" fill="#F8FAFC">{item["percent"]:.2f}%</text>
            </g>
            """.strip()
        )

    return "\n".join([*segments, *tiles])


def draw_build_tempo(weekly_totals: list[dict]) -> str:
    if not weekly_totals:
        return """
        <text x="84" y="474" font-size="16" fill="#94A3B8">Tempo chart appears after tracked contribution activity.</text>
        """.strip()

    chart_left = 84
    chart_right = 1016
    chart_top = 452
    chart_bottom = 500
    chart_height = chart_bottom - chart_top
    totals = [item["total"] for item in weekly_totals]
    max_total = max(totals) or 1
    step = (chart_right - chart_left) / (len(weekly_totals) - 1) if len(weekly_totals) > 1 else 0

    points: list[tuple[float, float, int, str]] = []
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
    month_indices = {0, 4, 8, len(points) - 1}
    for index, (x, y, total, start_date) in enumerate(points):
        accent = "#F97316" if total == max_total and total > 0 else "#60A5FA"
        labels.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.5" fill="#0F172A" stroke="{accent}" stroke-width="3" />'
        )
        if total > 0:
            labels.append(
                f'<text x="{x:.2f}" y="{y - 12:.2f}" font-size="11" font-weight="600" text-anchor="middle" fill="#E2E8F0">{total}</text>'
            )
        if index in month_indices:
            labels.append(
                f'<text x="{x:.2f}" y="520" font-size="12" text-anchor="middle" fill="#64748B">{date.fromisoformat(start_date).strftime("%b")}</text>'
            )

    grid = [
        '<line x1="84" y1="500" x2="1016" y2="500" stroke="#1E293B" />',
        '<line x1="84" y1="476" x2="1016" y2="476" stroke="#142033" />',
        '<line x1="84" y1="452" x2="1016" y2="452" stroke="#142033" />',
    ]

    return "\n".join(
        [
            *grid,
            f'<path d="{area_path}" fill="url(#tempoFill)" opacity="0.9" />',
            f'<path d="{line_path}" fill="none" stroke="url(#tempoStroke)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />',
            *labels,
        ]
    )


def build_svg(profile: dict) -> str:
    now = current_datetime()
    source_tag = get_source_tag(profile)
    updated_label = now.strftime("%d %b %Y | %I:%M %p")

    micro_stats = [
        draw_micro_stat(256, 188, "active", format_number(profile["active_days"]), "#EC4899"),
        draw_micro_stat(358, 188, "repos", format_number(profile["public_repos"]), "#F97316"),
        draw_micro_stat(256, 254, "stars", format_number(profile["stars_earned"]), "#7C3AED"),
        draw_micro_stat(358, 254, "peak", format_number(profile["peak_day"]), "#38BDF8"),
    ]

    peak_week = max((week["total"] for week in profile["weekly_totals"]), default=0)

    return f"""<svg width="1100" height="560" viewBox="0 0 1100 560" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc" style="font-family:'Segoe UI','Trebuchet MS',sans-serif;">
  <title id="title">Live GitHub profile overview for {escape(profile["name"])}</title>
  <desc id="desc">Automatically refreshed GitHub stats showing contributions, repositories, stars, language mix, and recent build tempo.</desc>
  <defs>
    <linearGradient id="hero" x1="40" y1="24" x2="1060" y2="520" gradientUnits="userSpaceOnUse">
      <stop stop-color="#0F172A" />
      <stop offset="0.5" stop-color="#111827" />
      <stop offset="1" stop-color="#050816" />
    </linearGradient>
    <linearGradient id="tempoFill" x1="0" y1="430" x2="0" y2="500" gradientUnits="userSpaceOnUse">
      <stop stop-color="#2563EB" stop-opacity="0.35" />
      <stop offset="1" stop-color="#2563EB" stop-opacity="0" />
    </linearGradient>
    <linearGradient id="tempoStroke" x1="84" y1="470" x2="1016" y2="470" gradientUnits="userSpaceOnUse">
      <stop stop-color="#38BDF8" />
      <stop offset="0.55" stop-color="#2563EB" />
      <stop offset="1" stop-color="#EC4899" />
    </linearGradient>
  </defs>

  <rect x="10" y="10" width="1080" height="540" rx="30" fill="url(#hero)" stroke="#1E293B" />
  <circle cx="986" cy="114" r="104" fill="#2563EB" opacity="0.08" />
  <circle cx="124" cy="500" r="96" fill="#F97316" opacity="0.07" />
  <circle cx="954" cy="470" r="116" fill="#EC4899" opacity="0.06" />

  <rect x="44" y="34" width="154" height="32" rx="16" fill="#0F1B33" stroke="#22304A" />
  <text x="66" y="54" font-size="12" font-weight="700" fill="#60A5FA" letter-spacing="1.2">LIVE RECEIPTS</text>
  <text x="44" y="100" font-size="34" font-weight="700" fill="#F8FAFC">live build receipts</text>
  <text x="44" y="126" font-size="15" fill="#94A3B8">real GitHub data, auto-refreshed, zero fake flex.</text>

  <rect x="856" y="34" width="180" height="32" rx="16" fill="#0F1B33" stroke="#22304A" />
  <text x="876" y="54" font-size="12" font-weight="700" fill="#E2E8F0">{escape(source_tag)}</text>
  <text x="856" y="92" font-size="13" fill="#64748B">last refresh: {escape(updated_label)}</text>

  <rect x="44" y="146" width="430" height="224" rx="28" fill="#0D1526" stroke="#1E293B" />
  <text x="68" y="182" font-size="12" font-weight="700" fill="#64748B" letter-spacing="1.2">THIS YEAR</text>
  <text x="68" y="268" font-size="92" font-weight="800" fill="#F8FAFC">{format_number(profile["contributions_365d"])}</text>
  <text x="72" y="298" font-size="20" font-weight="700" fill="#CBD5E1">contributions</text>
  <text x="68" y="324" font-size="14" fill="#94A3B8">{escape(get_contribution_note(profile))}</text>
  <text x="68" y="346" font-size="13" fill="#64748B">shipping publicly since {profile["joined_year"]}</text>
  {"".join(micro_stats)}

  <rect x="500" y="146" width="556" height="224" rx="28" fill="#0D1526" stroke="#1E293B" />
  <text x="524" y="182" font-size="12" font-weight="700" fill="#64748B" letter-spacing="1.2">STACK TAPE</text>
  <text x="524" y="208" font-size="26" font-weight="700" fill="#F8FAFC">actual language mix</text>
  <text x="524" y="228" font-size="14" fill="#94A3B8">only the real repo languages make the lineup.</text>
  {draw_language_mix(profile["language_breakdown"])}

  <rect x="44" y="390" width="1012" height="140" rx="28" fill="#0D1526" stroke="#1E293B" />
  <text x="68" y="424" font-size="12" font-weight="700" fill="#64748B" letter-spacing="1.2">BUILD TEMPO</text>
  <text x="68" y="448" font-size="24" font-weight="700" fill="#F8FAFC">recent shipping curve</text>
  <text x="68" y="468" font-size="14" fill="#94A3B8">last 12 weeks of contribution movement</text>
  <rect x="890" y="412" width="136" height="30" rx="15" fill="#111B2E" />
  <text x="958" y="432" font-size="12" font-weight="700" text-anchor="middle" fill="#E2E8F0">peak week {peak_week}</text>
  {draw_build_tempo(profile["weekly_totals"])}
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
        "language_breakdown": profile["language_breakdown"],
        "weekly_totals": profile["weekly_totals"],
    }
    JSON_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main() -> None:
    profile = fetch_profile_data()
    write_outputs(profile)


if __name__ == "__main__":
    main()
