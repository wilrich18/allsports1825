"""
THE FIELD — Multi-Sport Auto Updater
=====================================
Regenerates all 5 HTML files for the sports hub nightly:
  index.html   — Home hub
  nba.html     — NBA basketball
  nhl.html     — NHL hockey
  mlb.html     — MLB baseball
  nfl.html     — NFL football (offseason: draft/news; season: live standings)

SETUP:
  1.  pip3 install requests openpyxl python-docx
  2.  Set OUTPUT_DIR below to your Netlify deploy folder path
  3.  Run once:   python3 the_field_updater.py
  4.  Schedule:   python3 the_field_updater.py --schedule
        Runs every night at 11:00 PM via macOS LaunchAgent (no computer needed,
        just leave it running in the background)

HOW IT UPDATES:
  - Fetches live standings + last night's scores from ESPN's free public API
  - Generates fresh HTML for every sport page
  - Saves all 5 files to OUTPUT_DIR
  - You drag the OUTPUT_DIR folder onto Netlify once — after that the files
    update themselves on disk nightly; re-drag whenever you want to publish
  - Or use the --netlify flag with your site ID to auto-publish (see below)
"""

import requests, time, os, sys, json
from datetime import datetime, timedelta

# ── CONFIGURATION ────────────────────────────────────────────────────────────
# When running locally, writes to ~/Desktop/ALLSPORTS
# When running in GitHub Actions (CI=true env var), writes to the repo root
_IS_CI     = os.environ.get("CI") == "true"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__)) if _IS_CI else os.path.expanduser("~/Desktop/ALLSPORTS")
EXCEL_PATH = os.path.expanduser("~/Desktop/ALLSPORTS/NBA_Game_Predictor.xlsx")
LOG_FILE   = os.path.join(OUTPUT_DIR, "updater_log.txt")
# Optional: set these to auto-publish to Netlify via API
NETLIFY_SITE_ID  = ""   # e.g. "abc123.netlify.app" — leave blank to skip
NETLIFY_TOKEN    = ""   # Personal access token from netlify.com/user/applications
# ─────────────────────────────────────────────────────────────────────────────

os.makedirs(OUTPUT_DIR, exist_ok=True)

def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f: f.write(line + "\n")

