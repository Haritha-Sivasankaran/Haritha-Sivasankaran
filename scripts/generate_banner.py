import base64
import json
import re
import urllib.request
from pathlib import Path

# Cache path for icons if needed (retaining original structure)
CACHE_DIR = Path("scripts")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
cache_path = CACHE_DIR / "banner_icons_cache.json"

def main():
    # Netflix profile avatars definitions (drawn in raw vectors inside the SVG)
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 320" width="1000" height="320">
  <defs>
    <linearGradient id="pageBg" x1="0" y1="0" x2="1000" y2="320" gradientUnits="userSpaceOnUse">
      <stop stop-color="#050505" />
      <stop offset="0.5" stop-color="#0b0b0f" />
      <stop offset="1" stop-color="#040406" />
    </linearGradient>

    <!-- Glass gradients -->
    <linearGradient id="appleGlass" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#3B82F6" stop-opacity="0.9" />
      <stop offset="100%" stop-color="#8B5CF6" stop-opacity="0.9" />
    </linearGradient>
    <linearGradient id="appleBubble" cx="30%" cy="30%" r="70%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.5" />
      <stop offset="60%" stop-color="#0071e3" stop-opacity="0.8" />
      <stop offset="100%" stop-color="#8B5CF6" stop-opacity="0.9" />
    </linearGradient>

    <!-- Glow filters -->
    <filter id="glowNothing" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="6" result="blur" />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
    <filter id="glowSpotify" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="8" result="blur" />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>
  </defs>

  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;700;800&amp;family=DotGothic16&amp;family=IBM+Plex+Mono:wght@600&amp;display=swap');
    
    .title-who {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-weight: 800;
      fill: #ffffff;
      font-size: 34px;
      letter-spacing: -0.5px;
    }
    
    .profile-card {
      transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      cursor: pointer;
    }
    
    .profile-card:hover {
      transform: translateY(-8px);
    }
    
    .avatar-border {
      stroke: transparent;
      stroke-width: 3;
      transition: stroke 0.25s, filter 0.25s;
    }
    
    .profile-card:hover .avatar-border {
      stroke: #ffffff;
      filter: drop-shadow(0 4px 12px rgba(255, 255, 255, 0.25));
    }
    
    .card-nothing:hover .avatar-border {
      stroke: #eb4034;
      filter: drop-shadow(0 4px 15px rgba(235, 64, 52, 0.4));
    }
    
    .card-spotify:hover .avatar-border {
      stroke: #1db954;
      filter: drop-shadow(0 4px 15px rgba(29, 185, 84, 0.4));
    }
    
    .card-apple:hover .avatar-border {
      stroke: #0071e3;
      filter: drop-shadow(0 4px 15px rgba(0, 113, 227, 0.4));
    }
    
    .card-arc:hover .avatar-border {
      stroke: #8b5cf6;
      filter: drop-shadow(0 4px 15px rgba(139, 92, 246, 0.4));
    }

    .label-text {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-weight: 500;
      fill: #7f7f7f;
      font-size: 14px;
      transition: fill 0.25s;
    }
    
    .profile-card:hover .label-text {
      fill: #ffffff;
    }
    
    .card-nothing:hover .label-text {
      fill: #eb4034;
      font-family: 'DotGothic16', sans-serif;
    }
    
    .card-spotify:hover .label-text {
      fill: #1db954;
    }
    
    .card-apple:hover .label-text {
      fill: #3B82F6;
    }
    
    .card-arc:hover .label-text {
      fill: #8b5cf6;
    }
    
    @keyframes blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.2; }
    }
    .nothing-red-dot {
      animation: blink 1.5s infinite;
    }
  </style>

  <!-- Background Base -->
  <rect width="1000" height="320" rx="16" fill="url(#pageBg)" />
  <rect width="997" height="317" x="1.5" y="1.5" rx="14.5" stroke="rgba(255,255,255,0.04)" stroke-width="1.4" fill="none" />

  <!-- Title Text -->
  <text x="500" y="65" text-anchor="middle" class="title-who">Who is exploring Haritha's workspace?</text>

  <!-- PROFILE 1: NOTHING OS (MONOCHROME RETRO MATRIX) -->
  <a href="#-build-receipts" class="profile-card card-nothing">
    <g transform="translate(180, 100)">
      <!-- Avatar frame -->
      <rect x="0" y="0" width="110" height="110" rx="8" fill="#000000" stroke="#222" stroke-width="1" />
      <!-- Grid dots -->
      <pattern id="matrixPattern" width="6" height="6" patternUnits="userSpaceOnUse">
        <circle cx="3" cy="3" r="0.8" fill="#444" />
      </pattern>
      <rect x="5" y="5" width="100" height="100" fill="url(#matrixPattern)" />
      <!-- Blinking LED indicator -->
      <circle cx="55" cy="55" r="4.5" fill="#eb4034" filter="url(#glowNothing)" class="nothing-red-dot" />
      <!-- Outer hover border overlay -->
      <rect x="0" y="0" width="110" height="110" rx="8" fill="none" class="avatar-border" />
      <!-- Label -->
      <text x="55" y="135" text-anchor="middle" class="label-text">Nothing OS</text>
    </g>
  </a>

  <!-- PROFILE 2: APPLE LIQUID GLASS (TRANSLUCENT GLOW) -->
  <a href="#-full-stack-overview" class="profile-card card-apple">
    <g transform="translate(340, 100)">
      <!-- Avatar frame -->
      <rect x="0" y="0" width="110" height="110" rx="22" fill="#0c0d12" stroke="#1e293b" stroke-width="1" />
      <!-- Glossy bubble -->
      <circle cx="55" cy="55" r="30" fill="url(#appleBubble)" />
      <!-- Glass glare layer -->
      <path d="M 25 35 Q 55 45 85 35 Q 70 20 55 20 T 25 35" fill="#ffffff" fill-opacity="0.15" />
      <!-- Outer hover border overlay -->
      <rect x="0" y="0" width="110" height="110" rx="22" fill="none" class="avatar-border" />
      <!-- Label -->
      <text x="55" y="135" text-anchor="middle" class="label-text">Liquid Glass</text>
    </g>
  </a>

  <!-- PROFILE 3: SPOTIFY WRAPPED (MUSIC PLAYER WIDGET) -->
  <a href="#-2026-developer-wrapped" class="profile-card card-spotify">
    <g transform="translate(500, 100)">
      <!-- Avatar frame -->
      <rect x="0" y="0" width="110" height="110" rx="12" fill="#121212" stroke="#282828" stroke-width="1" />
      <!-- Vinyl record visual -->
      <circle cx="55" cy="55" r="36" fill="#000000" />
      <circle cx="55" cy="55" r="28" fill="none" stroke="#282828" stroke-width="1" stroke-dasharray="3 3" />
      <circle cx="55" cy="55" r="20" fill="none" stroke="#282828" stroke-width="1" />
      <circle cx="55" cy="55" r="10" fill="#1db954" />
      <circle cx="55" cy="55" r="2.5" fill="#121212" />
      <!-- Outer hover border overlay -->
      <rect x="0" y="0" width="110" height="110" rx="12" fill="none" class="avatar-border" />
      <!-- Label -->
      <text x="55" y="135" text-anchor="middle" class="label-text">Wrapped</text>
    </g>
  </a>

  <!-- PROFILE 4: ARC BROWSER (SIDEBAR FRAME) -->
  <a href="https://www.linkedin.com/in/haritha-sivasankaran/" target="_blank" class="profile-card card-arc">
    <g transform="translate(660, 100)">
      <!-- Avatar frame -->
      <rect x="0" y="0" width="110" height="110" rx="12" fill="#181824" stroke="#2d2d3d" stroke-width="1" />
      <!-- Simulated Arc Sidebar wireframe -->
      <rect x="10" y="10" width="24" height="90" rx="4" fill="#242435" />
      <rect x="42" y="10" width="58" height="90" rx="4" fill="#11111a" />
      <!-- Mini circles representing workspace tabs inside sidebar -->
      <circle cx="22" cy="22" r="3.5" fill="#8b5cf6" />
      <circle cx="22" cy="34" r="3.5" fill="#10b981" />
      <circle cx="22" cy="46" r="3.5" fill="#3B82F6" />
      <!-- Outer hover border overlay -->
      <rect x="0" y="0" width="110" height="110" rx="12" fill="none" class="avatar-border" />
      <!-- Label -->
      <text x="55" y="135" text-anchor="middle" class="label-text">Arc Sidebar</text>
    </g>
  </a>

</svg>
"""

    # Generate banner SVG
    banner_path = Path("assets/profile-banner-v5.svg")
    banner_path.write_text(svg_content, encoding="utf-8")
    print("OK: Netflix Profile Selector Banner generated successfully at assets/profile-banner-v5.svg!")

if __name__ == "__main__":
    main()
