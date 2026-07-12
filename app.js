// --- Global Application State & Fallback Data ---
let appData = {
  username: "Haritha-Sivasankaran",
  name: "Haritha Sivasankaran",
  contributions_365d: 418,
  active_days: 41,
  peak_day: 46,
  public_repos: 12,
  private_repos: 7,
  stars_earned: 2,
  language_breakdown: [
    { name: "Jupyter Notebook", percent: 21.47 },
    { name: "JavaScript", percent: 16.8 },
    { name: "TypeScript", percent: 16.39 },
    { name: "Python", percent: 14.96 },
    { name: "Java", percent: 14.65 },
    { name: "HTML", percent: 9.97 }
  ],
  weekly_totals: [
    { start: "2026-04-19", total: 1 },
    { start: "2026-04-26", total: 0 },
    { start: "2026-05-03", total: 0 },
    { start: "2026-05-10", total: 0 },
    { start: "2026-05-17", total: 26 },
    { start: "2026-05-24", total: 88 },
    { start: "2026-05-31", total: 23 },
    { start: "2026-06-07", total: 67 },
    { start: "2026-06-14", total: 99 },
    { start: "2026-06-21", total: 32 },
    { start: "2026-06-28", total: 42 },
    { start: "2026-07-05", total: 20 }
  ],
  longest_streak: 8,
  weekday_counts: [49, 36, 44, 66, 77, 81, 65],
  top_repo_name: "Obsidian-Chess",
  top_repo_lang: "JavaScript",
  top_track_name: "CHANGELOG.md",
  focus_repo_name: "TransitPulse-2.0",
  focus_repo_lang: "JavaScript"
};

// Language Colors Palette
const LANGUAGE_COLORS = {
  "Python": "#60A5FA",
  "HTML": "#3B82F6",
  "JavaScript": "#F59E0B",
  "TypeScript": "#3B82F6",
  "CSS": "#8B5CF6",
  "Java": "#8B5CF6",
  "Jupyter Notebook": "#10B981",
  "React": "#60A5FA",
  "MySQL": "#22C55E",
  "Angular": "#DD0031",
  "Vue": "#4FC08D",
  "Svelte": "#FF3E00",
};

// Initial Memories in ChatGPT Bank
let memoryBank = {
  tech: [
    "Adept in Java (Spring Boot & Spring AI) and Python (data analytics & automation).",
    "Frontend tools include React, Angular, Vue.js, Svelte, and Next.js with TypeScript.",
    "Handles Bitbucket/GitLab pipelines, Docker containers, and Ansible playbook deployments."
  ],
  behavior: [
    "Shows consistent midweek commitment peak (Wednesdays and Thursdays).",
    "Often works late-night streams or runs automated telemetry pipelines.",
    "Maintains active private workspace grind (87% of total work is private)."
  ],
  personal: [
    "Prefers dark, highly-visual telemetry displays (monochrome & glass).",
    "Active project: Obsidian Chess (offline JavaScript chess engine).",
    "Listens to tech stack progress updates via Spotify Wrapped."
  ]
};

// Spotify playlist
const TRACKS_PLAYLIST = [
  { name: "dspy_pipeline.py", artist: "Active Repo: Obsidian-Chess", duration: 222, repo: "Obsidian-Chess", details: "128 UPDATES · ACTIVE PIPELINE" },
  { name: "transitpulse.py", artist: "Active Repo: TransitPulse-2.0", duration: 180, repo: "TransitPulse-2.0", details: "92 UPDATES · KAFKA ROUTER" },
  { name: "generate_profile_assets.py", artist: "Active Repo: Haritha-Sivasankaran", duration: 245, repo: "Haritha-Sivasankaran", details: "418 UPDATES · TELEMETRY SCRIPT" },
  { name: "generate_banner.py", artist: "Active Repo: Haritha-Sivasankaran", duration: 142, repo: "Haritha-Sivasankaran", details: "56 UPDATES · SVG BANNER BUILD" }
];
let currentTrackIndex = 0;
let isPlaying = false;
let playSeconds = 0;
let playInterval = null;
let isShuffle = false;
let isRepeat = false;