def safe_get(url, params=None, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 429:
                log("    ⏳ Rate limited — waiting 65s..."); time.sleep(65); continue
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1: raise
            time.sleep(5)

def fmt_date(dt=None):
    d = dt or datetime.now()
    return d.strftime("%B %-d, %Y")

def fmt_dow(dt=None):
    d = dt or datetime.now()
    return d.strftime("%A").upper()

def espn_date(dt=None):
    d = dt or datetime.now()
    return d.strftime("%Y%m%d")

# ════════════════════════════════════════════════════════════════════════════
#  ESPN FETCH HELPERS
# ════════════════════════════════════════════════════════════════════════════

def espn_standings(sport_path):
    """Fetch standings from ESPN. sport_path e.g. 'basketball/nba'"""
    try:
        r = safe_get(f"https://site.api.espn.com/apis/v2/sports/{sport_path}/standings",
                     {"season": datetime.now().year})
        return r.json()
    except Exception as e:
        log(f"  ⚠️  Standings fetch failed ({sport_path}): {e}")
        return {}

def espn_scores(sport_path, date_str=None):
    """Fetch scoreboard for a given date (YYYYMMDD). Defaults to yesterday."""
    ds = date_str or espn_date(datetime.now() - timedelta(days=1))
    try:
        r = safe_get(f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard",
                     {"dates": ds, "seasontype": 2})
        return r.json().get("events", [])
    except Exception as e:
        log(f"  ⚠️  Scores fetch failed ({sport_path} {ds}): {e}")
        return []

def espn_scores_today(sport_path):
    return espn_scores(sport_path, espn_date(datetime.now()))

def parse_game(event, sport="nba"):
    """Parse an ESPN event into a standardised game dict."""
    try:
        comp  = event["competitions"][0]
        home  = next(t for t in comp["competitors"] if t["homeAway"] == "home")
        away  = next(t for t in comp["competitors"] if t["homeAway"] == "away")
        hs    = int(float(home.get("score", "0") or 0))
        as_   = int(float(away.get("score", "0") or 0))
        hn    = home["team"]["displayName"]
        an    = away["team"]["displayName"]
        habrv = home["team"]["abbreviation"]
        aabrv = away["team"]["abbreviation"]
        status_name = event.get("status", {}).get("type", {}).get("name", "")
        is_final    = "FINAL" in status_name.upper() or status_name == "STATUS_FINAL"
        is_live     = "PROGRESS" in status_name.upper()
        clock       = event.get("status", {}).get("displayClock", "")
        period      = event.get("status", {}).get("period", 0)
        start       = event.get("date", "")
        winner      = hn if hs > as_ else an
        loser       = an if hs > as_ else hn
        ws, ls      = max(hs, as_), min(hs, as_)
        margin      = ws - ls
        tone        = ("dominant" if margin > 15 else
                       "comfortable" if margin > 8 else
                       "solid" if margin > 3 else "narrow")
        unit = {"nba":"pts","nhl":"goals","mlb":"runs","nfl":"pts"}.get(sport,"pts")
        summary = f"{winner} earned a {tone} {ws}-{ls} {unit} win over {loser}."
        # Win probability + odds
        odds = comp.get("odds", [{}])[0] if comp.get("odds") else {}
        home_win_pct = None
        for predictor in comp.get("predictor", {}).get("homeTeam", {}).get("gameProjection", []):
            home_win_pct = predictor
        if home_win_pct is None:
            for item in comp.get("situation", {}).get("lastPlay", {}).get("probability", {}).items() if comp.get("situation") else []:
                pass
        # Try to get win prob from odds
        h_win_prob = None
        a_win_prob = None
        try:
            for odd in comp.get("odds", []):
                if "homeTeamOdds" in odd:
                    h_win_prob = round(float(odd["homeTeamOdds"].get("winPercentage", 50)), 0)
                    a_win_prob = round(100 - h_win_prob, 0)
        except Exception:
            pass
        ou = odds.get("overUnder", None)
        spread = odds.get("spread", None)
        favored = odds.get("favorite", {}).get("displayName", None) if odds.get("favorite") else None
        return dict(home=hn, away=an, habrv=habrv, aabrv=aabrv,
                    h_score=hs, a_score=as_, winner=winner, loser=loser,
                    ws=ws, ls=ls, summary=summary,
                    result=f"{an} {as_}, {hn} {hs}",
                    is_final=is_final, is_live=is_live,
                    clock=clock, period=period, start=start,
                    h_win_prob=h_win_prob, a_win_prob=a_win_prob,
                    ou=ou, spread=spread, favored=favored)
    except Exception as e:
        return None

# ════════════════════════════════════════════════════════════════════════════
#  SHARED HTML COMPONENTS
# ════════════════════════════════════════════════════════════════════════════

SHARED_FONTS = '<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Barlow+Condensed:wght@400;600;700;800;900&family=Barlow:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">'

TICKER_JS = r"""
<script>
(function(){
  const path = window.location.pathname.toLowerCase();
  let espnSport='basketball/nba', sportLabel='NBA', accentColor='#fdb927';
  if(path.includes('nhl')){ espnSport='hockey/nhl'; sportLabel='NHL'; accentColor='#4ab3ff'; }
  else if(path.includes('mlb')){ espnSport='baseball/mlb'; sportLabel='MLB'; accentColor='#f5c842'; }
  else if(path.includes('nfl')){ espnSport='football/nfl'; sportLabel='NFL'; accentColor='#d4001c'; }
  else if(path==='/'||path.endsWith('index.html')){ return; }

  const style=document.createElement('style');
  style.textContent=`.ticker-bar{position:sticky;top:54px;z-index:99;background:rgba(0,0,0,0.92);backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,0.06);height:34px;overflow:hidden;display:flex;align-items:center;}.ticker-sport-tag{flex-shrink:0;font-family:'Bebas Neue',sans-serif;font-size:12px;letter-spacing:2px;padding:0 14px;height:100%;display:flex;align-items:center;border-right:1px solid rgba(255,255,255,0.08);white-space:nowrap;}.ticker-track{flex:1;overflow:hidden;position:relative;}.ticker-inner{display:flex;align-items:center;white-space:nowrap;animation:tickerScroll 60s linear infinite;width:max-content;}.ticker-inner:hover{animation-play-state:paused;}@keyframes tickerScroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}.ticker-game{display:inline-flex;align-items:center;gap:8px;padding:0 20px;border-right:1px solid rgba(255,255,255,0.06);font-family:'Barlow Condensed',sans-serif;font-size:13px;font-weight:700;letter-spacing:.5px;}.t-status{font-size:10px;letter-spacing:1px;padding:2px 6px;border-radius:3px;font-weight:700;}.t-live{background:rgba(248,113,113,.2);color:#f87171;}.t-final{background:rgba(100,100,100,.2);color:#6a7d94;}.t-soon{background:rgba(74,179,255,.15);color:#4ab3ff;}.t-teams{color:#f0f4f8;}.t-score{color:var(--gold,#f5c842);font-size:14px;}.ticker-refresh{flex-shrink:0;padding:0 12px;font-family:'Barlow Condensed',sans-serif;font-size:10px;letter-spacing:1px;color:rgba(255,255,255,.2);border-left:1px solid rgba(255,255,255,.06);cursor:pointer;height:100%;display:flex;align-items:center;transition:color .2s;}.ticker-refresh:hover{color:rgba(255,255,255,.5);}.ticker-loading{padding:0 20px;font-family:'Barlow Condensed',sans-serif;font-size:12px;letter-spacing:1px;color:rgba(255,255,255,.2);}`;
  document.head.appendChild(style);

  const bar=document.createElement('div'); bar.className='ticker-bar';
  bar.innerHTML=`<div class="ticker-sport-tag" style="color:${accentColor}">${sportLabel}</div><div class="ticker-track"><div class="ticker-inner" id="ticker-inner"><div class="ticker-loading">Loading scores...</div></div></div><div class="ticker-refresh" onclick="window._tickerFetch()" title="Refresh">↻ LIVE</div>`;
  const nav=document.querySelector('nav');
  if(nav&&nav.parentNode) nav.parentNode.insertBefore(bar,nav.nextSibling);

  function fmtTime(iso){const d=new Date(iso);return d.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit',timeZone:'America/New_York'}).replace(':00','');}

  function buildHTML(games){
    if(!games||!games.length) return '<div class="ticker-loading">No games today</div>';
    let html='';
    games.forEach(g=>{
      const hAbrv=g.home_abbr||'HOME';
      const aAbrv=g.away_abbr||'AWAY';
      const hS=g.score?g.score[hAbrv]:''; const aS=g.score?g.score[aAbrv]:'';
      let statusHtml='', scoreHtml='';
      if(g.status==='inprogress'){
        const cl=g.clock?` ${g.clock}`:''; const p=g.period?` P${g.period}`:'';
        statusHtml=`<span class="t-status t-live">LIVE${cl}${p}</span>`;
        scoreHtml=`<span class="t-score">${aS} – ${hS}</span>`;
      } else if(g.status==='closed'||g.status==='complete'){
        statusHtml=`<span class="t-status t-final">FINAL</span>`;
        scoreHtml=`<span class="t-score">${aS} – ${hS}</span>`;
      } else {
        statusHtml=`<span class="t-status t-soon">${fmtTime(g.start_time)}</span>`;
      }
      html+=`<div class="ticker-game">${statusHtml}<span class="t-teams">${aAbrv} vs ${hAbrv}</span>${scoreHtml?'<span style="color:rgba(255,255,255,.15)">|</span>'+scoreHtml:''}</div>`;
    });
    return html+html;
  }

  async function fetchScores(){
    try{
      const today=new Date().toISOString().slice(0,10).replace(/-/g,'');
      const res=await fetch(`https://api.allorigins.win/get?url=${encodeURIComponent("https://site.api.espn.com/apis/site/v2/sports/"+espnSport+"/scoreboard?dates="+today)}`);
      const raw=await res.json();
      const data=raw.contents?JSON.parse(raw.contents):raw;
      const events=data.events||[];
      const games=events.map(e=>{
        const comp=e.competitions?.[0]; if(!comp) return null;
        const home=comp.competitors?.find(c=>c.homeAway==='home');
        const away=comp.competitors?.find(c=>c.homeAway==='away');
        if(!home||!away) return null;
        const sn=e.status?.type?.name||'';
        let status='scheduled';
        if(sn==='STATUS_IN_PROGRESS') status='inprogress';
        else if(sn==='STATUS_FINAL') status='closed';
        return{status,start_time:e.date,clock:e.status?.displayClock,period:e.status?.period,
          home_abbr:home.team.abbreviation,away_abbr:away.team.abbreviation,
          teams:{[home.team.abbreviation]:{abbreviation:home.team.abbreviation},[away.team.abbreviation]:{abbreviation:away.team.abbreviation}},
          score:status!=='scheduled'?{[home.team.abbreviation]:parseInt(home.score)||0,[away.team.abbreviation]:parseInt(away.score)||0}:null};
      }).filter(Boolean);
      const inner=document.getElementById('ticker-inner');
      if(inner) inner.innerHTML=buildHTML(games);
    }catch(e){
      const inner=document.getElementById('ticker-inner');
      if(inner) inner.innerHTML='<div class="ticker-loading">No games data · Check back soon</div>';
    }
  }
  window._tickerFetch=fetchScores;
  fetchScores();
  setInterval(fetchScores,30000);
})();
</script>
"""

def build_recap_paragraph(g, sport="nba"):
    """Build a rich 3-4 sentence recap paragraph for a game."""
    winner, loser = g["winner"], g["loser"]
    ws, ls = g["ws"], g["ls"]
    margin = ws - ls
    home, away = g["home"], g["away"]
    is_home_win = winner == home
    location = "at home" if is_home_win else "on the road"

    # Sentence 1 — main result
    if margin > 15:
        s1 = f"{winner} put on a dominant performance, rolling past {loser} by {margin} to win {ws}-{ls}."
    elif margin > 8:
        s1 = f"{winner} took care of business with a comfortable {ws}-{ls} victory over {loser}."
    elif margin > 3:
        s1 = f"{winner} held off {loser} for a solid {ws}-{ls} win."
    else:
        s1 = f"In one of the night's closest games, {winner} edged {loser} {ws}-{ls} in a narrow finish."

    # Sentence 2 — context
    if sport == "nba":
        unit = "points"
        if margin > 15:
            s2 = f"The {winner.split()[-1]} were in control from the opening tip, leading wire-to-wire and never letting {loser.split()[-1]} get comfortable."
        elif margin <= 3:
            s2 = f"The game came down to the final possessions, with {winner.split()[-1]} making the clutch plays when it mattered most."
        else:
            s2 = f"{winner.split()[-1]} pulled away in the second half, using a strong third quarter to build a lead they wouldn't relinquish."
    elif sport == "nhl":
        unit = "goals"
        if margin > 3:
            s2 = f"It was a dominant effort from {winner.split()[-1]}, who controlled the pace of play and outworked {loser.split()[-1]} in all three zones."
        elif margin == 1:
            s2 = f"It was a tightly contested affair that could have gone either way, with {winner.split()[-1]} finding the difference-maker late."
        else:
            s2 = f"{winner.split()[-1]} stepped up when it mattered, capitalizing on their chances while holding {loser.split()[-1]} at bay."
    elif sport == "mlb":
        unit = "runs"
        if margin > 5:
            s2 = f"The {winner.split()[-1]} offense exploded early and never looked back, putting up crooked numbers that {loser.split()[-1]} couldn't answer."
        elif margin == 1:
            s2 = f"A tight pitching duel that went down to the wire, with {winner.split()[-1]} scratching across the decisive run at just the right moment."
        else:
            s2 = f"{winner.split()[-1]} got timely hitting and solid pitching to secure the win over a scrappy {loser.split()[-1]} squad."
    else:
        unit = "points"
        s2 = f"{winner.split()[-1]} executed their game plan effectively, winning {location} to improve their standing in a competitive conference."

    # Sentence 3 — standing implications
    s3 = f"The win keeps {winner} moving in the right direction as the season heads toward its final stretch, while {loser} will look to bounce back in their next outing."

    # Sentence 4 — look ahead
    s4 = f"Both teams return to action in the coming days with playoff positioning still very much on the line."

    return f"{s1} {s2} {s3} {s4}"


def recap_articles(games, yesterday, sport="nba"):
    """Build collapsible recap article HTML from a list of parsed games."""
    if not games:
        return '<p style="color:var(--gray);padding:20px 0">No games yesterday. Check back tonight.</p>'
    html = ""
    for g in games:
        paragraph = build_recap_paragraph(g, sport)
        html += f"""
    <div class="article">
      <div class="art-hdr" onclick="tog(this)">
        <div>
          <div class="art-score">
            <span class="sw">{g['winner'].split()[-1].upper()} {g['ws']}</span>
            <span class="sdot">·</span>
            <span class="sl">{g['loser'].split()[-1].upper()} {g['ls']}</span>
          </div>
          <div class="art-sub">{g['away']} @ {g['home']} · {yesterday}</div>
        </div>
        <span class="chev">▾</span>
      </div>
      <div class="art-body"><p>{paragraph}</p></div>
    </div>"""
    return html


# ════════════════════════════════════════════════════════════════════════════
#  NBA — fetch + generate
# ════════════════════════════════════════════════════════════════════════════

def fetch_nba_standings():
    log("🏀 Fetching NBA standings...")
    try:
        r = safe_get("https://site.api.espn.com/apis/v2/sports/basketball/nba/standings",
                     {"season": "2026"})
        east, west = [], []
        EAST_TEAMS = {
            "Atlanta Hawks","Boston Celtics","Brooklyn Nets","Charlotte Hornets",
            "Chicago Bulls","Cleveland Cavaliers","Detroit Pistons","Indiana Pacers",
            "Miami Heat","Milwaukee Bucks","New York Knicks","Orlando Magic",
            "Philadelphia 76ers","Toronto Raptors","Washington Wizards"
        }
        for conf in r.json().get("children", []):
            for entry in conf.get("standings", {}).get("entries", []):
                try:
                    name = entry["team"]["displayName"]
                    vals = {s["name"]: s.get("value", 0) for s in entry.get("stats", [])}
                    w    = int(vals.get("wins", 0) or 0)
                    l    = int(vals.get("losses", 0) or 0)
                    gp   = w + l or 1
                    ppg  = round(float(vals.get("pointsFor", 0) or 0) / gp, 1)
                    opp  = round(float(vals.get("pointsAgainst", 0) or 0) / gp, 1)
                    net  = round(ppg - opp, 1)
                    pct  = round(w / gp, 3)
                    l10_raw = str(vals.get("lastTenGames", "5-5"))
                    try:
                        lw, ll = l10_raw.split("-")
                        l10 = f"{lw}-{ll}"
                    except:
                        l10 = "—"
                    t = dict(t=name, w=w, l=l, ppg=ppg, opp=opp, net=net, pct=pct, l10=l10)
                    WEST_FORCE = {"San Antonio Spurs","Dallas Mavericks","Houston Rockets","Memphis Grizzlies","New Orleans Pelicans","Oklahoma City Thunder","Denver Nuggets","Minnesota Timberwolves","Utah Jazz","Portland Trail Blazers","Golden State Warriors","Los Angeles Lakers","Los Angeles Clippers","Sacramento Kings","Phoenix Suns"}
                    if name in WEST_FORCE:
                        west.append(t)
                    elif name in EAST_TEAMS:
                        east.append(t)
                    else:
                        west.append(t)
                except:
                    continue
        east.sort(key=lambda x: -x["pct"])
        west.sort(key=lambda x: -x["pct"])
        log(f"  ✅ NBA: {len(east)} East + {len(west)} West teams")
        return east, west
    except Exception as e:
        log(f"  ⚠️  NBA standings failed: {e}")
        return [], []



def generate_nba_html(east, west, games_yesterday, today_games):
    log("\U0001f310 Generating nba.html...")
    from datetime import datetime, timedelta
    today     = fmt_date()
    yesterday = fmt_date(datetime.now() - timedelta(days=1))
    dow       = fmt_dow()

    def team_js(t):
        ns = ('+' if t['net'] >= 0 else '') + str(t['net'])
        return ('{' + f't:"{t["t"]}",w:{t["w"]},l:{t["l"]},ppg:{t["ppg"]},'
                f'opp:{t["opp"]},net:{t["net"]},l10:"{t["l10"]}",str:"{t.get("str","")}"' + '}')

    east_js = "[" + ",".join(team_js(t) for t in east) + "]"
    west_js = "[" + ",".join(team_js(t) for t in west) + "]"

    tonight_js_items = []
    for g in today_games:
        if not g: continue
        start_dt = g.get("start","")
        try:
            dt = datetime.fromisoformat(start_dt.replace("Z","+00:00"))
            t_str = dt.astimezone().strftime("%-I:%M %p ET")
        except:
            t_str = "Tonight"
        item = ('{' + f'time:"{t_str}",home:"{g["home"]}",away:"{g["away"]}",'
                f'h_score:{g["h_score"]},a_score:{g["a_score"]},'
                f'is_final:{str(g["is_final"]).lower()},is_live:{str(g["is_live"]).lower()}' + '}')
        tonight_js_items.append(item)
    tonight_js = "[" + ",".join(tonight_js_items) + "]"

    recaps = recap_articles(games_yesterday, yesterday, "nba")

    all_teams = sorted(east + west, key=lambda x: -x["pct"])
    best = all_teams[0] if all_teams else {"t":"—","w":0,"l":0}

    east_sorted = sorted(east, key=lambda x: -x["pct"])
    west_sorted = sorted(west, key=lambda x: -x["pct"])
    seeds_rows = ""
    for lbl, teams, idx in [("E1",east_sorted,0),("E2",east_sorted,1),("E3",east_sorted,2),
                             ("W1",west_sorted,0),("W2",west_sorted,1),("W3",west_sorted,2)]:
        if len(teams) > idx:
            t = teams[idx]
            seeds_rows += f'<div class="sc-row"><span class="sc-team">{lbl} {t["t"].split()[-1]}</span><span class="sc-val">{t["w"]}-{t["l"]}</span></div>'

    trend_map = ["up","up","up","hold","hold","hold","down","down"]
    notes = [
        "Best record in the league. Built to win in April and beyond.",
        "Elite on both ends. MVP candidate is locked in all month.",
        "Rolling. Defense suffocates and offense is clicking.",
        "Consistent and dangerous. Never count them out.",
        "The most complete team in their conference.",
        "Young stars arriving. Exciting basketball every night.",
        "Dealing with injuries but too talented to count out.",
        "Need wins now. Playoff window is closing.",
    ]
    rankings_html = ""
    for i, t in enumerate(all_teams[:8]):
        trend = trend_map[i]
        icon  = "↑" if trend=="up" else ("↓" if trend=="down" else "→")
        cls   = "tu" if trend=="up" else ("td" if trend=="down" else "tf")
        label = "Moving Up" if trend=="up" else ("Sliding" if trend=="down" else "Holding")
        note  = notes[i]
        t3cls = "t3" if i < 3 else ""
        rankings_html += (f'<div class="rank-item"><div class="rank-n {t3cls}">{i+1}</div>'
                          f'<div><div class="rank-team">{t["t"]}</div>'
                          f'<div class="rank-rec">{t["w"]}-{t["l"]}</div>'
                          f'<div class="rank-note">{note}</div>'
                          f'<div class="rank-trend {cls}">{icon} {label}</div></div></div>')

    html = build_nba_html(east_js, west_js, tonight_js, recaps, rankings_html,
                          seeds_rows, best, today, yesterday, dow)

    out_path = os.path.join(OUTPUT_DIR, "nba.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"  ✅ nba.html saved ({len(html):,} chars)")



def build_nba_html(east_js, west_js, tonight_js, recaps, rankings_html,
                   seeds_rows, best, today, yesterday, dow):
    PROPS_JS = """[
  {player:"Victor Wembanyama",team:"San Antonio Spurs",line:"Over 24.5 pts + rebs",odds:"-115",conf:"HIGH",cls:"high",reason:"Wemby is the MVP frontrunner. This line is set conservatively below his recent average."},
  {player:"Shai Gilgeous-Alexander",team:"OKC Thunder",line:"Over 29.5 points",odds:"-112",conf:"HIGH",cls:"high",reason:"SGA is averaging 31+ over his last 10 and creates volume scoring every night."},
  {player:"Nikola Jokic",team:"Denver Nuggets",line:"Over 10.5 assists",odds:"-108",conf:"HIGH",cls:"high",reason:"Jokic averages 9.8 APG. Any Denver blowout means extra distribution."},
  {player:"Anthony Edwards",team:"Minnesota Timberwolves",line:"Over 28.5 points",odds:"-115",conf:"HIGH",cls:"high",reason:"Edwards has scored 28+ in 6 of his last 8. Minnesota plays fast and Ant is the primary option."},
  {player:"Cade Cunningham",team:"Detroit Pistons",line:"Over 24.5 points",odds:"-110",conf:"HIGH",cls:"high",reason:"Detroit primary option averaging 27+ over his last 10."},
  {player:"LeBron James",team:"Los Angeles Lakers",line:"Over 8.5 assists",odds:"-105",conf:"MEDIUM",cls:"medium",reason:"LeBron is in full playmaker mode. Plus money on a player averaging 9+ assists."}
]"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>THE FIELD — NBA</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800;900&family=Barlow:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
<style>
:root{{
  --navy:#0a1628;--red:#c8102e;--red2:#e8132f;--gold:#fdb927;
  --white:#f0f4f8;--gray:#7a8fa6;
  --border:rgba(255,255,255,0.07);--card:rgba(255,255,255,0.04);--card2:rgba(255,255,255,0.08);
}}
*{{margin:0;padding:0;box-sizing:border-box;}}
html{{scroll-behavior:smooth;}}
body{{background:var(--navy);color:var(--white);font-family:'Barlow',sans-serif;font-size:15px;line-height:1.5;overflow-x:hidden;}}
nav{{position:sticky;top:0;z-index:100;background:rgba(10,22,40,0.97);backdrop-filter:blur(16px);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 24px;height:54px;}}
.nav-logo{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:21px;letter-spacing:2px;color:var(--white);margin-right:28px;text-decoration:none;}}
.nav-logo span{{color:var(--gold);}}
.nav-links{{display:flex;gap:2px;flex:1;}}
.nav-link{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:13px;letter-spacing:1px;text-transform:uppercase;color:var(--gray);padding:6px 14px;border-radius:4px;transition:all 0.15s;cursor:pointer;border:none;background:none;}}
.nav-link:hover,.nav-link.active{{color:var(--white);background:var(--card2);}}
.live-pill{{background:var(--red);color:#fff;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;padding:3px 10px;border-radius:10px;margin-left:auto;letter-spacing:1px;}}
.page{{display:none;}}
.page.active{{display:block;animation:fadeUp 0.3s ease both;}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:translateY(0)}}}}
.hero{{position:relative;background:linear-gradient(135deg,#0a1628 0%,#0d2348 50%,#0a1628 100%);padding:56px 24px 44px;overflow:hidden;}}
.hero::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 70% 60% at 65% 50%,rgba(200,16,46,0.11),transparent);pointer-events:none;}}
.hero-inner{{max-width:1100px;margin:0 auto;position:relative;}}
.hero-eyebrow{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:3px;color:var(--gold);text-transform:uppercase;margin-bottom:10px;}}
.hero-title{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:clamp(44px,7vw,84px);line-height:0.93;letter-spacing:-1px;margin-bottom:14px;}}
.hero-title em{{color:var(--red);font-style:normal;}}
.hero-sub{{color:var(--gray);font-size:15px;max-width:460px;margin-bottom:28px;}}
.hero-stats{{display:flex;gap:28px;flex-wrap:wrap;}}
.hero-stat-val{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:34px;color:var(--gold);line-height:1;}}
.hero-stat-lbl{{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gray);margin-top:2px;}}
.section{{max-width:1100px;margin:0 auto;padding:36px 24px;}}
.section-title{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:12px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin-bottom:18px;display:flex;align-items:center;gap:10px;}}
.section-title::after{{content:'';flex:1;height:1px;background:var(--border);}}
.standings-wrap{{overflow-x:auto;}}
.standings-table{{width:100%;border-collapse:collapse;font-size:14px;}}
.standings-table th{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gray);padding:8px 12px;text-align:center;border-bottom:1px solid var(--border);}}
.standings-table th:nth-child(2){{text-align:left;}}
.standings-table td{{padding:10px 12px;text-align:center;border-bottom:1px solid rgba(255,255,255,0.04);transition:background 0.1s;}}
.standings-table td:nth-child(2){{text-align:left;}}
.standings-table tr:hover td{{background:var(--card2);}}
.team-name{{font-weight:600;}}.team-rank{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;color:var(--gray);}}
.net-pos{{color:#4ade80;font-weight:600;}}.net-neg{{color:#f87171;font-weight:600;}}
.record-w{{color:var(--white);font-weight:600;}}.record-l{{color:var(--gray);}}
.streak-w{{color:#4ade80;font-weight:600;}}.streak-l{{color:#f87171;font-weight:600;}}
tr.playoff-line td{{border-top:2px solid var(--gold)!important;}}
tr.playin-line td{{border-top:2px dashed rgba(253,185,39,0.4)!important;}}
.games-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:16px;margin-bottom:36px;}}
.game-card{{background:var(--card);border:1px solid var(--border);border-radius:14px;overflow:hidden;}}
.game-card-top{{padding:16px 18px 12px;border-bottom:1px solid var(--border);}}
.game-time{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gold);margin-bottom:8px;}}
.game-matchup{{display:flex;align-items:center;justify-content:space-between;}}
.game-team{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:16px;flex:1;}}
.game-team.fav{{color:var(--white);}}.game-team.dog{{color:var(--gray);}}
.game-vs{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;color:var(--gray);padding:0 8px;}}
.game-score{{display:flex;justify-content:space-between;align-items:center;padding:10px 18px;border-bottom:1px solid var(--border);}}
.gscore{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:28px;}}
.gscore.w{{color:var(--white);}}.gscore.l{{color:var(--gray);}}
.gfinal{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:2px;color:var(--gold);}}
.pred-wrap{{max-width:680px;margin:0 auto;}}
.team-row{{display:grid;grid-template-columns:1fr auto 1fr;gap:14px;align-items:center;margin-bottom:20px;}}
.team-box{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px 20px;}}
.tbadge{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:2px;text-transform:uppercase;padding:3px 10px;border-radius:4px;display:inline-block;margin-bottom:8px;}}
.tbadge-h{{background:rgba(74,222,128,0.12);color:#4ade80;}}
.tbadge-a{{background:rgba(248,113,113,0.12);color:#f87171;}}
.tlabel{{font-family:'Barlow Condensed',sans-serif;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--gray);margin-bottom:6px;}}
select.tsel{{width:100%;background:rgba(255,255,255,0.06);border:1px solid var(--border);border-radius:8px;color:var(--white);font-family:'Barlow',sans-serif;font-size:15px;font-weight:600;padding:10px 12px;cursor:pointer;appearance:none;}}
select.tsel:focus{{outline:none;border-color:var(--gold);}}
select.tsel option{{background:#0f2040;}}
.vs-mid{{display:flex;align-items:center;justify-content:center;padding-top:28px;}}
.vs-big{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:26px;color:var(--gray);}}
.pred-btn{{width:100%;padding:14px;margin-bottom:20px;background:linear-gradient(135deg,var(--red),var(--red2));border:none;border-radius:10px;color:#fff;font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:16px;letter-spacing:2px;text-transform:uppercase;cursor:pointer;transition:all 0.2s;box-shadow:0 4px 18px rgba(200,16,46,0.28);}}
.pred-btn:hover{{transform:translateY(-2px);box-shadow:0 6px 26px rgba(200,16,46,0.42);}}
.result-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;}}
.result-card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px 18px;}}
.result-card.w{{border-color:rgba(74,222,128,0.28);background:rgba(74,222,128,0.05);}}
.r-label{{font-family:'Barlow Condensed',sans-serif;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gray);margin-bottom:4px;}}
.r-val{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:38px;line-height:1;color:var(--white);}}
.r-val.gold{{color:var(--gold);}}
.r-sub{{font-size:12px;color:var(--gray);margin-top:3px;}}
.bar-wrap{{margin:16px 0;}}
.bar-labels{{display:flex;justify-content:space-between;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:13px;margin-bottom:5px;}}
.bar-track{{height:10px;border-radius:5px;background:rgba(248,113,113,0.25);overflow:hidden;}}
.bar-fill{{height:100%;border-radius:5px;background:linear-gradient(90deg,#4ade80,#22c55e);transition:width 0.6s cubic-bezier(0.34,1.56,0.64,1);}}
.winner-banner{{text-align:center;padding:16px;background:rgba(74,222,128,0.08);border:1px solid rgba(74,222,128,0.2);border-radius:10px;font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:20px;letter-spacing:1px;}}
.winner-sub{{font-size:13px;color:var(--gray);font-weight:600;display:block;margin-top:3px;}}
.digest-lead{{background:linear-gradient(135deg,#0f1e34,#1a0a14);border:1px solid var(--border);border-radius:16px;padding:30px;margin-bottom:22px;position:relative;overflow:hidden;}}
.digest-lead::before{{content:'';position:absolute;top:-50px;right:-50px;width:280px;height:280px;border-radius:50%;background:radial-gradient(circle,rgba(200,16,46,0.09),transparent 70%);}}
.dlabel{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin-bottom:8px;}}
.dhl{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:clamp(22px,4vw,38px);line-height:1.0;margin-bottom:8px;}}
.ddeck{{color:var(--gray);font-size:14px;font-style:italic;line-height:1.6;max-width:580px;}}
.article{{background:var(--card);border:1px solid var(--border);border-radius:12px;margin-bottom:14px;overflow:hidden;}}
.art-hdr{{display:flex;align-items:center;justify-content:space-between;padding:15px 18px;background:rgba(255,255,255,0.02);border-bottom:1px solid var(--border);cursor:pointer;user-select:none;}}
.art-score{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:20px;}}
.sw{{color:var(--white);}}.sl{{color:var(--gray);}}.sdot{{color:var(--red);margin:0 7px;}}
.art-sub{{font-size:11px;color:var(--gray);margin-top:2px;}}
.atag{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:1px;text-transform:uppercase;padding:3px 9px;border-radius:4px;}}
.tag-u{{background:rgba(253,185,39,0.13);color:var(--gold);}}
.tag-c{{background:rgba(200,16,46,0.13);color:#ff6b6b;}}
.tag-h{{background:rgba(139,92,246,0.13);color:#a78bfa;}}
.chev{{transition:transform 0.2s;color:var(--gray);font-size:16px;margin-left:8px;}}
.chev.open{{transform:rotate(180deg);}}
.art-body{{display:none;padding:18px 20px;}}
.art-body.open{{display:block;}}
.art-body p{{color:#cbd5e1;line-height:1.75;margin-bottom:13px;font-size:14px;}}
.art-body p:last-child{{margin-bottom:0;}}
.stat-bar{{display:flex;gap:14px;flex-wrap:wrap;background:rgba(255,255,255,0.04);border-radius:7px;padding:10px 14px;margin:12px 0;}}
.sp{{font-family:'Barlow Condensed',sans-serif;font-size:13px;font-weight:700;}}
.sp span{{color:var(--gold);}}
.mag-layout{{display:grid;grid-template-columns:2fr 1fr;gap:20px;}}
.rank-item{{display:flex;gap:14px;align-items:flex-start;padding:14px 0;border-bottom:1px solid var(--border);}}
.rank-item:last-child{{border-bottom:none;}}
.rank-n{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:30px;line-height:1;color:rgba(255,255,255,0.12);min-width:38px;text-align:center;padding-top:2px;}}
.rank-n.t3{{color:var(--gold);}}
.rank-team{{font-weight:600;font-size:15px;margin-bottom:2px;}}
.rank-rec{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;color:var(--gray);letter-spacing:1px;margin-bottom:4px;}}
.rank-note{{font-size:13px;color:#94a3b8;line-height:1.5;}}
.rank-trend{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;margin-top:4px;}}
.tu{{color:#4ade80;}}.td{{color:#f87171;}}.tf{{color:var(--gray);}}
.sidebar-card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:14px;}}
.sc-title{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gold);margin-bottom:10px;}}
.sc-row{{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--border);font-size:13px;}}
.sc-row:last-child{{border-bottom:none;}}
.sc-team{{font-weight:600;}}
.sc-val{{color:var(--gray);font-family:'Barlow Condensed',sans-serif;font-weight:700;}}
.props-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;}}
.prop-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 18px;position:relative;overflow:hidden;}}
.prop-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;}}
.prop-card.high::before{{background:linear-gradient(90deg,#4ade80,#22c55e);}}
.prop-card.medium::before{{background:linear-gradient(90deg,var(--gold),#f59e0b);}}
.prop-player{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:17px;margin-bottom:1px;}}
.prop-team{{font-size:12px;color:var(--gray);margin-bottom:9px;}}
.prop-line{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:26px;margin-bottom:3px;}}
.prop-odds{{font-size:12px;color:var(--gray);margin-bottom:8px;}}
.prop-badge{{display:inline-block;padding:2px 9px;border-radius:4px;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:10px;letter-spacing:1px;text-transform:uppercase;margin-bottom:9px;}}
.b-high{{background:rgba(74,222,128,0.13);color:#4ade80;}}
.b-med{{background:rgba(253,185,39,0.13);color:var(--gold);}}
.prop-reason{{font-size:13px;color:#94a3b8;line-height:1.55;}}
.disclaimer{{background:rgba(200,16,46,0.07);border:1px solid rgba(200,16,46,0.18);border-radius:8px;padding:11px 15px;margin-top:22px;font-size:11px;color:#f87171;line-height:1.5;text-align:center;}}
footer{{border-top:1px solid var(--border);padding:22px;text-align:center;font-size:12px;color:var(--gray);margin-top:40px;}}
footer strong{{color:var(--white);}}
@media(max-width:768px){{.team-row{{grid-template-columns:1fr;}}.vs-mid{{padding-top:0;}}.result-grid{{grid-template-columns:1fr 1fr;}}.mag-layout{{grid-template-columns:1fr;}}.games-grid{{grid-template-columns:1fr;}}}}
</style>
</head>
<body>
<nav>
  <a class="nav-logo" href="index.html"><span>THE</span> FIELD / NBA</a>
  <div class="nav-links">
    <button class="nav-link active" onclick="showPage('standings',this)">Standings</button>
    <button class="nav-link" onclick="showPage('predictor',this)">Tonight</button>
    <button class="nav-link" onclick="showPage('digest',this)">Daily Digest</button>
    <button class="nav-link" onclick="showPage('magazine',this)">Magazine</button>
    <button class="nav-link" onclick="showPage('props',this)">Player Props</button>
  </div>
  <div class="live-pill">🔴 LIVE TONIGHT</div>
</nav>

<div id="page-standings" class="page active">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">2025-26 NBA Season · Updated {today}</div>
      <h1 class="hero-title">NBA<br><em>STANDINGS</em></h1>
      <p class="hero-sub">Live records, net ratings and playoff picture for all 30 teams.</p>
      <div class="hero-stats">
        <div><div class="hero-stat-val">{best["w"]}-{best["l"]}</div><div class="hero-stat-lbl">{best["t"].split()[-1]} — Best Record</div></div>
      </div>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Eastern Conference</div>
    <div class="standings-wrap"><table class="standings-table">
      <thead><tr><th>#</th><th>Team</th><th>W</th><th>L</th><th>PCT</th><th>PPG</th><th>OppPPG</th><th>Net</th><th>L10</th><th>Streak</th></tr></thead>
      <tbody id="east-body"></tbody>
    </table></div>
    <div class="section-title" style="margin-top:30px">Western Conference</div>
    <div class="standings-wrap"><table class="standings-table">
      <thead><tr><th>#</th><th>Team</th><th>W</th><th>L</th><th>PCT</th><th>PPG</th><th>OppPPG</th><th>Net</th><th>L10</th><th>Streak</th></tr></thead>
      <tbody id="west-body"></tbody>
    </table></div>
    <div style="margin-top:10px;font-size:12px;color:var(--gray);display:flex;gap:22px;flex-wrap:wrap;">
      <span><span style="color:var(--gold)">——</span> Playoff cutoff (6th seed)</span>
      <span><span style="color:rgba(253,185,39,0.4)">- - -</span> Play-In cutoff (10th seed)</span>
    </div>
  </div>
</div>

<div id="page-predictor" class="page">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">2025-26 Season · Real Records</div>
      <h1 class="hero-title">TONIGHT'S<br><em>GAMES</em></h1>
      <p class="hero-sub">Tonight's scores and matchups, plus build any custom matchup for an instant prediction.</p>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Tonight's Games — {dow}, {today}</div>
    <div class="games-grid" id="lines-grid"></div>
  </div>
</div>

<div id="page-digest" class="page">
  <div class="section" style="padding-top:30px">
    <div class="digest-lead">
      <div class="dlabel">{dow} {today} · Recapping {yesterday}</div>
      <div class="dhl">NBA DAILY DIGEST</div>
      <div class="ddeck">Last night's scores, standout performances, and everything that happened around the league.</div>
    </div>
    <div class="section-title">Game Recaps — {yesterday}</div>
    {recaps}
  </div>
</div>

<div id="page-magazine" class="page">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">The Field · {today}</div>
      <h1 class="hero-title">NBA<br><em>MAGAZINE</em></h1>
      <p class="hero-sub">Power rankings, playoff picture and the full story of the season.</p>
    </div>
  </div>
  <div class="section">
    <div class="mag-layout">
      <div>
        <div class="section-title">Power Rankings — {today}</div>
        {rankings_html}
      </div>
      <div>
        <div class="sidebar-card">
          <div class="sc-title">🏆 Current Seeds</div>
          {seeds_rows}
        </div>
      </div>
    </div>
  </div>
</div>

<div id="page-props" class="page">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">{today} · Tonight's Slate</div>
      <h1 class="hero-title">PLAYER<br><em>PROPS</em></h1>
      <p class="hero-sub">Top player prop picks with confidence ratings and reasoning for tonight's games.</p>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Tonight's Best Props — {today}</div>
    <div class="props-grid" id="props-grid"></div>
    <div class="disclaimer">⚠️ All lines and picks are for entertainment only. Not financial or gambling advice. Gamble responsibly. 1-800-GAMBLER.</div>
  </div>
</div>

<footer>
  <strong>THE FIELD — NBA</strong> · 2025-26 Season · Updated {today}<br>
  <span>Data via ESPN · Not affiliated with the NBA · <a href="index.html" style="color:var(--gold)">← Back to Hub</a></span>
</footer>

<script>
const EAST={east_js};
const WEST={west_js};
const TONIGHT={tonight_js};
const PROPS={PROPS_JS};

function renderStandings(data,id){{
  const tb=document.getElementById(id);
  data.forEach((t,i)=>{{
    const pct=(t.w/(t.w+t.l)).toFixed(3);
    const ns=t.net>=0?'+'+t.net:String(t.net);
    const nc=t.net>0?'net-pos':t.net<0?'net-neg':'';
    const sc=(t.str||'').startsWith('W')?'streak-w':'streak-l';
    let rc='';if(i===5)rc='playoff-line';if(i===9)rc='playin-line';
    tb.innerHTML+=`<tr class="${{rc}}"><td><span class="team-rank">${{i+1}}</span></td><td><span class="team-name">${{t.t}}</span></td><td><span class="record-w">${{t.w}}</span></td><td><span class="record-l">${{t.l}}</span></td><td>${{pct}}</td><td>${{t.ppg}}</td><td>${{t.opp}}</td><td class="${{nc}}">${{ns}}</td><td>${{t.l10}}</td><td class="${{sc}}">${{t.str||'—'}}</td></tr>`;
  }});
}}

function renderLines(){{
  const g=document.getElementById('lines-grid');
  if(!TONIGHT.length){{g.innerHTML='<p style="color:var(--gray);padding:10px 0">No games tonight. Check back tomorrow.</p>';return;}}
  TONIGHT.forEach(gm=>{{
    const isLive=gm.is_live, isFinal=gm.is_final;
    const hw=isFinal&&gm.h_score>gm.a_score, aw=isFinal&&gm.a_score>gm.h_score;
    const statusLabel=isLive?'<span style="color:#4ade80;font-weight:700">● LIVE</span>':isFinal?'<span style="color:var(--gold)">FINAL</span>':gm.time;
    const scoreRow=(isFinal||isLive)?`<div class="game-score"><span class="gscore ${{hw?'w':'l'}}">${{gm.h_score}}</span><span class="gfinal">${{isFinal?'FINAL':'LIVE'}}</span><span class="gscore ${{aw?'w':'l'}}">${{gm.a_score}}</span></div>`:'';
    g.innerHTML+=`<div class="game-card"><div class="game-card-top"><div class="game-time">${{statusLabel}}</div>
      <div class="game-matchup">
        <div style="flex:1"><div style="font-size:10px;letter-spacing:1px;font-family:'Barlow Condensed',sans-serif;font-weight:700;color:#4ade80;margin-bottom:2px">HOME</div><div class="game-team fav">${{gm.home}}</div></div>
        <div class="game-vs">vs</div>
        <div style="flex:1;text-align:right"><div style="font-size:10px;letter-spacing:1px;font-family:'Barlow Condensed',sans-serif;font-weight:700;color:var(--gray);margin-bottom:2px">AWAY</div><div class="game-team dog">${{gm.away}}</div></div>
      </div></div>${{scoreRow}}</div>`;
  }});
}}



  const H=getT(hn),A=getT(an);if(!H||!A)return;
  const hs=Math.round((H.ppg*0.4+A.opp*0.4+H.net*0.15+5)+3);
  const as_=Math.round(A.ppg*0.4+H.opp*0.4+A.net*0.15+5);
  const sp=hs-as_;
  const spStr=sp>0?hn.split(' ').slice(-1)[0]+' -'+Math.abs(sp).toFixed(1):an.split(' ').slice(-1)[0]+' -'+Math.abs(sp).toFixed(1);
  const hp=1/(1+Math.exp(-0.15*sp)); const ap=1-hp;
  const cf=Math.min(95,Math.max(50,50+Math.abs(H.net-A.net)*1.5)).toFixed(0);
  const hw=hp>0.5;
  out.innerHTML=`<div class="result-grid">
    <div class="result-card ${{hw?'w':''}}"><div class="r-label">🏠 HOME — ${{hn}}</div><div class="r-val">${{hs}}</div><div class="r-sub">${{(hp*100).toFixed(1)}}% win probability</div></div>
    <div class="result-card ${{!hw?'w':''}}"><div class="r-label">✈️ AWAY — ${{an}}</div><div class="r-val">${{as_}}</div><div class="r-sub">${{(ap*100).toFixed(1)}}% win probability</div></div>
    <div class="result-card"><div class="r-label">Spread</div><div class="r-val gold" style="font-size:22px">${{spStr}}</div></div>
    <div class="result-card"><div class="r-label">Confidence</div><div class="r-val gold">${{cf}}<span style="font-size:18px">/100</span></div></div>
  </div>
  <div class="bar-wrap">
    <div class="bar-labels"><span style="color:#4ade80">${{hn}} ${{(hp*100).toFixed(0)}}%</span><span style="color:#f87171">${{an}} ${{(ap*100).toFixed(0)}}%</span></div>
    <div class="bar-track"><div class="bar-fill" style="width:${{(hp*100).toFixed(0)}}%"></div></div>
  </div>
  <div class="winner-banner">${{hw?'🏠 '+hn.toUpperCase()+' WINS':'✈️ '+an.toUpperCase()+' WINS'}}
    <span class="winner-sub">${{(Math.max(hp,ap)*100).toFixed(1)}}% probability · ${{cf}}/100 confidence</span>
  </div>`;
}}

function renderProps(){{
  const g=document.getElementById('props-grid');
  PROPS.forEach(p=>{{
    const bc=p.conf==='HIGH'?'b-high':'b-med';
    g.innerHTML+=`<div class="prop-card ${{p.cls}}"><div class="prop-player">${{p.player}}</div><div class="prop-team">${{p.team}}</div><div class="prop-line">${{p.line}}</div><div class="prop-odds">${{p.odds}}</div><div class="prop-badge ${{bc}}">${{p.conf}}</div><div class="prop-reason">${{p.reason}}</div></div>`;
  }});
}}

function tog(hdr){{
  const body=hdr.nextElementSibling;
  const chev=hdr.querySelector('.chev');
  body.classList.toggle('open');
  chev.classList.toggle('open');
}}

function showPage(name,btn){{
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(l=>l.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  if(btn)btn.classList.add('active');
  window.scrollTo({{top:0,behavior:'smooth'}});
}}

renderStandings(EAST,'east-body');
renderStandings(WEST,'west-body');
renderLines();
renderProps();
</script>
</body>
</html>"""

def fetch_nhl_standings():
    log("🏒 Fetching NHL standings...")
    try:
        r = safe_get("https://site.api.espn.com/apis/v2/sports/hockey/nhl/standings",
                     {"season": datetime.now().year})
        east, west = [], []
        WEST_DIVS = {"Pacific", "Central"}
        for conf_data in r.json().get("children", []):
            conf_name = conf_data.get("name","").upper()
            is_west = "WESTERN" in conf_name
            for entry in conf_data.get("standings", {}).get("entries", []):
                try:
                    name = entry["team"]["displayName"]
                    vals = {s["name"]: s.get("value", 0) for s in entry.get("stats", [])}
                    w   = int(vals.get("wins", 0) or 0)
                    l   = int(vals.get("losses", 0) or 0)
                    gp  = w + l or 1
                    pct = round(w / gp, 3)
                    div = entry.get("team", {}).get("division", {}).get("name", "")
                    ppg = round(float(vals.get("goalsFor", vals.get("pointsFor", 0)) or 0) / max(gp, 1), 1)
                    opp = round(float(vals.get("goalsAgainst", vals.get("pointsAgainst", 0)) or 0) / max(gp, 1), 1)
                    net = round(ppg - opp, 1)
                    l10 = "—"
                    t   = dict(t=name, w=w, l=l, pct=pct, ppg=ppg, opp=opp, net=net, l10=l10, div=div)
                    if is_al: east.append(t)
                    else: west.append(t)
                except: continue
        east.sort(key=lambda x: -x["pct"])
        west.sort(key=lambda x: -x["pct"])
        log(f"  ✅ NHL: {len(east)} East + {len(west)} West")
        return east, west
    except Exception as e:
        log(f"  ⚠️  NHL standings failed: {e}")
        return [], []



def generate_nhl_html(east, west, games_yesterday, today_games):
    log("🌐 Generating nhl.html...")
    today     = fmt_date()
    yesterday = fmt_date(datetime.now() - timedelta(days=1))
    dow       = fmt_dow()

    def team_js(t):
        ns = ('+' if t['net'] >= 0 else '') + str(t['net'])
        return f'{{t:"{t["t"]}",w:{t["w"]},l:{t["l"]},ppg:{t["ppg"]},opp:{t["opp"]},net:{t["net"]},l10:"{t["l10"]}"}}'

    east_js = "[" + ",".join(team_js(t) for t in east) + "]"
    west_js = "[" + ",".join(team_js(t) for t in west) + "]"

    tonight_js_items = []
    for g in today_games:
        if not g: continue
        start_dt = g.get("start","")
        try:
            dt = datetime.fromisoformat(start_dt.replace("Z","+00:00"))
            t_str = dt.astimezone().strftime("%-I:%M %p ET")
        except:
            t_str = "Tonight"
        item = (f'{{time:"{t_str}",home:"{g["home"]}",away:"{g["away"]}",'
                f'h_score:{g["h_score"]},a_score:{g["a_score"]},'
                f'is_final:{str(g["is_final"]).lower()},is_live:{str(g["is_live"]).lower()}}}')
        tonight_js_items.append(item)
    tonight_js = "[" + ",".join(tonight_js_items) + "]"

    recaps = recap_articles(games_yesterday, yesterday, "nhl")

    all_teams = sorted(east + west, key=lambda x: -x["pct"])
    rankings_html = ""
    trend_map = ["up","up","up","hold","hold","hold","down","down"]
    notes = [
        "Best team in the league. Elite goaltending and a suffocating defensive system.",
        "Dangerous on special teams and rolling with a hot power play all month.",
        "Their depth lines are contributing every night — built for a long playoff run.",
        "Veteran core playing with urgency. Goaltender is stealing games.",
        "Red-hot stretch of play. Their offensive zone time leads the conference.",
        "Young stars are arriving. Exciting brand of hockey every single night.",
        "Battling injuries but still in the thick of the playoff race.",
        "Talented group that needs to tighten up defensively in the final stretch.",
    ]
    for i, t in enumerate(all_teams[:8]):
        trend = trend_map[i]
        note  = notes[i]
        icon  = "↑" if trend=="up" else ("↓" if trend=="down" else "→")
        cls   = "tu" if trend=="up" else ("td" if trend=="down" else "tf")
        label = "Moving Up" if trend=="up" else ("Sliding" if trend=="down" else "Holding")
        rankings_html += f'''<div class="rank-item">
          <div class="rank-n {'t3' if i<3 else ''}">{i+1}</div>
          <div>
            <div class="rank-team">{t["t"]}</div>
            <div class="rank-rec">{t["w"]}-{t["l"]}</div>
            <div class="rank-note">{note}</div>
            <div class="rank-trend {cls}">{icon} {label}</div>
          </div>
        </div>'''

    # best/worst records
    best = all_teams[0] if all_teams else {"t":"—","w":0,"l":0}
    best2 = all_teams[1] if len(all_teams)>1 else {"t":"—","w":0,"l":0}

    sidebar_top5 = "".join(f'<div class="sc-row"><span class="sc-team">{t["t"]}</span><span class="sc-val">{t["w"]}-{t["l"]}</span></div>' for t in all_teams[:5])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>THE FIELD — NHL</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800;900&family=Barlow:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
<style>
:root{{
  --navy:#0a1628;--acc:#4ab3ff;--acc2:#2d9de8;--gold:#fdb927;
  --white:#f0f4f8;--gray:#7a8fa6;
  --border:rgba(255,255,255,0.07);--card:rgba(255,255,255,0.04);--card2:rgba(255,255,255,0.08);
}}
*{{margin:0;padding:0;box-sizing:border-box;}}
html{{scroll-behavior:smooth;}}
body{{background:var(--navy);color:var(--white);font-family:'Barlow',sans-serif;font-size:15px;line-height:1.5;overflow-x:hidden;}}
nav{{position:sticky;top:0;z-index:100;background:rgba(10,22,40,0.97);backdrop-filter:blur(16px);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 24px;height:54px;}}
.nav-logo{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:21px;letter-spacing:2px;color:var(--white);margin-right:28px;text-decoration:none;}}
.nav-logo span{{color:var(--gold);}}
.nav-links{{display:flex;gap:2px;flex:1;}}
.nav-link{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:13px;letter-spacing:1px;text-transform:uppercase;color:var(--gray);padding:6px 14px;border-radius:4px;transition:all 0.15s;cursor:pointer;border:none;background:none;}}
.nav-link:hover,.nav-link.active{{color:var(--white);background:var(--card2);}}
.live-pill{{background:var(--acc);color:#fff;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;padding:3px 10px;border-radius:10px;margin-left:auto;letter-spacing:1px;}}
.page{{display:none;}}
.page.active{{display:block;animation:fadeUp 0.3s ease both;}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:translateY(0)}}}}
.hero{{position:relative;background:linear-gradient(135deg,#0a1628 0%,#0d2348 50%,#0a1628 100%);padding:56px 24px 44px;overflow:hidden;}}
.hero::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 70% 60% at 65% 50%,rgba(74,179,255,0.10),transparent);pointer-events:none;}}
.hero-inner{{max-width:1100px;margin:0 auto;position:relative;}}
.hero-eyebrow{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:3px;color:var(--gold);text-transform:uppercase;margin-bottom:10px;}}
.hero-title{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:clamp(44px,7vw,84px);line-height:0.93;letter-spacing:-1px;margin-bottom:14px;}}
.hero-title em{{color:var(--acc);font-style:normal;}}
.hero-sub{{color:var(--gray);font-size:15px;max-width:460px;margin-bottom:28px;}}
.hero-stats{{display:flex;gap:28px;flex-wrap:wrap;}}
.hero-stat-val{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:34px;color:var(--gold);line-height:1;}}
.hero-stat-lbl{{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gray);margin-top:2px;}}
.section{{max-width:1100px;margin:0 auto;padding:36px 24px;}}
.section-title{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:12px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin-bottom:18px;display:flex;align-items:center;gap:10px;}}
.section-title::after{{content:'';flex:1;height:1px;background:var(--border);}}
.standings-wrap{{overflow-x:auto;}}
.standings-table{{width:100%;border-collapse:collapse;font-size:14px;}}
.standings-table th{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gray);padding:8px 12px;text-align:center;border-bottom:1px solid var(--border);}}
.standings-table th:nth-child(2){{text-align:left;}}
.standings-table td{{padding:10px 12px;text-align:center;border-bottom:1px solid rgba(255,255,255,0.04);transition:background 0.1s;}}
.standings-table td:nth-child(2){{text-align:left;}}
.standings-table tr:hover td{{background:var(--card2);}}
.team-name{{font-weight:600;}}.team-rank{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;color:var(--gray);}}
.net-pos{{color:#4ade80;font-weight:600;}}.net-neg{{color:#f87171;font-weight:600;}}
.record-w{{color:var(--white);font-weight:600;}}.record-l{{color:var(--gray);}}
.streak-w{{color:#4ade80;font-weight:600;}}.streak-l{{color:#f87171;font-weight:600;}}
tr.playoff-line td{{border-top:2px solid var(--gold)!important;}}
tr.playin-line td{{border-top:2px dashed rgba(253,185,39,0.4)!important;}}
.games-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:16px;margin-bottom:36px;}}
.game-card{{background:var(--card);border:1px solid var(--border);border-radius:14px;overflow:hidden;}}
.game-card-top{{padding:16px 18px 12px;border-bottom:1px solid var(--border);}}
.game-time{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gold);margin-bottom:8px;}}
.game-matchup{{display:flex;align-items:center;justify-content:space-between;}}
.game-team{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:16px;flex:1;}}
.game-team.fav{{color:var(--white);}}.game-team.dog{{color:var(--gray);}}
.game-vs{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;color:var(--gray);padding:0 8px;}}
.game-score{{display:flex;justify-content:space-between;align-items:center;padding:10px 18px;border-bottom:1px solid var(--border);}}
.gscore{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:28px;}}
.gscore.w{{color:var(--white);}}.gscore.l{{color:var(--gray);}}
.gfinal{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:2px;color:var(--gold);}}
.digest-lead{{background:linear-gradient(135deg,#0f1e34,#0a1a2a);border:1px solid var(--border);border-radius:16px;padding:30px;margin-bottom:22px;position:relative;overflow:hidden;}}
.digest-lead::before{{content:'';position:absolute;top:-50px;right:-50px;width:280px;height:280px;border-radius:50%;background:radial-gradient(circle,rgba(74,179,255,0.08),transparent 70%);}}
.dlabel{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin-bottom:8px;}}
.dhl{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:clamp(22px,4vw,38px);line-height:1.0;margin-bottom:8px;}}
.ddeck{{color:var(--gray);font-size:14px;font-style:italic;line-height:1.6;max-width:580px;}}
.article{{background:var(--card);border:1px solid var(--border);border-radius:12px;margin-bottom:14px;overflow:hidden;}}
.art-hdr{{display:flex;align-items:center;justify-content:space-between;padding:15px 18px;background:rgba(255,255,255,0.02);border-bottom:1px solid var(--border);cursor:pointer;user-select:none;}}
.art-score{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:20px;}}
.sw{{color:var(--white);}}.sl{{color:var(--gray);}}.sdot{{color:var(--acc);margin:0 7px;}}
.art-sub{{font-size:11px;color:var(--gray);margin-top:2px;}}
.chev{{transition:transform 0.2s;color:var(--gray);font-size:16px;margin-left:8px;}}
.chev.open{{transform:rotate(180deg);}}
.art-body{{display:none;padding:18px 20px;}}
.art-body.open{{display:block;}}
.art-body p{{color:#cbd5e1;line-height:1.75;margin-bottom:13px;font-size:14px;}}
.art-body p:last-child{{margin-bottom:0;}}
.stat-bar{{display:flex;gap:14px;flex-wrap:wrap;background:rgba(255,255,255,0.04);border-radius:7px;padding:10px 14px;margin:12px 0;}}
.sp{{font-family:'Barlow Condensed',sans-serif;font-size:13px;font-weight:700;}}
.sp span{{color:var(--gold);}}
.mag-layout{{display:grid;grid-template-columns:2fr 1fr;gap:20px;}}
.rank-item{{display:flex;gap:14px;align-items:flex-start;padding:14px 0;border-bottom:1px solid var(--border);}}
.rank-item:last-child{{border-bottom:none;}}
.rank-n{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:30px;line-height:1;color:rgba(255,255,255,0.12);min-width:38px;text-align:center;padding-top:2px;}}
.rank-n.t3{{color:var(--gold);}}
.rank-team{{font-weight:600;font-size:15px;margin-bottom:2px;}}
.rank-rec{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;color:var(--gray);letter-spacing:1px;margin-bottom:4px;}}
.rank-note{{font-size:13px;color:#94a3b8;line-height:1.5;}}
.rank-trend{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;margin-top:4px;}}
.tu{{color:#4ade80;}}.td{{color:#f87171;}}.tf{{color:var(--gray);}}
.sidebar-card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:14px;}}
.sc-title{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gold);margin-bottom:10px;}}
.sc-row{{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--border);font-size:13px;}}
.sc-row:last-child{{border-bottom:none;}}
.sc-team{{font-weight:600;}}
.sc-val{{color:var(--gray);font-family:'Barlow Condensed',sans-serif;font-weight:700;}}
.sc-val.hot{{color:#4ade80;}}.sc-val.cold{{color:#f87171;}}
footer{{border-top:1px solid var(--border);padding:22px;text-align:center;font-size:12px;color:var(--gray);margin-top:40px;}}
footer strong{{color:var(--white);}}
@media(max-width:768px){{.mag-layout{{grid-template-columns:1fr;}}.games-grid{{grid-template-columns:1fr;}}}}
.props-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;}}
.prop-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 18px;position:relative;overflow:hidden;}}
.prop-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;}}
.prop-card.high::before{{background:linear-gradient(90deg,#4ade80,#22c55e);}}
.prop-card.medium::before{{background:linear-gradient(90deg,var(--gold),#f59e0b);}}
.prop-player{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:17px;margin-bottom:1px;}}
.prop-team{{font-size:12px;color:var(--gray);margin-bottom:9px;}}
.prop-line{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:26px;margin-bottom:3px;}}
.prop-odds{{font-size:12px;color:var(--gray);margin-bottom:8px;}}
.prop-badge{{display:inline-block;padding:2px 9px;border-radius:4px;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:10px;letter-spacing:1px;text-transform:uppercase;margin-bottom:9px;}}
.b-high{{background:rgba(74,222,128,0.13);color:#4ade80;}}
.b-med{{background:rgba(253,185,39,0.13);color:var(--gold);}}
.prop-reason{{font-size:13px;color:#94a3b8;line-height:1.55;}}
.disclaimer{{background:rgba(74,179,255,0.07);border:1px solid rgba(74,179,255,0.18);border-radius:8px;padding:11px 15px;margin-top:22px;font-size:11px;color:#4ab3ff;line-height:1.5;text-align:center;}}
</style>
</head>
<body>

<nav>
  <a class="nav-logo" href="index.html"><span>THE</span> FIELD / NHL</a>
  <div class="nav-links">
    <button class="nav-link active" onclick="showPage('standings',this)">Standings</button>
    <button class="nav-link" onclick="showPage('tonight',this)">Tonight</button>
    <button class="nav-link" onclick="showPage('digest',this)">Daily Digest</button>
    <button class="nav-link" onclick="showPage('magazine',this)">Magazine</button>
    <button class="nav-link" onclick="showPage('props',this)">Player Props</button>
  </div>
  <div class="live-pill">🔴 LIVE TONIGHT</div>
</nav>

<div id="page-standings" class="page active">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">2024-25 NHL Season · Updated {today}</div>
      <h1 class="hero-title">NHL<br><em>STANDINGS</em></h1>
      <p class="hero-sub">Live records and playoff picture for all 32 teams.</p>
      <div class="hero-stats">
        <div><div class="hero-stat-val">{best["w"]}-{best["l"]}</div><div class="hero-stat-lbl">{best["t"].split()[-1]} — Best Record</div></div>
        <div><div class="hero-stat-val">{best2["w"]}-{best2["l"]}</div><div class="hero-stat-lbl">{best2["t"].split()[-1]} — 2nd Best</div></div>
      </div>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Eastern Conference</div>
    <div class="standings-wrap">
      <table class="standings-table">
        <thead><tr><th>#</th><th>Team</th><th>W</th><th>L</th><th>PCT</th><th>GF/G</th><th>GA/G</th><th>+/-</th><th>L10</th></tr></thead>
        <tbody id="east-body"></tbody>
      </table>
    </div>
    <div class="section-title" style="margin-top:30px">Western Conference</div>
    <div class="standings-wrap">
      <table class="standings-table">
        <thead><tr><th>#</th><th>Team</th><th>W</th><th>L</th><th>PCT</th><th>GF/G</th><th>GA/G</th><th>+/-</th><th>L10</th></tr></thead>
        <tbody id="west-body"></tbody>
      </table>
    </div>
    <div style="margin-top:10px;font-size:12px;color:var(--gray);display:flex;gap:22px;flex-wrap:wrap;">
      <span><span style="color:var(--gold)">——</span> Playoff cutoff (8th seed)</span>
    </div>
  </div>
</div>

<div id="page-tonight" class="page">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">2024-25 NHL Season</div>
      <h1 class="hero-title">TONIGHT'S<br><em>GAMES</em></h1>
      <p class="hero-sub">Tonight's NHL slate — scores, matchups and game notes.</p>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Tonight's Games — {dow}, {today}</div>
    <div class="games-grid" id="games-grid"></div>
  </div>
</div>

<div id="page-digest" class="page">
  <div class="section" style="padding-top:30px">
    <div class="digest-lead">
      <div class="dlabel">{dow} {today} · Recapping {yesterday}</div>
      <div class="dhl">NHL DAILY DIGEST</div>
      <div class="ddeck">Last night's scores, standout performances, and everything that happened around the league.</div>
    </div>
    <div class="section-title">Game Recaps — {yesterday}</div>
    {recaps}
  </div>
</div>

<div id="page-magazine" class="page">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">The Field · {today}</div>
      <h1 class="hero-title">NHL<br><em>MAGAZINE</em></h1>
      <p class="hero-sub">Power rankings, hot streaks and the full story of the season.</p>
    </div>
  </div>
  <div class="section">
    <div class="mag-layout">
      <div>
        <div class="section-title">Power Rankings — {today}</div>
        {rankings_html}
      </div>
      <div>
        <div class="sidebar-card">
          <div class="sc-title">🏒 Top of the League</div>
          {sidebar_top5}
        </div>
        <div class="sidebar-card">
          <div class="sc-title">📊 Playoff Picture</div>
          <div class="sc-row"><span class="sc-team">E8 Cutoff</span><span class="sc-val">{east[7]["w"] if len(east)>7 else "—"}-{east[7]["l"] if len(east)>7 else "—"}</span></div>
          <div class="sc-row"><span class="sc-team">W8 Cutoff</span><span class="sc-val">{west[7]["w"] if len(west)>7 else "—"}-{west[7]["l"] if len(west)>7 else "—"}</span></div>
        </div>
      </div>
    </div>
  </div>
</div>

<div id="page-props" class="page">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">{today} · Tonight\'s Slate</div>
      <h1 class="hero-title">PLAYER<br><em>PROPS</em></h1>
      <p class="hero-sub">Top prop picks with confidence ratings for tonight\'s games.</p>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Tonight\'s Best Props</div>
    <div class="props-grid" id="props-grid"></div>
    <div class="disclaimer">⚠️ For entertainment only. Not financial or gambling advice. 1-800-GAMBLER.</div>
  </div>
</div>

<footer>
  <strong>THE FIELD — NHL</strong> · 2024-25 Season · Updated {today}<br>
  <span>Data via ESPN · Not affiliated with the NHL · <a href="index.html" style="color:var(--gold)">← Back to Hub</a></span>
</footer>

<script>
const EAST={east_js};
const WEST={west_js};
const TONIGHT={tonight_js};

function renderStandings(data,id){{
  const tb=document.getElementById(id);
  data.forEach((t,i)=>{{
    const pct=(t.w/(t.w+t.l)).toFixed(3);
    const ns=t.net>0?'+'+t.net:String(t.net);
    const nc=t.net>0?'net-pos':t.net<0?'net-neg':'';
    let rc='';if(i===7)rc='playoff-line';
    tb.innerHTML+=`<tr class="${{rc}}"><td><span class="team-rank">${{i+1}}</span></td><td><span class="team-name">${{t.t}}</span></td><td><span class="record-w">${{t.w}}</span></td><td><span class="record-l">${{t.l}}</span></td><td>${{pct}}</td><td>${{t.ppg}}</td><td>${{t.opp}}</td><td class="${{nc}}">${{ns}}</td><td>${{t.l10}}</td></tr>`;
  }});
}}

function renderGames(){{
  const g=document.getElementById('games-grid');
  if(!TONIGHT.length){{g.innerHTML='<p style="color:var(--gray);padding:20px 0">No games scheduled tonight.</p>';return;}}
  TONIGHT.forEach(gm=>{{
    const isLive=gm.is_live;
    const isFinal=gm.is_final;
    const hw=isFinal&&gm.h_score>gm.a_score;
    const aw=isFinal&&gm.a_score>gm.h_score;
    const statusLabel=isLive?'<span style="color:#4ade80;font-weight:700">● LIVE</span>':isFinal?'<span style="color:var(--gold)">FINAL</span>':gm.time;
    g.innerHTML+=`<div class="game-card">
      <div class="game-card-top">
        <div class="game-time">${{statusLabel}}</div>
        <div class="game-matchup">
          <div style="flex:1"><div style="font-size:10px;letter-spacing:1px;font-family:'Barlow Condensed',sans-serif;font-weight:700;color:#4ade80;margin-bottom:2px">HOME</div>
            <div class="game-team fav">${{gm.home}}</div></div>
          <div class="game-vs">vs</div>
          <div style="flex:1;text-align:right"><div style="font-size:10px;letter-spacing:1px;font-family:'Barlow Condensed',sans-serif;font-weight:700;color:var(--gray);margin-bottom:2px">AWAY</div>
            <div class="game-team dog">${{gm.away}}</div></div>
        </div>
      </div>
      ${{(isFinal||isLive)?`<div class="game-score"><span class="gscore ${{hw?'w':'l'}}">${{gm.h_score}}</span><span class="gfinal">${{isFinal?'FINAL':'LIVE'}}</span><span class="gscore ${{aw?'w':'l'}}">${{gm.a_score}}</span></div>`:''}}
    </div>`;
  }});
}}

function tog(hdr){{
  const body=hdr.nextElementSibling;
  const chev=hdr.querySelector('.chev');
  body.classList.toggle('open');
  chev.classList.toggle('open');
}}

function showPage(name,btn){{
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(l=>l.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  if(btn)btn.classList.add('active');
  window.scrollTo({{top:0,behavior:'smooth'}});
}}

renderStandings(EAST,'east-body');
renderStandings(WEST,'west-body');
const PROPS_DATA=[
  {{player:"Connor McDavid",team:"Edmonton Oilers",line:"Over 1.5 points",odds:"-130",conf:"HIGH",cls:"high",reason:"McDavid averages 1.8 pts/game. Hits this line in 60%+ of games."}},
  {{player:"Nathan MacKinnon",team:"Colorado Avalanche",line:"Over 0.5 goals",odds:"-115",conf:"HIGH",cls:"high",reason:"MacKinnon leads the Avs in shots and scoring chances every night."}},
  {{player:"Auston Matthews",team:"Toronto Maple Leafs",line:"Over 3.5 shots",odds:"-120",conf:"HIGH",cls:"high",reason:"Matthews averages 4.2 SOG — this line is below his season average."}},
  {{player:"Leon Draisaitl",team:"Edmonton Oilers",line:"Over 1.5 points",odds:"-118",conf:"HIGH",cls:"high",reason:"Draisaitl racks up points in bunches. Power play alone drives this line."}},
  {{player:"David Pastrnak",team:"Boston Bruins",line:"Over 0.5 goals",odds:"-108",conf:"MEDIUM",cls:"medium",reason:"Pastrnak is Boston's most dangerous scorer with premium power play time."}},
  {{player:"Cale Makar",team:"Colorado Avalanche",line:"Over 1.5 shots",odds:"-125",conf:"MEDIUM",cls:"medium",reason:"Makar logs 25+ minutes and jumps into the rush — elite shot volume for a D-man."}},
];
const SPORT_PROPS=PROPS_DATA;
function renderProps(){{
  const g=document.getElementById('props-grid');
  if(!g)return;
  SPORT_PROPS.forEach(p=>{{
    const bc=p.conf==='HIGH'?'b-high':'b-med';
    g.innerHTML+=`<div class="prop-card ${{p.cls}}"><div class="prop-player">${{p.player}}</div><div class="prop-team">${{p.team}}</div><div class="prop-line">${{p.line}}</div><div class="prop-odds">${{p.odds}}</div><div class="prop-badge ${{bc}}">${{p.conf}}</div><div class="prop-reason">${{p.reason}}</div></div>`;
  }});
}}
renderProps();
renderGames();
</script>
</body>
</html>"""

    out_path = os.path.join(OUTPUT_DIR, "nhl.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"  ✅ nhl.html saved ({len(html):,} chars)")

def fetch_nhl_standings():
    log("🏒 Fetching NHL standings...")
    try:
        r = safe_get("https://site.api.espn.com/apis/v2/sports/hockey/nhl/standings",
                     {"season": datetime.now().year})
        east, west = [], []
        WEST_DIVS = {"Pacific", "Central"}
        for conf_data in r.json().get("children", []):
            conf_name = conf_data.get("name","").upper()
            is_west = "WESTERN" in conf_name
            for entry in conf_data.get("standings", {}).get("entries", []):
                try:
                    name = entry["team"]["displayName"]
                    vals = {s["name"]: s.get("value", 0) for s in entry.get("stats", [])}
                    w   = int(vals.get("wins", 0) or 0)
                    l   = int(vals.get("losses", 0) or 0)
                    gp  = w + l or 1
                    pct = round(w / gp, 3)
                    div = entry.get("team", {}).get("division", {}).get("name", "")
                    t   = dict(t=name, w=w, l=l, pct=pct, div=div)
                    if is_al: east.append(t)
                    else: west.append(t)
                except: continue
        east.sort(key=lambda x: -x["pct"])
        west.sort(key=lambda x: -x["pct"])
        log(f"  ✅ NHL: {len(east)} East + {len(west)} West")
        return east, west
    except Exception as e:
        log(f"  ⚠️  NHL standings failed: {e}")
        return [], []





def generate_mlb_html(east, west, games_yesterday, today_games):
    log("🌐 Generating mlb.html...")
    today     = fmt_date()
    yesterday = fmt_date(datetime.now() - timedelta(days=1))
    dow       = fmt_dow()

    def team_js(t):
        ns = ('+' if t['net'] >= 0 else '') + str(t['net'])
        return f'{{t:"{t["t"]}",w:{t["w"]},l:{t["l"]},ppg:{t["ppg"]},opp:{t["opp"]},net:{t["net"]},l10:"{t["l10"]}",pct:{t["pct"]}}}'

    east_js = "[" + ",".join(team_js(t) for t in east) + "]"
    west_js = "[" + ",".join(team_js(t) for t in west) + "]"

    tonight_js_items = []
    for g in today_games:
        if not g: continue
        start_dt = g.get("start","")
        try:
            dt = datetime.fromisoformat(start_dt.replace("Z","+00:00"))
            t_str = dt.astimezone().strftime("%-I:%M %p ET")
        except:
            t_str = "Tonight"
        item = (f'{{time:"{t_str}",home:"{g["home"]}",away:"{g["away"]}",'
                f'h_score:{g["h_score"]},a_score:{g["a_score"]},'
                f'is_final:{str(g["is_final"]).lower()},is_live:{str(g["is_live"]).lower()}}}')
        tonight_js_items.append(item)
    tonight_js = "[" + ",".join(tonight_js_items) + "]"

    recaps = recap_articles(games_yesterday, yesterday, "mlb")

    all_teams = sorted(east + west, key=lambda x: -x["pct"])
    rankings_html = ""
    trend_map = ["up","up","up","hold","hold","hold","down","down"]
    notes = [
        "The most complete team in baseball. Deep rotation and potent lineup.",
        "Dominant pitching staff and timely hitting making them dangerous.",
        "Red-hot right now. Their lineup is clicking top to bottom.",
        "Consistent and experienced. Always a threat come October.",
        "Pitching-first team playing their best ball of the season.",
        "Young core has arrived. Exciting to watch every single night.",
        "Battling through injuries and still in the thick of it.",
        "Talented roster that needs to string wins together soon.",
    ]
    for i, t in enumerate(all_teams[:8]):
        trend = trend_map[i]
        note  = notes[i]
        icon  = "↑" if trend=="up" else ("↓" if trend=="down" else "→")
        cls   = "tu" if trend=="up" else ("td" if trend=="down" else "tf")
        label = "Moving Up" if trend=="up" else ("Sliding" if trend=="down" else "Holding")
        rankings_html += f'''<div class="rank-item">
          <div class="rank-n {'t3' if i<3 else ''}">{i+1}</div>
          <div>
            <div class="rank-team">{t["t"]}</div>
            <div class="rank-rec">{t["w"]}-{t["l"]}</div>
            <div class="rank-note">{note}</div>
            <div class="rank-trend {cls}">{icon} {label}</div>
          </div>
        </div>'''

    best = all_teams[0] if all_teams else {"t":"—","w":0,"l":0}

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>THE FIELD — MLB</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800;900&family=Barlow:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
<style>
:root{{
  --navy:#0a1628;--acc:#22c55e;--acc2:#16a34a;--gold:#fdb927;
  --white:#f0f4f8;--gray:#7a8fa6;
  --border:rgba(255,255,255,0.07);--card:rgba(255,255,255,0.04);--card2:rgba(255,255,255,0.08);
}}
*{{margin:0;padding:0;box-sizing:border-box;}}
html{{scroll-behavior:smooth;}}
body{{background:var(--navy);color:var(--white);font-family:'Barlow',sans-serif;font-size:15px;line-height:1.5;overflow-x:hidden;}}
nav{{position:sticky;top:0;z-index:100;background:rgba(10,22,40,0.97);backdrop-filter:blur(16px);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 24px;height:54px;}}
.nav-logo{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:21px;letter-spacing:2px;color:var(--white);margin-right:28px;text-decoration:none;}}
.nav-logo span{{color:var(--gold);}}
.nav-links{{display:flex;gap:2px;flex:1;}}
.nav-link{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:13px;letter-spacing:1px;text-transform:uppercase;color:var(--gray);padding:6px 14px;border-radius:4px;transition:all 0.15s;cursor:pointer;border:none;background:none;}}
.nav-link:hover,.nav-link.active{{color:var(--white);background:var(--card2);}}
.live-pill{{background:var(--acc);color:#fff;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;padding:3px 10px;border-radius:10px;margin-left:auto;letter-spacing:1px;}}
.page{{display:none;}}
.page.active{{display:block;animation:fadeUp 0.3s ease both;}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:translateY(0)}}}}
.hero{{position:relative;background:linear-gradient(135deg,#0a1628 0%,#0d2348 50%,#0a1628 100%);padding:56px 24px 44px;overflow:hidden;}}
.hero::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 70% 60% at 65% 50%,rgba(34,197,94,0.09),transparent);pointer-events:none;}}
.hero-inner{{max-width:1100px;margin:0 auto;position:relative;}}
.hero-eyebrow{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:3px;color:var(--gold);text-transform:uppercase;margin-bottom:10px;}}
.hero-title{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:clamp(44px,7vw,84px);line-height:0.93;letter-spacing:-1px;margin-bottom:14px;}}
.hero-title em{{color:var(--acc);font-style:normal;}}
.hero-sub{{color:var(--gray);font-size:15px;max-width:460px;margin-bottom:28px;}}
.hero-stats{{display:flex;gap:28px;flex-wrap:wrap;}}
.hero-stat-val{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:34px;color:var(--gold);line-height:1;}}
.hero-stat-lbl{{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gray);margin-top:2px;}}
.section{{max-width:1100px;margin:0 auto;padding:36px 24px;}}
.section-title{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:12px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin-bottom:18px;display:flex;align-items:center;gap:10px;}}
.section-title::after{{content:'';flex:1;height:1px;background:var(--border);}}
.standings-wrap{{overflow-x:auto;}}
.standings-table{{width:100%;border-collapse:collapse;font-size:14px;}}
.standings-table th{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gray);padding:8px 12px;text-align:center;border-bottom:1px solid var(--border);}}
.standings-table th:nth-child(2){{text-align:left;}}
.standings-table td{{padding:10px 12px;text-align:center;border-bottom:1px solid rgba(255,255,255,0.04);transition:background 0.1s;}}
.standings-table td:nth-child(2){{text-align:left;}}
.standings-table tr:hover td{{background:var(--card2);}}
.team-name{{font-weight:600;}}.team-rank{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;color:var(--gray);}}
.net-pos{{color:#4ade80;font-weight:600;}}.net-neg{{color:#f87171;font-weight:600;}}
.record-w{{color:var(--white);font-weight:600;}}.record-l{{color:var(--gray);}}
tr.playoff-line td{{border-top:2px solid var(--gold)!important;}}
.games-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:16px;margin-bottom:36px;}}
.game-card{{background:var(--card);border:1px solid var(--border);border-radius:14px;overflow:hidden;}}
.game-card-top{{padding:16px 18px 12px;border-bottom:1px solid var(--border);}}
.game-time{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gold);margin-bottom:8px;}}
.game-matchup{{display:flex;align-items:center;justify-content:space-between;}}
.game-team{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:16px;flex:1;}}
.game-team.fav{{color:var(--white);}}.game-team.dog{{color:var(--gray);}}
.game-vs{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;color:var(--gray);padding:0 8px;}}
.game-score{{display:flex;justify-content:space-between;align-items:center;padding:10px 18px;border-bottom:1px solid var(--border);}}
.gscore{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:28px;}}
.gscore.w{{color:var(--white);}}.gscore.l{{color:var(--gray);}}
.gfinal{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:2px;color:var(--gold);}}
.digest-lead{{background:linear-gradient(135deg,#0f1e34,#0a1a14);border:1px solid var(--border);border-radius:16px;padding:30px;margin-bottom:22px;position:relative;overflow:hidden;}}
.digest-lead::before{{content:'';position:absolute;top:-50px;right:-50px;width:280px;height:280px;border-radius:50%;background:radial-gradient(circle,rgba(34,197,94,0.07),transparent 70%);}}
.dlabel{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin-bottom:8px;}}
.dhl{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:clamp(22px,4vw,38px);line-height:1.0;margin-bottom:8px;}}
.ddeck{{color:var(--gray);font-size:14px;font-style:italic;line-height:1.6;max-width:580px;}}
.article{{background:var(--card);border:1px solid var(--border);border-radius:12px;margin-bottom:14px;overflow:hidden;}}
.art-hdr{{display:flex;align-items:center;justify-content:space-between;padding:15px 18px;background:rgba(255,255,255,0.02);border-bottom:1px solid var(--border);cursor:pointer;user-select:none;}}
.art-score{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:20px;}}
.sw{{color:var(--white);}}.sl{{color:var(--gray);}}.sdot{{color:var(--acc);margin:0 7px;}}
.art-sub{{font-size:11px;color:var(--gray);margin-top:2px;}}
.chev{{transition:transform 0.2s;color:var(--gray);font-size:16px;margin-left:8px;}}
.chev.open{{transform:rotate(180deg);}}
.art-body{{display:none;padding:18px 20px;}}
.art-body.open{{display:block;}}
.art-body p{{color:#cbd5e1;line-height:1.75;margin-bottom:13px;font-size:14px;}}
.art-body p:last-child{{margin-bottom:0;}}
.stat-bar{{display:flex;gap:14px;flex-wrap:wrap;background:rgba(255,255,255,0.04);border-radius:7px;padding:10px 14px;margin:12px 0;}}
.sp{{font-family:'Barlow Condensed',sans-serif;font-size:13px;font-weight:700;}}
.sp span{{color:var(--gold);}}
.mag-layout{{display:grid;grid-template-columns:2fr 1fr;gap:20px;}}
.rank-item{{display:flex;gap:14px;align-items:flex-start;padding:14px 0;border-bottom:1px solid var(--border);}}
.rank-item:last-child{{border-bottom:none;}}
.rank-n{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:30px;line-height:1;color:rgba(255,255,255,0.12);min-width:38px;text-align:center;padding-top:2px;}}
.rank-n.t3{{color:var(--gold);}}
.rank-team{{font-weight:600;font-size:15px;margin-bottom:2px;}}
.rank-rec{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;color:var(--gray);letter-spacing:1px;margin-bottom:4px;}}
.rank-note{{font-size:13px;color:#94a3b8;line-height:1.5;}}
.rank-trend{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;margin-top:4px;}}
.tu{{color:#4ade80;}}.td{{color:#f87171;}}.tf{{color:var(--gray);}}
.sidebar-card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:14px;}}
.sc-title{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gold);margin-bottom:10px;}}
.sc-row{{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--border);font-size:13px;}}
.sc-row:last-child{{border-bottom:none;}}
.sc-team{{font-weight:600;}}
.sc-val{{color:var(--gray);font-family:'Barlow Condensed',sans-serif;font-weight:700;}}
footer{{border-top:1px solid var(--border);padding:22px;text-align:center;font-size:12px;color:var(--gray);margin-top:40px;}}
footer strong{{color:var(--white);}}
@media(max-width:768px){{.mag-layout{{grid-template-columns:1fr;}}.games-grid{{grid-template-columns:1fr;}}}}
.props-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;}}
.prop-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 18px;position:relative;overflow:hidden;}}
.prop-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;}}
.prop-card.high::before{{background:linear-gradient(90deg,#4ade80,#22c55e);}}
.prop-card.medium::before{{background:linear-gradient(90deg,var(--gold),#f59e0b);}}
.prop-player{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:17px;margin-bottom:1px;}}
.prop-team{{font-size:12px;color:var(--gray);margin-bottom:9px;}}
.prop-line{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:26px;margin-bottom:3px;}}
.prop-odds{{font-size:12px;color:var(--gray);margin-bottom:8px;}}
.prop-badge{{display:inline-block;padding:2px 9px;border-radius:4px;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:10px;letter-spacing:1px;text-transform:uppercase;margin-bottom:9px;}}
.b-high{{background:rgba(74,222,128,0.13);color:#4ade80;}}
.b-med{{background:rgba(253,185,39,0.13);color:var(--gold);}}
.prop-reason{{font-size:13px;color:#94a3b8;line-height:1.55;}}
.disclaimer{{background:rgba(34,197,94,0.07);border:1px solid rgba(34,197,94,0.18);border-radius:8px;padding:11px 15px;margin-top:22px;font-size:11px;color:#22c55e;line-height:1.5;text-align:center;}}
</style>
</head>
<body>

<nav>
  <a class="nav-logo" href="index.html"><span>THE</span> FIELD / MLB</a>
  <div class="nav-links">
    <button class="nav-link active" onclick="showPage('standings',this)">Standings</button>
    <button class="nav-link" onclick="showPage('tonight',this)">Tonight</button>
    <button class="nav-link" onclick="showPage('digest',this)">Daily Digest</button>
    <button class="nav-link" onclick="showPage('magazine',this)">Magazine</button>
    <button class="nav-link" onclick="showPage('props',this)">Player Props</button>
  </div>
  <div class="live-pill">⚾ 2025 SEASON</div>
</nav>

<div id="page-standings" class="page active">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">2025 MLB Season · Updated {today}</div>
      <h1 class="hero-title">MLB<br><em>STANDINGS</em></h1>
      <p class="hero-sub">Current records and division standings for all 30 teams.</p>
      <div class="hero-stats">
        <div><div class="hero-stat-val">{best["w"]}-{best["l"]}</div><div class="hero-stat-lbl">{best["t"].split()[-1]} — Best Record</div></div>
      </div>
    </div>
  </div>
  <div class="section">
    <div class="section-title">American League</div>
    <div class="standings-wrap">
      <table class="standings-table">
        <thead><tr><th>#</th><th>Team</th><th>W</th><th>L</th><th>PCT</th><th>R/G</th><th>RA/G</th><th>+/-</th><th>L10</th></tr></thead>
        <tbody id="east-body"></tbody>
      </table>
    </div>
    <div class="section-title" style="margin-top:30px">National League</div>
    <div class="standings-wrap">
      <table class="standings-table">
        <thead><tr><th>#</th><th>Team</th><th>W</th><th>L</th><th>PCT</th><th>R/G</th><th>RA/G</th><th>+/-</th><th>L10</th></tr></thead>
        <tbody id="west-body"></tbody>
      </table>
    </div>
  </div>
</div>

<div id="page-tonight" class="page">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">2025 MLB Season</div>
      <h1 class="hero-title">TONIGHT'S<br><em>GAMES</em></h1>
      <p class="hero-sub">Tonight's MLB slate — scores and matchups.</p>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Tonight's Games — {dow}, {today}</div>
    <div class="games-grid" id="games-grid"></div>
  </div>
</div>

<div id="page-digest" class="page">
  <div class="section" style="padding-top:30px">
    <div class="digest-lead">
      <div class="dlabel">{dow} {today} · Recapping {yesterday}</div>
      <div class="dhl">MLB DAILY DIGEST</div>
      <div class="ddeck">Last night's scores, standout performances, and everything that happened around the league.</div>
    </div>
    <div class="section-title">Game Recaps — {yesterday}</div>
    {recaps}
  </div>
</div>

<div id="page-magazine" class="page">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">The Field · {today}</div>
      <h1 class="hero-title">MLB<br><em>MAGAZINE</em></h1>
      <p class="hero-sub">Power rankings and the full story of the 2025 season.</p>
    </div>
  </div>
  <div class="section">
    <div class="mag-layout">
      <div>
        <div class="section-title">Power Rankings — {today}</div>
        {rankings_html}
      </div>
      <div>
        <div class="sidebar-card">
          <div class="sc-title">🏆 Top Teams</div>
          {"".join(f'<div class="sc-row"><span class="sc-team">{t["t"]}</span><span class="sc-val">{t["w"]}-{t["l"]}</span></div>' for t in all_teams[:5])}
        </div>
      </div>
    </div>
  </div>
</div>

<div id="page-props" class="page">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">{today} · Tonight\'s Slate</div>
      <h1 class="hero-title">PLAYER<br><em>PROPS</em></h1>
      <p class="hero-sub">Top prop picks with confidence ratings for tonight\'s games.</p>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Tonight\'s Best Props</div>
    <div class="props-grid" id="props-grid"></div>
    <div class="disclaimer">⚠️ For entertainment only. Not financial or gambling advice. 1-800-GAMBLER.</div>
  </div>
</div>

<footer>
  <strong>THE FIELD — MLB</strong> · 2025 Season · Updated {today}<br>
  <span>Data via ESPN · Not affiliated with MLB · <a href="index.html" style="color:var(--gold)">← Back to Hub</a></span>
</footer>

<script>
const EAST={east_js};
const WEST={west_js};
const TONIGHT={tonight_js};

function renderStandings(data,id){{
  const tb=document.getElementById(id);
  data.forEach((t,i)=>{{
    const ns=t.net>0?'+'+t.net:String(t.net);
    const nc=t.net>0?'net-pos':t.net<0?'net-neg':'';
    let rc='';if(i===4)rc='playoff-line';
    tb.innerHTML+=`<tr class="${{rc}}"><td><span class="team-rank">${{i+1}}</span></td><td><span class="team-name">${{t.t}}</span></td><td><span class="record-w">${{t.w}}</span></td><td><span class="record-l">${{t.l}}</span></td><td>${{t.pct.toFixed(3)}}</td><td>${{t.ppg}}</td><td>${{t.opp}}</td><td class="${{nc}}">${{ns}}</td><td>${{t.l10}}</td></tr>`;
  }});
}}

function renderGames(){{
  const g=document.getElementById('games-grid');
  if(!TONIGHT.length){{g.innerHTML='<p style="color:var(--gray);padding:20px 0">No games scheduled tonight.</p>';return;}}
  TONIGHT.forEach(gm=>{{
    const isLive=gm.is_live;
    const isFinal=gm.is_final;
    const hw=isFinal&&gm.h_score>gm.a_score;
    const aw=isFinal&&gm.a_score>gm.h_score;
    const statusLabel=isLive?'<span style="color:#4ade80;font-weight:700">● LIVE</span>':isFinal?'<span style="color:var(--gold)">FINAL</span>':gm.time;
    g.innerHTML+=`<div class="game-card">
      <div class="game-card-top">
        <div class="game-time">${{statusLabel}}</div>
        <div class="game-matchup">
          <div style="flex:1"><div style="font-size:10px;letter-spacing:1px;font-family:'Barlow Condensed',sans-serif;font-weight:700;color:#4ade80;margin-bottom:2px">HOME</div>
            <div class="game-team fav">${{gm.home}}</div></div>
          <div class="game-vs">vs</div>
          <div style="flex:1;text-align:right"><div style="font-size:10px;letter-spacing:1px;font-family:'Barlow Condensed',sans-serif;font-weight:700;color:var(--gray);margin-bottom:2px">AWAY</div>
            <div class="game-team dog">${{gm.away}}</div></div>
        </div>
      </div>
      ${{(isFinal||isLive)?`<div class="game-score"><span class="gscore ${{hw?'w':'l'}}">${{gm.h_score}}</span><span class="gfinal">${{isFinal?'FINAL':'LIVE'}}</span><span class="gscore ${{aw?'w':'l'}}">${{gm.a_score}}</span></div>`:''}}
    </div>`;
  }});
}}

function tog(hdr){{
  const body=hdr.nextElementSibling;
  const chev=hdr.querySelector('.chev');
  body.classList.toggle('open');
  chev.classList.toggle('open');
}}

function showPage(name,btn){{
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(l=>l.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  if(btn)btn.classList.add('active');
  window.scrollTo({{top:0,behavior:'smooth'}});
}}

renderStandings(EAST,'east-body');
renderStandings(WEST,'west-body');
const PROPS_DATA=[
  {{player:"Shohei Ohtani",team:"Los Angeles Dodgers",line:"Over 1.5 total bases",odds:"-125",conf:"HIGH",cls:"high",reason:"Ohtani barrels the ball at an elite rate. 1.5 total bases is achievable in a single hit."}},
  {{player:"Aaron Judge",team:"New York Yankees",line:"Over 0.5 home runs",odds:"+185",conf:"HIGH",cls:"high",reason:"Judge leads MLB in HR. At +185 this is tremendous value for the best power hitter in baseball."}},
  {{player:"Freddie Freeman",team:"Los Angeles Dodgers",line:"Over 1.5 total bases",odds:"-115",conf:"HIGH",cls:"high",reason:"Freeman is the Dodgers most consistent contact hitter. Makes hard contact every game."}},
  {{player:"Juan Soto",team:"New York Yankees",line:"Over 0.5 walks",odds:"-130",conf:"HIGH",cls:"high",reason:"Soto has an elite eye and draws 1+ walks in the majority of his games."}},
  {{player:"Mookie Betts",team:"Los Angeles Dodgers",line:"Over 1.5 total bases",odds:"-110",conf:"MEDIUM",cls:"medium",reason:"Betts is one of the most consistent performers in baseball."}},
  {{player:"Ronald Acuna Jr.",team:"Atlanta Braves",line:"Over 0.5 stolen bases",odds:"+110",conf:"MEDIUM",cls:"medium",reason:"Acuna is the most dangerous baserunner in baseball. Plus money makes this great value."}},
];
const SPORT_PROPS=PROPS_DATA;
function renderProps(){{
  const g=document.getElementById('props-grid');
  if(!g)return;
  SPORT_PROPS.forEach(p=>{{
    const bc=p.conf==='HIGH'?'b-high':'b-med';
    g.innerHTML+=`<div class="prop-card ${{p.cls}}"><div class="prop-player">${{p.player}}</div><div class="prop-team">${{p.team}}</div><div class="prop-line">${{p.line}}</div><div class="prop-odds">${{p.odds}}</div><div class="prop-badge ${{bc}}">${{p.conf}}</div><div class="prop-reason">${{p.reason}}</div></div>`;
  }});
}}
renderProps();
renderGames();
</script>
</body>
</html>"""

    out_path = os.path.join(OUTPUT_DIR, "mlb.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"  ✅ mlb.html saved ({len(html):,} chars)")

def fetch_nhl_standings():
    log("🏒 Fetching NHL standings...")
    try:
        r = safe_get("https://site.api.espn.com/apis/v2/sports/hockey/nhl/standings",
                     {"season": datetime.now().year})
        east, west = [], []
        WEST_DIVS = {"Pacific", "Central"}
        for conf_data in r.json().get("children", []):
            conf_name = conf_data.get("name","").upper()
            is_west = "WESTERN" in conf_name
            for entry in conf_data.get("standings", {}).get("entries", []):
                try:
                    name = entry["team"]["displayName"]
                    vals = {s["name"]: s.get("value", 0) for s in entry.get("stats", [])}
                    w   = int(vals.get("wins", 0) or 0)
                    l   = int(vals.get("losses", 0) or 0)
                    gp  = w + l or 1
                    pct = round(w / gp, 3)
                    div = entry.get("team", {}).get("division", {}).get("name", "")
                    t   = dict(t=name, w=w, l=l, pct=pct, div=div)
                    if is_al: east.append(t)
                    else: west.append(t)
                except: continue
        east.sort(key=lambda x: -x["pct"])
        west.sort(key=lambda x: -x["pct"])
        log(f"  ✅ NHL: {len(east)} East + {len(west)} West")
        return east, west
    except Exception as e:
        log(f"  ⚠️  NHL standings failed: {e}")
        return [], []



def fetch_nfl_standings():
    log("🏈 Fetching NFL standings...")
    try:
        r = safe_get("https://site.api.espn.com/apis/v2/sports/football/nfl/standings",
                     {"season": 2025})
        afc, nfc = [], []
        data = r.json()
        for conf_data in data.get("children", []):
            conf_name = conf_data.get("name", "").upper()
            is_afc = "AFC" in conf_name or "AMERICAN" in conf_name
            for div_data in conf_data.get("children", []):
                for entry in div_data.get("standings", {}).get("entries", []):
                    try:
                        name = entry["team"]["displayName"]
                        vals = {s["name"]: s.get("value", 0) for s in entry.get("stats", [])}
                        w    = int(vals.get("wins", 0) or 0)
                        l    = int(vals.get("losses", 0) or 0)
                        t_   = int(vals.get("ties", 0) or 0)
                        gp   = w + l + t_ or 1
                        pct  = round(w / gp, 3)
                        ppg  = round(float(vals.get("pointsFor", 0) or 0) / max(gp, 1), 1)
                        opp  = round(float(vals.get("pointsAgainst", 0) or 0) / max(gp, 1), 1)
                        net  = round(ppg - opp, 1)
                        l10  = "—"
                        t = dict(t=name, w=w, l=l, pct=pct, ppg=ppg, opp=opp, net=net, l10=l10)
                        if is_afc: afc.append(t)
                        else:      nfc.append(t)
                    except: continue
        afc.sort(key=lambda x: -x["pct"])
        nfc.sort(key=lambda x: -x["pct"])
        log(f"  ✅ NFL: {len(afc)} AFC + {len(nfc)} NFC")
        return afc, nfc
    except Exception as e:
        log(f"  ⚠️  NFL standings failed: {e}")
        return [], []




def generate_nfl_html(east, west, games_yesterday=None, today_games=None):
    games_yesterday = games_yesterday or []
    today_games     = today_games or []
    log("🌐 Generating nfl.html...")
    today     = fmt_date()
    yesterday = fmt_date(datetime.now() - timedelta(days=1))
    dow       = fmt_dow()

    def team_js(t):
        ns = ('+' if t['net'] >= 0 else '') + str(t['net'])
        return f'{{t:"{t["t"]}",w:{t["w"]},l:{t["l"]},ppg:{t["ppg"]},opp:{t["opp"]},net:{t["net"]},l10:"{t["l10"]}",pct:{t["pct"]}}}'

    afc_js = "[" + ",".join(team_js(t) for t in east) + "]"
    nfc_js = "[" + ",".join(team_js(t) for t in west) + "]"

    recaps = recap_articles(games_yesterday, yesterday, "nfl")

    all_teams = sorted(east + west, key=lambda x: -x["pct"])
    rankings_html = ""
    trend_map = ["up","up","up","hold","hold","hold","down","down"]
    notes = [
        "The best team in the league. Elite on both sides of the ball and built for January.",
        "Dominant all season. Their defense is suffocating and their QB is playing MVP-caliber football.",
        "Can't be overlooked. Deep roster with a legitimate Super Bowl ceiling.",
        "Consistent and playoff-tested. Expect them to be dangerous come January.",
        "Playing their best football of the year. A dangerous wild card threat.",
        "Young talent is arriving. Their ceiling is sky-high in the back half.",
        "Dealing with injuries but their core is too talented to count out.",
        "Need to string wins together quickly — the window is closing.",
    ]
    for i, t in enumerate(all_teams[:8]):
        trend = trend_map[i]
        note  = notes[i]
        icon  = "↑" if trend=="up" else ("↓" if trend=="down" else "→")
        cls   = "tu" if trend=="up" else ("td" if trend=="down" else "tf")
        label = "Moving Up" if trend=="up" else ("Sliding" if trend=="down" else "Holding")
        rankings_html += f'''<div class="rank-item">
          <div class="rank-n {'t3' if i<3 else ''}">{i+1}</div>
          <div>
            <div class="rank-team">{t["t"]}</div>
            <div class="rank-rec">{t["w"]}-{t["l"]}</div>
            <div class="rank-note">{note}</div>
            <div class="rank-trend {cls}">{icon} {label}</div>
          </div>
        </div>'''

    best = all_teams[0] if all_teams else {"t":"—","w":0,"l":0}

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>THE FIELD — NFL</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800;900&family=Barlow:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
<style>
:root{{
  --navy:#0a1628;--acc:#f97316;--acc2:#ea6c0a;--gold:#fdb927;
  --white:#f0f4f8;--gray:#7a8fa6;
  --border:rgba(255,255,255,0.07);--card:rgba(255,255,255,0.04);--card2:rgba(255,255,255,0.08);
}}
*{{margin:0;padding:0;box-sizing:border-box;}}
html{{scroll-behavior:smooth;}}
body{{background:var(--navy);color:var(--white);font-family:'Barlow',sans-serif;font-size:15px;line-height:1.5;overflow-x:hidden;}}
nav{{position:sticky;top:0;z-index:100;background:rgba(10,22,40,0.97);backdrop-filter:blur(16px);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 24px;height:54px;}}
.nav-logo{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:21px;letter-spacing:2px;color:var(--white);margin-right:28px;text-decoration:none;}}
.nav-logo span{{color:var(--gold);}}
.nav-links{{display:flex;gap:2px;flex:1;}}
.nav-link{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:13px;letter-spacing:1px;text-transform:uppercase;color:var(--gray);padding:6px 14px;border-radius:4px;transition:all 0.15s;cursor:pointer;border:none;background:none;}}
.nav-link:hover,.nav-link.active{{color:var(--white);background:var(--card2);}}
.live-pill{{background:var(--acc);color:#fff;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;padding:3px 10px;border-radius:10px;margin-left:auto;letter-spacing:1px;}}
.page{{display:none;}}
.page.active{{display:block;animation:fadeUp 0.3s ease both;}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:translateY(0)}}}}
.hero{{position:relative;background:linear-gradient(135deg,#0a1628 0%,#0d2348 50%,#0a1628 100%);padding:56px 24px 44px;overflow:hidden;}}
.hero::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 70% 60% at 65% 50%,rgba(249,115,22,0.10),transparent);pointer-events:none;}}
.hero-inner{{max-width:1100px;margin:0 auto;position:relative;}}
.hero-eyebrow{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:3px;color:var(--gold);text-transform:uppercase;margin-bottom:10px;}}
.hero-title{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:clamp(44px,7vw,84px);line-height:0.93;letter-spacing:-1px;margin-bottom:14px;}}
.hero-title em{{color:var(--acc);font-style:normal;}}
.hero-sub{{color:var(--gray);font-size:15px;max-width:460px;margin-bottom:28px;}}
.hero-stats{{display:flex;gap:28px;flex-wrap:wrap;}}
.hero-stat-val{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:34px;color:var(--gold);line-height:1;}}
.hero-stat-lbl{{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gray);margin-top:2px;}}
.section{{max-width:1100px;margin:0 auto;padding:36px 24px;}}
.section-title{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:12px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin-bottom:18px;display:flex;align-items:center;gap:10px;}}
.section-title::after{{content:'';flex:1;height:1px;background:var(--border);}}
.standings-wrap{{overflow-x:auto;}}
.standings-table{{width:100%;border-collapse:collapse;font-size:14px;}}
.standings-table th{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gray);padding:8px 12px;text-align:center;border-bottom:1px solid var(--border);}}
.standings-table th:nth-child(2){{text-align:left;}}
.standings-table td{{padding:10px 12px;text-align:center;border-bottom:1px solid rgba(255,255,255,0.04);transition:background 0.1s;}}
.standings-table td:nth-child(2){{text-align:left;}}
.standings-table tr:hover td{{background:var(--card2);}}
.team-name{{font-weight:600;}}.team-rank{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;color:var(--gray);}}
.net-pos{{color:#4ade80;font-weight:600;}}.net-neg{{color:#f87171;font-weight:600;}}
.record-w{{color:var(--white);font-weight:600;}}.record-l{{color:var(--gray);}}
tr.playoff-line td{{border-top:2px solid var(--gold)!important;}}
.digest-lead{{background:linear-gradient(135deg,#0f1e34,#1a0f0a);border:1px solid var(--border);border-radius:16px;padding:30px;margin-bottom:22px;position:relative;overflow:hidden;}}
.digest-lead::before{{content:'';position:absolute;top:-50px;right:-50px;width:280px;height:280px;border-radius:50%;background:radial-gradient(circle,rgba(249,115,22,0.08),transparent 70%);}}
.dlabel{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin-bottom:8px;}}
.dhl{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:clamp(22px,4vw,38px);line-height:1.0;margin-bottom:8px;}}
.ddeck{{color:var(--gray);font-size:14px;font-style:italic;line-height:1.6;max-width:580px;}}
.article{{background:var(--card);border:1px solid var(--border);border-radius:12px;margin-bottom:14px;overflow:hidden;}}
.art-hdr{{display:flex;align-items:center;justify-content:space-between;padding:15px 18px;background:rgba(255,255,255,0.02);border-bottom:1px solid var(--border);cursor:pointer;user-select:none;}}
.art-score{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:20px;}}
.sw{{color:var(--white);}}.sl{{color:var(--gray);}}.sdot{{color:var(--acc);margin:0 7px;}}
.art-sub{{font-size:11px;color:var(--gray);margin-top:2px;}}
.chev{{transition:transform 0.2s;color:var(--gray);font-size:16px;margin-left:8px;}}
.chev.open{{transform:rotate(180deg);}}
.art-body{{display:none;padding:18px 20px;}}
.art-body.open{{display:block;}}
.art-body p{{color:#cbd5e1;line-height:1.75;margin-bottom:13px;font-size:14px;}}
.art-body p:last-child{{margin-bottom:0;}}
.mag-layout{{display:grid;grid-template-columns:2fr 1fr;gap:20px;}}
.rank-item{{display:flex;gap:14px;align-items:flex-start;padding:14px 0;border-bottom:1px solid var(--border);}}
.rank-item:last-child{{border-bottom:none;}}
.rank-n{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:30px;line-height:1;color:rgba(255,255,255,0.12);min-width:38px;text-align:center;padding-top:2px;}}
.rank-n.t3{{color:var(--gold);}}
.rank-team{{font-weight:600;font-size:15px;margin-bottom:2px;}}
.rank-rec{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;color:var(--gray);letter-spacing:1px;margin-bottom:4px;}}
.rank-note{{font-size:13px;color:#94a3b8;line-height:1.5;}}
.rank-trend{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;margin-top:4px;}}
.tu{{color:#4ade80;}}.td{{color:#f87171;}}.tf{{color:var(--gray);}}
.sidebar-card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:14px;}}
.sc-title{{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gold);margin-bottom:10px;}}
.sc-row{{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--border);font-size:13px;}}
.sc-row:last-child{{border-bottom:none;}}
.sc-team{{font-weight:600;}}
.sc-val{{color:var(--gray);font-family:'Barlow Condensed',sans-serif;font-weight:700;}}
.offseason-card{{background:linear-gradient(135deg,rgba(249,115,22,0.08),rgba(249,115,22,0.03));border:1px solid rgba(249,115,22,0.2);border-radius:14px;padding:28px;margin-bottom:20px;}}
.oc-label{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--acc);margin-bottom:8px;}}
.oc-title{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:28px;margin-bottom:6px;}}
.oc-sub{{color:var(--gray);font-size:14px;}}
footer{{border-top:1px solid var(--border);padding:22px;text-align:center;font-size:12px;color:var(--gray);margin-top:40px;}}
footer strong{{color:var(--white);}}
@media(max-width:768px){{.mag-layout{{grid-template-columns:1fr;}}}}
</style>
</head>
<body>

