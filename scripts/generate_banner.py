import base64
import json
import re
import urllib.request
from pathlib import Path

# Curated constellation of 22 stack badges
# Sizes: L (r=22, size=24), M (r=18, size=20), S (r=14, size=16)
ICONS = {
    # Frontend cluster
    "react": {"label": "React", "x": 86, "y": 66, "r": 19, "size": 21, "anim": 1, "glow": "#61DAFB", "color": "#61DAFB"},
    "typescript": {"label": "TypeScript", "x": 166, "y": 45, "r": 18, "size": 20, "anim": 4, "glow": "#3178C6", "color": "#3178C6"},
    "javascript": {"label": "JavaScript", "x": 245, "y": 76, "r": 14, "size": 16, "anim": 3, "glow": "#F7DF1E", "color": "#F7DF1E"},
    "tailwindcss": {"label": "Tailwind CSS", "x": 104, "y": 157, "r": 14, "size": 16, "anim": 3, "glow": "#38BDF8", "color": "#38BDF8"},
    "html5": {"label": "HTML5", "x": 48, "y": 118, "r": 13, "size": 15, "anim": 1, "glow": "#E34F26", "color": "#E34F26"},
    "css3": {"label": "CSS3", "x": 178, "y": 176, "r": 13, "size": 15, "anim": 2, "glow": "#1572B6", "color": "#1572B6"},
    "figma": {"label": "Figma", "x": 268, "y": 156, "r": 13, "size": 15, "anim": 4, "glow": "#F24E1E", "color": "#F24E1E"},
    "nextdotjs": {"label": "Next.js", "x": 314, "y": 45, "r": 14, "size": 16, "anim": 4, "glow": "#00E5FF", "color": "#FFFFFF"},
    "angular": {"label": "Angular", "x": 130, "y": 110, "r": 14, "size": 16, "anim": 1, "glow": "#DD0031", "color": "#DD0031"},
    "vuedotjs": {"label": "Vue.js", "x": 216, "y": 126, "r": 14, "size": 16, "anim": 2, "glow": "#4FC08D", "color": "#4FC08D"},
    "svelte": {"label": "Svelte", "x": 50, "y": 180, "r": 13, "size": 15, "anim": 3, "glow": "#FF3E00", "color": "#FF3E00"},

    # Backend and data cluster
    "java": {"label": "Java", "x": 914, "y": 66, "r": 19, "size": 21, "anim": 2, "glow": "#EA2D2E", "color": "#EA2D2E"},
    "springboot": {"label": "Spring Boot", "x": 836, "y": 45, "r": 17, "size": 19, "anim": 4, "glow": "#6DB33F", "color": "#6DB33F"},
    "python": {"label": "Python", "x": 925, "y": 154, "r": 19, "size": 21, "anim": 3, "glow": "#3776AB", "color": "#3776AB"},
    "docker": {"label": "Docker", "x": 840, "y": 174, "r": 16, "size": 18, "anim": 1, "glow": "#2496ED", "color": "#2496ED"},
    "postgresql": {"label": "PostgreSQL", "x": 760, "y": 82, "r": 14, "size": 16, "anim": 1, "glow": "#4169E1", "color": "#4169E1"},
    "mysql": {"label": "MySQL", "x": 958, "y": 112, "r": 13, "size": 15, "anim": 4, "glow": "#4479A1", "color": "#4479A1"},
    "mongodb": {"label": "MongoDB", "x": 784, "y": 144, "r": 13, "size": 15, "anim": 3, "glow": "#47A248", "color": "#47A248"},
    "apachekafka": {"label": "Apache Kafka", "x": 716, "y": 154, "r": 14, "size": 16, "anim": 2, "glow": "#FFDD00", "color": "#FFFFFF"},
    "spring": {"label": "Spring AI", "x": 870, "y": 105, "r": 14, "size": 16, "anim": 2, "glow": "#6DB33F", "color": "#6DB33F"},

    # Tooling accents near the edges of the center frame
    "nodedotjs": {"label": "Node.js", "x": 318, "y": 176, "r": 14, "size": 16, "anim": 2, "glow": "#339933", "color": "#339933"},
    "git": {"label": "Git", "x": 390, "y": 30, "r": 12, "size": 14, "anim": 3, "glow": "#F05032", "color": "#F05032"},
    "postman": {"label": "Postman", "x": 610, "y": 30, "r": 12, "size": 14, "anim": 1, "glow": "#FF6C37", "color": "#FF6C37"},
    "githubactions": {"label": "GitHub Actions", "x": 682, "y": 176, "r": 13, "size": 15, "anim": 2, "glow": "#2088FF", "color": "#2088FF"},
    "amazonwebservices": {"label": "AWS", "x": 686, "y": 48, "r": 13, "size": 15, "anim": 4, "glow": "#FF9900", "color": "#FF9900"},
    "rabbitmq": {"label": "RabbitMQ", "x": 390, "y": 190, "r": 13, "size": 15, "anim": 1, "glow": "#FF6600", "color": "#FF6600"},
    "bitbucket": {"label": "Bitbucket", "x": 460, "y": 30, "r": 12, "size": 14, "anim": 3, "glow": "#0052CC", "color": "#0052CC"},
    "gitlab": {"label": "GitLab", "x": 540, "y": 30, "r": 12, "size": 14, "anim": 1, "glow": "#FC6D26", "color": "#FC6D26"},
    "ansible": {"label": "Ansible", "x": 610, "y": 190, "r": 13, "size": 15, "anim": 4, "glow": "#EE0000", "color": "#FFFFFF"}
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

def load_icon_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        if isinstance(cached, dict):
            return cached
    except Exception as e:
        print(f"Could not read existing icon cache: {e}")
    return {}

def main():
    print("Preparing encoded icon cache...")
    
    cache_path = Path("scripts/banner_icons_cache.json")
    encoded_icons = load_icon_cache(cache_path)

    for key, info in ICONS.items():
        if key in encoded_icons:
            continue

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
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&amp;display=swap');
    
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
      font-size: 40px;
      letter-spacing: -0.8px;
      paint-order: stroke;
      stroke: #05070f;
      stroke-width: 3px;
      text-shadow: 0px 4px 12px rgba(0, 0, 0, 0.4);
    }}
    .role-pill-text {{
      font-family: 'Sora', -apple-system, sans-serif;
      font-weight: 800;
      fill: #BAE6FD;
      font-size: 10px;
      letter-spacing: 1.6px;
    }}
    .stack-line {{
      font-family: 'Sora', -apple-system, sans-serif;
      font-weight: 700;
      fill: #CBD5E1;
      font-size: 8px;
      letter-spacing: 2px;
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

  <!-- Center identity glass panel -->
  <rect x="245" y="50" width="510" height="128" rx="30" fill="#050A14" fill-opacity="0.76" stroke="#7DD3FC" stroke-opacity="0.12" />
  <rect x="267" y="66" width="466" height="92" rx="24" fill="#0B1220" fill-opacity="0.52" stroke="#FFFFFF" stroke-opacity="0.06" />
  <path d="M295 154 H705" stroke="url(#bgGradient)" stroke-width="1.2" stroke-opacity="0.22" stroke-linecap="round" />
  <rect x="381" y="112" width="238" height="27" rx="13.5" fill="#0EA5E9" fill-opacity="0.10" stroke="#38BDF8" stroke-opacity="0.20" />

  <!-- Glowing Tech Stack Badges Halo -->
  {badges_str}

  <!-- Developer Name -->
  <text x="500" y="91" text-anchor="middle" dominant-baseline="middle" class="title" filter="url(#shadow)">Haritha Sivasankaran</text>
  
  <!-- Current role and stack -->
  <text x="500" y="130" text-anchor="middle" class="role-pill-text">SYSTEMS ENGINEER @ TCS</text>
  <text x="500" y="164" text-anchor="middle" class="stack-line">FULL-STACK BUILDER | REACT | TYPESCRIPT | JAVA | PYTHON</text>
</svg>"""

    banner_path = Path("assets/profile-banner-v5.svg")
    banner_path.write_text(svg_content, encoding="utf-8")
    print("OK: 22-badge clean profile banner generated successfully!")

if __name__ == "__main__":
    main()
