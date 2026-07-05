import base64
import json
import re
import urllib.request
from pathlib import Path

# Define icons to fetch (Simple Icons names) with updated coordinates
ICONS = {
    # Top Row (8 icons)
    "python": {"label": "Python", "x": 90, "y": 45, "size": 34, "opacity": 0.8, "anim": 1},
    "java": {"label": "Java", "x": 210, "y": 55, "size": 30, "opacity": 0.7, "anim": 2},
    "typescript": {"label": "TypeScript", "x": 330, "y": 45, "size": 34, "opacity": 0.85, "anim": 3},
    "git": {"label": "Git", "x": 450, "y": 50, "size": 30, "opacity": 0.75, "anim": 4},
    "docker": {"label": "Docker", "x": 550, "y": 50, "size": 36, "opacity": 0.85, "anim": 1},
    "nextdotjs": {"label": "Next.js", "x": 670, "y": 45, "size": 38, "opacity": 0.9, "anim": 2},
    "jupyter": {"label": "Jupyter", "x": 790, "y": 55, "size": 30, "opacity": 0.7, "anim": 3},
    "vite": {"label": "Vite", "x": 910, "y": 45, "size": 34, "opacity": 0.8, "anim": 4},
    
    # Bottom Row (8 icons)
    "css3": {"label": "CSS3", "x": 90, "y": 135, "size": 30, "opacity": 0.75, "anim": 1},
    "javascript": {"label": "JavaScript", "x": 210, "y": 125, "size": 32, "opacity": 0.85, "anim": 2},
    "html5": {"label": "HTML5", "x": 330, "y": 135, "size": 30, "opacity": 0.75, "anim": 3},
    "react": {"label": "React", "x": 450, "y": 130, "size": 38, "opacity": 0.9, "anim": 4},
    "nodedotjs": {"label": "Node.js", "x": 550, "y": 130, "size": 34, "opacity": 0.8, "anim": 1},
    "tailwindcss": {"label": "Tailwind CSS", "x": 670, "y": 135, "size": 32, "opacity": 0.85, "anim": 2},
    "visualstudiocode": {"label": "VS Code", "x": 790, "y": 125, "size": 32, "opacity": 0.85, "anim": 3},
    "github": {"label": "GitHub", "x": 910, "y": 135, "size": 34, "opacity": 0.8, "anim": 4}
}

def get_base64_icon(name: str) -> str:
    url = f"https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/{name}.svg"
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            svg_data = response.read()
            if b"<svg" in svg_data:
                svg_text = svg_data.decode("utf-8")
                # Format to uniform clean white (#F8FAFC)
                svg_text = re.sub(r'fill="[^"]+"', '', svg_text)
                svg_text = svg_text.replace("<svg ", '<svg fill="#F8FAFC" ')
                encoded = base64.b64encode(svg_text.encode("utf-8")).decode("utf-8")
                return f"data:image/svg+xml;base64,{encoded}"
    except Exception as e:
        print(f"Error fetching icon {name}: {e}")
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

    # Ensure LinkedIn is also fetched and cached
    if "linkedin" not in encoded_icons:
        linkedin_b64 = get_base64_icon("linkedin")
        if linkedin_b64:
            encoded_icons["linkedin"] = linkedin_b64
            missing_fetched = True
            print("OK: LinkedIn icon encoded successfully.")

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
        anim = info["anim"]
        
        # Calculate top-left based on center coordinates
        img_x = x - (size / 2)
        img_y = y - (size / 2)
        
        icon_elem = f"""
  <image class="float-icon-{anim}" href="{b64}" x="{img_x}" y="{img_y}" width="{size}" height="{size}" opacity="{opacity}" />"""
        icon_elements.append(icon_elem)

    icons_str = "".join(icon_elements)
    
    linkedin_b64 = encoded_icons.get("linkedin", "")

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
      <feGaussianBlur stdDeviation="24" />
    </filter>

    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="2" dy="4" stdDeviation="4" flood-opacity="0.3" flood-color="#000000" />
    </filter>
  </defs>

  <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@800&amp;display=swap');
    
    @keyframes float1 {{
      0% {{ transform: translateY(0px); }}
      50% {{ transform: translateY(-6px); }}
      100% {{ transform: translateY(0px); }}
    }}
    @keyframes float2 {{
      0% {{ transform: translateY(0px); }}
      50% {{ transform: translateY(-9px); }}
      100% {{ transform: translateY(0px); }}
    }}
    @keyframes float3 {{
      0% {{ transform: translateY(0px); }}
      50% {{ transform: translateY(6px); }}
      100% {{ transform: translateY(0px); }}
    }}
    @keyframes float4 {{
      0% {{ transform: translateY(0px); }}
      50% {{ transform: translateY(9px); }}
      100% {{ transform: translateY(0px); }}
    }}
    .float-icon-1 {{ animation: float1 5s ease-in-out infinite; }}
    .float-icon-2 {{ animation: float2 6.5s ease-in-out infinite; }}
    .float-icon-3 {{ animation: float3 5.8s ease-in-out infinite; }}
    .float-icon-4 {{ animation: float4 7.2s ease-in-out infinite; }}
    
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

  <!-- Floating Tech Stack Icons -->
  {icons_str}

  <!-- Developer Name -->
  <text x="500" y="115" text-anchor="middle" dominant-baseline="middle" class="title" filter="url(#shadow)">Haritha Sivasankaran</text>
</svg>"""

    # Generate v5 file to bypass cache
    banner_path = Path("assets/profile-banner-v5.svg")
    banner_path.write_text(svg_content, encoding="utf-8")
    print("OK: Banner SVG generated successfully at assets/profile-banner-v5.svg!")

if __name__ == "__main__":
    main()
