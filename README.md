# THE FIELD — Sports Analytics Hub

Automatically updated sports analytics site covering NBA, NHL, MLB, and NFL.  
Live at: **https://thefieldsports.netlify.app/**

---

## What it does

Every night at 11:05 PM CT, a GitHub Actions workflow:
1. Fetches live standings + scores from the ESPN public API
2. Regenerates all 5 HTML files (`index.html`, `nba.html`, `nhl.html`, `mlb.html`, `nfl.html`)
3. Commits and pushes them to this repo
4. Netlify detects the push and redeploys automatically (if connected)

---

## Setup — New Repo + Netlify

### 1. Create the GitHub repo

```bash
# On your Mac terminal
cd ~/Desktop/ALLSPORTS
git init
git add .
git commit -m "Initial commit"
# Create a NEW repo at github.com/new (e.g. wilrich18/thefield)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

### 2. Connect Netlify to GitHub

1. Go to [netlify.com](https://netlify.com) → **Add new site** → **Import from Git**
2. Choose GitHub → select your new repo
3. Build command: *(leave blank)*
4. Publish directory: *(leave blank / use `.`)*
5. Click **Deploy**

Netlify will now auto-redeploy every time GitHub Actions pushes new HTML.

### 3. Enable GitHub Actions

The workflow file is already included at `.github/workflows/nightly.yml`.  
Once the repo is on GitHub, it will run automatically at 11:05 PM CT every night.

To trigger it manually: **GitHub repo → Actions → Nightly Sports Update → Run workflow**

---

## Run locally

```bash
pip3 install requests
python3 the_field_updater.py
```

Files are saved to `~/Desktop/ALLSPORTS/`.

## Schedule locally (macOS only)

```bash
python3 the_field_updater.py --schedule
```

This installs a LaunchAgent that runs the updater at 11:00 PM every night.

---

## File structure

```
├── the_field_updater.py        # Main script — generates all HTML
├── index.html                  # Hub page (auto-generated)
├── nba.html                    # NBA page (auto-generated)
├── nhl.html                    # NHL page (auto-generated)
├── mlb.html                    # MLB page (auto-generated)
├── nfl.html                    # NFL page (auto-generated)
├── .github/
│   └── workflows/
│       └── nightly.yml         # GitHub Actions nightly schedule
└── README.md
```

---

*Data via ESPN public API. For entertainment purposes only.*
