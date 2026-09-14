# MeasureLog

A Windows desktop app for logging measurements you repeat: several **tests**, at
several **locations**, in **replicates**, several times a day.

It ships as one file — `MeasureLog.exe`. Copy it to any Windows 10 or 11
computer and double-click. No Python, no installer, no admin rights.

---

## Get the app

**[Download the latest MeasureLog.exe from the Releases page](../../releases/latest)**

Once a release exists, this link always points at the newest build:

```
https://github.com/GreenEra-Samuel/Data-Reporting/releases/latest/download/MeasureLog.exe
```

The first time you open a freshly downloaded program, Windows may show a blue
*"Windows protected your PC"* box. Click **More info** → **Run anyway**. That
appears because the file is new and not commercially code-signed, not because
anything is wrong with it. A SHA256 checksum is published alongside each build.

No release yet? See [Building the .exe](#building-the-exe) — it is one push of a
git tag, or one double-click on Windows.

---

## What it does

| | |
|---|---|
| **Locations** | As many as you need; six is the usual case. Reorder them into the order you actually walk your round. |
| **SOP library** | The 14 tests from the laboratory SOPs are built in. Tick the ones you run and they arrive complete with units, replicate counts, QC limits and method notes. |
| **Tests** | Up to 20 or well beyond. Each has its own unit, decimal places, replicate count and acceptable range. Anything not in the SOPs is added by hand. |
| **Replicates** | Per test, so triplicate pH can sit next to a single-reading temperature. |
| **Runs** | One round of measurements. Repeat a round with one click and the app numbers them Round 1, Round 2, … through the day. |
| **Live statistics** | Mean, standard deviation and %RSD appear as you type, per test, per location. |
| **Range checks** | Readings outside a test's acceptable range turn red immediately — not after you export. |
| **Spread check** | If your replicates disagree more than a threshold you set, the row says *Check spread*. Tests can carry their own limit — pH uses the 2% RSD its SOP requires — and anything without one falls back to the app-wide setting. |
| **Exports** | Excel workbook or CSV, for any date range. |
| **Your data** | One file you can copy, back up, or keep on a shared drive. |

---

## The first five minutes

1. **Setup tab** — click **Add from SOP library**, tick the tests you run, and
   they are added with their units, replicate counts, QC limits and method
   notes already filled in. Anything not in the SOPs goes in through **New
   test**. Everything stays editable afterwards.

   The sampling points from the SOPs — Influent, Digester 1, Digester 2,
   Effluent — are listed for you; rename them or add more to match your round.
   Do this once.

2. **Entry tab** — click **New run**, then start typing.
   - Pick a location from the buttons along the top.
   - Type a reading, press **Enter** to drop to the next test, **Tab** to move
     across to the next replicate.
   - Mean, SD and %RSD fill in as you go. Out-of-range readings turn red.
   - **Ctrl+1 … Ctrl+6** jump between locations.
   - Every value saves the moment you leave the cell. There is no save button
     to forget.

3. **Next round** — click **Repeat run**. You get a fresh empty grid with the
   same operator and notes, labelled as the next round of the day.

4. **Review tab** — the whole run as a tests-by-locations grid. Switch between
   mean, mean ± SD, %RSD, range, or how many replicates are done. **Copy table**
   puts it on the clipboard ready to paste into Excel.

5. **Export tab** — pick a date range and write an Excel workbook or CSV files.

### Keyboard

| Key | Does |
|---|---|
| `Enter` / `↓` | Next test, same replicate column |
| `Shift+Enter` / `↑` | Previous test |
| `Tab` | Next replicate across the row |
| `Esc` | Undo the cell you are editing |
| `Ctrl+1` … `Ctrl+9` | Jump to that location |
| `Ctrl+N` | New run |
| `F1` | Quick start |
| Right-click a cell | Add a note, clear the cell, clear the row |

---

## Where your measurements live

Everything sits in one SQLite file:

```
C:\Users\<you>\Documents\MeasureLog\measurelog.db
```

The **Export tab** shows the exact path, opens the folder, and can back it up on
demand. The app also keeps a dated backup automatically, once a day, in
`Documents\MeasureLog\backups` (the last 15 are kept).

**Moving to another computer:** copy `measurelog.db` to the same folder there.

**A shared drive, so a team sees the same records:** put `datadir.txt` next to
`MeasureLog.exe` containing the folder path, for example:

```
\\fileserver\lab\measurelog
```

**From a USB stick:** put an empty file called `portable.flag` next to
`MeasureLog.exe`. Data then lives in a `MeasureLog-Data` folder beside the
program, and travels with the stick.

An `MEASURELOG_DATA_DIR` environment variable overrides all of the above.

---

## What the exports contain

| Export | Shape | Good for |
|---|---|---|
| **Excel workbook** | Four sheets: every reading, the statistics, one row per location, and your setup | Sharing the whole picture |
| **Every reading (CSV)** | One row per replicate, including notes and range checks | The full record, archiving |
| **Statistics (CSV)** | One row per run/location/test: n, mean, SD, %RSD, min, max, range, status | Reporting |
| **One row per location (CSV)** | Mean of each test across the columns | Charting and pivot tables |

Numbers export as numbers, not text, and blanks stay blank rather than becoming
zeros — so averages downstream stay honest.

---

## Building the .exe

### Option A — let GitHub build it (nothing to install)

Push a version tag and the workflow builds, tests and publishes the program to
the Releases page:

```bash
git tag v1.0.0
git push origin v1.0.0
```

A few minutes later, `MeasureLog.exe` is on the Releases page with a permanent
download link.

You can also cut a release without touching git: go to **Actions → Build
Windows app → Run workflow**, and type the tag (for example `v1.0.0`) in the
*Publish a release under this tag* box. The workflow creates the tag at the
commit it builds and publishes the release itself.

Every ordinary push builds the program too and attaches it to the workflow run
under **Actions → the run → Artifacts**, which is handy for testing before you
release.

### Option B — build on your own Windows machine

With [Python 3.9+](https://www.python.org/downloads/windows/) installed
("Add python.exe to PATH" ticked), double-click:

```
packaging\build_windows.bat
```

It installs what it needs, runs the tests, builds `dist\MeasureLog.exe` and
self-tests the result. On macOS or Linux the same recipe builds a native app:

```bash
pip install -r requirements-build.txt
pyinstaller packaging/MeasureLog.spec --noconfirm --clean
```

---

## Upgrading

Replace the old `MeasureLog.exe` with the new one. Your measurements are in a
separate file, so nothing is lost: the app upgrades the data file in place the
first time it opens it, keeping every reading already recorded.

## Running from source

```bash
pip install -r requirements.txt   # only needed for Excel export
python main.py
```

Useful flags: `--version`, `--data-dir DIR`, and `--selftest`, which checks that
a build can store, summarise and export data (this is what CI runs against the
finished `.exe`).

### Tests

```bash
python -m unittest discover -s tests -v        # Windows / macOS
xvfb-run -a python -m unittest discover -s tests -v   # headless Linux
```

The interface tests drive the real widgets — typing into cells, navigating,
switching locations and tabs — and skip themselves when there is no display.

### Layout

```
main.py                   entry point; also --selftest and --version
measurelog/
  catalog.py              the test library taken from the laboratory SOPs
  config.py               where the data folder is, and daily backups
  db.py                   SQLite schema, migrations, and every read and write
  models.py               Location, Test, Run, Cell
  stats.py                mean, SD, %RSD, range checks, spread check
  exporters.py            CSV and Excel writers
  ui/
    app.py                main window, menus, shortcuts, event bus
    entry_tab.py          the data entry grid
    runs_tab.py           browse and edit past runs
    review_tab.py         one run as a tests-by-locations matrix
    export_tab.py         exports, backups, data file location
    setup_tab.py          locations, tests and preferences
    dialogs.py            add/edit dialogs
    widgets.py            scrolling frame, number entry, tooltips
    theme.py              colours and ttk styling
packaging/                PyInstaller spec, icon, Windows build script
tests/                    unit tests and interface tests
```