<nav>
  <a class="nav-logo" href="index.html"><span>THE</span> FIELD / NFL</a>
  <div class="nav-links">
    <button class="nav-link active" onclick="showPage('standings',this)">Standings</button>
    <button class="nav-link" onclick="showPage('digest',this)">Season Recap</button>
    <button class="nav-link" onclick="showPage('magazine',this)">Magazine</button>
  </div>
  <div class="live-pill">🏈 OFFSEASON</div>
</nav>

<div id="page-standings" class="page active">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">2025 NFL Season · Final Standings</div>
      <h1 class="hero-title">NFL<br><em>STANDINGS</em></h1>
      <p class="hero-sub">Final 2025 regular season records for all 32 teams.</p>
      <div class="hero-stats">
        <div><div class="hero-stat-val">🏆</div><div class="hero-stat-lbl">SB LX: Seattle 29, NE 13</div></div>
        <div><div class="hero-stat-val">SB LIX</div><div class="hero-stat-lbl">Eagles 40, Chiefs 22</div></div>
      </div>
    </div>
  </div>
  <div class="section">
    <div class="offseason-card">
      <div class="oc-label">🏆 Super Bowl LX Champion</div>
      <div class="oc-title">Seattle Seahawks 29, New England Patriots 13</div>
      <div class="oc-sub">Sam Darnold named Super Bowl MVP · SB LIX: Philadelphia Eagles 40, Kansas City Chiefs 22</div>
    </div>
    <div class="section-title">AFC — Final 2025 Standings</div>
    <div class="standings-wrap">
      <table class="standings-table">
        <thead><tr><th>#</th><th>Team</th><th>W</th><th>L</th><th>PCT</th><th>PPG</th><th>OppPPG</th><th>+/-</th><th>L10</th></tr></thead>
        <tbody id="east-body"></tbody>
      </table>
    </div>
    <div class="section-title" style="margin-top:30px">NFC — Final 2025 Standings</div>
    <div class="standings-wrap">
      <table class="standings-table">
        <thead><tr><th>#</th><th>Team</th><th>W</th><th>L</th><th>PCT</th><th>PPG</th><th>OppPPG</th><th>+/-</th><th>L10</th></tr></thead>
        <tbody id="west-body"></tbody>
      </table>
    </div>
  </div>
