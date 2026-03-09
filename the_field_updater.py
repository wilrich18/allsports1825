#!/usr/bin/env python3
"""THE FIELD — Multi-Sport Auto Updater"""

import os, json, time
from datetime import datetime
import requests

# ── BallDontLie API key for NBA digest recaps ────────────────────────────
BALLDONTLIE_API_KEY = "9b37b045-f189-4ccb-bff2-d8678f51b02d"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "updater_log.txt")

def log(msg):
    ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{ts} {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def save(name, html):
    path = os.path.join(BASE_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"  ✅ {name} saved ({len(html):,} chars)")

def safe_get(url, params=None, headers=None, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=20)
            if r.status_code == 429:
                log("    ⏳ Rate limited — waiting 65s...")
                time.sleep(65)
                continue
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                raise
            time.sleep(5)

# ── Shared CSS ────────────────────────────────────────────────────────────
def base_css(acc, acc2, hero_rgba):
    return f"""*{{margin:0;padding:0;box-sizing:border-box;}}
:root{{--navy:#0a1628;--acc:{acc};--acc2:{acc2};--gold:#fdb927;--white:#f0f4f8;--gray:#7a8fa6;--border:rgba(255,255,255,0.07);--card:rgba(255,255,255,0.04);--card2:rgba(255,255,255,0.08);}}
body{{background:var(--navy);color:var(--white);font-family:'Barlow',sans-serif;min-height:100vh;overflow-x:hidden;}}
a{{color:inherit;text-decoration:none;}}
nav{{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(10,22,40,0.95);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);}}
.nav-inner{{display:flex;align-items:center;padding:0 24px;height:54px;overflow-x:auto;gap:0;}}
.nav-logo{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:16px;letter-spacing:3px;color:var(--white);margin-right:24px;white-space:nowrap;flex-shrink:0;}}
.nav-logo span{{color:var(--gold);}}
.nav-links{{display:flex;gap:2px;}}
.nav-link{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;letter-spacing:2px;text-transform:uppercase;padding:6px 14px;border-radius:6px;border:none;background:transparent;color:var(--gray);cursor:pointer;transition:all 0.2s;white-space:nowrap;}}
.nav-link:hover,.nav-link.active{{color:var(--white);background:var(--card2);}}
.nav-link.active{{color:var(--acc);}}
.page{{display:none;min-height:100vh;padding-top:54px;}}
.page.active{{display:block;}}
.hero{{background:linear-gradient(135deg,#0a1628,#0d2348,#0a1628);padding:60px 24px 50px;position:relative;overflow:hidden;}}
.hero::before{{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 70% 60% at 65% 50%,{hero_rgba},transparent);pointer-events:none;}}
.hero-inner{{max-width:1100px;margin:0 auto;position:relative;z-index:1;}}
.hero-eyebrow{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:4px;text-transform:uppercase;color:var(--gold);margin-bottom:14px;}}
.hero-title{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:clamp(52px,8vw,96px);line-height:0.9;letter-spacing:2px;margin-bottom:14px;}}
.hero-title em{{font-style:normal;-webkit-text-stroke:1px rgba(255,255,255,0.3);color:transparent;}}
.hero-sub{{font-size:14px;color:var(--gray);max-width:500px;line-height:1.6;}}
.live-pill{{display:inline-flex;align-items:center;gap:6px;background:rgba(74,222,128,0.1);border:1px solid rgba(74,222,128,0.3);border-radius:20px;padding:4px 12px;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:2px;color:#4ade80;margin-bottom:16px;}}
.section{{max-width:1100px;margin:0 auto;padding:40px 24px;}}
.section-title{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:13px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin-bottom:20px;}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:28px;}}
@media(max-width:700px){{.two-col{{grid-template-columns:1fr;}}}}
.standings-wrap{{overflow-x:auto;}}
.standings-table{{width:100%;border-collapse:collapse;font-size:13px;}}
.standings-table th{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--gray);padding:8px 12px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap;}}
.standings-table td{{padding:10px 12px;border-bottom:1px solid rgba(255,255,255,0.03);white-space:nowrap;}}
.standings-table tr:hover td{{background:var(--card);}}
.standings-table tr.playoff-line td{{border-bottom:2px solid var(--acc);}}
.team-rank{{font-family:'Barlow Condensed',sans-serif;font-weight:700;color:var(--gray);font-size:12px;}}
.team-name{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:14px;}}
.record-w{{color:var(--white);font-weight:600;}}.record-l{{color:var(--gray);}}
.net-pos{{color:#4ade80;font-weight:600;}}.net-neg{{color:#f87171;font-weight:600;}}
.div-header-row td{{padding:10px 12px 4px;background:rgba(255,255,255,0.02);border-bottom:1px solid var(--border);}}
.div-label{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:10px;letter-spacing:3px;text-transform:uppercase;color:var(--acc);}}
.games-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;}}
.sched-tab{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;letter-spacing:1px;text-transform:uppercase;padding:8px 18px;border-radius:8px;border:1px solid rgba(255,255,255,0.12);background:rgba(255,255,255,0.04);color:var(--gray);cursor:pointer;transition:all 0.2s;}}
.sched-tab.active,.sched-tab:hover{{background:var(--acc);color:#fff;border-color:var(--acc);}}
.game-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;transition:border-color 0.2s;}}
.game-card:hover{{border-color:rgba(255,255,255,0.15);}}
.game-card-top{{padding:16px;}}
.game-time{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--gray);margin-bottom:10px;}}
.game-matchup{{display:flex;align-items:center;gap:8px;}}
.game-team{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:15px;flex:1;}}
.game-team.fav{{color:var(--white);}}.game-team.dog{{color:var(--gray);text-align:right;}}
.game-vs{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;color:var(--gray);padding:0 4px;}}
.game-score{{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;border-top:1px solid var(--border);background:rgba(0,0,0,0.2);}}
.gscore{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:26px;}}
.gscore.w{{color:var(--white);}}.gscore.l{{color:var(--gray);}}
.gfinal{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:10px;letter-spacing:2px;color:var(--gold);}}
.digest-lead{{background:linear-gradient(135deg,#0f1e34,#1a1428);border:1px solid var(--border);border-radius:16px;padding:28px;margin-bottom:20px;position:relative;overflow:hidden;}}
.digest-lead::before{{content:'';position:absolute;top:-40px;right:-40px;width:240px;height:240px;border-radius:50%;background:radial-gradient(circle,rgba(253,185,39,0.06),transparent 70%);}}
.dlabel{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin-bottom:8px;}}
.dhl{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:clamp(20px,4vw,34px);line-height:1.0;margin-bottom:8px;}}
.ddeck{{color:var(--gray);font-size:14px;line-height:1.6;max-width:580px;}}
.article{{background:var(--card);border:1px solid var(--border);border-radius:12px;margin-bottom:12px;overflow:hidden;}}
.art-hdr{{display:flex;align-items:center;justify-content:space-between;padding:14px 16px;background:rgba(255,255,255,0.02);border-bottom:1px solid var(--border);cursor:pointer;user-select:none;}}
.art-score{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:18px;}}
.art-teams{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:13px;color:var(--gray);margin-top:2px;}}
.chev{{font-size:12px;color:var(--gray);transition:transform 0.2s;}}.chev.open{{transform:rotate(180deg);}}
.art-body{{display:none;padding:16px;font-size:13px;line-height:1.7;color:var(--gray);}}.art-body.open{{display:block;}}
.mag-layout{{display:grid;grid-template-columns:1fr 340px;gap:28px;}}
@media(max-width:900px){{.mag-layout{{grid-template-columns:1fr;}}}}
.rank-item{{display:flex;align-items:flex-start;gap:14px;padding:14px 0;border-bottom:1px solid var(--border);}}
.rank-item:last-child{{border-bottom:none;}}
.rank-n{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:28px;color:var(--gray);line-height:1;min-width:32px;}}
.rank-n.t3{{color:var(--gold);}}
.rank-team{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:15px;}}
.rank-rec{{font-size:12px;color:var(--gray);margin-top:2px;}}
.rank-note{{font-size:12px;color:var(--gray);margin-top:4px;line-height:1.5;}}
.rank-trend{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:10px;letter-spacing:1px;text-transform:uppercase;margin-top:4px;}}
.tu{{color:#4ade80;}}.td{{color:#f87171;}}.tf{{color:var(--gray);}}
.sidebar-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px;margin-bottom:16px;}}
.sc-title{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--gold);margin-bottom:12px;}}
.sc-row{{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:13px;}}
.sc-row:last-child{{border-bottom:none;}}
.sc-team{{color:var(--white);font-family:'Barlow Condensed',sans-serif;font-weight:600;}}
.sc-val{{color:var(--gray);font-family:'Barlow Condensed',sans-serif;font-weight:700;}}
.props-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;}}
.prop-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px;}}
.prop-card.high{{border-left:3px solid #4ade80;}}.prop-card.medium{{border-left:3px solid var(--gold);}}
.prop-player{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:18px;margin-bottom:2px;}}
.prop-team{{font-size:11px;color:var(--gray);letter-spacing:1px;margin-bottom:10px;font-family:'Barlow Condensed',sans-serif;font-weight:600;text-transform:uppercase;}}
.prop-line{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:15px;margin-bottom:4px;}}
.prop-odds{{font-size:13px;color:var(--gray);margin-bottom:8px;}}
.prop-badge{{display:inline-block;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:10px;letter-spacing:1px;padding:2px 8px;border-radius:4px;margin-bottom:8px;}}
.b-high{{background:rgba(74,222,128,0.15);color:#4ade80;}}.b-med{{background:rgba(253,185,39,0.15);color:var(--gold);}}
.prop-reason{{font-size:12px;color:var(--gray);line-height:1.5;}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.4}}}}
.game-lines{{display:flex;gap:6px;padding:8px 16px;border-top:1px solid var(--border);flex-wrap:wrap;background:rgba(0,0,0,0.15);}}
.gl-item{{flex:1;min-width:60px;text-align:center;}}
.gl-lbl{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:9px;letter-spacing:2px;text-transform:uppercase;color:var(--gray);margin-bottom:2px;}}
.gl-val{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:14px;color:var(--gold);}}
footer{{border-top:1px solid var(--border);padding:24px;text-align:center;font-size:12px;color:var(--gray);}}
footer strong{{color:var(--white);}}"""

# ── Shared JS ─────────────────────────────────────────────────────────────
SHARED_JS = """
function renderStandings(data,id){
  const tb=document.getElementById(id);
  if(!tb)return;
  const tbl=tb.closest('table');
  const hasOTL=tbl&&Array.from(tbl.querySelectorAll('thead th')).some(th=>th.textContent==='OTL');
  const sorted=[...data].sort((a,b)=>(b.w/(b.w+b.l||1))-(a.w/(a.w+a.l||1)));
  sorted.forEach((t,i)=>{
    const gp=t.w+t.l||1,pct=(t.w/gp).toFixed(3);
    const ns=t.net>0?'+'+t.net:String(t.net),nc=t.net>0?'net-pos':t.net<0?'net-neg':'';
    const otlTd=hasOTL?`<td>${t.otl??0}</td>`:'';
    tb.innerHTML+=`<tr class="${i===7?'playoff-line':''}"><td><span class="team-rank">${i+1}</span></td><td><span class="team-name">${t.t}</span></td><td><span class="record-w">${t.w}</span></td><td><span class="record-l">${t.l}</span></td>${otlTd}<td>${pct}</td><td>${t.ppg}</td><td>${t.opp}</td><td class="${nc}">${ns}</td><td>${t.l10}</td></tr>`;
  });
}
function buildGameCard(gm){
  const isLive=gm.is_live,isFinal=gm.is_final;
  const hw=isFinal&&gm.h_score>gm.a_score,aw=isFinal&&gm.a_score>gm.h_score;
  const lbl=isLive?'<span style="color:#4ade80;font-weight:700;animation:pulse 1.2s infinite">● LIVE</span>':isFinal?'<span style="color:var(--gold)">FINAL</span>':gm.time;
  let scoreHtml='';
  if(isFinal||isLive){
    scoreHtml=`<div class="game-score"><span class="gscore ${hw?'w':'l'}">${gm.h_score}</span><span class="gfinal">${isFinal?'FINAL':'LIVE'}</span><span class="gscore ${aw?'w':'l'}">${gm.a_score}</span></div>`;
  }
  const spread=gm.spread||'—',total=gm.total||'—',hml=gm.h_ml||'—',aml=gm.a_ml||'—';
  const linesHtml=(!isFinal&&!isLive)?`<div class="game-lines"><div class="gl-item"><div class="gl-lbl">SPREAD</div><div class="gl-val">${spread}</div></div><div class="gl-item"><div class="gl-lbl">O/U</div><div class="gl-val">${total}</div></div><div class="gl-item"><div class="gl-lbl">HOME ML</div><div class="gl-val">${hml}</div></div><div class="gl-item"><div class="gl-lbl">AWAY ML</div><div class="gl-val">${aml}</div></div></div>`:'';
  return `<div class="game-card">
    <div class="game-card-top">
      <div class="game-time">${lbl}</div>
      <div class="game-matchup">
        <div style="flex:1">
          <div style="font-size:10px;letter-spacing:1px;font-family:'Barlow Condensed',sans-serif;font-weight:700;color:#4ade80;margin-bottom:2px">HOME</div>
          <div class="game-team fav">${gm.home}</div>
        </div>
        <div class="game-vs">vs</div>
        <div style="flex:1;text-align:right">
          <div style="font-size:10px;letter-spacing:1px;font-family:'Barlow Condensed',sans-serif;font-weight:700;color:var(--gray);margin-bottom:2px">AWAY</div>
          <div class="game-team dog">${gm.away}</div>
        </div>
      </div>
    </div>
    ${linesHtml}${scoreHtml}
  </div>`;
}
function parseESPNGames(events){
  return events.map(ev=>{
    const comp=ev.competitions[0];
    const teams={};comp.competitors.forEach(t=>teams[t.homeAway]=t);
    const home=teams.home||{},away=teams.away||{};
    const stype=comp.status?.type||{};
    const isFinal=stype.completed||false;
    const isLive=['STATUS_IN_PROGRESS','STATUS_HALFTIME','STATUS_END_PERIOD'].includes(stype.name);
    let timeStr='TBD';
    try{
      const dt=new Date(comp.date);
      let h24=(dt.getUTCHours()-4+24)%24,m=dt.getUTCMinutes();
      const ampm=h24<12?'AM':'PM';
      const h12=h24%12||12;
      timeStr=`${h12}:${m.toString().padStart(2,'0')} ${ampm} ET`;
    }catch(e){}
    let spread=null,total=null,h_ml=null,a_ml=null;
    try{
      const o=(comp.odds||[])[0]||{};
      if(o.details) spread=o.details;
      if(o.overUnder) total='O/U '+o.overUnder;
      const hmo=o.homeTeamOdds?.moneyLine;
      const amo=o.awayTeamOdds?.moneyLine;
      if(hmo) h_ml=(hmo>0?'+':'')+hmo;
      if(amo) a_ml=(amo>0?'+':'')+amo;
    }catch(e){}
    // Live game period/clock
    let liveDetail='';
    try{
      if(isLive){
        const period=comp.status?.period||'';
        const clock=comp.status?.displayClock||'';
        liveDetail=period&&clock?` · Q${period} ${clock}`:'';
      }
    }catch(e){}
    return {
      home:home.team?.displayName||'TBD',
      away:away.team?.displayName||'TBD',
      h_score:parseInt(home.score||0),
      a_score:parseInt(away.score||0),
      is_final:isFinal,is_live:isLive,
      time:timeStr+liveDetail,
      spread,total,h_ml,a_ml,
      gameDate:comp.date||''
    };
  });
}
function fmtDate(d){
  const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),dd=String(d.getDate()).padStart(2,'0');
  return `${y}-${m}-${dd}`;
}
function offsetDate(days){
  const d=new Date();d.setDate(d.getDate()+days);return fmtDate(d);
}
// ── ESPN game fetching for all sports ───────────────────────────
const _espnCache={};

async function fetchESPNGames(dateStr, gridId){
  const g=document.getElementById(gridId);
  if(!g)return;
  if(_espnCache[dateStr]!==undefined){
    _renderESPNGrid(dateStr,gridId);
    return;
  }
  g.innerHTML='<p style="color:var(--gray);padding:20px 0">Loading...</p>';
  try{
    const url=`https://site.api.espn.com/apis/site/v2/sports/${ESPN_SPORT}/${ESPN_LEAGUE}/scoreboard?dates=${dateStr.replace(/-/g,'')}`;
    const r=await fetch(url);
    const data=await r.json();
    _espnCache[dateStr]=parseESPNGames(data.events||[]);
  }catch(e){
    _espnCache[dateStr]=[];
    const g2=document.getElementById(gridId);
    if(g2) g2.innerHTML=`<p style="color:#f87171;padding:20px 0">Error: ${e.message}</p>`;
    return;
  }
  _renderESPNGrid(dateStr,gridId);
}

function _renderESPNGrid(dateStr,gridId){
  const g=document.getElementById(gridId);
  if(!g)return;
  const games=_espnCache[dateStr]||[];
  if(!games.length){g.innerHTML='<p style="color:var(--gray);padding:20px 0">No games scheduled.</p>';return;}
  g.innerHTML=games.map(buildGameCard).join('');
}

function renderGames(){
  // Fetch tonight immediately, stagger yesterday and tomorrow
  fetchESPNGames(offsetDate(0),'games-grid');
  setTimeout(()=>fetchESPNGames(offsetDate(-1),'yesterday-grid'),2000);
  setTimeout(()=>fetchESPNGames(offsetDate(1),'tomorrow-grid'),4000);
  // Refresh tonight every 60s
  setInterval(()=>{
    delete _espnCache[offsetDate(0)];
    fetchESPNGames(offsetDate(0),'games-grid');
  },60000);
}
function renderYesterday(){
  _renderESPNGrid(offsetDate(-1),'yesterday-grid');
}
function renderTomorrow(){
  _renderESPNGrid(offsetDate(1),'tomorrow-grid');
}
function tog(hdr){
  const body=hdr.nextElementSibling,chev=hdr.querySelector('.chev');
  body.classList.toggle('open');chev.classList.toggle('open');
}
function showPage(name,btn){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(l=>l.classList.remove('active'));
  const pg=document.getElementById('page-'+name);
  if(pg)pg.classList.add('active');
  if(btn)btn.classList.add('active');
  window.scrollTo({top:0,behavior:'smooth'});
}
function renderProps(allProps){
  const g=document.getElementById('props-grid');
  const note=document.getElementById('props-tonight-note');
  if(!g)return;
  // Wait for tonight's games to load, then filter props to only playing teams
  function doRender(){
    const todayStr=offsetDate(0);
    const cached=_espnCache[todayStr];
    if(!cached){
      setTimeout(doRender,800);
      return;
    }
    const tonightTeams=new Set();
    cached.forEach(gm=>{
      tonightTeams.add(gm.home.toLowerCase());
      tonightTeams.add(gm.away.toLowerCase());
    });
    const filtered=tonightTeams.size>0
      ? allProps.filter(p=>tonightTeams.has(p.team.toLowerCase())||[...tonightTeams].some(t=>p.team.toLowerCase().includes(t.split(' ').pop().toLowerCase())))
      : allProps;
    if(note){
      note.textContent=tonightTeams.size>0
        ? `Showing props for tonight's ${cached.length} game${cached.length!==1?'s':''} · ${filtered.length} props`
        : 'Could not load tonight\'s schedule';
    }
    if(!filtered.length){
      g.innerHTML='<p style="color:var(--gray)">No props available for tonight\'s games.</p>';
      return;
    }
    filtered.forEach(p=>{
      const bc=p.conf==='HIGH'?'b-high':'b-med';
      g.innerHTML+=`<div class="prop-card ${p.cls}"><div class="prop-player">${p.player}</div><div class="prop-team">${p.team}</div><div class="prop-line">${p.line}</div><div class="prop-odds">${p.odds}</div><div class="prop-badge ${bc}">${p.conf}</div><div class="prop-reason">${p.reason}</div></div>`;
    });
  }
  doRender();
}
function switchSched(tab,btn){
  ['today','yesterday','tomorrow'].forEach(t=>{
    const el=document.getElementById('sched-'+t);
    if(el) el.style.display=t===tab?'block':'none';
  });
  document.querySelectorAll('.sched-tab').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  if(tab==='yesterday'&&!document.getElementById('yesterday-grid').dataset.loaded){
    renderYesterday();
    document.getElementById('yesterday-grid').dataset.loaded='1';
  }
  if(tab==='tomorrow'&&!document.getElementById('tomorrow-grid').dataset.loaded){
    renderTomorrow();
    document.getElementById('tomorrow-grid').dataset.loaded='1';
  }
}
"""

def page_shell(sport, acc, acc2, hero_rgba, today, tabs_html, pages_html):
    css = base_css(acc, acc2, hero_rgba)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://fonts.googleapis.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com; font-src https://fonts.gstatic.com; connect-src https://site.api.espn.com https://api.balldontlie.io; img-src 'self' data:;">
<title>THE FIELD — {sport}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800;900&family=Barlow:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<nav>
  <div class="nav-inner">
    <a class="nav-logo" href="index.html"><span>THE</span> FIELD / {sport}</a>
    <div class="nav-links">{tabs_html}</div>
  </div>
</nav>
{pages_html}
<footer><strong>THE FIELD — {sport}</strong> · Data via ESPN · Updated {today} · For entertainment only · 1-800-GAMBLER</footer>
<script>{SHARED_JS}</script>
</body>
</html>"""

def standings_block(el, wl, e_label, w_label, c1="PPG", c2="OPP", show_otl=False):
    otl_th = "<th>OTL</th>" if show_otl else ""
    return f"""<div class="two-col">
  <div>
    <div class="section-title">{e_label}</div>
    <div class="standings-wrap"><table class="standings-table">
      <thead><tr><th>#</th><th>Team</th><th>W</th><th>L</th>{otl_th}<th>PCT</th><th>{c1}</th><th>{c2}</th><th>+/-</th><th>L10</th></tr></thead>
      <tbody id="east-body"></tbody>
    </table></div>
  </div>
  <div>
    <div class="section-title">{w_label}</div>
    <div class="standings-wrap"><table class="standings-table">
      <thead><tr><th>#</th><th>Team</th><th>W</th><th>L</th>{otl_th}<th>PCT</th><th>{c1}</th><th>{c2}</th><th>+/-</th><th>L10</th></tr></thead>
      <tbody id="west-body"></tbody>
    </table></div>
  </div>
</div>"""

def rankings_html(teams_all, picks):
    trend_cls = {"up":"tu","down":"td","flat":"tf"}
    trend_lbl = {"up":"↑ Moving Up","down":"↓ Sliding","flat":"→ Holding"}
    html = ""
    for i,(team,note,trend) in enumerate(picks):
        w = next((t['w'] for t in teams_all if t['t']==team), "—")
        l = next((t['l'] for t in teams_all if t['t']==team), "—")
        html += f"""<div class="rank-item"><div class="rank-n {'t3' if i<3 else ''}">{i+1}</div><div><div class="rank-team">{team}</div><div class="rank-rec">{w}-{l}</div><div class="rank-note">{note}</div><div class="rank-trend {trend_cls[trend]}">{trend_lbl[trend]}</div></div></div>"""
    return html

def sidebar_rows(teams):
    return "".join(f'<div class="sc-row"><span class="sc-team">{t["t"]}</span><span class="sc-val">{t["w"]}-{t["l"]}</span></div>' for t in teams[:5])

def storyline_articles(items):
    """items = list of (headline, body) tuples"""
    html = ""
    for h, b in items:
        html += f'''<div class="article"><div class="art-hdr" onclick="tog(this)"><div><div class="art-score">{h}</div></div><span class="chev">▼</span></div><div class="art-body">{b}</div></div>'''
    return html

def digest_articles(games, sport="", standings_east=None, standings_west=None):
    if not games:
        return '<p style="color:var(--gray)">No games yesterday.</p>'
    # Build a standings lookup for context
    all_teams = {}
    for t in (standings_east or []) + (standings_west or []):
        all_teams[t['t'].lower()] = t
    html = ""
    for g in games[:8]:
        hw = g['h_score'] > g['a_score']
        aw = g['a_score'] > g['h_score']
        h_style = "font-weight:700;color:var(--white)" if hw else "color:var(--gray)"
        a_style = "font-weight:700;color:var(--white)" if aw else "color:var(--gray)"
        winner = g["home"] if hw else g["away"]
        loser  = g["away"] if hw else g["home"]
        w_score = max(g["h_score"], g["a_score"])
        l_score = min(g["h_score"], g["a_score"])
        score_display = f'<span style="{h_style}">{g["home"]} {g["h_score"]}</span> &mdash; <span style="{a_style}">{g["away"]} {g["a_score"]}</span>'
        # Get standings context
        w_team = all_teams.get(winner.lower(), {})
        l_team = all_teams.get(loser.lower(), {})
        w_rec = f"{w_team.get('w','??')}-{w_team.get('l','??')}" if w_team else ""
        l_rec = f"{l_team.get('w','??')}-{l_team.get('l','??')}" if l_team else ""
        rec_note = f" ({w_rec})" if w_rec else ""
        opp_note = f" ({l_rec})" if l_rec else ""
        # Build rich metadata strip
        margin = abs(g["h_score"] - g["a_score"])
        if margin <= 3:
            game_type = "🔥 Nail-biter"
        elif margin <= 8:
            game_type = "⚔️ Competitive"
        elif margin <= 18:
            game_type = "✅ Convincing Win"
        else:
            game_type = "💥 Blowout"
        # Build richer standings context
        w_pos = ""
        l_pos = ""
        if w_team:
            all_sorted = sorted((standings_east or []) + (standings_west or []), key=lambda x: -x.get('pct', 0))
            try:
                w_rank = next(i+1 for i,t in enumerate(all_sorted) if t['t'] == winner)
                w_pos = f"#{w_rank} overall"
            except StopIteration:
                pass
        meta = f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px">'
        meta += f'<span style="font-size:11px;font-family:Barlow Condensed,sans-serif;font-weight:700;letter-spacing:1px;color:var(--gold)">{game_type}</span>'
        meta += f'<span style="font-size:11px;color:var(--gray)">Final: {g["h_score"]}-{g["a_score"]}</span>'
        if w_rec: meta += f'<span style="font-size:11px;color:#4ade80">✓ {winner} {w_rec}{" · "+w_pos if w_pos else ""}</span>'
        if l_rec: meta += f'<span style="font-size:11px;color:var(--gray)">✗ {loser} {l_rec}</span>'
        meta += '</div>'
        recap = generate_recap(sport, g["home"], g["h_score"], g["away"], g["a_score"], w_team=w_team, l_team=l_team)
        html += f"""<div class="article"><div class="art-hdr" onclick="tog(this)"><div><div class="art-score">{score_display}</div><div class="art-teams">Final · {game_type}</div></div><span class="chev">▼</span></div><div class="art-body">{meta}{recap}</div></div>"""
    return html

def magazine_page_html(sport, today, rnks, sidebar_html, storylines_html):
    """Full magazine page with power rankings + storylines + sidebar."""
    return f"""<div id="page-magazine" class="page">
  <div class="hero"><div class="hero-inner">
    <div class="hero-eyebrow">The Field · {today}</div>
    <h1 class="hero-title">{sport}<br><em>MAGAZINE</em></h1>
    <p class="hero-sub">Power rankings, season storylines and what to watch.</p>
  </div></div>
  <div class="section">
    <div class="mag-layout">
      <div>
        <div class="section-title">⚡ Power Rankings — {today}</div>
        {rnks}
        <div style="margin-top:36px">
          <div class="section-title">📰 Season Storylines</div>
          {storylines_html}
        </div>
      </div>
      <div>{sidebar_html}</div>
    </div>
  </div>
</div>"""

def tonight_page_html(sport, today):
    return f"""<div id="page-tonight" class="page">
  <div class="hero"><div class="hero-inner">
    <div class="live-pill">🔴 LIVE TONIGHT</div>
    <div class="hero-eyebrow">{today}</div>
    <h1 class="hero-title">TONIGHT'S<br><em>GAMES</em></h1>
    <p class="hero-sub">Live scores and {sport} matchups.</p>
  </div></div>
  <div class="section">
    <div style="display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap">
      <button class="sched-tab active" onclick="switchSched('today',this)">🔴 Tonight</button>
      <button class="sched-tab" onclick="switchSched('yesterday',this)">📋 Yesterday</button>
      <button class="sched-tab" onclick="switchSched('tomorrow',this)">📅 Tomorrow</button>
    </div>
    <div id="sched-today"><div class="games-grid" id="games-grid"></div></div>
    <div id="sched-yesterday" style="display:none"><div class="games-grid" id="yesterday-grid"></div></div>
    <div id="sched-tomorrow" style="display:none"><div class="games-grid" id="tomorrow-grid"></div></div>
  </div>
</div>"""

def props_page_html(sport, today):
    return f"""<div id="page-props" class="page">
  <div class="hero"><div class="hero-inner">
    <div class="hero-eyebrow">{today}</div>
    <h1 class="hero-title">PLAYER<br><em>PROPS</em></h1>
    <p class="hero-sub">Best prop bets for tonight's {sport} games.</p>
  </div></div>
  <div class="section">
    <div class="section-title">Tonight's Best Props</div>
    <div id="props-tonight-note" style="color:var(--gray);font-size:13px;margin-bottom:16px">Loading tonight's matchups...</div>
    <div class="props-grid" id="props-grid"></div>
    <p style="font-size:11px;color:var(--gray);margin-top:16px;text-align:center">For entertainment only. Not gambling advice. 1-800-GAMBLER.</p>
  </div>
</div>"""

# ════════════════════════════════════════════════════════════════
# DATA FETCHERS
# ════════════════════════════════════════════════════════════════

def fetch_games(sport, league):
    try:
        r = safe_get(f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard")
        out = []
        for ev in r.json().get("events", []):
            comp  = ev["competitions"][0]
            teams = {t["homeAway"]: t for t in comp["competitors"]}
            home, away = teams.get("home",{}), teams.get("away",{})
            stype = comp.get("status",{}).get("type",{})
            is_final = stype.get("completed", False)
            is_live  = stype.get("name","") in ("STATUS_IN_PROGRESS","STATUS_HALFTIME")
            # Parse time
            try:
                from datetime import timezone, timedelta
                dt = datetime.fromisoformat(comp.get("date","").replace("Z","+00:00"))
                et = dt - timedelta(hours=4)  # UTC to ET (EDT)
                h24 = et.hour
                ampm = "AM" if h24 < 12 else "PM"
                h12 = h24 % 12 or 12
                t_str = f"{h12}:{et.strftime('%M')} {ampm} ET"
            except:
                t_str = "TBD"
            # Parse odds
            spread = total = h_ml = a_ml = None
            try:
                odds_list = comp.get("odds", [])
                if odds_list:
                    o = odds_list[0]
                    raw_spread = o.get("details","")        # e.g. "LAL -5.5"
                    raw_ou     = o.get("overUnder","")       # e.g. 225.5
                    raw_hml    = o.get("homeTeamOdds",{}).get("moneyLine","")
                    raw_aml    = o.get("awayTeamOdds",{}).get("moneyLine","")
                    if raw_spread: spread = str(raw_spread)
                    if raw_ou:     total  = f"O/U {raw_ou}"
                    if raw_hml:    h_ml   = f"{'+' if int(raw_hml)>0 else ''}{raw_hml}"
                    if raw_aml:    a_ml   = f"{'+' if int(raw_aml)>0 else ''}{raw_aml}"
            except:
                pass
            out.append(dict(
                time=t_str,
                home=home.get("team",{}).get("displayName","TBD"),
                away=away.get("team",{}).get("displayName","TBD"),
                h_score=int(home.get("score",0) or 0),
                a_score=int(away.get("score",0) or 0),
                is_final=is_final, is_live=is_live,
                spread=spread, total=total, h_ml=h_ml, a_ml=a_ml,
            ))
        return out
    except Exception as e:
        log(f"  ⚠️  Games fetch failed: {e}")
        return []


def fallback_recap(home, h_score, away, a_score, sport="", w_team=None, l_team=None):
    """Auto-generate a rich recap with standings context."""
    winner = home if h_score > a_score else away
    loser  = away if h_score > a_score else home
    w_score = max(h_score, a_score)
    l_score = min(h_score, a_score)
    margin = abs(h_score - a_score)
    home_won = h_score > a_score

    # Standings context
    w_rec = f"{w_team['w']}-{w_team['l']}" if w_team else None
    l_rec = f"{l_team['w']}-{l_team['l']}" if l_team else None
    w_pct = w_team.get('pct', 0) if w_team else 0
    l_pct = l_team.get('pct', 0) if l_team else 0

    # Sport-specific score language
    if sport == "NHL":
        unit = "goals"
        close, comp, conv, blow = 1, 2, 3, 4
    elif sport == "MLB":
        unit = "runs"
        close, comp, conv, blow = 1, 2, 4, 6
    else:
        unit = "points"
        close, comp, conv, blow = 3, 8, 18, 999

    rec_note = f", now {w_rec}," if w_rec else ""
    opp_note = f", falling to {l_rec}," if l_rec else ""
    playoff_note = ""
    if w_team and w_pct >= 0.550:
        playoff_note = f" {winner} remains firmly in playoff position."
    elif l_team and l_pct <= 0.420:
        playoff_note = f" {loser} continues to struggle in the standings."

    if margin <= close:
        s1 = f"{winner} edged {loser} {w_score}-{l_score} in a thrilling finish last night."
        s2 = f"Just {margin} {unit} decided it — the kind of game that could have gone either way until the final moments."
        s3 = f"{winner}{rec_note} will take the close win.{opp_note and f' {loser}{opp_note} will feel this one.'}{playoff_note}"
    elif margin <= comp:
        s1 = f"{winner} defeated {loser} {w_score}-{l_score} in a competitive contest last night."
        s2 = f"{'Playing at home,' if home_won else 'On the road,'} {winner} found a way to pull ahead and held on for the {margin}-{unit} victory."
        s3 = f"{winner}{rec_note} picks up a solid win.{opp_note and f' {loser}{opp_note} will look to bounce back.'}{playoff_note}"
    elif margin <= conv:
        s1 = f"{winner} took care of business against {loser} last night, winning {w_score}-{l_score}."
        s2 = f"The {margin}-{unit} margin reflected {winner}'s control of the game — they set the tempo and never let {loser} dictate the action."
        s3 = f"A quality win for {winner}{rec_note} as they strengthen their standing.{playoff_note}"
    else:
        s1 = f"{winner} put on a dominant display against {loser}, winning {w_score}-{l_score} in a lopsided affair."
        s2 = f"The {margin}-{unit} gap was never in doubt — {winner} took over early and cruised to the comfortable victory."
        s3 = f"{loser}{opp_note} will need to regroup after being handled so decisively.{playoff_note}"

    return f"{s1} {s2} {s3}"

_BDL_GAMES_CACHE = None

def _fetch_bdl_games():
    """Fetch all BallDontLie games for yesterday — cached so we only call once."""
    global _BDL_GAMES_CACHE
    if _BDL_GAMES_CACHE is not None:
        return _BDL_GAMES_CACHE
    try:
        from datetime import timedelta
        ydate = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        hdrs = {"Authorization": BALLDONTLIE_API_KEY}
        r = requests.get("https://api.balldontlie.io/nba/v1/games",
                         params={"dates[]": ydate, "per_page": 30},
                         headers=hdrs, timeout=10)
        r.raise_for_status()
        _BDL_GAMES_CACHE = r.json().get("data", [])
        log(f"  ✅ BallDontLie: {len(_BDL_GAMES_CACHE)} games cached")
    except Exception as e:
        log(f"  ⚠️  BallDontLie fetch failed: {e}")
        _BDL_GAMES_CACHE = []
    return _BDL_GAMES_CACHE

def fetch_bdl_recap(home, h_score, away, a_score, sport="NBA", w_team=None, l_team=None):
    """Fetch NBA game recap via BallDontLie, write rich recap from score data."""
    try:
        games = _fetch_bdl_games()

        ht = at = hs = as_ = None
        for g in games:
            _ht = g.get("home_team", {}).get("full_name", "")
            _at = g.get("visitor_team", {}).get("full_name", "")
            if (home.lower() in _ht.lower() or _ht.lower() in home.lower()) and                (away.lower() in _at.lower() or _at.lower() in away.lower()):
                ht, at = _ht, _at
                hs = g.get("home_team_score", h_score)
                as_ = g.get("visitor_team_score", a_score)
                break

        if ht is None:
            return fallback_recap(home, h_score, away, a_score, sport=sport, w_team=w_team, l_team=l_team)

        winner = ht if hs > as_ else at
        loser  = at if hs > as_ else ht
        w_score, l_score = max(hs, as_), min(hs, as_)
        margin = abs(hs - as_)
        home_won = hs > as_

        if margin <= 3:
            s1 = f"{winner} survived a nail-biter against {loser}, escaping with a {w_score}-{l_score} victory last night."
            s2 = f"The game came down to the wire, with just {margin} points separating the two teams at the final buzzer."
            s3 = f"{loser} will feel the sting of this one, but {winner} showed the resilience to grind out a crucial win."
        elif margin <= 8:
            s1 = f"{winner} held off {loser} {w_score}-{l_score} in a competitive contest last night."
            s2 = f"{'The home crowd played a factor as' if home_won else 'The visitors came in and took care of business,'} {winner} pulled away late to secure the {margin}-point victory."
            s3 = f"{loser} made it a game but couldn't find enough offense down the stretch to force a different outcome."
        elif margin <= 18:
            s1 = f"{winner} took care of business against {loser} last night, winning convincingly {w_score}-{l_score}."
            s2 = f"The {margin}-point margin tells the story — {winner} controlled the tempo and never let {loser} get comfortable."
            s3 = f"It's a quality win for {winner} as they continue to build their case in the standings."
        else:
            s1 = f"{winner} put on a dominant display against {loser} last night, winning {w_score}-{l_score} in a blowout."
            s2 = f"The {margin}-point margin was a statement — {winner} led comfortably for most of the night and never let {loser} back into the game."
            s3 = f"{loser} will need to regroup quickly after being handled so decisively on the court."

        # Add standings context if available
        playoff_note = ""
        if w_team and w_team.get('pct',0) >= 0.550:
            playoff_note = f" {winner} stays firmly in playoff position at {w_team.get('w','?')}-{w_team.get('l','?')}."
        elif l_team and l_team.get('pct',0) <= 0.420:
            playoff_note = f" {loser} drops to {l_team.get('w','?')}-{l_team.get('l','?')} and continues to struggle."
        if playoff_note:
            s3 = s3 + playoff_note

        return f"{s1} {s2} {s3}"

    except Exception as e:
        log(f"  ⚠️  BallDontLie recap failed: {e}")
        return fallback_recap(home, h_score, away, a_score)

def generate_recap(sport, home, h_score, away, a_score, w_team=None, l_team=None):
    """Get a game recap — BallDontLie for NBA, fallback for others."""
    if sport == "NBA":
        return fetch_bdl_recap(home, h_score, away, a_score, sport=sport, w_team=w_team, l_team=l_team)
    return fallback_recap(home, h_score, away, a_score, sport=sport, w_team=w_team, l_team=l_team)

def fetch_yesterday(sport, league):
    """Fetch completed games from yesterday via ESPN scoreboard dates param."""
    try:
        from datetime import timedelta
        ydate = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        r = safe_get(
            f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard",
            {"dates": ydate}
        )
        out = []
        for ev in r.json().get("events", []):
            comp  = ev["competitions"][0]
            teams = {t["homeAway"]: t for t in comp["competitors"]}
            home, away = teams.get("home",{}), teams.get("away",{})
            stype = comp.get("status",{}).get("type",{})
            is_final = stype.get("completed", False)
            if not is_final:
                continue  # only include finished games for the digest
            h_score = int(home.get("score", 0) or 0)
            a_score = int(away.get("score", 0) or 0)
            winner = home.get("team",{}).get("displayName","") if h_score > a_score else away.get("team",{}).get("displayName","")
            out.append(dict(
                home=home.get("team",{}).get("displayName","TBD"),
                away=away.get("team",{}).get("displayName","TBD"),
                h_score=h_score,
                a_score=a_score,
                winner=winner,
                is_final=True, is_live=False,
            ))
        log(f"  📰 Yesterday ({ydate}): {len(out)} final games for {league}")
        return out
    except Exception as e:
        log(f"  ⚠️  Yesterday fetch failed ({league}): {e}")
        return []
    try:
        r = safe_get(f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard")
        out = []
        for ev in r.json().get("events", []):
            comp  = ev["competitions"][0]
            teams = {t["homeAway"]: t for t in comp["competitors"]}
            home, away = teams.get("home",{}), teams.get("away",{})
            stype = comp.get("status",{}).get("type",{})
            is_final = stype.get("completed", False)
            is_live  = stype.get("name","") in ("STATUS_IN_PROGRESS","STATUS_HALFTIME")
            # Parse time
            try:
                from datetime import timezone, timedelta
                dt = datetime.fromisoformat(comp.get("date","").replace("Z","+00:00"))
                et = dt - timedelta(hours=4)  # UTC to ET (EDT)
                h24 = et.hour
                ampm = "AM" if h24 < 12 else "PM"
                h12 = h24 % 12 or 12
                t_str = f"{h12}:{et.strftime('%M')} {ampm} ET"
            except:
                t_str = "TBD"
            # Parse odds
            spread = total = h_ml = a_ml = None
            try:
                odds_list = comp.get("odds", [])
                if odds_list:
                    o = odds_list[0]
                    raw_spread = o.get("details","")        # e.g. "LAL -5.5"
                    raw_ou     = o.get("overUnder","")       # e.g. 225.5
                    raw_hml    = o.get("homeTeamOdds",{}).get("moneyLine","")
                    raw_aml    = o.get("awayTeamOdds",{}).get("moneyLine","")
                    if raw_spread: spread = str(raw_spread)
                    if raw_ou:     total  = f"O/U {raw_ou}"
                    if raw_hml:    h_ml   = f"{'+' if int(raw_hml)>0 else ''}{raw_hml}"
                    if raw_aml:    a_ml   = f"{'+' if int(raw_aml)>0 else ''}{raw_aml}"
            except:
                pass
            out.append(dict(
                time=t_str,
                home=home.get("team",{}).get("displayName","TBD"),
                away=away.get("team",{}).get("displayName","TBD"),
                h_score=int(home.get("score",0) or 0),
                a_score=int(away.get("score",0) or 0),
                is_final=is_final, is_live=is_live,
                spread=spread, total=total, h_ml=h_ml, a_ml=a_ml,
            ))
        return out
    except Exception as e:
        log(f"  ⚠️  Games fetch failed: {e}")
        return []


def fetch_nba_standings():
    log("🏀 Fetching NBA standings...")
    try:
        r = safe_get("https://site.api.espn.com/apis/v2/sports/basketball/nba/standings", {"season": "2026"})
        east, west = [], []
        for conf in r.json().get("children", []):
            is_west = "WESTERN" in conf.get("name","").upper()
            top_entries = conf.get("standings",{}).get("entries",[])
            divs_list = conf.get("children",[]) if not top_entries else []
            def parse_nba_entry(entry, div_name=""):
                name = entry["team"]["displayName"]
                vals = {s["name"]: s.get("value",0) for s in entry.get("stats",[])}
                l   = int(float(vals.get("losses",0) or 0))
                gp  = int(float(vals.get("gamesPlayed", vals.get("points", 0)) or 0))
                w   = int(float(vals.get("wins", max(0, gp-l)) or 0))
                if gp == 0: gp = w + l
                gp  = gp or 1
                ppg = round(float(vals.get("avgPointsFor", vals.get("pointsFor",0)) or 0), 1)
                opp = round(float(vals.get("avgPointsAgainst", vals.get("pointsAgainst",0)) or 0), 1)
                if ppg > 200: ppg = round(ppg/gp,1); opp = round(opp/gp,1)
                net = round(ppg-opp, 1)
                pct = round(w/gp, 3)
                return dict(t=name, w=w, l=l, ppg=ppg, opp=opp, net=net, pct=pct, l10="—", div=div_name)
            if divs_list:
                for div in divs_list:
                    div_name = div.get("name","")
                    for entry in div.get("standings",{}).get("entries",[]):
                        try:
                            t = parse_nba_entry(entry, div_name)
                            if is_west: west.append(t)
                            else: east.append(t)
                        except: continue
            else:
                for entry in top_entries:
                    try:
                        t = parse_nba_entry(entry, "")
                        if is_west: west.append(t)
                        else: east.append(t)
                    except: continue
        east.sort(key=lambda x:-x["pct"]); west.sort(key=lambda x:-x["pct"])
        log(f"  ✅ NBA: {len(east)} East + {len(west)} West teams")
        return east, west
    except Exception as e:
        log(f"  ⚠️  NBA standings failed: {e}")
        return [], []


def fetch_nhl_standings():
    log("🏒 Fetching NHL standings...")
    try:
        r = safe_get("https://site.api.espn.com/apis/v2/sports/hockey/nhl/standings", {"season": datetime.now().year})
        east, west = [], []
        for conf in r.json().get("children",[]):
            is_west = "WESTERN" in conf.get("name","").upper()
            # Try flat entries first, then nested under divisions
            top_entries = conf.get("standings",{}).get("entries",[])
            divs_list = conf.get("children",[]) if not top_entries else []
            if not divs_list and not top_entries:
                continue
            # Process each division separately to capture div name
            if divs_list:
                for div in divs_list:
                    div_name = div.get("name","")
                    for entry in div.get("standings",{}).get("entries",[]):
                        try:
                            name = entry["team"]["displayName"]
                            vals = {s["name"]: s.get("value",0) for s in entry.get("stats",[])}
                            w   = int(float(vals.get("wins",0) or 0))
                            l   = int(float(vals.get("losses",0) or 0))
                            otl = int(float(vals.get("otLosses", vals.get("overtimeLosses",0)) or 0))
                            gp  = w+l+otl or 1
                            ppg = round(float(vals.get("goalsFor", vals.get("pointsFor",0)) or 0)/gp, 1)
                            opp = round(float(vals.get("goalsAgainst", vals.get("pointsAgainst",0)) or 0)/gp, 1)
                            net = round(ppg-opp, 1)
                            t = dict(t=name, w=w, l=l, otl=otl, pct=round(w/gp,3), ppg=ppg, opp=opp, net=net, l10="—", div=div_name)
                            if is_west: west.append(t)
                            else: east.append(t)
                        except: continue
            else:
                for entry in top_entries:
                    try:
                        name = entry["team"]["displayName"]
                        vals = {s["name"]: s.get("value",0) for s in entry.get("stats",[])}
                        w   = int(float(vals.get("wins",0) or 0))
                        l   = int(float(vals.get("losses",0) or 0))
                        otl = int(float(vals.get("otLosses", vals.get("overtimeLosses",0)) or 0))
                        gp  = w+l+otl or 1
                        ppg = round(float(vals.get("goalsFor", vals.get("pointsFor",0)) or 0)/gp, 1)
                        opp = round(float(vals.get("goalsAgainst", vals.get("pointsAgainst",0)) or 0)/gp, 1)
                        net = round(ppg-opp, 1)
                        t = dict(t=name, w=w, l=l, otl=otl, pct=round(w/gp,3), ppg=ppg, opp=opp, net=net, l10="—", div="")
                        if is_west: west.append(t)
                        else: east.append(t)
                    except: continue
        east.sort(key=lambda x:-x["pct"]); west.sort(key=lambda x:-x["pct"])
        log(f"  ✅ NHL: {len(east)} East + {len(west)} West")
        return east, west
    except Exception as e:
        log(f"  ⚠️  NHL standings failed: {e}")
        return [], []


def fetch_mlb_standings():
    log("⚾ Fetching MLB standings...")
    try:
        r = safe_get("https://site.api.espn.com/apis/v2/sports/baseball/mlb/standings", {"season": datetime.now().year})
        al, nl = [], []
        for conf in r.json().get("children",[]):
            cname = conf.get("name","").upper()
            if "CACTUS" in cname or "GRAPEFRUIT" in cname:
                continue
            is_al = "AMERICAN" in cname or cname.startswith("AL")
            entries = conf.get("standings",{}).get("entries",[])
            if not entries:
                for div in conf.get("children",[]):
                    dname = div.get("name","").upper()
                    div_al = is_al or "AMERICAN" in dname or dname.startswith("AL")
                    for entry in div.get("standings",{}).get("entries",[]):
                        try:
                            name = entry["team"]["displayName"]
                            vals = {s["name"]: s.get("value",0) for s in entry.get("stats",[])}
                            w = int(float(vals.get("wins",0) or 0))
                            l = int(float(vals.get("losses",0) or 0))
                            gp = w+l or 1
                            ppg = round(float(vals.get("runs", vals.get("pointsFor",0)) or 0)/gp, 1)
                            opp = round(float(vals.get("runsAllowed", vals.get("pointsAgainst",0)) or 0)/gp, 1)
                            t = dict(t=name,w=w,l=l,pct=round(w/gp,3),ppg=ppg,opp=opp,net=round(ppg-opp,1),l10="—")
                            if div_al: al.append(t)
                            else: nl.append(t)
                        except: continue
            else:
                for entry in entries:
                    try:
                        name = entry["team"]["displayName"]
                        vals = {s["name"]: s.get("value",0) for s in entry.get("stats",[])}
                        w = int(float(vals.get("wins",0) or 0))
                        l = int(float(vals.get("losses",0) or 0))
                        gp = w+l or 1
                        ppg = round(float(vals.get("runs", vals.get("pointsFor",0)) or 0)/gp, 1)
                        opp = round(float(vals.get("runsAllowed", vals.get("pointsAgainst",0)) or 0)/gp, 1)
                        t = dict(t=name,w=w,l=l,pct=round(w/gp,3),ppg=ppg,opp=opp,net=round(ppg-opp,1),l10="—")
                        if is_al: al.append(t)
                        else: nl.append(t)
                    except: continue
        al.sort(key=lambda x:-x["pct"]); nl.sort(key=lambda x:-x["pct"])
        if not al and not nl:
            log("  ℹ️  MLB spring training — regular season starts April 1")
            return [], []
        log(f"  ✅ MLB: {len(al)} AL + {len(nl)} NL teams")
        return al, nl
    except Exception as e:
        log(f"  ⚠️  MLB standings failed: {e}")
        return [], []


def fetch_nfl_standings():
    log("🏈 Fetching NFL standings...")
    try:
        r = safe_get("https://site.api.espn.com/apis/v2/sports/football/nfl/standings", {"season": "2025"})
        afc, nfc = [], []
        for conf in r.json().get("children",[]):
            is_afc = "AMERICAN" in conf.get("name","").upper()
            top_entries = conf.get("standings",{}).get("entries",[])
            divs_list = conf.get("children",[]) if not top_entries else []
            if divs_list:
                for div in divs_list:
                    div_name = div.get("name","")
                    for entry in div.get("standings",{}).get("entries",[]):
                        try:
                            name = entry["team"]["displayName"]
                            vals = {s["name"]: s.get("value",0) for s in entry.get("stats",[])}
                            w = int(float(vals.get("wins",0) or 0))
                            l = int(float(vals.get("losses",0) or 0))
                            gp = w+l or 1
                            ppg = round(float(vals.get("pointsFor",0) or 0)/gp, 1)
                            opp = round(float(vals.get("pointsAgainst",0) or 0)/gp, 1)
                            t = dict(t=name,w=w,l=l,pct=round(w/gp,3),ppg=ppg,opp=opp,net=round(ppg-opp,1),l10="—",div=div_name)
                            if is_afc: afc.append(t)
                            else: nfc.append(t)
                        except: continue
            else:
                for entry in top_entries:
                    try:
                        name = entry["team"]["displayName"]
                        vals = {s["name"]: s.get("value",0) for s in entry.get("stats",[])}
                        w = int(float(vals.get("wins",0) or 0))
                        l = int(float(vals.get("losses",0) or 0))
                        gp = w+l or 1
                        ppg = round(float(vals.get("pointsFor",0) or 0)/gp, 1)
                        opp = round(float(vals.get("pointsAgainst",0) or 0)/gp, 1)
                        t = dict(t=name,w=w,l=l,pct=round(w/gp,3),ppg=ppg,opp=opp,net=round(ppg-opp,1),l10="—",div="")
                        if is_afc: afc.append(t)
                        else: nfc.append(t)
                    except: continue
        afc.sort(key=lambda x:-x["pct"]); nfc.sort(key=lambda x:-x["pct"])
        log(f"  ✅ NFL: {len(afc)} AFC + {len(nfc)} NFC teams")
        return afc, nfc
    except Exception as e:
        log(f"  ⚠️  NFL standings failed: {e}")
        return [], []

# ════════════════════════════════════════════════════════════════
# HTML GENERATORS
# ════════════════════════════════════════════════════════════════

# Master player prop database — only shown when their team plays tonight
NBA_PROPS_DB = [
    {"player":"Shai Gilgeous-Alexander","team":"Oklahoma City Thunder","line":"Over 31.5 Pts","odds":"-115","conf":"HIGH","cls":"high","reason":"SGA leads the league at 32.5 PPG and has hit this in 8 of his last 10."},
    {"player":"Nikola Jokic","team":"Denver Nuggets","line":"Over 10.5 Reb","odds":"-120","conf":"HIGH","cls":"high","reason":"Jokic averages 12.6 RPG — consistently clears this line at home and away."},
    {"player":"Donovan Mitchell","team":"Cleveland Cavaliers","line":"Over 26.5 Pts","odds":"-118","conf":"HIGH","cls":"high","reason":"Mitchell is the Cavs' engine — hits this in 65%+ of games this season."},
    {"player":"Anthony Edwards","team":"Minnesota Timberwolves","line":"Over 25.5 Pts","odds":"-110","conf":"HIGH","cls":"high","reason":"Ant is the Wolves' primary scorer and hits this line at an elite rate."},
    {"player":"Jayson Tatum","team":"Boston Celtics","line":"Over 26.5 Pts","odds":"-112","conf":"HIGH","cls":"high","reason":"Tatum is Boston's go-to option every night — volume is always there."},
    {"player":"Tyrese Haliburton","team":"Indiana Pacers","line":"Over 9.5 Ast","odds":"-112","conf":"HIGH","cls":"high","reason":"Haliburton leads the league in assists — this line is conservative."},
    {"player":"Luka Doncic","team":"Dallas Mavericks","line":"Over 28.5 Pts","odds":"-114","conf":"HIGH","cls":"high","reason":"Luka averaging 29+ PPG — dominant usage rate in Dallas."},
    {"player":"Giannis Antetokounmpo","team":"Milwaukee Bucks","line":"Over 11.5 Reb","odds":"-118","conf":"HIGH","cls":"high","reason":"The Greek Freak is a rebounding machine — hits this in 70% of games."},
    {"player":"Ja Morant","team":"Memphis Grizzlies","line":"Over 22.5 Pts","odds":"-108","conf":"HIGH","cls":"high","reason":"Morant back in full swing — Grizzlies offense flows through him."},
    {"player":"LeBron James","team":"Los Angeles Lakers","line":"Over 7.5 Ast","odds":"-110","conf":"MEDIUM","cls":"medium","reason":"LeBron's playmaking is elite — dishes at a high rate every game."},
    {"player":"Stephen Curry","team":"Golden State Warriors","line":"Over 4.5 Threes","odds":"-105","conf":"MEDIUM","cls":"medium","reason":"Curry's volume from deep makes this line beatable on most nights."},
    {"player":"Devin Booker","team":"Phoenix Suns","line":"Over 27.5 Pts","odds":"-110","conf":"MEDIUM","cls":"medium","reason":"Book is the Suns' primary scorer — consistent output all season."},
    {"player":"Kevin Durant","team":"Phoenix Suns","line":"Over 26.5 Pts","odds":"-112","conf":"MEDIUM","cls":"medium","reason":"KD's efficiency is elite — hits this line in most games this year."},
    {"player":"Zion Williamson","team":"New Orleans Pelicans","line":"Over 24.5 Pts","odds":"-108","conf":"MEDIUM","cls":"medium","reason":"When healthy, Zion dominates inside and posts big scoring nights."},
    {"player":"Trae Young","team":"Atlanta Hawks","line":"Over 9.5 Ast","odds":"-115","conf":"MEDIUM","cls":"medium","reason":"Trae is the Hawks' offense — his assists number is consistent."},
    {"player":"Darius Garland","team":"Cleveland Cavaliers","line":"Over 22.5 Pts","odds":"-108","conf":"MEDIUM","cls":"medium","reason":"Garland is Cavs' second option — hits this when Mitchell is on."},
    {"player":"Paolo Banchero","team":"Orlando Magic","line":"Over 22.5 Pts","odds":"-110","conf":"MEDIUM","cls":"medium","reason":"Banchero is Orlando's cornerstone scorer — reliable prop target."},
    {"player":"Bam Adebayo","team":"Miami Heat","line":"Over 9.5 Reb","odds":"-114","conf":"MEDIUM","cls":"medium","reason":"Bam is a rebounding anchor for Miami — consistently hits this."},
    {"player":"Cade Cunningham","team":"Detroit Pistons","line":"Over 23.5 Pts","odds":"-108","conf":"MEDIUM","cls":"medium","reason":"Cunningham carrying Detroit — big usage and scoring every night."},
    {"player":"Jalen Brunson","team":"New York Knicks","line":"Over 25.5 Pts","odds":"-112","conf":"MEDIUM","cls":"medium","reason":"Brunson is NYC's star — hits this mark consistently at MSG and away."},
]

def build_nba_props(today_games):
    """Return props only for players whose teams are playing tonight."""
    if not today_games:
        return NBA_PROPS_DB[:6]
    playing_teams = set()
    for g in today_games:
        playing_teams.add(g.get("home","").lower())
        playing_teams.add(g.get("away","").lower())
    filtered = [p for p in NBA_PROPS_DB if any(
        pt in p["team"].lower() or p["team"].lower() in pt
        for pt in playing_teams
    )]
    return filtered if filtered else NBA_PROPS_DB[:6]

def generate_nba_html(east, west, yesterday, today_games):
    log("🌐 Generating nba.html...")
    today   = datetime.now().strftime("%B %-d, %Y")
    ej, wj  = json.dumps(east), json.dumps(west)
    tj      = json.dumps(today_games)
    all_t   = sorted(east+west, key=lambda x:-x["pct"])

    props = build_nba_props(today_games)
    pj = json.dumps(props)

    rnks = rankings_html(all_t, [
        ("Oklahoma City Thunder","OKC leads the West with elite two-way play and SGA in MVP form.","up"),
        ("Cleveland Cavaliers","Best record in the East — Donovan Mitchell is must-watch.","up"),
        ("Boston Celtics","Defending champs showing why — deep and battle-tested.","flat"),
        ("Minnesota Timberwolves","Edwards carrying the load — defense elite as always.","up"),
        ("Denver Nuggets","Jokic doing Jokic things. Watch when the Nuggets get healthy.","flat"),
        ("New York Knicks","Most improved team in the East. Brunson making everyone better.","up"),
        ("Golden State Warriors","Curry still special. Youth movement gaining momentum.","flat"),
        ("Indiana Pacers","Tyrese Haliburton leading the most exciting offense in the East.","down"),
        ("Memphis Grizzlies","Ja Morant back and locked in — watch this team surge.","up"),
        ("LA Lakers","LeBron and AD combo still formidable when healthy.","down"),
    ])

    e8 = f"{east[7]['w']}-{east[7]['l']}" if len(east)>7 else "—"
    w8 = f"{west[7]['w']}-{west[7]['l']}" if len(west)>7 else "—"

    tabs = """<button class="nav-link active" onclick="showPage('standings',this)">Standings</button>
      <button class="nav-link" onclick="showPage('tonight',this)">Tonight</button>
      <button class="nav-link" onclick="showPage('digest',this)">Daily Digest</button>
      <button class="nav-link" onclick="showPage('magazine',this)">Magazine</button>
      <button class="nav-link" onclick="showPage('props',this)">Player Props</button>"""

    nba_sidebar = (
        '<div class="sidebar-card"><div class="sc-title">&#127936; Best Records</div>' + sidebar_rows(all_t) + '</div>'
        '<div class="sidebar-card"><div class="sc-title">&#128202; Playoff Picture</div>'
        '<div class="sc-row"><span class="sc-team">E8 Cutoff</span><span class="sc-val">' + e8 + '</span></div>'
        '<div class="sc-row"><span class="sc-team">W8 Cutoff</span><span class="sc-val">' + w8 + '</span></div>'
        '</div>'
        '<div class="sidebar-card"><div class="sc-title">&#128293; Scoring Leaders</div>'
        '<div class="sc-row"><span class="sc-team">SGA</span><span class="sc-val">32.5 PPG</span></div>'
        '<div class="sc-row"><span class="sc-team">D. Mitchell</span><span class="sc-val">26.8 PPG</span></div>'
        '<div class="sc-row"><span class="sc-team">G. Antetokounmpo</span><span class="sc-val">26.3 PPG</span></div>'
        '<div class="sc-row"><span class="sc-team">A. Edwards</span><span class="sc-val">25.9 PPG</span></div>'
        '<div class="sc-row"><span class="sc-team">J. Tatum</span><span class="sc-val">25.1 PPG</span></div>'
        '</div>'
    )
    nba_stories = storyline_articles([
        ("SGA MVP Season", "Shai Gilgeous-Alexander is putting together one of the most dominant scoring seasons in NBA history, averaging 32.5 PPG. He is the heavy favorite for MVP and leading OKC to the best record in the West."),
        ("The Cavs Historic Run", "Cleveland is on track for one of the best records in franchise history. Donovan Mitchell has elevated his game to true superstar status, and the supporting cast is among the deepest in the league."),
        ("Jokic Doing Jokic Things", "Nikola Jokic is quietly putting together another MVP-caliber season averaging a triple-double. The question for Denver is whether the supporting cast can stay healthy enough for a deep playoff run."),
        ("Tatum Evolution", "Jayson Tatum has taken a leap as a playmaker this season, averaging career highs in assists. The Celtics look ready to defend their title with one of the deepest rosters in the East."),
    ])
    nba_mag_html = magazine_page_html("NBA", today, rnks, nba_sidebar, nba_stories)
    pages = f"""
<div id="page-standings" class="page active">
  <div class="hero"><div class="hero-inner">
    <div class="hero-eyebrow">2025-26 NBA Season Updated {today}</div>
    <h1 class="hero-title">NBA<br><em>STANDINGS</em></h1>
    <p class="hero-sub">Full Eastern and Western Conference standings.</p>
  </div></div>
  <div class="section">{standings_block(ej,wj,"Eastern Conference","Western Conference")}</div>
</div>
{tonight_page_html("NBA",today)}
<div id="page-digest" class="page">
  <div class="section" style="padding-top:30px">
    <div class="digest-lead">
      <div class="dlabel">Daily Digest {today}</div>
      <div class="dhl">Last Night NBA Action</div>
      <div class="ddeck">Scores and recaps from yesterday's games.</div>
    </div>
    {digest_articles(yesterday,"NBA",east,west)}
  </div>
</div>
{nba_mag_html}
{props_page_html("NBA",today)}
"""
    init = f"const EAST={ej};const WEST={wj};const TONIGHT={tj};const PROPS_DATA={pj};const ESPN_SPORT='basketball';const ESPN_LEAGUE='nba';renderStandings(EAST,'east-body');renderStandings(WEST,'west-body');renderGames();renderProps(PROPS_DATA);"
    html = page_shell("NBA","#c8102e","#e8132f","rgba(200,16,46,0.11)",today,tabs,pages)
    html = html.replace("</script>", init+"</script>")
    save("nba.html", html)


def generate_nhl_html(east, west, yesterday, today_games):
    log("🌐 Generating nhl.html...")
    today  = datetime.now().strftime("%B %-d, %Y")
    ej, wj = json.dumps(east), json.dumps(west)
    tj     = json.dumps(today_games)
    all_t  = sorted(east+west, key=lambda x:-x["pct"])

    props = [
        {"player":"Connor McDavid","team":"Edmonton Oilers","line":"Over 1.5 points","odds":"-130","conf":"HIGH","cls":"high","reason":"McDavid averages 1.8 pts/game. Hits this line in 60%+ of games."},
        {"player":"Nathan MacKinnon","team":"Colorado Avalanche","line":"Over 0.5 goals","odds":"-115","conf":"HIGH","cls":"high","reason":"MacKinnon leads the Avs in shots and scoring chances every night."},
        {"player":"Auston Matthews","team":"Toronto Maple Leafs","line":"Over 3.5 shots","odds":"-120","conf":"HIGH","cls":"high","reason":"Matthews averages 4.2 SOG — this line is below his season average."},
        {"player":"Leon Draisaitl","team":"Edmonton Oilers","line":"Over 1.5 points","odds":"-118","conf":"HIGH","cls":"high","reason":"Draisaitl racks up points in bunches. Power play alone drives this line."},
        {"player":"David Pastrnak","team":"Boston Bruins","line":"Over 0.5 goals","odds":"-108","conf":"MEDIUM","cls":"medium","reason":"Pastrnak is Boston's most dangerous scorer with premium power play time."},
        {"player":"Cale Makar","team":"Colorado Avalanche","line":"Over 1.5 shots","odds":"-125","conf":"MEDIUM","cls":"medium","reason":"Makar logs 25+ minutes — elite shot volume for a D-man."},
    ]
    pj = json.dumps(props)

    rnks = rankings_html(all_t, [
        ("Colorado Avalanche","Best team in hockey — MacKinnon and Makar leading a title run. Top overall seed in the NHL.","up"),
        ("Dallas Stars","Surging to #2 — battling Colorado for the Central crown and top seed. Heiskanen anchors the blue line.","up"),
        ("Carolina Hurricanes","Third-most points in the league. Brandon Bussi is 25-3-1. Perhaps the most complete team in the East.","flat"),
        ("Minnesota Wild","Kirill Kaprizov became the franchise's all-time goals leader (35) — Wild are a genuine Cup contender.","up"),
        ("Tampa Bay Lightning","Vasilevskiy is back to elite form. Kucherov among the league leaders in points.","flat"),
        ("Vegas Golden Knights","Hertl and Stone keep this team dangerous. Tomas Hertl scored an OT winner this week.","flat"),
        ("Buffalo Sabres","Won four in a row since the Olympic break — Tage Thompson is a superstar. Lindy Ruff hit 700 wins.","up"),
        ("Washington Capitals","Ovechkin closing in on the all-time goals record. This team is surging at the right time.","up"),
        ("Edmonton Oilers","McDavid and Draisaitl are the most dangerous duo in hockey when locked in.","flat"),
        ("Boston Bruins","Healthy and winning since the Olympic break — fighting hard for a playoff spot.","up"),
    ])

    e8 = f"{east[7]['w']}-{east[7]['l']}" if len(east)>7 else "—"
    w8 = f"{west[7]['w']}-{west[7]['l']}" if len(west)>7 else "—"

    tabs = """<button class="nav-link active" onclick="showPage('standings',this)">Standings</button>
      <button class="nav-link" onclick="showPage('tonight',this)">Tonight</button>
      <button class="nav-link" onclick="showPage('digest',this)">Daily Digest</button>
      <button class="nav-link" onclick="showPage('magazine',this)">Magazine</button>
      <button class="nav-link" onclick="showPage('props',this)">Player Props</button>"""

    pages = f"""
<div id="page-standings" class="page active">
  <div class="hero"><div class="hero-inner">
    <div class="hero-eyebrow">2024-25 NHL Season Updated {today}</div>
    <h1 class="hero-title">NHL<br><em>STANDINGS</em></h1>
    <p class="hero-sub">Eastern and Western Conference standings.</p>
  </div></div>
  <div class="section">{standings_block(ej,wj,"Eastern Conference","Western Conference","GF/G","GA/G",show_otl=True)}</div>
</div>
{tonight_page_html("NHL",today)}
<div id="page-digest" class="page">
  <div class="section" style="padding-top:30px">
    <div class="digest-lead">
      <div class="dlabel">Daily Digest {today}</div>
      <div class="dhl">Last Night NHL Action</div>
      <div class="ddeck">Scores and recaps from yesterday's games.</div>
    </div>
    {digest_articles(yesterday,"NHL",east,west)}
  </div>
</div>
""" + magazine_page_html("NHL", today, rnks,
        '<div class="sidebar-card"><div class="sc-title">Top of the League</div>' + sidebar_rows(all_t) + '</div>'
        '<div class="sidebar-card"><div class="sc-title">Playoff Picture</div>'
        '<div class="sc-row"><span class="sc-team">E8 Cutoff</span><span class="sc-val">' + e8 + '</span></div>'
        '<div class="sc-row"><span class="sc-team">W8 Cutoff</span><span class="sc-val">' + w8 + '</span></div>'
        '</div>'
        '<div class="sidebar-card"><div class="sc-title">Points Leaders</div>'
        '<div class="sc-row"><span class="sc-team">N. MacKinnon</span><span class="sc-val">94 pts</span></div>'
        '<div class="sc-row"><span class="sc-team">K. Kaprizov</span><span class="sc-val">35 G</span></div>'
        '<div class="sc-row"><span class="sc-team">N. Kucherov</span><span class="sc-val">88 pts</span></div>'
        '<div class="sc-row"><span class="sc-team">C. McDavid</span><span class="sc-val">85 pts</span></div>'
        '<div class="sc-row"><span class="sc-team">C. Makar</span><span class="sc-val">72 pts</span></div>'
        '</div>'
        '<div class="sidebar-card"><div class="sc-title">Goalie Leaders</div>'
        '<div class="sc-row"><span class="sc-team">B. Bussi (CAR)</span><span class="sc-val">25-3-1</span></div>'
        '<div class="sc-row"><span class="sc-team">A. Vasilevskiy</span><span class="sc-val">.922 SV%</span></div>'
        '<div class="sc-row"><span class="sc-team">J. Shesterkin</span><span class="sc-val">.918 SV%</span></div>'
        '</div>',
        storyline_articles([
            ("Colorado Title Run", "The Avalanche are the best team in hockey entering March. MacKinnon and Makar are putting up historic numbers and Colorado has the top overall seed locked in their sights."),
            ("Ovechkin Record Chase", "Alex Ovechkin is closing in on Wayne Gretzky all-time goals record, one of the most anticipated milestones in sports history. Every Capitals game is must-watch."),
            ("Kaprizov Franchise Record", "Kirill Kaprizov became the Wild all-time leading goal scorer this week with his 35th goal of the season. The Wild are a legitimate Cup contender."),
            ("Trade Deadline Fallout", "The 2026 NHL trade deadline has reshaped multiple contenders. Several top teams upgraded, making the stretch run and playoff picture even more compelling."),
        ])
    ) + props_page_html("NHL", today)
    init = f"const EAST={ej};const WEST={wj};const TONIGHT={tj};const PROPS_DATA={pj};const ESPN_SPORT='hockey';const ESPN_LEAGUE='nhl';renderStandings(EAST,'east-body');renderStandings(WEST,'west-body');renderGames();renderProps(PROPS_DATA);"
    html = page_shell("NHL","#4ab3ff","#2d9de8","rgba(74,179,255,0.10)",today,tabs,pages)
    html = html.replace("</script>", init+"</script>")
    save("nhl.html", html)


def generate_mlb_html(al, nl, yesterday, today_games):
    log("🌐 Generating mlb.html...")
    today  = datetime.now().strftime("%B %-d, %Y")
    ej, wj = json.dumps(al), json.dumps(nl)
    tj     = json.dumps(today_games)
    all_t  = sorted(al+nl, key=lambda x:-x["pct"])

    props = [
        {"player":"Shohei Ohtani","team":"Los Angeles Dodgers","line":"Over 1.5 total bases","odds":"-125","conf":"HIGH","cls":"high","reason":"Ohtani barrels the ball at an elite rate. Achievable in a single hit."},
        {"player":"Aaron Judge","team":"New York Yankees","line":"Over 0.5 home runs","odds":"+185","conf":"HIGH","cls":"high","reason":"Judge leads MLB in HR. Great value for the best power hitter in baseball."},
        {"player":"Freddie Freeman","team":"Los Angeles Dodgers","line":"Over 1.5 total bases","odds":"-115","conf":"HIGH","cls":"high","reason":"Freeman is the Dodgers' most consistent contact hitter."},
        {"player":"Juan Soto","team":"New York Yankees","line":"Over 0.5 walks","odds":"-130","conf":"HIGH","cls":"high","reason":"Soto has an elite eye and draws walks in the majority of his games."},
        {"player":"Mookie Betts","team":"Los Angeles Dodgers","line":"Over 1.5 total bases","odds":"-110","conf":"MEDIUM","cls":"medium","reason":"One of the most consistent performers in baseball."},
        {"player":"Ronald Acuña Jr.","team":"Atlanta Braves","line":"Over 0.5 stolen bases","odds":"+110","conf":"MEDIUM","cls":"medium","reason":"Most dangerous baserunner in baseball. Plus money is great value."},
    ]
    pj = json.dumps(props)

    spring = "" if al or nl else """<div style="background:rgba(253,185,39,0.08);border:1px solid rgba(253,185,39,0.2);border-radius:12px;padding:24px;margin-bottom:28px;text-align:center">
  <div style="font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:20px;color:var(--gold);margin-bottom:8px">⚾ Spring Training 2025</div>
  <div style="color:var(--gray);font-size:14px">Regular season standings will appear here starting April 1, 2025.</div>
</div>"""

    rnks = rankings_html(all_t, [
        ("Los Angeles Dodgers","Ohtani, Freeman, Betts — deepest lineup in baseball.","up"),
        ("New York Yankees","Judge is the best power hitter alive. Rotation is elite.","flat"),
        ("Atlanta Braves","Acuña healthy changes everything. Rotation is deep.","up"),
        ("Philadelphia Phillies","Wheeler and Nola give them the best 1-2 in the NL.","flat"),
        ("Baltimore Orioles","Young core is maturing fast. Could surprise everyone.","up"),
        ("Houston Astros","Always dangerous. Alvarez is a postseason monster.","flat"),
        ("Cleveland Guardians","Pitching staff is underrated. Bieber return is huge.","up"),
        ("San Diego Padres","Tatis healthy and hungry. Watch this team in the West.","down"),
        ("Boston Red Sox","Devers is a force. Rotation depth is the question.","flat"),
        ("Seattle Mariners","Julio Rodriguez emerging as a true franchise player.","up"),
    ])

    alwc = f"{al[5]['w']}-{al[5]['l']}" if len(al)>5 else "—"
    nlwc = f"{nl[5]['w']}-{nl[5]['l']}" if len(nl)>5 else "—"
    digest_note = yesterday if yesterday else []
    digest_fallback = digest_articles(digest_note,"MLB",al,nl) if digest_note else '<p style="color:var(--gray)">Spring training underway — regular season starts April 1.</p>'

    tabs = """<button class="nav-link active" onclick="showPage('standings',this)">Standings</button>
      <button class="nav-link" onclick="showPage('tonight',this)">Tonight</button>
      <button class="nav-link" onclick="showPage('digest',this)">Daily Digest</button>
      <button class="nav-link" onclick="showPage('magazine',this)">Magazine</button>
      <button class="nav-link" onclick="showPage('props',this)">Player Props</button>"""

    pages = f"""
<div id="page-standings" class="page active">
  <div class="hero"><div class="hero-inner">
    <div class="hero-eyebrow">2025 MLB Season · Updated {today}</div>
    <h1 class="hero-title">MLB<br><em>STANDINGS</em></h1>
    <p class="hero-sub">American League and National League standings.</p>
  </div></div>
  <div class="section">{spring}{standings_block(ej,wj,"American League","National League","R/G","RA/G")}</div>
</div>
{tonight_page_html("MLB",today)}
<div id="page-digest" class="page">
  <div class="section" style="padding-top:30px">
    <div class="digest-lead">
      <div class="dlabel">Daily Digest {today}</div>
      <div class="dhl">Last Night MLB Action</div>
      <div class="ddeck">Scores and recaps from yesterday's games.</div>
    </div>
    {digest_fallback}
  </div>
</div>
""" + magazine_page_html("MLB", today, rnks,
        '<div class="sidebar-card"><div class="sc-title">Best Records</div>'
        + (sidebar_rows(all_t) if all_t else '<div class="sc-row"><span class="sc-team">Season starts April 1</span></div>')
        + '</div>'
        '<div class="sidebar-card"><div class="sc-title">Playoff Picture</div>'
        '<div class="sc-row"><span class="sc-team">AL Wild Card</span><span class="sc-val">' + alwc + '</span></div>'
        '<div class="sc-row"><span class="sc-team">NL Wild Card</span><span class="sc-val">' + nlwc + '</span></div>'
        '</div>'
        '<div class="sidebar-card"><div class="sc-title">2025 World Series</div>'
        '<div class="sc-row"><span class="sc-team">Dodgers</span><span class="sc-val">Champs</span></div>'
        '<div class="sc-row"><span class="sc-team">WS MVP</span><span class="sc-val">F. Freeman</span></div>'
        '<div class="sc-row"><span class="sc-team">Season MVP</span><span class="sc-val">S. Ohtani</span></div>'
        '</div>'
        '<div class="sidebar-card"><div class="sc-title">Key Dates</div>'
        '<div class="sc-row"><span class="sc-team">Opening Day</span><span class="sc-val">April 1</span></div>'
        '<div class="sc-row"><span class="sc-team">All-Star Game</span><span class="sc-val">July 2026</span></div>'
        '</div>',
        storyline_articles([
            ("Spring Training 2026", "Teams are putting the finishing touches on rosters before Opening Day on April 1. The Dodgers enter as defending World Series champions with Shohei Ohtani healthy and ready for a full season. The Yankees, Braves, and Phillies all look like legitimate threats."),
            ("Ohtani Two-Way Return", "After focusing on hitting in 2024, Shohei Ohtani is returning to the mound in 2026. The combination of elite pitching and his 50-HR bat makes him the most valuable player in baseball history."),
            ("Judge Power Throne", "Aaron Judge continues to be the most feared power hitter in baseball. He is coming off back-to-back HR crowns and the Yankees have built a rotation around him capable of a World Series run."),
            ("Acuna Comeback", "Ronald Acuna Jr. returns from injury for Atlanta fully healthy. When Acuna is right, the Braves are a different team and a genuine NL pennant contender."),
        ])
    ) + props_page_html("MLB", today)
    init = f"const EAST={ej};const WEST={wj};const TONIGHT={tj};const PROPS_DATA={pj};const ESPN_SPORT='baseball';const ESPN_LEAGUE='mlb';renderStandings(EAST,'east-body');renderStandings(WEST,'west-body');renderGames();renderProps(PROPS_DATA);"
    html = page_shell("MLB","#22c55e","#16a34a","rgba(34,197,94,0.08)",today,tabs,pages)
    html = html.replace("</script>", init+"</script>")
    save("mlb.html", html)


def generate_nfl_html(afc, nfc, yesterday=None, today_games=None):
    log("🌐 Generating nfl.html...")
    today  = datetime.now().strftime("%B %-d, %Y")
    ej, wj = json.dumps(afc), json.dumps(nfc)
    all_t  = sorted(afc+nfc, key=lambda x:-x["pct"])

    rnks = rankings_html(all_t, [
        ("Seattle Seahawks","Super Bowl LX champions. Macdonald's defense is the best in football.","up"),
        ("Kansas City Chiefs","Three Super Bowls in five years — Mahomes is a dynasty builder.","flat"),
        ("Buffalo Bills","Josh Allen is the best player in football. Year in, year out.","up"),
        ("Philadelphia Eagles","Super Bowl LIX champs still loaded. Hurts and a deep roster.","flat"),
        ("Baltimore Ravens","Lamar Jackson is a force of nature. Defense is ferocious.","flat"),
        ("Detroit Lions","Most improved franchise of the decade. Goff is the real deal.","up"),
        ("Minnesota Vikings","Sam Darnold's redemption story ends in Seattle — but watch this team.","flat"),
        ("Los Angeles Rams","McVay keeps finding ways to win. Stafford still elite.","flat"),
        ("Cincinnati Bengals","Burrow and Chase — one of the best QB/WR duos ever.","up"),
        ("Green Bay Packers","Love is developing into a real franchise QB.","up"),
    ])

    tabs = """<button class="nav-link active" onclick="showPage('standings',this)">Standings</button>
      <button class="nav-link" onclick="showPage('digest',this)">Season Recap</button>
      <button class="nav-link" onclick="showPage('magazine',this)">Magazine</button>"""

    pages = f"""
<div id="page-standings" class="page active">
  <div class="hero"><div class="hero-inner">
    <div class="hero-eyebrow">2025 NFL Season · Final Standings</div>
    <h1 class="hero-title">NFL<br><em>STANDINGS</em></h1>
    <p class="hero-sub">Final AFC and NFC standings from the 2025 season.</p>
  </div></div>
  <div class="section">{standings_block(ej,wj,"AFC","NFC")}</div>
</div>
<div id="page-digest" class="page">
  <div class="section" style="padding-top:30px">
    <div class="digest-lead">
      <div class="dlabel">Season Recap · 2025-26</div>
      <div class="dhl">Super Bowl LX: Seahawks 29, Patriots 13</div>
      <div class="ddeck">Kenneth Walker III was named Super Bowl MVP as Seattle dominated New England 29-13 to claim the Lombardi Trophy.</div>
    </div>
    <div class="article"><div class="art-hdr" onclick="tog(this)"><div><div class="art-score">Seahawks 29 — Patriots 13</div><div class="art-teams">Super Bowl LX · Final</div></div><span class="chev">▼</span></div><div class="art-body">Seattle Seahawks won Super Bowl LX 29-13 over the New England Patriots. Kenneth Walker III rushed for 135 yards and was named MVP — the first RB to win Super Bowl MVP since Terrell Davis in 1998. Kicker Jason Myers set a Super Bowl record with 5 field goals. Seattle's defense sacked Drake Maye 6 times.</div></div>
    <div class="article"><div class="art-hdr" onclick="tog(this)"><div><div class="art-score">2025 Season Awards</div><div class="art-teams">AP NFL Awards</div></div><span class="chev">▼</span></div><div class="art-body">MVP: Josh Allen (Buffalo Bills). Super Bowl MVP: Kenneth Walker III (135 rush yds). Defensive POY: Myles Garrett. Coach of the Year: Mike Macdonald (Seattle).</div></div>
  </div>
</div>
"""
    nfl_sidebar = (
        '<div class="sidebar-card"><div class="sc-title">🏈 Final Records</div>' + sidebar_rows(all_t) + '</div>'
        '<div class="sidebar-card"><div class="sc-title">🏆 Super Bowl LX</div>'
        '<div class="sc-row"><span class="sc-team">Seahawks</span><span class="sc-val">29</span></div>'
        '<div class="sc-row"><span class="sc-team">Patriots</span><span class="sc-val">13</span></div>'
        '<div class="sc-row"><span class="sc-team">SB MVP</span><span class="sc-val">K. Walker III</span></div>'
        '<div class="sc-row"><span class="sc-team">AP MVP</span><span class="sc-val">M. Stafford</span></div>'
        '</div>'
        '<div class="sidebar-card"><div class="sc-title">📅 2026 NFL Draft</div>'
        '<div class="sc-row"><span class="sc-team">Date</span><span class="sc-val">April 23-25</span></div>'
        '<div class="sc-row"><span class="sc-team">Location</span><span class="sc-val">Green Bay</span></div>'
        '</div>'
        '<div class="sidebar-card"><div class="sc-title">🗓️ 2026 Season</div>'
        '<div class="sc-row"><span class="sc-team">Kickoff</span><span class="sc-val">September 2026</span></div>'
        '<div class="sc-row"><span class="sc-team">Super Bowl LXI</span><span class="sc-val">Feb 2027</span></div>'
        '</div>'
    )
    nfl_stories = storyline_articles([
        ("Seattle's Championship Run", "Kenneth Walker III rushed for 135 yards and was named Super Bowl LX MVP as the Seattle Seahawks dominated the New England Patriots 29-13. Mike Macdonald's defense was suffocating all season — Drake Maye was sacked six times in the biggest game of his young career."),
        ("Stafford Wins AP MVP", "Matthew Stafford won the 2025 AP NFL MVP award, throwing for 46 touchdowns in arguably the greatest season of his career. The Rams' offense under Stafford and Sean McVay was the most efficient in the NFL all year."),
        ("Drake Maye's Rise", "Despite the Super Bowl loss, Drake Maye's emergence as New England's franchise QB was the feel-good story of the season. The Patriots got back to the Super Bowl faster than anyone expected — Maye's ceiling is sky-high heading into 2026."),
        ("The Josh Allen Question", "Josh Allen won the AP MVP in 2025 before this season started — his regular season dominance is unquestioned. But Allen and the Bills still haven't broken through in the playoffs, and that narrative will define his legacy heading into 2026."),
    ])
    pages += magazine_page_html("NFL", today, rnks, nfl_sidebar, nfl_stories)
    init = f"const EAST={ej};const WEST={wj};renderStandings(EAST,'east-body');renderStandings(WEST,'west-body');"
    html = page_shell("NFL","#f97316","#ea6c0a","rgba(249,115,22,0.10)",today,tabs,pages)
    html = html.replace("</script>", init+"</script>")
    save("nfl.html", html)


def generate_hub_html():
    log("🌐 Generating index.html...")
    today = datetime.now().strftime("%B %-d, %Y")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>THE FIELD - Sports Analytics Hub</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Barlow+Condensed:wght@400;600;700;800;900&family=Barlow:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
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
.sport-card.nba:hover{{border-color:rgba(200,16,46,0.6);}}.sport-card.mlb:hover{{border-color:rgba(34,197,94,0.4);}}.sport-card.nhl:hover{{border-color:rgba(74,179,255,0.5);}}.sport-card.nfl:hover{{border-color:rgba(249,115,22,0.6);}}
.card-bg{{position:absolute;inset:0;opacity:0;transition:opacity 0.25s ease;}}
.sport-card.nba .card-bg{{background:linear-gradient(135deg,rgba(200,16,46,0.12),transparent);}}.sport-card.mlb .card-bg{{background:linear-gradient(135deg,rgba(34,197,94,0.10),transparent);}}.sport-card.nhl .card-bg{{background:linear-gradient(135deg,rgba(74,179,255,0.12),transparent);}}.sport-card.nfl .card-bg{{background:linear-gradient(135deg,rgba(249,115,22,0.12),transparent);}}
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
.dot-live{{background:#4ade80;box-shadow:0 0 6px #4ade80;animation:pulse 2s infinite;}}.dot-spring{{background:#e8c840;}}.dot-off{{background:var(--gray);}}
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
  <p class="hero-sub"><strong>Standings. Recaps. Props. Rankings.</strong><br>Four sports, one place. Updated every night automatically.</p>
  <div class="sports-grid">
    <a class="sport-card nba" href="nba.html"><div class="card-bg"></div><div class="card-inner">
      <div class="status-row"><div class="status-dot dot-live"></div><div class="status-text">Season In Progress</div></div>
      <div class="card-sport-logo" style="color:#c8102e">NBA</div>
      <div class="card-name">Basketball</div><div class="card-fullname">National Basketball Association</div>
      <div class="card-features"><span class="card-feat">Standings</span><span class="card-feat">Tonight</span><span class="card-feat">Digest</span><span class="card-feat">Props</span><span class="card-feat">Rankings</span></div>
      <div class="card-cta">Open NBA <div class="card-arrow">→</div></div>
    </div></a>
    <a class="sport-card mlb" href="mlb.html"><div class="card-bg"></div><div class="card-inner">
      <div class="status-row"><div class="status-dot dot-spring"></div><div class="status-text">Spring Training</div></div>
      <div class="card-sport-logo" style="color:#22c55e">MLB</div>
      <div class="card-name">Baseball</div><div class="card-fullname">Major League Baseball</div>
      <div class="card-features"><span class="card-feat">Standings</span><span class="card-feat">Tonight</span><span class="card-feat">Digest</span><span class="card-feat">Props</span><span class="card-feat">Rankings</span></div>
      <div class="card-cta">Open MLB <div class="card-arrow">→</div></div>
    </div></a>
    <a class="sport-card nhl" href="nhl.html"><div class="card-bg"></div><div class="card-inner">
      <div class="status-row"><div class="status-dot dot-live"></div><div class="status-text">Season In Progress</div></div>
      <div class="card-sport-logo" style="color:#4ab3ff">NHL</div>
      <div class="card-name">Hockey</div><div class="card-fullname">National Hockey League</div>
      <div class="card-features"><span class="card-feat">Standings</span><span class="card-feat">Tonight</span><span class="card-feat">Digest</span><span class="card-feat">Props</span><span class="card-feat">Rankings</span></div>
      <div class="card-cta">Open NHL <div class="card-arrow">→</div></div>
    </div></a>
    <a class="sport-card nfl" href="nfl.html"><div class="card-bg"></div><div class="card-inner">
      <div class="status-row"><div class="status-dot dot-off"></div><div class="status-text">Offseason · 2025 Final</div></div>
      <div class="card-sport-logo" style="color:#f97316">NFL</div>
      <div class="card-name">Football</div><div class="card-fullname">National Football League</div>
      <div class="card-features"><span class="card-feat">Final Standings</span><span class="card-feat">Recap</span><span class="card-feat">Power Rankings</span><span class="card-feat">Draft Preview</span></div>
      <div class="card-cta">Open NFL <div class="card-arrow">→</div></div>
    </div></a>
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
    save("index.html", html)


def main():
    log("=" * 55)
    log("🏟️   THE FIELD — MULTI-SPORT AUTO UPDATER")
    log("=" * 55)

    log("\n[1/4] NBA")
    nba_east, nba_west = fetch_nba_standings()
    nba_today     = fetch_games("basketball", "nba")
    nba_yesterday = fetch_yesterday("basketball", "nba")
    generate_nba_html(nba_east, nba_west, nba_yesterday, nba_today)

    log("\n[2/4] NHL")
    nhl_east, nhl_west = fetch_nhl_standings()
    nhl_today     = fetch_games("hockey", "nhl")
    nhl_yesterday = fetch_yesterday("hockey", "nhl")
    generate_nhl_html(nhl_east, nhl_west, nhl_yesterday, nhl_today)

    log("\n[3/4] MLB")
    mlb_al, mlb_nl = fetch_mlb_standings()
    mlb_today     = fetch_games("baseball", "mlb")
    mlb_yesterday = fetch_yesterday("baseball", "mlb")
    generate_mlb_html(mlb_al, mlb_nl, mlb_yesterday, mlb_today)

    log("\n[4/4] NFL")
    nfl_afc, nfl_nfc = fetch_nfl_standings()
    generate_nfl_html(nfl_afc, nfl_nfc)

    log("\n[5/5] Hub")
    generate_hub_html()

    log("\n" + "=" * 55)
    log("🎉  All done! 5 files updated in:")
    log(f"    {BASE_DIR}/")
    log("=" * 55)

if __name__ == "__main__":
    main()
