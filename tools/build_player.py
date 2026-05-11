"""
웹 플레이어 빌더 (v3.0).

기능: 연속재생, 반복버튼 수정, 청취횟수, 검색
"""

import argparse
import json
import re
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from src.config import OUTPUT_MP3_DIR, SUPABASE_URL, SUPABASE_BUCKET_NAME

def parse_filename(stem: str) -> dict:
    info = {"episode": None, "category": "", "subtitle": stem, "date": "", "date_compact": ""}
    parts = stem.split("_")
    if not parts: return info
    try:
        info["episode"] = int(parts[0])
    except: pass
    if len(parts) >= 2:
        last = parts[-1]
        if re.match(r'^\d{8}$', last):
            info["date_compact"] = last
            info["date"] = f"{last[:4]}.{last[4:6]}.{last[6:8]}"
            parts = parts[:-1]
    if len(parts) >= 2:
        info["category"] = parts[1]
        info["subtitle"] = " ".join(parts[2:]) if len(parts) > 2 else ""
    return info

def collect_episodes(output_dir: Path) -> list:
    episodes = []
    allowed_episodes = set()
    if SUPABASE_URL:
        try:
            from supabase import create_client
            import os
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
            client = create_client(SUPABASE_URL, key)
            res = client.table("episodes").select("episode_num").execute()
            allowed_episodes = {row["episode_num"] for row in res.data if row.get("episode_num")}
        except Exception: pass

    for mp3_path in sorted(output_dir.glob("*.mp3")):
        stem = mp3_path.stem
        player_json = output_dir / f"{stem}_player.json"
        if not player_json.exists(): continue
        try:
            with open(player_json, 'r', encoding='utf-8') as f:
                player_data = json.load(f)
        except: continue
        meta = parse_filename(stem)
        if SUPABASE_URL and allowed_episodes:
            if meta.get("episode") not in allowed_episodes: continue
        meta["stem"] = stem
        scripts = player_data.get("script", [])
        meta["duration"] = max(s.get("end", 0) for s in scripts) if scripts else 0
        episodes.append(meta)
    episodes.sort(key=lambda e: (e["episode"] or 0, e["date_compact"]), reverse=True)
    return episodes

# DYNAMIC_PLAYER_TEMPLATE: __EPISODE_LIST__ placeholder is replaced at build time
DYNAMIC_PLAYER_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title id="pageTitle">학습 플레이어</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
<style>
:root {
  --bg: #0f172a; --panel: #1e293b; --accent: #38bdf8; --text: #f1f5f9; --muted: #94a3b8;
}
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
body { background: var(--bg); color: var(--text); font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 0; line-height: 1.6; overflow-x: hidden; }