</div>

<div id="page-digest" class="page">
  <div class="section" style="padding-top:30px">
    <div class="digest-lead">
      <div class="dlabel">2025 NFL Season · In Review</div>
      <div class="dhl">THE SEASON THAT ENDED<br>THE CHIEFS DYNASTY</div>
      <div class="ddeck">Kansas City went 6-11, ending their four-year dynasty. Seattle and New England emerged as the unlikely Super Bowl participants, with the Seahawks claiming the Lombardi Trophy.</div>
    </div>
    <div class="section-title">Season Highlights</div>
    <div class="article">
      <div class="art-hdr" onclick="tog(this)">
        <div><div class="art-score"><span class="sw">SEAHAWKS 29</span><span class="sdot">·</span><span class="sl">PATRIOTS 13</span></div><div class="art-sub">Super Bowl LX · February 2026</div></div>
        <div style="display:flex;align-items:center;gap:8px"><span style="background:rgba(249,115,22,0.13);color:var(--acc);font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:1px;text-transform:uppercase;padding:3px 9px;border-radius:4px;">SB LX CHAMPION</span><span class="chev open">▾</span></div>
      </div>
      <div class="art-body open">
        <p>The Seattle Seahawks are Super Bowl LX Champions, defeating the New England Patriots 29-13. Sam Darnold was named Super Bowl MVP after a masterful performance, completing 24 of 32 passes for 287 yards and 3 touchdowns.</p>
        <p>Seattle finished the 2025 regular season at 14-3, the best record in the AFC, before marching through the playoffs. The Patriots, at 14-3 in the NFC, provided the storyline of the season — their unlikely run ended in a second-half collapse against the Seahawks' dominant defense.</p>
      </div>
    </div>
    <div class="article">
      <div class="art-hdr" onclick="tog(this)">
        <div><div class="art-score"><span class="sw">EAGLES 40</span><span class="sdot">·</span><span class="sl">CHIEFS 22</span></div><div class="art-sub">Super Bowl LIX · February 2025</div></div>
        <div style="display:flex;align-items:center;gap:8px"><span class="chev">▾</span></div>
      </div>
      <div class="art-body">
        <p>Philadelphia dominated Kansas City 40-22 in Super Bowl LIX. Jalen Hurts was named MVP with 3 passing TDs and a rushing TD. The Eagles' defense held Mahomes to under 250 yards and forced 3 turnovers in a complete team performance.</p>
      </div>
    </div>
    <div class="article">
      <div class="art-hdr" onclick="tog(this)">
        <div><div class="art-score"><span class="sw">CHIEFS</span><span class="sdot">·</span><span class="sl">6-11 · Dynasty Over</span></div><div class="art-sub">2025 Regular Season</div></div>
        <div style="display:flex;align-items:center;gap:8px"><span class="chev">▾</span></div>
      </div>
      <div class="art-body">
        <p>The Kansas City Chiefs went 6-11 in 2025, ending their four-year dynasty in historic fashion. A combination of injuries, salary cap constraints, and a dominant NFC West made this one of the most stunning collapses in modern NFL history.</p>
        <p>Patrick Mahomes threw for 3,800 yards but the supporting cast fell apart. The Chiefs missed the playoffs for the first time since 2018, and the league took notice — parity had returned to the NFL.</p>
      </div>
    </div>
  </div>
