import base64
import json
import re
import urllib.request
from pathlib import Path

# Organic Constellation of 26 Stack Badges with spacious center corridor
# Sizes: L (r=22, size=24), M (r=18, size=20), S (r=14, size=16)
ICONS = {
    # Left Side Galaxy Cloud (x <= 260)
    "react": {"label": "React", "x": 80, "y": 45, "r": 22, "size": 24, "anim": 1, "glow": "#61DAFB", "color": "#61DAFB"},
    "nodedotjs": {"label": "Node.js", "x": 60, "y": 110, "r": 18, "size": 20, "anim": 2, "glow": "#339933", "color": "#339933"},
    "tailwindcss": {"label": "Tailwind CSS", "x": 90, "y": 175, "r": 14, "size": 16, "anim": 3, "glow": "#38BDF8", "color": "#38BDF8"},
    "typescript": {"label": "TypeScript", "x": 150, "y": 55, "r": 22, "size": 24, "anim": 4, "glow": "#3178C6", "color": "#3178C6"},
    "html5": {"label": "HTML5", "x": 130, "y": 115, "r": 14, "size": 16, "anim": 1, "glow": "#E34F26", "color": "#E34F26"},
    "css3": {"label": "CSS3", "x": 160, "y": 175, "r": 14, "size": 16, "anim": 2, "glow": "#1572B6", "color": "#1572B6"},
    "javascript": {"label": "JavaScript", "x": 220, "y": 75, "r": 14, "size": 16, "anim": 3, "glow": "#F7DF1E", "color": "#F7DF1E"},
    "express": {"label": "Express", "x": 210, "y": 135, "r": 14, "size": 16, "anim": 4, "glow": "#FFFFFF", "color": "#FFFFFF"},
    "graphql": {"label": "GraphQL", "x": 260, "y": 40, "r": 14, "size": 16, "anim": 1, "glow": "#E10098", "color": "#E10098"},

    # Right Side Galaxy Cloud (x >= 740)
    "java": {"label": "Java", "x": 920, "y": 45, "r": 22, "size": 24, "anim": 2, "glow": "#EA2D2E", "color": "#EA2D2E"},
    "python": {"label": "Python", "x": 940, "y": 110, "r": 22, "size": 24, "anim": 3, "glow": "#3776AB", "color": "#3776AB"},
    "mysql": {"label": "MySQL", "x": 910, "y": 175, "r": 14, "size": 16, "anim": 4, "glow": "#4479A1", "color": "#4479A1"},
    "docker": {"label": "Docker", "x": 850, "y": 55, "r": 18, "size": 20, "anim": 1, "glow": "#2496ED", "color": "#2496ED"},
    "apachekafka": {"label": "Apache Kafka", "x": 870, "y": 115, "r": 18, "size": 20, "anim": 2, "glow": "#FFDD00", "color": "#FFFFFF"},
    "mongodb": {"label": "MongoDB", "x": 840, "y": 175, "r": 14, "size": 16, "anim": 3, "glow": "#47A248", "color": "#47A248"},
    "springboot": {"label": "Spring Boot", "x": 780, "y": 75, "r": 18, "size": 20, "anim": 4, "glow": "#6DB33F", "color": "#6DB33F"},
    "postgresql": {"label": "PostgreSQL", "x": 790, "y": 135, "r": 14, "size": 16, "anim": 1, "glow": "#4169E1", "color": "#4169E1"},
    "redis": {"label": "Redis", "x": 740, "y": 40, "r": 14, "size": 16, "anim": 3, "glow": "#DC382D", "color": "#DC382D"},

    # Top & Bottom Caps (Pushed vertically away from text corridors)
    "git": {"label": "Git", "x": 400, "y": 32, "r": 14, "size": 16, "anim": 3, "glow": "#F05032", "color": "#F05032"},
    "nextdotjs": {"label": "Next.js", "x": 600, "y": 32, "r": 18, "size": 20, "anim": 4, "glow": "#00E5FF", "color": "#FFFFFF"},
    "rabbitmq": {"label": "RabbitMQ", "x": 330, "y": 192, "r": 18, "size": 20, "anim": 1, "glow": "#FF6600", "color": "#FF6600"},
    "githubactions": {"label": "GitHub Actions", "x": 670, "y": 192, "r": 14, "size": 16, "anim": 2, "glow": "#2088FF", "color": "#2088FF"},

    # Fill-in Badges for Inner Spaces
    "fastapi": {"label": "FastAPI", "x": 330, "y": 35, "r": 14, "size": 16, "anim": 3, "glow": "#009688", "color": "#009688"},
    "supabase": {"label": "Supabase", "x": 670, "y": 35, "r": 14, "size": 16, "anim": 1, "glow": "#3ECF8E", "color": "#3ECF8E"},
    "prisma": {"label": "Prisma", "x": 270, "y": 185, "r": 14, "size": 16, "anim": 2, "glow": "#5A67D8", "color": "#FFFFFF"},
    "figma": {"label": "Figma", "x": 730, "y": 185, "r": 14, "size": 16, "anim": 4, "glow": "#F24E1E", "color": "#F24E1E"}
}