// --- Initialize App ---
document.addEventListener("DOMContentLoaded", async () => {
  // Try to load real data
  try {
    const response = await fetch(`assets/profile-data.json?t=${Date.now()}`);
    if (response.ok) {
      const data = await response.json();
      appData = { ...appData, ...data };
      console.log("Telemetry loaded successfully from assets.", appData);
    }
  } catch (err) {
    console.warn("Could not fetch profile-data.json, using static fallback telemetry.", err);
  }

  // Populate UI
  populateTelemetryData();
  populateMemoryLogs();
  initLiquidGlassCards();
  initSpotifyPlayer();

  // Hide loader
  const loader = document.getElementById("loader");
  if (loader) {
    setTimeout(() => {
      loader.classList.add("fade-out");
      document.body.classList.remove("loading-state");
    }, 400);
  }

  // Netflix-style Theme Selector Bar actions
  const profileBarCards = document.querySelectorAll(".profile-bar-card");
  profileBarCards.forEach(card => {
    card.addEventListener("click", () => {
      profileBarCards.forEach(c => c.classList.remove("active"));
      card.classList.add("active");
      
      const theme = card.getAttribute("data-theme");
      applyTheme(theme);
      showToast(`${card.querySelector('.profile-bar-name').innerText} Mode`, `Theme updated to match style layout.`);
    });
  });

  // Setup Arc Sidebar navigation click to smooth-scroll
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const targetId = tab.getAttribute("data-scroll");
      const targetElement = document.getElementById(targetId);
      if (targetElement) {
        // Remove active class from all tabs, add to clicked
        tabs.forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        
        // Update URL path string
        const cleanName = targetId.replace("section-", "");
        document.getElementById("current-url").innerText = cleanName;

        // Smooth scroll
        targetElement.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });

  // Sidebar Workspace Button Theme Swapper
  const wsButtons = document.querySelectorAll(".workspace-btn");
  wsButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      wsButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      
      const theme = btn.getAttribute("data-theme");
      applyTheme(theme);

      // Sync active state in the inline Netflix bar
      profileBarCards.forEach(card => {
        if (card.getAttribute("data-theme") === theme) {
          card.classList.add("active");
        } else {
          card.classList.remove("active");
        }
      });
      
      showToast("Workspace Shifted", `Switched to visual theme: ${theme.toUpperCase()}`);
    });
  });

  // Reload action
  document.getElementById("btn-reload").addEventListener("click", () => {
    const btn = document.getElementById("btn-reload");
    btn.style.transform = "rotate(360deg)";
    btn.style.transition = "transform 0.5s ease";
    setTimeout(() => {
      btn.style.transform = "none";
      btn.style.transition = "none";
    }, 500);
    populateTelemetryData();
    showToast("Telemetry Reloaded", "Refreshed numbers from internal JSON cache.");
  });

  // ChatGPT Memory Form submit
  const addMemoryForm = document.getElementById("add-memory-form");
  addMemoryForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = document.getElementById("memory-input-text");
    const text = input.value.trim();
    if (!text) return;

    // Distribute memory based on keyword detection
    let category = "personal";
    const textLower = text.toLowerCase();
    if (textLower.includes("java") || textLower.includes("python") || textLower.includes("react") || textLower.includes("js") || textLower.includes("ts") || textLower.includes("docker") || textLower.includes("sql") || textLower.includes("code") || textLower.includes("stack") || textLower.includes("kafka")) {
      category = "tech";
    } else if (textLower.includes("commit") || textLower.includes("pipeline") || textLower.includes("midweek") || textLower.includes("night") || textLower.includes("work") || textLower.includes("grind") || textLower.includes("telemetry")) {
      category = "behavior";
    }

    memoryBank[category].push(text);
    input.value = "";
    populateMemoryLogs();
    showToast("Memory memorized", `Added to ChatGPT memory bank under ${category.toUpperCase()}`);
  });

  // Clear Memories
  document.getElementById("btn-clear-memories").addEventListener("click", () => {
    memoryBank.tech = [];
    memoryBank.behavior = [];
    memoryBank.personal = [];
    populateMemoryLogs();
    showToast("Memories Cleared", "Forgetfulness is absolute. Memory bank is empty.");
  });

  // Set up Scroll Spy to highlight sidebar tabs based on scroll position
  setupScrollSpy();
});