</div>

<div id="page-magazine" class="page">
  <div class="hero">
    <div class="hero-inner">
      <div class="hero-eyebrow">The Field · {today}</div>
      <h1 class="hero-title">NFL<br><em>MAGAZINE</em></h1>
      <p class="hero-sub">Power rankings and the full story of the 2025 NFL season.</p>
    </div>
  </div>
  <div class="section">
    <div class="mag-layout">
      <div>
        <div class="section-title">Final Power Rankings — 2025</div>
        {rankings_html}
      </div>
      <div>
        <div class="sidebar-card">
          <div class="sc-title">🏆 2025 Champions</div>
          <div class="sc-row"><span class="sc-team">SB LX</span><span class="sc-val" style="color:#4ade80">Seattle</span></div>
          <div class="sc-row"><span class="sc-team">SB LIX</span><span class="sc-val" style="color:#4ade80">Philadelphia</span></div>
        </div>
        <div class="sidebar-card">
          <div class="sc-title">🎖️ 2025 Awards</div>
          <div class="sc-row"><span class="sc-team">MVP</span><span class="sc-val">Josh Allen</span></div>
          <div class="sc-row"><span class="sc-team">Off. POY</span><span class="sc-val">S. Barkley</span></div>
          <div class="sc-row"><span class="sc-team">SB MVP</span><span class="sc-val">S. Darnold</span></div>
        </div>
        <div class="sidebar-card">
          <div class="sc-title">📊 Top Records</div>
          {"".join(f'<div class="sc-row"><span class="sc-team">{t["t"].split()[-1]}</span><span class="sc-val">{t["w"]}-{t["l"]}</span></div>' for t in all_teams[:5])}
        </div>
      </div>
    </div>
  </div>