def get_base64_icon(name: str, color_fallback: str) -> str:
    url = f"https://cdn.simpleicons.org/{name}"
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            svg_data = response.read()
            if b"<svg" in svg_data:
                encoded = base64.b64encode(svg_data).decode("utf-8")
                return f"data:image/svg+xml;base64,{encoded}"
    except Exception:
        pass

    url_fallback = f"https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{name}.svg"
    try:
        req = urllib.request.Request(
            url_fallback, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            svg_data = response.read()
            if b"<svg" in svg_data:
                svg_text = svg_data.decode("utf-8")
                svg_text = re.sub(r'fill="[^"]+"', '', svg_text)
                svg_text = svg_text.replace("<svg ", f'<svg fill="{color_fallback}" ')
                encoded = base64.b64encode(svg_text.encode("utf-8")).decode("utf-8")
                return f"data:image/svg+xml;base64,{encoded}"
    except Exception as e:
        print(f"Error fetching fallback icon for {name}: {e}")
    return ""

def main():
    print("Fetching and encoding colored icons...")
    encoded_icons = {}
    
    cache_path = Path("scripts/banner_icons_cache.json")
    if cache_path.exists():
        try:
            cache_path.unlink()
        except Exception:
            pass

    for key, info in ICONS.items():
        label = info["label"]
        b64 = get_base64_icon(key, info["color"])
        if b64:
            encoded_icons[key] = b64
            print(f"OK: {label} logo encoded.")
        else:
            print(f"FAIL: {label} failed.")

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(encoded_icons, f, indent=2)

    badge_elements = []
    
    for key, info in ICONS.items():
        if key not in encoded_icons:
            continue
        b64 = encoded_icons[key]
        x = info["x"]
        y = info["y"]
        r = info["r"]
        size = info["size"]
        anim = info["anim"]
        glow_color = info["glow"]
        
        badge_elem = f"""
  <!-- Badge: {info['label']} -->
  <g class="float-icon-{anim}">
    <!-- Ambient Glow behind badge -->
    <circle cx="{x}" cy="{y}" r="{r + 10}" fill="{glow_color}" opacity="0.18" filter="url(#blurGlow)" />
    
    <!-- Circular Glass Plate -->
    <circle cx="{x}" cy="{y}" r="{r}" fill="#0b0b16" fill-opacity="0.8" stroke="{glow_color}" stroke-width="1.3" stroke-opacity="0.85" filter="url(#shadow)" />
    
    <!-- Centered Brand Icon -->
    <image href="{b64}" x="{x - (size/2)}" y="{y - (size/2)}" width="{size}" height="{size}" />
  </g>"""
        badge_elements.append(badge_elem)

    badges_str = "".join(badge_elements)

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 220" width="1000" height="220">
  <defs>
    <linearGradient id="pageBg" x1="0" y1="0" x2="1000" y2="220" gradientUnits="userSpaceOnUse">
      <stop stop-color="#040408" />
      <stop offset="0.55" stop-color="#07070F" />
      <stop offset="1" stop-color="#020205" />
    </linearGradient>

    <linearGradient id="bgGradient" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#3B82F6" />
      <stop offset="50%" stop-color="#8B5CF6" />
      <stop offset="100%" stop-color="#00E5FF" />
    </linearGradient>
    
    <pattern id="gridPattern" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M 32 0 H 0 V 32" fill="none" stroke="#1E1B4B" stroke-width="1.2" stroke-opacity="0.22" />
    </pattern>

    <filter id="blurGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="12" />
    </filter>

    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="1" dy="2" stdDeviation="2" flood-opacity="0.5" flood-color="#000000" />
    </filter>
  </defs>

  <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@800&amp;display=swap');
    
    @keyframes float1 {{
      0% {{ transform: translateY(0px) rotate(0deg); }}
      50% {{ transform: translateY(-5px) rotate(1deg); }}
      100% {{ transform: translateY(0px) rotate(0deg); }}
    }}
    @keyframes float2 {{
      0% {{ transform: translateY(0px) rotate(0deg); }}
      50% {{ transform: translateY(-8px) rotate(-1deg); }}
      100% {{ transform: translateY(0px) rotate(0deg); }}
    }}
    @keyframes float3 {{
      0% {{ transform: translateY(0px) rotate(0deg); }}
      50% {{ transform: translateY(5px) rotate(1.5deg); }}
      100% {{ transform: translateY(0px) rotate(0deg); }}
    }}
    @keyframes float4 {{
      0% {{ transform: translateY(0px) rotate(0deg); }}
      50% {{ transform: translateY(8px) rotate(-1.5deg); }}
      100% {{ transform: translateY(0px) rotate(0deg); }}
    }}
    .float-icon-1 {{ animation: float1 4.5s ease-in-out infinite; }}
    .float-icon-2 {{ animation: float2 5.8s ease-in-out infinite; }}
    .float-icon-3 {{ animation: float3 5.2s ease-in-out infinite; }}
    .float-icon-4 {{ animation: float4 6.5s ease-in-out infinite; }}
    
    .title {{
      font-family: 'Sora', -apple-system, sans-serif;
      font-weight: 800;
      fill: #ffffff;
      font-size: 42px;
      letter-spacing: -0.5px;
      text-shadow: 0px 4px 12px rgba(0, 0, 0, 0.4);
    }}
  </style>

  <!-- Background Base matching profile pages -->
  <rect width="1000" height="220" rx="20" fill="url(#pageBg)" />
  <rect width="1000" height="220" rx="20" fill="url(#gridPattern)" />

  <!-- Ambient Glow Backdrops -->
  <circle cx="150" cy="110" r="120" fill="#3B82F6" opacity="0.10" filter="url(#blurGlow)" />
  <circle cx="850" cy="110" r="140" fill="#8B5CF6" opacity="0.10" filter="url(#blurGlow)" />
  <circle cx="500" cy="110" r="100" fill="#00E5FF" opacity="0.06" filter="url(#blurGlow)" />

  <rect x="1.5" y="1.5" width="997" height="217" rx="18.5" stroke="#131326" stroke-width="1.4" fill="none" />

  <!-- Animated Waving Background Layers -->
  <g>
    <!-- Wave 1 (Back wave) -->
    <path d="M0 0 L 0 140 Q 250 180 500 150 T 1000 175 L 1000 0 Z" fill="url(#bgGradient)" opacity="0.05">
      <animate
          attributeName="d"
          dur="20s"
          repeatCount="indefinite"
          keyTimes="0;0.333;0.667;1"
          calcMode="spline"
          keySplines="0.2 0 0.2 1;0.2 0 0.2 1;0.2 0 0.2 1"
          begin="0s"
          values="M0 0 L 0 140 Q 250 180 500 150 T 1000 175 L 1000 0 Z; M0 0 L 0 165 Q 250 180 500 160 T 1000 150 L 1000 0 Z; M0 0 L 0 185 Q 250 155 500 185 T 1000 150 L 1000 0 Z; M0 0 L 0 140 Q 250 180 500 150 T 1000 175 L 1000 0 Z" />
    </path>
    <!-- Wave 2 (Front wave) -->
    <path d="M0 0 L 0 155 Q 250 200 500 170 T 1000 180 L 1000 0 Z" fill="url(#bgGradient)" opacity="0.08">
      <animate
          attributeName="d"
          dur="20s"
          repeatCount="indefinite"
          keyTimes="0;0.333;0.667;1"
          calcMode="spline"
          keySplines="0.2 0 0.2 1;0.2 0 0.2 1;0.2 0 0.2 1"
          begin="-10s"
          values="M0 0 L 0 155 Q 250 200 500 170 T 1000 180 L 1000 0 Z; M0 0 L 0 170 Q 250 140 500 140 T 1000 160 L 1000 0 Z; M0 0 L 0 165 Q 250 145 500 170 T 1000 185 L 1000 0 Z; M0 0 L 0 155 Q 250 200 500 170 T 1000 180 L 1000 0 Z" />
    </path>
  </g>

  <!-- Glowing Tech Stack Badges Halo -->
  {badges_str}

  <!-- Developer Name -->
  <text x="500" y="105" text-anchor="middle" dominant-baseline="middle" class="title" filter="url(#shadow)">Haritha Sivasankaran</text>
  
  <!-- Subtitle / Stacks info -->
  <text x="500" y="145" text-anchor="middle" font-family="'Sora', -apple-system, sans-serif" font-weight="600" fill="#64748B" font-size="9" letter-spacing="2.8" opacity="0.85">FULL STACK ENGINEER  •  REACT · TYPESCRIPT · JAVA · PYTHON</text>
</svg>"""

    banner_path = Path("assets/profile-banner-v5.svg")
    banner_path.write_text(svg_content, encoding="utf-8")
    print("OK: 26-badge Constellation Name Banner generated successfully!")

if __name__ == "__main__":
    main()
