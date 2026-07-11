import base64
import json
import re
import urllib.request
from pathlib import Path

ICONS = {
    # Left Side: React and TypeScript (Brand colors)
    "react": {"label": "React", "x": 140, "y": 110, "size": 52, "opacity": 0.95, "anim": 1, "glow": "#61DAFB", "color": "#61DAFB"},
    "typescript": {"label": "TypeScript", "x": 240, "y": 110, "size": 44, "opacity": 0.95, "anim": 2, "glow": "#3178C6", "color": "#3178C6"},

    # Right Side: Python and Java (Brand colors)
    "python": {"label": "Python", "x": 760, "y": 110, "size": 46, "opacity": 0.95, "anim": 3, "glow": "#3776AB", "color": "#3776AB"},
    "java": {"label": "Java", "x": 860, "y": 110, "size": 52, "opacity": 0.95, "anim": 4, "glow": "#EA2D2E", "color": "#EA2D2E"}
}

def get_base64_icon(name: str, color_fallback: str) -> str:
    # First try fetching from simpleicons colored CDN
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

    # Fallback to jsdelivr raw icon & color it manually
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
    
    # Force refresh cache
    cache_path = Path("scripts/banner_icons_cache.json")
    if cache_path.exists():
        try:
            cache_path.unlink()
        except Exception:
            pass

    # Fetch icons
    for key, info in ICONS.items():
        label = info["label"]
        b64 = get_base64_icon(key, info["color"])
        if b64:
            encoded_icons[key] = b64
            print(f"OK: {label} colored logo encoded.")
        else:
            print(f"FAIL: {label} failed.")

    # Save cache
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(encoded_icons, f, indent=2)

    # SVG Construction
    icon_elements = []
    glow_elements = []
    
    for key, info in ICONS.items():
        if key not in encoded_icons:
            continue
        b64 = encoded_icons[key]
        x = info["x"]
        y = info["y"]
        size = info["size"]
        opacity = info["opacity"]
        anim = info["anim"]
        glow_color = info["glow"]
        
        # Calculate top-left based on center coordinates
        img_x = x - (size / 2)
        img_y = y - (size / 2)
        
        # Subtle matching brand color glow behind each icon
        glow_elem = f"""
  <circle cx="{x}" cy="{y}" r="{size + 20}" fill="{glow_color}" opacity="0.08" filter="url(#blurGlow)" />"""
        glow_elements.append(glow_elem)
        
        icon_elem = f"""
  <image class="float-icon-{anim}" href="{b64}" x="{img_x}" y="{img_y}" width="{size}" height="{size}" opacity="{opacity}" />"""
        icon_elements.append(icon_elem)

    glows_str = "".join(glow_elements)
    icons_str = "".join(icon_elements)

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

    <filter id="blurGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="20" />
    </filter>

    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="2" dy="4" stdDeviation="4" flood-opacity="0.3" flood-color="#000000" />
    </filter>
  </defs>

  <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@800&amp;display=swap');
    
    @keyframes float1 {{
      0% {{ transform: translateY(0px); }}
      50% {{ transform: translateY(-5px); }}
      100% {{ transform: translateY(0px); }}
    }}
    @keyframes float2 {{
      0% {{ transform: translateY(0px); }}
      50% {{ transform: translateY(-8px); }}
      100% {{ transform: translateY(0px); }}
    }}
    @keyframes float3 {{
      0% {{ transform: translateY(0px); }}
      50% {{ transform: translateY(5px); }}
      100% {{ transform: translateY(0px); }}
    }}
    @keyframes float4 {{
      0% {{ transform: translateY(0px); }}
      50% {{ transform: translateY(8px); }}
      100% {{ transform: translateY(0px); }}
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

  <!-- Brand Glow Spots -->
  {glows_str}

  <!-- Floating Tech Stack Icons -->
  {icons_str}

  <!-- Developer Name -->
  <text x="500" y="105" text-anchor="middle" dominant-baseline="middle" class="title" filter="url(#shadow)">Haritha Sivasankaran</text>
  
  <!-- Subtitle / Stacks info -->
  <text x="500" y="145" text-anchor="middle" font-family="'Sora', -apple-system, sans-serif" font-weight="600" fill="#94A3B8" font-size="13" letter-spacing="1.5" opacity="0.85">FULL STACK ENGINEER  •  SLEEK FRONTENDS &amp; HIGH-PERFORMANCE BACKENDS</text>
</svg>"""

    # Generate v5 file to bypass cache
    banner_path = Path("assets/profile-banner-v5.svg")
    banner_path.write_text(svg_content, encoding="utf-8")
    print("OK: 4 Colored Stack Logos Name Banner generated successfully at assets/profile-banner-v5.svg!")

if __name__ == "__main__":
    main()
