import base64
import json
import urllib.request
from pathlib import Path

# Define icons to fetch (Simple Icons names)
ICONS = {
    "python": {"label": "Python", "x": 80, "y": 50, "size": 34, "opacity": 0.8, "rot": 12, "anim": 1},
    "javascript": {"label": "JavaScript", "x": 160, "y": 130, "size": 32, "opacity": 0.85, "rot": -8, "anim": 2},
    "html5": {"label": "HTML5", "x": 320, "y": 130, "size": 30, "opacity": 0.75, "rot": 5, "anim": 3},
    "css3": {"label": "CSS3", "x": 80, "y": 130, "size": 30, "opacity": 0.75, "rot": -10, "anim": 4},
    "java": {"label": "Java", "x": 160, "y": 50, "size": 30, "opacity": 0.7, "rot": 10, "anim": 1},
    "typescript": {"label": "TypeScript", "x": 240, "y": 115, "size": 34, "opacity": 0.85, "rot": -5, "anim": 2},
    "react": {"label": "React", "x": 240, "y": 45, "size": 38, "opacity": 0.9, "rot": 15, "anim": 3},
    "nodedotjs": {"label": "Node.js", "x": 320, "y": 50, "size": 34, "opacity": 0.8, "rot": 8, "anim": 4},
    
    "nextdotjs": {"label": "Next.js", "x": 680, "y": 50, "size": 38, "opacity": 0.9, "rot": -15, "anim": 1},
    "tailwindcss": {"label": "Tailwind CSS", "x": 820, "y": 130, "size": 32, "opacity": 0.85, "rot": 8, "anim": 2},
    "vite": {"label": "Vite", "x": 920, "y": 50, "size": 34, "opacity": 0.8, "rot": -10, "anim": 3},
    "docker": {"label": "Docker", "x": 750, "y": 130, "size": 36, "opacity": 0.85, "rot": 12, "anim": 4},
    "git": {"label": "Git", "x": 680, "y": 130, "size": 30, "opacity": 0.75, "rot": -8, "anim": 1},
    "github": {"label": "GitHub", "x": 820, "y": 50, "size": 34, "opacity": 0.8, "rot": 5, "anim": 2},
    "visualstudiocode": {"label": "VS Code", "x": 920, "y": 130, "size": 32, "opacity": 0.85, "rot": 10, "anim": 3},
    "jupyter": {"label": "Jupyter", "x": 750, "y": 50, "size": 30, "opacity": 0.7, "rot": -5, "anim": 4}
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
    
    # Try to load cache first to save network calls
    cache_path = Path("scripts/banner_icons_cache.json")
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                encoded_icons = json.load(f)
            print("Loaded icons from cache.")
        except Exception:
            pass

    # Fetch missing icons
    missing_fetched = False
    for key, info in ICONS.items():
        if key not in encoded_icons:
            label = info["label"]
            b64 = get_base64_icon(key)
            if b64:
                encoded_icons[key] = b64
                missing_fetched = True
                print(f"OK: {label} encoded successfully.")
            else:
                print(f"FAIL: {label} failed.")

    if missing_fetched:
        with open("scripts/banner_icons_cache.json", "w", encoding="utf-8") as f:
            json.dump(encoded_icons, f, indent=2)

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
        half_size = size / 2
        
        # Nested structure: 
        # Outer group translates to (x, y) and applies initial rotation.
        # Inner group animates float independently.
        icon_elem = f"""
  <g transform="translate({x}, {y}) rotate({rot})">
    <g class="float-icon-{anim}">
      <image href="{b64}" x="-{half_size}" y="-{half_size}" width="{size}" height="{size}" opacity="{opacity}" />
    </g>
  </g>"""
        icon_elements.append(icon_elem)

    icons_str = "".join(icon_elements)

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 220" width="1000" height="220">
  <defs>
    <linearGradient id="bgGradient" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#0F172A" />
      <stop offset="45%" stop-color="#2563EB" />
      <stop offset="100%" stop-color="#EC4899" />
    </linearGradient>
    
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="2" dy="4" stdDeviation="4" flood-opacity="0.3" />
    </filter>
  </defs>

  <style>
    @keyframes float1 {{
      0% {{ transform: translateY(0px) rotate(0deg); }}
      50% {{ transform: translateY(-5px) rotate(1deg); }}
      100% {{ transform: translateY(0px) rotate(0deg); }}
    }}
    @keyframes float2 {{
      0% {{ transform: translateY(0px) rotate(0deg); }}
      50% {{ transform: translateY(-7px) rotate(-1.5deg); }}
      100% {{ transform: translateY(0px) rotate(0deg); }}
    }}
    @keyframes float3 {{
      0% {{ transform: translateY(0px) rotate(0deg); }}
      50% {{ transform: translateY(5px) rotate(1deg); }}
      100% {{ transform: translateY(0px) rotate(0deg); }}
    }}
    @keyframes float4 {{
      0% {{ transform: translateY(0px) rotate(0deg); }}
      50% {{ transform: translateY(7px) rotate(-1deg); }}
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

  <!-- Animated Waving Background Layers from capsule-render -->
  <g>
    <!-- Wave 1 (Back wave) -->
    <path d="M0 0 L 0 140 Q 250 180 500 150 T 1000 175 L 1000 0 Z" fill="url(#bgGradient)" opacity="0.45">
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
    <path d="M0 0 L 0 155 Q 250 200 500 170 T 1000 180 L 1000 0 Z" fill="url(#bgGradient)" opacity="0.65">
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

  <!-- Floating Tech Stack Icons -->
  {icons_str}

  <!-- Developer Name -->
  <text x="500" y="100" text-anchor="middle" dominant-baseline="middle" class="title" filter="url(#shadow)">Haritha Sivasankaran</text>
</svg>"""

    banner_path = Path("assets/profile-banner.svg")
    banner_path.write_text(svg_content, encoding="utf-8")
    print("OK: Banner SVG generated successfully at assets/profile-banner.svg!")

if __name__ == "__main__":
    main()