// --- Theme Application ---
function applyTheme(theme) {
  document.body.className = "";
  document.body.classList.add(`theme-${theme}`);
  
  // Update sidebar active workspace button
  const wsButtons = document.querySelectorAll(".workspace-btn");
  wsButtons.forEach(btn => {
    if (btn.getAttribute("data-theme") === theme) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  // Update URL Sync labels
  const syncLabel = document.getElementById("sync-mode-label");
  if (theme === "nothing") {
    syncLabel.innerText = "MONOCHROME · ONLINE";
  } else if (theme === "apple") {
    syncLabel.innerText = "LIQUID GLASS LINKED";
  } else if (theme === "spotify") {
    syncLabel.innerText = "WRAPPED TELEMETRY";
  } else {
    syncLabel.innerText = "TOKEN SYNCED";
  }
}

// --- Scroll Spy Implementation ---
function setupScrollSpy() {
  const scrollContainer = document.getElementById("viewport-scroll-container");
  const sections = document.querySelectorAll(".scroll-section");
  const navTabs = document.querySelectorAll(".nav-tab");
  
  const observerOptions = {
    root: scrollContainer,
    rootMargin: "-20% 0px -60% 0px", // triggers when section is in upper-mid viewport
    threshold: 0
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.getAttribute("id");
        
        // Highlight corresponding navigation tab
        navTabs.forEach(tab => {
          if (tab.getAttribute("data-scroll") === id) {
            tab.classList.add("active");
            
            // Update URL bar text based on current section
            const cleanName = id.replace("section-", "");
            document.getElementById("current-url").innerText = cleanName;
          } else {
            tab.classList.remove("active");
          }
        });
      }
    });
  }, observerOptions);

  sections.forEach(section => observer.observe(section));
}

// --- Populate Telemetry Data ---
function populateTelemetryData() {
  document.getElementById("stat-total-contribs").innerText = formatNumber(appData.contributions_365d);
  document.getElementById("stat-active-days").innerText = appData.active_days;
  document.getElementById("stat-peak-day").innerText = appData.peak_day;
  document.getElementById("stat-repos-count").innerText = appData.public_repos + (appData.private_repos || 0);
  document.getElementById("stat-stars-earned").innerText = appData.stars_earned;

  // Render language frequencies
  const track = document.getElementById("lang-bar-track");
  const list = document.getElementById("lang-list-grid");
  
  if (track && list) {
    track.innerHTML = "";
    list.innerHTML = "";

    // Normalize languages
    const totalBytesPercent = appData.language_breakdown.reduce((sum, item) => sum + item.percent, 0);

    appData.language_breakdown.forEach((lang, index) => {
      const color = LANGUAGE_COLORS[lang.name] || "#6b7280";
      const normalizedPercent = (lang.percent / totalBytesPercent) * 100;
      
      // Add bar segment
      const segment = document.createElement("div");
      segment.className = "language-bar-segment";
      segment.style.width = `${normalizedPercent}%`;
      segment.style.backgroundColor = color;
      track.appendChild(segment);

      // Add row
      const row = document.createElement("div");
      row.className = "language-row";
      row.innerHTML = `
        <div class="lang-header-row font-sans">
          <span class="lang-color-dot" style="background-color: ${color}"></span>
          <span>${escapeHTML(lang.name)}</span>
          <span class="lang-pct font-mono">${lang.percent.toFixed(1)}%</span>
        </div>
        <div class="lang-progress-bg">
          <div class="lang-progress-fill" style="width: ${normalizedPercent}%; background-color: ${color}"></div>
        </div>
      `;
      list.appendChild(row);
    });
  }

  // Draw Activity Tempo SVG Chart
  drawTempoChart();
}