.app { display: flex; flex-direction: column; height: 100vh; max-width: 800px; margin: 0 auto; }
header { padding: 16px; background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(10px); position: sticky; top: 0; z-index: 100; border-bottom: 1px solid rgba(255,255,255,0.1); }
.nav-top { display: flex; align-items: center; gap: 15px; margin-bottom: 12px; }
.back-btn { color: var(--muted); text-decoration: none; font-size: 28px; flex-shrink: 0; }
.title-area { flex: 1; min-width: 0; }
.title-area h1 { margin: 0; font-size: 22px; font-weight: bold; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.play-count-badge { font-size: 13px; color: #4ade80; font-weight: 600; margin-top: 2px; display: none; }

.player-container { background: var(--panel); padding: 16px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1); }
audio { width: 100%; height: 54px; border-radius: 12px; }

.controls-row { display: flex; align-items: center; justify-content: space-between; margin-top: 15px; gap: 10px; }
.btn-group { display: flex; gap: 6px; background: rgba(0,0,0,0.3); padding: 6px; border-radius: 12px; }
.ctrl-btn { background: none; border: none; color: var(--muted); padding: 10px 14px; border-radius: 10px; cursor: pointer; font-size: 17px; transition: 0.2s; display: flex; align-items: center; gap: 5px; white-space: nowrap; }
.ctrl-btn.active { background: var(--accent); color: white; }
.ctrl-btn.repeat-full { background: #a855f7; color: white; }
.speed-val { min-width: 60px; text-align: center; font-weight: bold; color: var(--accent); font-size: 20px; }

.script-container { flex: 1; overflow-y: auto; padding: 16px; scroll-behavior: smooth; }
.line { padding: 20px; margin-bottom: 15px; background: rgba(255,255,255,0.04); border-radius: 16px; border: 1px solid rgba(255,255,255,0.06); transition: 0.3s; cursor: pointer; }
.line:active { transform: scale(0.97); background: rgba(255,255,255,0.1); }
.line.current { background: rgba(56, 189, 248, 0.2); border-color: var(--accent); box-shadow: 0 0 20px rgba(56, 189, 248, 0.1); }
.line .time { font-size: 14px; color: var(--accent); font-weight: bold; margin-bottom: 8px; }
.line .text { font-size: 22px; font-weight: 500; word-break: keep-all; line-height: 1.4; color: #fff; }

#loader { position: fixed; inset: 0; background: var(--bg); display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 1000; }
.spinner { width: 50px; height: 50px; border: 5px solid var(--panel); border-top-color: var(--accent); border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 20px; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div id="loader"><div class="spinner"></div><div style="font-size:20px;">로딩 중...</div></div>
<div class="app">
  <header>
    <div class="nav-top">
      <a href="index.html" class="back-btn"><i class="bi bi-chevron-left"></i></a>
      <div class="title-area">
        <h1 id="title">로딩 중...</h1>
        <div class="play-count-badge" id="playCountBadge"></div>
      </div>
    </div>
    <div class="player-container">
      <audio id="player" controls controlsList="nodownload noplaybackrate"></audio>
      <div class="controls-row">
        <div class="btn-group">
          <button class="ctrl-btn" onclick="changeSpeed(-0.1)"><i class="bi bi-dash-lg"></i></button>
          <div class="ctrl-btn speed-val" id="speedDisp">1.0x</div>
          <button class="ctrl-btn" onclick="changeSpeed(0.1)"><i class="bi bi-plus-lg"></i></button>
        </div>
        <div class="btn-group">
          <button id="repeatBtn" class="ctrl-btn" onclick="toggleRepeat()"><i class="bi bi-repeat"></i> 반복</button>
          <button id="autoNextBtn" class="ctrl-btn" onclick="toggleAutoNext()"><i class="bi bi-collection-play"></i> 연속</button>
        </div>
      </div>
    </div>
  </header>
  <main class="script-container" id="scriptList"></main>
</div>
<script>
const EPISODE_LIST = __EPISODE_LIST__;

let SCRIPT = [];
let repeatMode = 0; // 0=off, 1=구간반복, 2=전체반복
let isAutoNext = false;
let currentIdx = -1;
const player = document.getElementById('player');
const scriptList = document.getElementById('scriptList');

async function init() {
  const params = new URLSearchParams(window.location.search);
  const rawId = params.get('id');
  if(!rawId) {
    document.getElementById('loader').innerHTML = '<div>❌ 회차 ID가 없습니다.</div>';
    return;
  }

  const id = decodeURIComponent(rawId);

  try {
    const res = await fetch(`${id}_player.json?v=${Date.now()}`);
    if (!res.ok) throw new Error(`파일을 찾을 수 없습니다 (상태: ${res.status})`);

    const data = await res.json();
    SCRIPT = data.script || [];
    document.getElementById('title').textContent = data.subtitle || id;
    document.title = data.subtitle || id;
    player.src = data.mp3_url;

    const key = 'ebs_played_' + id;
    const pdata = JSON.parse(localStorage.getItem(key) || '{}');
    pdata.play_count = (pdata.play_count || 0) + 1;
    pdata.last_played = new Date().toISOString();
    localStorage.setItem(key, JSON.stringify(pdata));
    const badge = document.getElementById('playCountBadge');
    badge.textContent = pdata.play_count + '회 청취';
    badge.style.display = 'block';

    if (SCRIPT.length === 0) {
      scriptList.innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted);">스크립트 데이터가 없습니다.</div>';
    }

    SCRIPT.forEach((s, i) => {
      const div = document.createElement('div');
      div.className = 'line';
      div.id = `line-${i}`;
      div.innerHTML = `<div class="time">${formatTime(s.start)}</div><div class="text">${s.text}</div>`;
      div.onclick = () => seekTo(i);
      scriptList.appendChild(div);
    });

    document.getElementById('loader').style.display = 'none';
  } catch(e) {
    console.error(e);
    document.getElementById('loader').innerHTML = `
      <div style="padding:20px;text-align:center;">
        <div style="font-size:40px;margin-bottom:10px;">⚠️</div>
        <div style="font-size:18px;margin-bottom:10px;color:var(--accent);font-weight:bold;">${e.message}</div>
        <div style="font-size:13px;color:var(--muted);margin-bottom:20px;">ID: ${id}</div>
        <button onclick="location.reload()" style="background:var(--accent);color:white;border:none;padding:12px 24px;border-radius:10px;font-weight:bold;cursor:pointer;">페이지 새로고침</button>
      </div>`;
  }
}

function formatTime(s) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}분 ${sec}초`;
}

function seekTo(idx) {
  if(idx < 0 || idx >= SCRIPT.length) return;
  player.currentTime = SCRIPT[idx].start;
  player.play();
  highlight(idx);
}

function highlight(idx) {
  if(currentIdx === idx) return;
  const old = document.getElementById(`line-${currentIdx}`);
  if(old) old.classList.remove('current');
  const el = document.getElementById(`line-${idx}`);
  if(el) {
    el.classList.add('current');
    currentIdx = idx;
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

player.ontimeupdate = () => {
  const t = player.currentTime;
  const idx = SCRIPT.findIndex(s => t >= s.start && t < s.end);
  if(idx !== -1) {
    highlight(idx);
  } else if(repeatMode === 1 && currentIdx >= 0 && SCRIPT[currentIdx] && t > SCRIPT[currentIdx].end) {
    player.currentTime = SCRIPT[currentIdx].start;
  }
};

player.addEventListener('ended', () => {
  if(repeatMode === 1 && currentIdx >= 0 && SCRIPT[currentIdx]) {
    player.currentTime = SCRIPT[currentIdx].start;
    player.play();
    return;
  }
  if(repeatMode === 2) {
    player.currentTime = 0;
    player.play();
    return;
  }
  if(isAutoNext) goNextEpisode();
});

function goNextEpisode() {
  const params = new URLSearchParams(window.location.search);
  const currentStem = decodeURIComponent(params.get('id') || '');
  const idx = EPISODE_LIST.findIndex(e => e.stem === currentStem);
  if(idx >= 0 && idx < EPISODE_LIST.length - 1) {
    const next = EPISODE_LIST[idx + 1];
    const loader = document.getElementById('loader');
    loader.style.display = 'flex';
    loader.innerHTML = '<div class="spinner"></div><div style="font-size:18px;">다음 회차 로딩 중...</div>';
    window.location.href = 'play.html?id=' + encodeURIComponent(next.stem);
  }
}

function changeSpeed(delta) {
  let s = Math.round((player.playbackRate + delta) * 10) / 10;
  if(s < 0.5) s = 0.5;
  if(s > 2.0) s = 2.0;
  player.playbackRate = s;
  document.getElementById('speedDisp').textContent = s.toFixed(1) + 'x';
}

function toggleRepeat() {
  repeatMode = (repeatMode + 1) % 3;
  const btn = document.getElementById('repeatBtn');
  if(repeatMode === 0) {
    btn.classList.remove('active', 'repeat-full');
    btn.innerHTML = '<i class="bi bi-repeat"></i> 반복';
  } else if(repeatMode === 1) {
    btn.classList.add('active');
    btn.classList.remove('repeat-full');
    btn.innerHTML = '<i class="bi bi-repeat-1"></i> 구간';
  } else {
    btn.classList.add('active', 'repeat-full');
    btn.innerHTML = '<i class="bi bi-repeat"></i> 전체';
  }
}

function toggleAutoNext() {
  isAutoNext = !isAutoNext;
  document.getElementById('autoNextBtn').classList.toggle('active', isAutoNext);
}

init();
</script>
</body>
</html>
"""

# DASHBOARD_TEMPLATE uses .format() so CSS/JS braces must be doubled {{}}
DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EBS 학습 대시보드</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
<style>
:root {{
  --bg: #0f172a; --panel: #1e293b; --accent: #38bdf8; --text: #f1f5f9; --muted: #94a3b8;
}}
body {{ background: var(--bg); color: var(--text); font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 0; }}
.container {{ max-width: 900px; margin: 0 auto; padding: 24px; }}
header {{ display: flex; align-items: center; gap: 15px; margin-bottom: 20px; border-bottom: 2px solid rgba(255,255,255,0.1); padding-bottom: 24px; }}
header h1 {{ margin: 0; font-size: 32px; color: var(--accent); font-weight: 800; }}
.search-bar {{ margin-bottom: 24px; position: relative; }}
.search-bar input {{
  width: 100%; padding: 16px 20px 16px 50px;
  background: var(--panel); border: 2px solid rgba(255,255,255,0.1);
  border-radius: 16px; color: var(--text); font-size: 18px;
  outline: none; box-sizing: border-box; transition: border-color 0.2s;
}}
.search-bar input:focus {{ border-color: var(--accent); }}
.search-bar input::placeholder {{ color: var(--muted); }}
.search-icon {{ position: absolute; left: 16px; top: 50%; transform: translateY(-50%); color: var(--muted); font-size: 22px; pointer-events: none; }}
.no-results {{ text-align: center; padding: 40px; color: var(--muted); font-size: 18px; display: none; }}
.grid {{ display: grid; grid-template-columns: 1fr; gap: 20px; }}
.card {{
  background: var(--panel); padding: 28px; border-radius: 24px; text-decoration: none; color: inherit;
  border: 2px solid rgba(255,255,255,0.06); transition: 0.3s; display: flex; flex-direction: column; gap: 12px;
  box-shadow: 0 4px 15px rgba(0,0,0,0.2);
}}
.card:active {{ transform: scale(0.98); background: #26354a; }}
.card .ep-top {{ display: flex; justify-content: space-between; align-items: center; }}
.card .ep-tag {{ font-size: 16px; color: var(--accent); font-weight: 800; letter-spacing: 1px; }}
.play-badge {{ font-size: 14px; color: var(--muted); font-weight: 600; display: none; }}
.play-badge.has-plays {{ display: inline; color: #4ade80; }}
.card h3 {{ margin: 0; font-size: 28px; line-height: 1.3; color: #fff; font-weight: bold; }}
.card .meta {{ font-size: 18px; color: var(--muted); display: flex; justify-content: space-between; margin-top: 10px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.08); }}
@media (min-width: 700px) {{
  .grid {{ grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); }}
}}
</style>
</head>
<body>
<div class="container">
  <header>
    <i class="bi bi-headphones" style="font-size: 40px; color: var(--accent);"></i>
    <h1>EBS 왕초보 영어</h1>
  </header>
  <div class="search-bar">
    <i class="bi bi-search search-icon"></i>
    <input type="text" id="searchInput" placeholder="회차 번호나 제목으로 검색..." oninput="filterCards()">
  </div>
  <div class="grid" id="cardGrid">
    {cards_html}
  </div>
  <div class="no-results" id="noResults">검색 결과가 없습니다.</div>
</div>
<script>
function filterCards() {{
  const q = document.getElementById('searchInput').value.trim().toLowerCase();
  const cards = document.querySelectorAll('#cardGrid .card');
  let visible = 0;
  cards.forEach(function(card) {{
    const ep = (card.dataset.ep || '');
    const title = (card.dataset.title || '').toLowerCase();
    const category = (card.dataset.category || '').toLowerCase();
    const match = !q || ep.includes(q) || title.includes(q) || category.includes(q);
    card.style.display = match ? '' : 'none';
    if(match) visible++;
  }});
  document.getElementById('noResults').style.display = visible === 0 ? 'block' : 'none';
}}

function loadPlayCounts() {{
  const cards = document.querySelectorAll('#cardGrid .card');
  cards.forEach(function(card) {{
    const stem = card.dataset.stem;
    if(!stem) return;
    try {{
      const data = JSON.parse(localStorage.getItem('ebs_played_' + stem) || '{{}}');
      const count = data.play_count || 0;
      if(count > 0) {{
        const badge = card.querySelector('.play-badge');
        if(badge) {{
          badge.textContent = count + '회';
          badge.classList.add('has-plays');
        }}
      }}
    }} catch(e) {{}}
  }});
}}

loadPlayCounts();
</script>
</body>
</html>
"""


def build_universal_player_html(output_dir: Path, episodes: list):
    # Sort ascending (oldest first) for continuous play navigation
    asc_episodes = sorted(episodes, key=lambda e: (e.get("episode") or 0))
    episode_list = [{"stem": ep["stem"], "ep": ep.get("episode") or 0} for ep in asc_episodes]
    episode_list_json = json.dumps(episode_list, ensure_ascii=False)
    html = DYNAMIC_PLAYER_TEMPLATE.replace('__EPISODE_LIST__', episode_list_json)
    with open(output_dir / "play.html", "w", encoding="utf-8") as f:
        f.write(html)


def build_episode_data_json(stem: str, output_dir: Path):
    json_path = output_dir / f"{stem}_player.json"
    if not json_path.exists(): return
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    meta = parse_filename(stem)
    if SUPABASE_URL:
        mp3_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_BUCKET_NAME}/episodes/{meta.get('episode')}_{meta.get('date_compact')}.mp3"
    else:
        mp3_url = f"{stem}.mp3"
    data.update({
        "episode_num": meta["episode"], "category": meta["category"],
        "subtitle": meta["subtitle"], "date": meta["date"], "mp3_url": mp3_url
    })
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_dashboard(output_dir: Path = OUTPUT_MP3_DIR):
    episodes = collect_episodes(output_dir)
    cards = []
    for ep in episodes:
        cards.append(f'''
<a class="card" href="play.html?id={ep["stem"]}" data-stem="{ep["stem"]}" data-ep="{ep["episode"]}" data-title="{ep["subtitle"]}" data-category="{ep["category"]}">
  <div class="ep-top">
    <div class="ep-tag">제 {ep["episode"]}회</div>
    <span class="play-badge"></span>
  </div>
  <h3>{ep["subtitle"]}</h3>
  <div class="meta">
    <span><i class="bi bi-calendar3"></i> {ep["date"]}</span>
    <span><i class="bi bi-clock"></i> {int(ep["duration"]//60)}분 {int(ep["duration"]%60):02d}초</span>
  </div>
</a>''')

    html_content = DASHBOARD_TEMPLATE.format(cards_html="".join(cards))
    with open(output_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(html_content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard-only", action="store_true")
    args = parser.parse_args()
    OUTPUT_MP3_DIR.mkdir(parents=True, exist_ok=True)
    episodes = collect_episodes(OUTPUT_MP3_DIR)
    build_universal_player_html(OUTPUT_MP3_DIR, episodes)
    if not args.dashboard_only:
        for ep in episodes: build_episode_data_json(ep['stem'], OUTPUT_MP3_DIR)
    build_dashboard(OUTPUT_MP3_DIR)


if __name__ == "__main__":
    main()