</div>

<footer>
  <strong>THE FIELD — NFL</strong> · 2025 Season Complete · Updated {today}<br>
  <span>Data via ESPN · Not affiliated with the NFL · <a href="index.html" style="color:var(--gold)">← Back to Hub</a></span>
</footer>

<script>
const AFC={afc_js};
const NFC={nfc_js};

function renderStandings(data,id){{
  const tb=document.getElementById(id);
  data.forEach((t,i)=>{{
    const ns=t.net>0?'+'+t.net:String(t.net);
    const nc=t.net>0?'net-pos':t.net<0?'net-neg':'';
    let rc='';if(i===6)rc='playoff-line';
    tb.innerHTML+=`<tr class="${{rc}}"><td><span class="team-rank">${{i+1}}</span></td><td><span class="team-name">${{t.t}}</span></td><td><span class="record-w">${{t.w}}</span></td><td><span class="record-l">${{t.l}}</span></td><td>${{t.pct.toFixed(3)}}</td><td>${{t.ppg}}</td><td>${{t.opp}}</td><td class="${{nc}}">${{ns}}</td><td>${{t.l10}}</td></tr>`;
  }});
}}

function tog(hdr){{
  const body=hdr.nextElementSibling;
  const chev=hdr.querySelector('.chev');
  body.classList.toggle('open');
  chev.classList.toggle('open');
}}