// --- Draw SVG Tempo Chart ---
function drawTempoChart() {
  const svg = document.getElementById("tempo-chart-svg");
  if (!svg) return;

  svg.innerHTML = "";
  
  const width = 300;
  const height = 110;
  const padding = 15;
  const chartHeight = height - padding * 2;
  const chartWidth = width - padding * 2;

  const data = appData.weekly_totals;
  if (!data || data.length === 0) return;

  const totals = data.map(w => w.total);
  const maxTotal = Math.max(...totals, 1);
  const step = chartWidth / (data.length - 1);

  // Generate points
  const points = data.map((week, index) => {
    const x = padding + step * index;
    const ratio = week.total / maxTotal;
    const y = padding + chartHeight - (ratio * chartHeight);
    return { x, y, val: week.total, date: week.start };
  });

  // Create paths
  let linePathD = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;
  let areaPathD = `M ${points[0].x.toFixed(1)} ${height - padding} L ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;

  for (let i = 1; i < points.length; i++) {
    linePathD += ` L ${points[i].x.toFixed(1)} ${points[i].y.toFixed(1)}`;
    areaPathD += ` L ${points[i].x.toFixed(1)} ${points[i].y.toFixed(1)}`;
  }
  areaPathD += ` L ${points[points.length - 1].x.toFixed(1)} ${height - padding} Z`;

  // Draw elements
  svg.innerHTML = `
    <!-- Defs for gradients -->
    <defs>
      <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.25"></stop>
        <stop offset="100%" stop-color="var(--accent)" stop-opacity="0"></stop>
      </linearGradient>
    </defs>

    <!-- Grid line -->
    <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="var(--border)" stroke-width="1"></line>
    
    <!-- Area under chart -->
    <path d="${areaPathD}" fill="url(#chartFill)"></path>
    
    <!-- Line path -->
    <path d="${linePathD}" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"></path>
  `;

  // Draw dots
  points.forEach((pt, idx) => {
    const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("cx", pt.x);
    dot.setAttribute("cy", pt.y);
    dot.setAttribute("r", "3.5");
    dot.setAttribute("fill", "var(--bg-frame)");
    dot.setAttribute("stroke", "var(--accent)");
    dot.setAttribute("stroke-width", "2");
    dot.style.cursor = "pointer";
    
    dot.addEventListener("mouseenter", () => {
      dot.setAttribute("r", "5.5");
      dot.setAttribute("fill", "var(--accent)");
      showToast(`${pt.date}`, `${pt.val} commits this week`);
    });
    dot.addEventListener("mouseleave", () => {
      dot.setAttribute("r", "3.5");
      dot.setAttribute("fill", "var(--bg-frame)");
    });

    svg.appendChild(dot);
  });
}

// --- ChatGPT Memory Logs Management ---
function populateMemoryLogs() {
  const lists = {
    tech: document.getElementById("mem-list-tech"),
    behavior: document.getElementById("mem-list-behavior"),
    personal: document.getElementById("mem-list-personal")
  };

  Object.keys(lists).forEach(category => {
    const listElement = lists[category];
    if (!listElement) return;

    listElement.innerHTML = "";

    if (memoryBank[category].length === 0) {
      listElement.innerHTML = `<li class="font-mono" style="color: var(--text-secondary); font-size: 11px; padding: 10px;">No memories in bank</li>`;
      return;
    }

    memoryBank[category].forEach((memory, index) => {
      const li = document.createElement("li");
      li.className = "memory-item font-sans";
      li.innerHTML = `
        <span>${escapeHTML(memory)}</span>
        <button class="btn-forget-memory" title="Forget Memory">&times;</button>
      `;

      li.querySelector(".btn-forget-memory").addEventListener("click", () => {
        li.classList.add("removing");
        setTimeout(() => {
          memoryBank[category].splice(index, 1);
          populateMemoryLogs();
          showToast("Memory Forgotten", "Forget action complete. Item removed.");
        }, 300);
      });

      listElement.appendChild(li);
    });
  });
}

// --- Apple Liquid Glass Mouse reflections ---
function initLiquidGlassCards() {
  const cards = document.querySelectorAll(".liquid-glass-card");
  
  cards.forEach(card => {
    card.addEventListener("mousemove", (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      card.style.setProperty("--mouse-x", `${x}px`);
      card.style.setProperty("--mouse-y", `${y}px`);
    });
  });
}

// --- Spotify Media Player Logics ---
function initSpotifyPlayer() {
  updateTrackDisplay();

  const playBtn = document.getElementById("btn-player-play-pause");
  const prevBtn = document.getElementById("btn-player-prev");
  const nextBtn = document.getElementById("btn-player-next");
  const shuffleBtn = document.getElementById("btn-player-shuffle");
  const repeatBtn = document.getElementById("btn-player-repeat");
  const timelineScrubber = document.getElementById("timeline-scrubber");

  playBtn.addEventListener("click", togglePlay);
  prevBtn.addEventListener("click", playPrev);
  nextBtn.addEventListener("click", playNext);
  
  shuffleBtn.addEventListener("click", () => {
    isShuffle = !isShuffle;
    shuffleBtn.style.color = isShuffle ? "var(--accent)" : "#9ca3af";
    showToast("Shuffle Toggled", isShuffle ? "Playlist shuffle enabled." : "Shuffle disabled.");
  });

  repeatBtn.addEventListener("click", () => {
    isRepeat = !isRepeat;
    repeatBtn.style.color = isRepeat ? "var(--accent)" : "#9ca3af";
    showToast("Repeat Toggled", isRepeat ? "Track repeat enabled." : "Repeat disabled.");
  });

  timelineScrubber.addEventListener("click", (e) => {
    const rect = timelineScrubber.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const totalWidth = rect.width;
    const ratio = clickX / totalWidth;
    
    const track = TRACKS_PLAYLIST[currentTrackIndex];
    playSeconds = Math.floor(ratio * track.duration);
    updateProgressBar();
  });
}

function updateTrackDisplay() {
  const track = TRACKS_PLAYLIST[currentTrackIndex];
  
  document.getElementById("wrapped-track-name").innerText = track.name;
  document.getElementById("wrapped-track-details").innerText = track.details;
  document.getElementById("player-title").innerText = track.name;
  document.getElementById("player-artist").innerText = track.artist;
  document.getElementById("player-time-total").innerText = formatTime(track.duration);
  
  playSeconds = 0;
  updateProgressBar();

  const appArchetype = document.getElementById("wrapped-archetype-title");
  const appArchetypeSub = document.getElementById("wrapped-archetype-sub");
  const appArchetypeDesc = document.getElementById("wrapped-archetype-desc");
  
  if (currentTrackIndex === 0) {
    appArchetype.innerText = "The Architect";
    appArchetypeSub.innerText = "FULL STACK ENGINEER";
    appArchetypeDesc.innerText = "Designing reliable Spring Boot backend layers integrated with React frontend nodes.";
  } else if (currentTrackIndex === 1) {
    appArchetype.innerText = "The Explorer";
    appArchetypeSub.innerText = "ASYNCHRONOUS DEVS";
    appArchetypeDesc.innerText = "Chasing real-time streams, building data pipelines with Apache Kafka and fast routes.";
  } else if (currentTrackIndex === 2 || currentTrackIndex === 3) {
    appArchetype.innerText = "The Artisan";
    appArchetypeSub.innerText = "FRONTEND CRAFTER";
    appArchetypeDesc.innerText = "Sculpting modern layouts with sleek interactive cues, premium glass aesthetics, and dot matrix details.";
  }
}

function togglePlay() {
  isPlaying = !isPlaying;
  const playBtn = document.getElementById("btn-player-play-pause");
  const reels = document.querySelectorAll(".reel");
  
  if (isPlaying) {
    playBtn.innerText = "⏸️";
    reels.forEach(reel => reel.classList.remove("paused"));
    
    playInterval = setInterval(() => {
      const track = TRACKS_PLAYLIST[currentTrackIndex];
      playSeconds++;
      
      if (playSeconds >= track.duration) {
        if (isRepeat) {
          playSeconds = 0;
        } else {
          playNext();
          return;
        }
      }
      updateProgressBar();
    }, 1000);
  } else {
    playBtn.innerText = "▶️";
    reels.forEach(reel => reel.classList.add("paused"));
    clearInterval(playInterval);
  }
}

function playNext() {
  if (isShuffle) {
    currentTrackIndex = Math.floor(Math.random() * TRACKS_PLAYLIST.length);
  } else {
    currentTrackIndex = (currentTrackIndex + 1) % TRACKS_PLAYLIST.length;
  }
  
  const wasPlaying = isPlaying;
  if (isPlaying) togglePlay();
  
  updateTrackDisplay();
  
  if (wasPlaying) togglePlay();
}

function playPrev() {
  currentTrackIndex = (currentTrackIndex - 1 + TRACKS_PLAYLIST.length) % TRACKS_PLAYLIST.length;
  const wasPlaying = isPlaying;
  if (isPlaying) togglePlay();
  updateTrackDisplay();
  if (wasPlaying) togglePlay();
}

function updateProgressBar() {
  const track = TRACKS_PLAYLIST[currentTrackIndex];
  const progressPercent = (playSeconds / track.duration) * 100;
  
  document.getElementById("player-progress-fill").style.width = `${progressPercent}%`;
  document.getElementById("player-progress-thumb").style.left = `${progressPercent}%`;
  document.getElementById("player-time-current").innerText = formatTime(playSeconds);
}

// --- Toast / Notification Mechanism ---
let toastTimeout = null;
function showToast(title, text) {
  const toast = document.getElementById("toast");
  const toastTitle = toast.querySelector(".toast-title");
  const toastText = document.getElementById("toast-text-msg");
  
  toastTitle.innerText = title;
  toastText.innerText = text;
  
  clearTimeout(toastTimeout);
  toast.classList.add("active");
  
  toastTimeout = setTimeout(() => {
    toast.classList.remove("active");
  }, 3500);
}

// --- Helpers ---
function formatNumber(num) {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function formatTime(secs) {
  const minutes = Math.floor(secs / 60);
  const seconds = secs % 60;
  return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
}

function escapeHTML(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
