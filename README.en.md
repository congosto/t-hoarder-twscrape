<p align="center">
  <img src="logo_t-hoarder.png" alt="t-hoarder-twscrape" width="90">
</p>

<h1 align="center">t-hoarder-twscrape</h1>

<p align="center">
  A <a href="https://streamlit.io">Streamlit</a> app to collect, explore and
  analyze Twitter/X data with <a href="https://github.com/vladkens/twscrape">twscrape</a>.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: GPL-3.0" src="https://img.shields.io/badge/License-GPLv3-blue.svg"></a>
</p>

<p align="center">
  <a href="README.md">Español</a> · <b>English</b>
</p>

---

## What it is

**t-hoarder-twscrape** is a graphical interface to download tweets and Twitter/X
profiles through [twscrape](https://github.com/vladkens/twscrape) and work with
that data without leaving the app: organize it into projects, explore it in an
interactive dashboard, generate activity charts and build retweet/mention graphs
with community detection.

It is the evolution of the **t-hoarder** family of tools, adapted to scraping
with twscrape.

## Features

The app is organized into sections (top bar):

✅ **Project** — create and select the working project; each project groups its datasets.  
✅ **Download** — downloads with twscrape: historical search (*Search*), user timeline (*User TL*), retweets and replies of a dataset.  
✅ **Dashboard** — interactive dashboard (self-contained HTML) to explore a dataset: KPIs, posting rhythm, metrics heatmap and a filterable table.  
✅ **Tools** — *Merge datasets* (join and deduplicate) and *Clean dataset* (cleanup by language/criteria), with an append-only context log that preserves history.  
✅ **Graphs** — community detection, graph generation (GDF/GEXF), tweet classification by community and an interactive viewer with ForceAtlas2 running in the browser.  
✅ **Charts** — analysis charts for tweets and for user profiles.  
✅ **Settings** — twscrape account management (add, active, delete).

## Requirements

- **Python 3.11+** (developed on 3.13).
- One or more **Twitter/X accounts** so that twscrape can authenticate.

## Installation

This guide is written so that anyone can follow it, without assuming any
familiarity with the terminal. There are four steps: install Python, download the
app, install its dependencies and run it.

### Step 1 · Install Python

The app works with **Python 3.11 or higher**.

1. Go to [python.org/downloads](https://www.python.org/downloads/) and download the installer for your system.
2. Run the installer.
3. **⚠️ Very important (Windows):** on the installer's first screen, tick the **"Add python.exe to PATH"** checkbox before clicking "Install Now". If you don't, the commands below won't work.
4. Finish the installation.

To check it was installed correctly, open a terminal (see Step 3) and type:

```bash
python --version
```

It should reply something like `Python 3.13.x`. (On macOS/Linux you may need to
type `python3` instead of `python`.)

### Step 2 · Download the app

You have two options. If you don't use git, choose **Option A**.

**Option A · Download the ZIP (the easiest, no git)**

1. Open the [project page on GitHub](https://github.com/congosto/t-hoarder-twscrape).
2. Click the green **" Code "** button and then **" Download ZIP "**.
3. Unzip the `.zip` file wherever you want to keep it. A folder named something like `t-hoarder-twscrape-main` will be created.

> **⚠️ Important — where to place the folder:** choose a path whose folders
> **do not contain spaces, accents or special characters** (`ñ`, `á`, `#`,
> `&`…). Paths with those characters cause problems when running the app. For
> example, avoid `C:\Users\José Ramón\Desktop\...` and use something like
> `C:\apps\t-hoarder-twscrape`.

**Option B · Clone with git** (if you already use git)

```bash
git clone https://github.com/congosto/t-hoarder-twscrape.git
```

### Step 3 · Open a terminal inside the app folder

You need to open a terminal **located in the folder** you just downloaded (the
one containing the `app` and `scripts` folders).

- **Windows:** open that folder in File Explorer, click the address bar (at the top), type `powershell` and press Enter. A terminal will open already placed in that folder.
- **macOS:** open the **Terminal** app, type `cd ` (with a trailing space) and drag the folder onto the Terminal window; press Enter.
- **Linux:** right-click inside the folder and choose "Open a terminal here" (or use `cd` to reach the folder).

### Step 4 · Install the dependencies

In the same terminal from Step 3, copy and paste this command:

```bash
pip install -r app/requirements.txt
```

This downloads and installs the libraries the app needs (Streamlit, pandas,
matplotlib, twscrape…). It takes a while the first time; you only need to do it
once. They are common libraries, so they won't interfere with other programs.

> The NLTK stopwords (used in the word clouds) are downloaded automatically the
> first time those charts are generated.

## Running

In the terminal (located in the app folder, Step 3), start the app:

```bash
streamlit run app/app.py
```

It will open by itself in your browser (if not, go to `http://localhost:8501`).
To **stop** the app, go back to the terminal and press `Ctrl + C`.

Whenever you want to use it again, just repeat this last step: open the terminal
in the app folder (Step 3) and run `streamlit run app/app.py`.

> **Windows shortcut:** the repository includes `restart_app.ps1`, which closes
> any previous instance and starts the app. Right-click it → "Run with
> PowerShell".

### Create a shortcut with an icon (optional)

To avoid opening the terminal every time, you can create a shortcut with the
t-hoarder icon and start the app with a double click.

**Windows**

1. Right-click on the Desktop (or wherever you want) → **New → Shortcut**.
2. In "Type the location of the item", paste the following, replacing `PATH` with the real path of your folder:
   ```
   powershell.exe -ExecutionPolicy Bypass -File "PATH\restart_app.ps1"
   ```
3. Give it a name (for example `t-hoarder-twscrape`) and click "Finish".
4. Right-click the shortcut → **Properties** → **"Change Icon…"** button → **"Browse…"** → select the **`t-hoarder.ico`** file from the app folder → OK.

**macOS**

1. In the app folder, create a text file named `t-hoarder.command` with this content:
   ```bash
   #!/bin/bash
   cd "$(dirname "$0")"
   streamlit run app/app.py
   ```
2. Make it executable: open Terminal in the folder and run
   `chmod +x t-hoarder.command`. You can now start the app by double-clicking it.
3. For the icon: select `t-hoarder.command`, press **Cmd + I** (Get Info), open `logo_t-hoarder.png` in Preview, copy it (**Cmd + C**) and paste it (**Cmd + V**) onto the small icon at the top-left of the Info window.

**Linux**

1. In the app folder, create a file `t-hoarder.desktop` with this content, replacing `PATH` with the real path of your folder:
   ```ini
   [Desktop Entry]
   Type=Application
   Name=t-hoarder-twscrape
   Exec=bash -c "cd 'PATH' && streamlit run app/app.py"
   Icon=PATH/logo_t-hoarder.png
   Terminal=true
   ```
2. Mark it as executable (right-click → Properties → Permissions → "Allow executing file as program", or `chmod +x t-hoarder.desktop`). Depending on your desktop environment, you may have to confirm "Trust and Launch" the first time.

## Account setup

twscrape needs at least one **authenticated account with cookies** to be able to
download data. If you add more accounts, it will rotate between them to spread the
request quota. Recommendations:

- A **pool of 5 accounts or more**.
- **Don't use your personal account**, in case Twitter/X ever blocks it.
- It's better if the accounts have **some age and activity**.

### How to get an account's cookies

1. Open **Chrome** and sign in to [https://x.com](https://x.com) with the account you're going to add.
2. Press **F12** (Developer Tools) → **Application** tab → **Cookies** → `https://x.com`.
3. Copy the values of **`auth_token`** and **`ct0`**.

### Adding the account

In **Settings → New Account**, fill in:

- **Username** — the account's username
- **Password** — the account's password
- **Email** — email associated with the account
- **Email Password** — password of that email
- **Auth Token** — the `auth_token` cookie obtained above
- **ct0** — the `ct0` cookie obtained above

## Repository layout

```
app/          Streamlit app (app.py, requirements.txt)
scripts/      Scraping and logic modules (accounts, download, scraping,
              projects, context, graphs, charts, dashboard, utils…)
logo_t-hoarder.png / t-hoarder.ico   App branding
```

The collected data (`data/`), the twscrape credentials (`accounts.db`) and the
internal development notes are not part of the repository.

## Acknowledgements

- [**vladkens**](https://github.com/vladkens) for the [twscrape](https://github.com/vladkens/twscrape) library.
- **Agustín Nieto** ([@agusnieto77](https://github.com/agusnieto77)) for the [twscraper](https://github.com/agusnieto77/twscraper) library, which served as a basis for using twscrape.

## License

Distributed under the **GNU General Public License v3.0**. See [LICENSE](LICENSE).

Copyright (C) 2026 María Luz Congosto ([@congosto](https://github.com/congosto)).

> **Responsible use:** this tool scrapes Twitter/X, which may go against the
> platform's terms of service. Use it responsibly, for research and analysis, and
> at your own risk.