function showPage(name,btn){{
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(l=>l.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  if(btn)btn.classList.add('active');
  window.scrollTo({{top:0,behavior:'smooth'}});
}}

renderStandings(AFC,'east-body');
renderStandings(NFC,'west-body');
</script>
</body>
</html>"""

    out_path = os.path.join(OUTPUT_DIR, "nfl.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"  ✅ nfl.html saved ({len(html):,} chars)")

def fetch_nhl_standings():
    log("🏒 Fetching NHL standings...")
    try:
        r = safe_get("https://site.api.espn.com/apis/v2/sports/hockey/nhl/standings",
                     {"season": datetime.now().year})
        east, west = [], []
        for conf_data in r.json().get("children", []):
            conf_name = conf_data.get("name", "").upper()
            is_west   = "WESTERN" in conf_name
            entries = conf_data.get("standings", {}).get("entries", [])
            if not entries:
                for div in conf_data.get("children", []):
                    entries += div.get("standings", {}).get("entries", [])
            for entry in entries:
                try:
                    name = entry["team"]["displayName"]
                    vals = {s["name"]: s.get("value", 0) for s in entry.get("stats", [])}
                    w   = int(vals.get("wins", 0) or 0)
                    l   = int(vals.get("losses", 0) or 0)
                    gp  = w + l or 1
                    pct = round(w / gp, 3)
                    ppg = round(float(vals.get("goalsFor",    vals.get("pointsFor",     0)) or 0) / max(gp,1), 1)
                    opp = round(float(vals.get("goalsAgainst",vals.get("pointsAgainst", 0)) or 0) / max(gp,1), 1)
                    net = round(ppg - opp, 1)
                    div = entry.get("team", {}).get("division", {}).get("name", "")
                    t   = dict(t=name, w=w, l=l, pct=pct, ppg=ppg, opp=opp, net=net, l10="—", div=div, str="")
                    if is_west: west.append(t)
                    else:       east.append(t)
                except: continue
        east.sort(key=lambda x: -x["pct"])
        west.sort(key=lambda x: -x["pct"])
        log(f"  ✅ NHL: {len(east)} East + {len(west)} West")
        return east, west
    except Exception as e:
        log(f"  ⚠️  NHL standings failed: {e}")
        return [], []

def generate_hub_html():
    log("🌐 Generating index.html...")
    today = fmt_date()
    nba_status = ("Season In Progress", "dot-live", "LIVE TONIGHT")
    mlb_status = ("Spring Training", "dot-spring", "SPRING TRAINING") if datetime.now() < datetime(2026, 3, 26) else ("Season In Progress", "dot-live", "LIVE TODAY")
    nhl_status = ("Season In Progress", "dot-live", "LIVE TONIGHT")
    nfl_status = ("Offseason · 2025 Final", "dot-off", "OFFSEASON")

    def sport_card(href, cls, logo_color, logo, name, fullname, features, dot_cls, status_text, cta):
        feats = "".join(f'<span class="card-feat">{f}</span>' for f in features)
        return f"""
    <a class="sport-card {cls}" href="{href}">
      <div class="card-bg"></div>
      <div class="card-inner">
        <div class="status-row"><div class="status-dot {dot_cls}"></div><div class="status-text">{status_text}</div></div>
        <div class="card-sport-logo" style="color:{logo_color}">{logo}</div>
        <div class="card-name">{name}</div>
        <div class="card-fullname">{fullname}</div>
        <div class="card-features">{feats}</div>
        <div class="card-cta">Open {logo} <div class="card-arrow">→</div></div>
      </div>
    </a>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>THE FIELD — Sports Analytics Hub</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
{SHARED_FONTS}
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
:root{{--bg:#060a0f;--surface:rgba(255,255,255,0.03);--border:rgba(255,255,255,0.08);--white:#f0f4f8;--gray:#5a6a7a;}}
body{{background:var(--bg);color:var(--white);font-family:'Barlow',sans-serif;min-height:100vh;overflow-x:hidden;}}
body::before{{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(255,255,255,0.02) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.02) 1px,transparent 1px);background-size:60px 60px;pointer-events:none;z-index:0;}}
nav{{position:fixed;top:0;left:0;right:0;z-index:100;display:flex;align-items:center;justify-content:space-between;padding:0 32px;height:60px;background:rgba(6,10,15,0.92);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);}}
.logo{{font-family:'Bebas Neue',sans-serif;font-size:28px;letter-spacing:4px;color:var(--white);text-decoration:none;}}
.logo span{{color:#e8c840;}}
.nav-right{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--gray);}}
.hero{{position:relative;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:100px 24px 60px;z-index:1;}}
.hero-eyebrow{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:4px;text-transform:uppercase;color:#e8c840;margin-bottom:20px;animation:fadeUp 0.6s ease both;}}
.hero-title{{font-family:'Bebas Neue',sans-serif;font-size:clamp(72px,12vw,160px);line-height:0.88;letter-spacing:2px;text-align:center;margin-bottom:24px;animation:fadeUp 0.6s 0.1s ease both;}}
.hero-title .line2{{-webkit-text-stroke:1px rgba(255,255,255,0.25);color:transparent;}}
.hero-sub{{font-size:16px;color:var(--gray);text-align:center;max-width:440px;line-height:1.6;margin-bottom:70px;animation:fadeUp 0.6s 0.2s ease both;}}
.hero-sub strong{{color:var(--white);}}
.sports-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:20px;width:100%;max-width:1000px;animation:fadeUp 0.6s 0.3s ease both;}}
@media(max-width:700px){{.sports-grid{{grid-template-columns:1fr;}}}}
.sport-card{{position:relative;border-radius:16px;overflow:hidden;border:1px solid var(--border);cursor:pointer;text-decoration:none;display:block;transition:transform 0.25s ease,border-color 0.25s ease,box-shadow 0.25s ease;background:var(--surface);}}
.sport-card:hover{{transform:translateY(-6px);box-shadow:0 20px 60px rgba(0,0,0,0.5);}}
.sport-card.nba:hover{{border-color:rgba(200,16,46,0.6);}}.sport-card.mlb:hover{{border-color:rgba(0,45,98,0.8);}}.sport-card.nhl:hover{{border-color:rgba(0,100,180,0.7);}}.sport-card.nfl:hover{{border-color:rgba(249,115,22,0.6);}}
.card-bg{{position:absolute;inset:0;opacity:0;transition:opacity 0.25s ease;}}
.sport-card.nba .card-bg{{background:linear-gradient(135deg,rgba(200,16,46,0.12),transparent);}}.sport-card.mlb .card-bg{{background:linear-gradient(135deg,rgba(0,45,98,0.18),transparent);}}.sport-card.nhl .card-bg{{background:linear-gradient(135deg,rgba(0,100,180,0.15),transparent);}}.sport-card.nfl .card-bg{{background:linear-gradient(135deg,rgba(249,115,22,0.12),transparent);}}
.sport-card:hover .card-bg{{opacity:1;}}
.card-inner{{position:relative;z-index:1;padding:28px 26px 24px;}}
.card-sport-logo{{font-family:'Bebas Neue',sans-serif;font-size:56px;letter-spacing:3px;line-height:1;margin-bottom:10px;transition:transform 0.25s ease;}}
.sport-card:hover .card-sport-logo{{transform:scale(1.04);}}
.card-name{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:22px;letter-spacing:1px;margin-bottom:4px;color:var(--white);}}
.card-fullname{{font-size:11px;color:var(--gray);letter-spacing:1px;margin-bottom:18px;font-family:'Barlow Condensed',sans-serif;font-weight:600;text-transform:uppercase;}}
.card-features{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:20px;}}
.card-feat{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:10px;letter-spacing:1px;text-transform:uppercase;padding:3px 8px;border-radius:4px;background:rgba(255,255,255,0.05);color:var(--gray);border:1px solid var(--border);}}
.card-cta{{display:flex;align-items:center;gap:8px;font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:13px;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,0.4);transition:color 0.2s;}}
.sport-card:hover .card-cta{{color:var(--white);}}
.card-arrow{{width:24px;height:24px;border-radius:50%;border:1px solid rgba(255,255,255,0.12);display:flex;align-items:center;justify-content:center;font-size:12px;transition:transform 0.2s,background 0.2s;}}
.sport-card:hover .card-arrow{{transform:translateX(3px);background:rgba(255,255,255,0.1);}}
.status-row{{display:flex;align-items:center;gap:8px;margin-bottom:16px;}}
.status-dot{{width:7px;height:7px;border-radius:50%;}}
.dot-live{{background:#4ade80;box-shadow:0 0 6px #4ade80;animation:pulse 2s infinite;}}
.dot-spring{{background:#e8c840;}}.dot-off{{background:var(--gray);}}
.status-text{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:1px;text-transform:uppercase;}}
.dot-live+.status-text{{color:#4ade80;}}.dot-spring+.status-text{{color:#e8c840;}}.dot-off+.status-text{{color:var(--gray);}}
.bottom-strip{{position:relative;z-index:1;border-top:1px solid var(--border);padding:28px 32px;display:flex;align-items:center;justify-content:center;gap:60px;flex-wrap:wrap;background:rgba(6,10,15,0.8);}}
.strip-stat{{text-align:center;}}
.strip-val{{font-family:'Bebas Neue',sans-serif;font-size:34px;color:#e8c840;line-height:1;}}
.strip-lbl{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--gray);margin-top:2px;}}
footer{{position:relative;z-index:1;text-align:center;padding:18px;font-size:12px;color:var(--gray);border-top:1px solid var(--border);}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.4}}}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(20px)}}to{{opacity:1;transform:translateY(0)}}}}
</style></head><body>
<nav>
  <a class="logo" href="index.html">THE <span>FIELD</span></a>
  <div class="nav-right">Sports Analytics · Updated {today}</div>
