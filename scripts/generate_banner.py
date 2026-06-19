import base64
import json
import urllib.request
from pathlib import Path

# Define icons to fetch (Simple Icons names)
ICONS = {
    "python": {"label": "Python", "x": 90, "y": 45, "size": 34, "opacity": 0.8, "rot": 12, "anim": 1},
    "javascript": {"label": "JavaScript", "x": 160, "y": 120, "size": 32, "opacity": 0.85, "rot": -8, "anim": 2},
    "html5": {"label": "HTML5", "x": 300, "y": 120, "size": 30, "opacity": 0.75, "rot": 5, "anim": 3},
    "css3": {"label": "CSS3", "x": 90, "y": 120, "size": 30, "opacity": 0.75, "rot": -10, "anim": 4},
    "java": {"label": "Java", "x": 160, "y": 40, "size": 30, "opacity": 0.7, "rot": 10, "anim": 1},
    "typescript": {"label": "TypeScript", "x": 230, "y": 105, "size": 34, "opacity": 0.85, "rot": -5, "anim": 2},
    "react": {"label": "React", "x": 230, "y": 40, "size": 38, "opacity": 0.9, "rot": 15, "anim": 3},
    "nodedotjs": {"label": "Node.js", "x": 300, "y": 45, "size": 34, "opacity": 0.8, "rot": 8, "anim": 4},
    
    "nextdotjs": {"label": "Next.js", "x": 670, "y": 45, "size": 38, "opacity": 0.9, "rot": -15, "anim": 1},
    "tailwindcss": {"label": "Tailwind CSS", "x": 810, "y": 120, "size": 32, "opacity": 0.85, "rot": 8, "anim": 2},
    "vite": {"label": "Vite", "x": 880, "y": 45, "size": 34, "opacity": 0.8, "rot": -10, "anim": 3},
    "docker": {"label": "Docker", "x": 740, "y": 120, "size": 36, "opacity": 0.85, "rot": 12, "anim": 4},
    "git": {"label": "Git", "x": 670, "y": 115, "size": 30, "opacity": 0.75, "rot": -8, "anim": 1},
    "github": {"label": "GitHub", "x": 810, "y": 40, "size": 34, "opacity": 0.8, "rot": 5, "anim": 2},
    "visualstudiocode": {"label": "VS Code", "x": 880, "y": 115, "size": 32, "opacity": 0.85, "rot": 10, "anim": 3},
    "jupyter": {"label": "Jupyter", "x": 740, "y": 40, "size": 30, "opacity": 0.7, "rot": -5, "anim": 4}
}

def get_base64_icon(name: str) -> str:
    url = f"https://cdn.simpleicons.org/{name}"  # Get colored icons
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

    # Fallback to jsDelivr if CDN fails/404s
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
                # Style fallback icons to white
                if "fill=" not in svg_text:
                    svg_text = svg_text.replace("<svg ", '<svg fill="#ffffff" ')
                else:
                    svg_text = svg_text.replace('fill="#000"', 'fill="#ffffff"').replace('fill="currentColor"', 'fill="#ffffff"')
                encoded = base64.b64encode(svg_text.encode("utf-8")).decode("utf-8")
                return f"data:image/svg+xml;base64,{encoded}"
    except Exception as e:
        print(f"Failed to fetch {name} from fallback: {e}")
    return ""

def main():
    print("Fetching and encoding icons...")
    encoded_icons = {}
    for key, info in ICONS.items():
        label = info["label"]
        b64 = get_base64_icon(key)
        if b64:
            encoded_icons[key] = b64
            print(f"OK: {label} encoded successfully.")
        else:
            print(f"FAIL: {label} failed.")

    # SVG Construction
    icon_elements = []
    for key, info in ICONS.items():
        if key not in encoded_icons:
            continue
        b64 = encoded_icons[key]
        x = info["x"]
        y = info["y"]
        size = info["size"]
        opacity = info["opacity"]
        rot = info["rot"]
        anim = info["anim"]
        
        icon_elem = f"""
  <g class="float-icon-{anim}" transform="translate({x}, {y}) rotate({rot})">
    <image href="{b64}" width="{size}" height="{size}" opacity="{opacity}" />
  </g>"""
        icon_elements.append(icon_elem)

    icons_str = "".join(icon_elements)

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 220" width="1000" height="220">
  <defs>
    <linearGradient id="bgGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0F172A" />
      <stop offset="45%" stop-color="#2563EB" />
      <stop offset="100%" stop-color="#EC4899" />
    </linearGradient>
    
    <clipPath id="waveClip">
      <path d="M 0 0 L 1000 0 L 1000 185 C 750 225, 250 145, 0 185 Z" />
    </clipPath>
    
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="2" dy="4" stdDeviation="4" flood-opacity="0.3" />
    </filter>
  </defs>

  <style>
    @keyframes float1 {{
      0% {{ transform: translateY(0px) rotate(0deg); }}
      50% {{ transform: translateY(-6px) rotate(2deg); }}
      100% {{ transform: translateY(0px) rotate(0deg); }}
    }}
    @keyframes float2 {{
      0% {{ transform: translateY(0px) rotate(0deg); }}
      50% {{ transform: translateY(-8px) rotate(-2deg); }}
      100% {{ transform: translateY(0px) rotate(0deg); }}
    }}
    @keyframes float3 {{
      0% {{ transform: translateY(0px) rotate(0deg); }}
      50% {{ transform: translateY(6px) rotate(1deg); }}
      100% {{ transform: translateY(0px) rotate(0deg); }}
    }}
    @keyframes float4 {{
      0% {{ transform: translateY(0px) rotate(0deg); }}
      50% {{ transform: translateY(8px) rotate(-1deg); }}
      100% {{ transform: translateY(0px) rotate(0deg); }}
    }}
    .float-icon-1 {{ animation: float1 5s ease-in-out infinite; }}
    .float-icon-2 {{ animation: float2 6.5s ease-in-out infinite; }}
    .float-icon-3 {{ animation: float3 5.8s ease-in-out infinite; }}
    .float-icon-4 {{ animation: float4 7.2s ease-in-out infinite; }}
    
    .title {{
      font-family: system-ui, -apple-system, sans-serif;
      font-weight: 800;
      fill: #ffffff;
      font-size: 42px;
      text-shadow: 0px 4px 12px rgba(0, 0, 0, 0.4);
    }}
  </style>

  <!-- Main clipped background -->
  <rect width="1000" height="220" fill="url(#bgGradient)" clip-path="url(#waveClip)" />

  <!-- Floating Tech Stack Icons -->
  {icons_str}

  <!-- Developer Name -->
  <text x="500" y="105" text-anchor="middle" dominant-baseline="middle" class="title" filter="url(#shadow)">Haritha Sivasankaran</text>
</svg>"""

    banner_path = Path("assets/profile-banner.svg")
    banner_path.write_text(svg_content, encoding="utf-8")
    print("OK: Banner SVG generated successfully at assets/profile-banner.svg!")

if __name__ == "__main__":
    main()