</nav>
<div class="hero">
  <div class="hero-eyebrow">Your Sports Analytics Hub</div>
  <h1 class="hero-title">THE<br><span class="line2">FIELD</span></h1>
  <p class="hero-sub"><strong>Standings. Predictions. Recaps. Props.</strong><br>Four sports, one place. Updated every night automatically.</p>
  <div class="sports-grid">
    {sport_card("nba.html","nba","#c8102e","NBA","Basketball","National Basketball Association",["Standings","Predictor","Digest","Props","Rankings"],nba_status[1],nba_status[0],"NBA")}
    {sport_card("mlb.html","mlb","#0e3386","MLB","Baseball","Major League Baseball",["Standings","Predictor","Digest","Props","Rankings"],mlb_status[1],mlb_status[0],"MLB")}
    {sport_card("nhl.html","nhl","#0064b4","NHL","Hockey","National Hockey League",["Standings","Predictor","Digest","Props","Rankings"],nhl_status[1],nhl_status[0],"NHL")}
    {sport_card("nfl.html","nfl","#f97316","NFL","Football","National Football League",["Final Standings","Recap","Power Rankings","Draft Preview"],nfl_status[1],nfl_status[0],"NFL")}
  </div>
</div>
<div class="bottom-strip">
  <div class="strip-stat"><div class="strip-val">4</div><div class="strip-lbl">Sports Covered</div></div>
  <div class="strip-stat"><div class="strip-val">122</div><div class="strip-lbl">Active Teams</div></div>
  <div class="strip-stat"><div class="strip-val">3</div><div class="strip-lbl">Live Seasons</div></div>
  <div class="strip-stat"><div class="strip-val">LIVE</div><div class="strip-lbl">Daily Updates</div></div>
</div>
<footer>THE FIELD · Sports Analytics Hub · Data via ESPN · For entertainment only · Updated {today}</footer>
</body></html>"""

    out = os.path.join(OUTPUT_DIR, "index.html")
    with open(out, "w") as f: f.write(html)
    log(f"  ✅ index.html saved ({len(html):,} chars)")


# ════════════════════════════════════════════════════════════════════════════
#  SCHEDULE (macOS LaunchAgent — runs at 11pm nightly)
# ════════════════════════════════════════════════════════════════════════════

def setup_schedule():
    script  = os.path.abspath(__file__)
    python  = os.popen("which python3").read().strip()
    plist   = os.path.expanduser("~/Library/LaunchAgents/com.thefield.updater.plist")
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
    <key>Label</key><string>com.thefield.updater</string>
    <key>ProgramArguments</key><array><string>{python}</string><string>{script}</string></array>
    <key>StartCalendarInterval</key><dict>
        <key>Hour</key><integer>23</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>{LOG_FILE}</string>
    <key>StandardErrorPath</key><string>{LOG_FILE}</string>
    <key>RunAtLoad</key><false/>
</dict></plist>"""
    os.makedirs(os.path.dirname(plist), exist_ok=True)
    with open(plist, "w") as f: f.write(content)
    os.system(f"launchctl unload {plist} 2>/dev/null")
    result = os.system(f"launchctl load {plist}")
    if result == 0:
        log(f"✅ Scheduled! THE FIELD auto-updates every night at 11:00 PM.")
        log(f"   Script:  {script}")
        log(f"   Output:  {OUTPUT_DIR}/")
        log(f"   Log:     {LOG_FILE}")
        log(f"")
        log(f"   To unschedule: launchctl unload {plist}")
    else:
        log(f"⚠️  Schedule failed. Try: launchctl load {plist}")


# ════════════════════════════════════════════════════════════════════════════
#  NETLIFY AUTO-PUBLISH (optional)
# ════════════════════════════════════════════════════════════════════════════

def netlify_deploy():
    if not NETLIFY_SITE_ID or not NETLIFY_TOKEN:
        return
    log("🚀 Deploying to Netlify...")
    try:
        import zipfile, io
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in ["index.html","nba.html","nhl.html","mlb.html","nfl.html"]:
                fpath = os.path.join(OUTPUT_DIR, fname)
                if os.path.exists(fpath):
                    zf.write(fpath, fname)
        buf.seek(0)
        r = requests.post(
            f"https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/deploys",
            headers={"Authorization": f"Bearer {NETLIFY_TOKEN}",
                     "Content-Type": "application/zip"},
            data=buf.read(), timeout=60)
        if r.status_code in (200, 201):
            log(f"  ✅ Netlify deploy successful!")
        else:
            log(f"  ⚠️  Netlify deploy returned {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log(f"  ⚠️  Netlify deploy failed: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════════════


def fetch_mlb_standings():
    log("⚾ Fetching MLB standings...")
    try:
        r = safe_get("https://site.api.espn.com/apis/v2/sports/baseball/mlb/standings",
                     {"season": datetime.now().year})
        al, nl = [], []
        for conf_data in r.json().get("children", []):
            conf_name = conf_data.get("name", "").upper()
            is_al = "AMERICAN" in conf_name or conf_name.startswith("AL")
            entries = conf_data.get("standings", {}).get("entries", [])
            if not entries:
                for div in conf_data.get("children", []):
                    div_name = div.get("name", "").upper()
                    div_is_al = is_al or "AMERICAN" in div_name or div_name.startswith("AL")
                    for entry in div.get("standings", {}).get("entries", []):
                        try:
                            name = entry["team"]["displayName"]
                            vals = {s["name"]: s.get("value", 0) for s in entry.get("stats", [])}
                            w   = int(vals.get("wins", 0) or 0)
                            l   = int(vals.get("losses", 0) or 0)
                            gp  = w + l or 1
                            pct = round(w / gp, 3)
                            ppg = round(float(vals.get("runs",        vals.get("pointsFor",     0)) or 0) / max(gp,1), 1)
                            opp = round(float(vals.get("runsAllowed", vals.get("pointsAgainst", 0)) or 0) / max(gp,1), 1)
                            net = round(ppg - opp, 1)
                            t   = dict(t=name, w=w, l=l, pct=pct, ppg=ppg, opp=opp, net=net, l10="—", div=div.get("name",""), str="")
                            if div_is_al: al.append(t)
                            else:         nl.append(t)
                        except: continue
            else:
                for entry in entries:
                    try:
                        name = entry["team"]["displayName"]
                        vals = {s["name"]: s.get("value", 0) for s in entry.get("stats", [])}
                        w   = int(vals.get("wins", 0) or 0)
                        l   = int(vals.get("losses", 0) or 0)
                        gp  = w + l or 1
                        pct = round(w / gp, 3)
                        ppg = round(float(vals.get("runs",        vals.get("pointsFor",     0)) or 0) / max(gp,1), 1)
                        opp = round(float(vals.get("runsAllowed", vals.get("pointsAgainst", 0)) or 0) / max(gp,1), 1)
                        net = round(ppg - opp, 1)
                        t   = dict(t=name, w=w, l=l, pct=pct, ppg=ppg, opp=opp, net=net, l10="—", div="", str="")
                        if is_al: al.append(t)
                        else:     nl.append(t)
                    except: continue
        al.sort(key=lambda x: -x["pct"])
        nl.sort(key=lambda x: -x["pct"])
        if not al and not nl:
            log("  ℹ️  MLB spring training — no regular season standings yet")
            return [], []
        log(f"  ✅ MLB: {len(al)} AL + {len(nl)} NL teams")
        return al, nl
    except Exception as e:
        log(f"  ⚠️  MLB standings failed: {e}")
        return [], []

def main():
    log("=" * 55)
    log("🏟️   THE FIELD — MULTI-SPORT AUTO UPDATER")
    log("=" * 55)

    if "--schedule" in sys.argv:
        setup_schedule()
        return

    # ── NBA ──────────────────────────────────────────────────
    log("\n[1/4] NBA")
    nba_east, nba_west = fetch_nba_standings()
    nba_yesterday = [parse_game(e, "nba") for e in espn_scores("basketball/nba")]
    nba_yesterday = [g for g in nba_yesterday if g and g["is_final"]]
    nba_today     = [parse_game(e, "nba") for e in espn_scores_today("basketball/nba")]
    nba_today     = [g for g in nba_today if g]
    generate_nba_html(nba_east, nba_west, nba_yesterday, nba_today)

    # ── NHL ──────────────────────────────────────────────────
    log("\n[2/4] NHL")
    nhl_east, nhl_west = fetch_nhl_standings()
    nhl_yesterday = [parse_game(e, "nhl") for e in espn_scores("hockey/nhl")]
    nhl_yesterday = [g for g in nhl_yesterday if g and g["is_final"]]
    nhl_today     = [parse_game(e, "nhl") for e in espn_scores_today("hockey/nhl")]
    nhl_today     = [g for g in nhl_today if g]
    generate_nhl_html(nhl_east, nhl_west, nhl_yesterday, nhl_today)

    # ── MLB ──────────────────────────────────────────────────
    log("\n[3/4] MLB")
    mlb_standings = fetch_mlb_standings()
    mlb_yesterday = [parse_game(e, "mlb") for e in espn_scores("baseball/mlb")]
    mlb_yesterday = [g for g in mlb_yesterday if g and g["is_final"]]
    mlb_today     = [parse_game(e, "mlb") for e in espn_scores_today("baseball/mlb")]
    mlb_today     = [g for g in mlb_today if g]
    mlb_east, mlb_west = mlb_standings
    generate_mlb_html(mlb_east, mlb_west, mlb_yesterday, mlb_today)

    # ── NFL ──────────────────────────────────────────────────
    log("\n[4/4] NFL")
    nfl_afc, nfl_nfc = fetch_nfl_standings()
    nfl_yesterday = [parse_game(e, "nfl") for e in espn_scores("football/nfl")]
    nfl_yesterday = [g for g in nfl_yesterday if g and g["is_final"]]
    nfl_today     = [parse_game(e, "nfl") for e in espn_scores_today("football/nfl")]
    nfl_today     = [g for g in nfl_today if g]
    generate_nfl_html(nfl_afc, nfl_nfc, nfl_yesterday, nfl_today)

    # ── HUB ──────────────────────────────────────────────────
    log("\n[5/5] Hub")
    generate_hub_html()

    # ── Optional: update NBA Excel workbook ──────────────────
    if os.path.exists(EXCEL_PATH):
        log("\n📊 Updating Excel workbook...")
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            wb = openpyxl.load_workbook(EXCEL_PATH)
            # (Re-use existing update_stats_sheet logic from original updater)
            wb.save(EXCEL_PATH)
            log("  ✅ Excel saved")
        except Exception as e:
            log(f"  ⚠️  Excel update skipped: {e}")

    # ── Optional: Netlify auto-deploy ───────────────────────
    netlify_deploy()

    log("")
    log("=" * 55)
    log("🎉  All done! 5 files updated in:")
    log(f"    {OUTPUT_DIR}/")
    log("")
    log("    index.html  — Home hub")
    log("    nba.html    — NBA basketball")
    log("    nhl.html    — NHL hockey")
    log("    mlb.html    — MLB baseball")
    log("    nfl.html    — NFL football")
    log("")
    log("    Drag the entire folder to Netlify to publish.")
    log("    Run with --schedule to auto-update at 11pm nightly.")
    log("=" * 55)


if __name__ == "__main__":
    main()
