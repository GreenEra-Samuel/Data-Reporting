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
| **Your files** | A file browser built into the app. Add a photo, a meter printout or a calibration certificate to a run and MeasureLog keeps its own copy, so the paperwork travels with the readings. |
| **Importing** | Already have the numbers in a spreadsheet? Read a CSV or Excel file straight into a run. It works out which column is which, and shows you every row it understood — and every row it did not — before anything is written. |
| **Tidying up** | Ctrl-click or Shift-click to select several tests, locations or runs, then Delete. Anything holding readings can be hidden instead of deleted, so your records stay intact. |
| **Live statistics** | Mean, standard deviation and %RSD appear as you type, per test, per location. |
| **Range checks** | Readings outside a test's acceptable range turn red immediately — not after you export. |
| **Spread check** | If your replicates disagree more than a threshold you set, the row says *Check spread*. Tests can carry their own limit — pH uses the 2% RSD its SOP requires — and anything without one falls back to the app-wide setting. |
| **Exports** | Excel workbook or CSV, for any date range. |
| **Your data** | One file you can copy, back up, or keep on a shared drive. |

---

## The first few minutes

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

5. **Files tab** — browse your computer without leaving the app, then either
   **Add to this run** or **Import readings**. See [Files and imports](#files-and-imports).

6. **Export tab** — pick a date range and write an Excel workbook or CSV files.

### Tidying up

On the **Setup** and **Runs** lists, Ctrl-click or Shift-click picks several rows
at once (Ctrl+A selects all), and **Delete** removes them together.

Nothing disappears silently. Deleting tests or locations that already hold
readings offers to hide them from the entry screen instead — they stop cluttering
your grid but their measurements stay in the exports. The confirmation always
says how many readings are at stake before you commit.

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
| `Ctrl+A`, `Delete` | In the Setup, Runs and Files lists: select all, delete the selection |
| `Backspace` | In the file browser: up to the folder above |

---

## Files and imports

The **Files tab** is the app's own file explorer — shortcuts to Desktop,
Documents, Downloads and any USB stick down the side, a folder you can type or
click your way into, and every file labelled in plain words (*Excel workbook*,
*JPEG image*, *PDF document*) rather than by its extension. CSV and Excel files
are shown in green, because those are the ones readings can be read out of.

Pick a file — or several, with Ctrl-click — and you have two choices.

### Add to this run

MeasureLog copies the file into `Documents\MeasureLog\files` and lists it
against the run. It is a copy, not a shortcut, so moving, renaming or deleting
the original later leaves your record intact, and a data folder handed to
somebody else brings every document with it.

Each file can carry a line saying what it is — *"calibration certificate"*,
*"meter printout"* — and the list will **Open** it, **Save a copy** somewhere
else, or **Remove** it. Removing deletes MeasureLog's copy and nothing else;
your original is never touched. The **Entry** tab shows how many files a run
carries, and the **Runs** list has a Files column.

### Import readings

Point it at a CSV or Excel file and MeasureLog reads the measurements into the
run. Two shapes of file are understood, and it works out which one it is looking
at:

| Shape | Looks like |
|---|---|
| **One row per reading** | Columns for the location, the test and the value — plus replicate and note if you have them |
| **A grid** | Tests down one side, locations across the top — the layout of the Review tab, of the app's own exports, and of most hand-kept spreadsheets |

Names do not have to match exactly: `Total Solids`, `total solids`, `TotalSolids`
and `Total Solids (%)` all find the same test, and test codes work too. Numbers
written `2,450` or `1.234,5` are read the way you meant them.

Nothing is written until you have seen what it understood. The dialog shows
every row with what will happen to it, and puts the rows it could not use at the
top with the reason — *no test called "Unobtainium"*, *"abc" is not a number*,
*that is a limit rather than a reading*. Fix the column choices if the guess was
wrong, then import.

Two choices worth knowing about:

- **Replace readings already recorded in this run** is off by default, so an
  import fills the empty cells and leaves anything you have already typed alone.
- **Keep a copy of this file with the run** is on by default, so the spreadsheet
  the numbers came from is filed against the run as well.

Since the app's own exports are ordinary CSV files, anything MeasureLog writes
out it can read back in — useful for moving a day's readings between computers.

---

## Where your measurements live

Every reading sits in one SQLite file, with the files you have added beside it:

```
C:\Users\<you>\Documents\MeasureLog\measurelog.db
C:\Users\<you>\Documents\MeasureLog\files\
```

The **Export tab** shows the exact path, opens the folder, and can back it up on
demand. The app also keeps a dated backup automatically, once a day, in
`Documents\MeasureLog\backups` (the last 15 are kept).

**Moving to another computer:** copy `measurelog.db` to the same folder there —
and the `files` folder with it, if you have added any.

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

## The app icon

The icon is the Green Era Campus mark with **LAB** underneath, drawn by
`packaging/make_icon.py` and committed as `icon.ico` (embedded in the .exe) and
`icon.png` (used for the window itself). Detail is added as the icon grows,
because a 16-pixel icon carrying three lines of text is just a smudge:

| Size | Shows |
|---|---|
| 16, 24 px | the cream tile and the green mark, filling the tile |
| 32, 48, 64 px | the mark with LAB underneath |
| 128 px and up | plus the GREEN / ERA / CAMPUS wordmark inside the mark |

To change it, edit the constants at the top of that script — the brand colours,
the wording (`STRAPLINE = "LAB"`, swap for `"TESTING"`), or the geometry — then:

```bash
pip install pillow
python packaging/make_icon.py --preview
```

`--preview` also writes `icon-preview.png`, every size side by side, so you can
check the result before committing. The colours there were matched by eye from
the supplied logo; if you have the exact brand values, put them in `GREEN` and
`CREAM` and re-run.

The wordmark is set in Montserrat Bold, under the SIL Open Font License — the
licence travels with the font in `packaging/fonts/`.

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
a build can store, summarise, export, import and file away data (this is what CI
runs against the finished `.exe`).

### Tests

```bash
python -m unittest discover -s tests -v        # Windows / macOS
xvfb-run -a python -m unittest discover -s tests -v   # headless Linux
```

The interface tests drive the real widgets — typing into cells, navigating,
switching locations and tabs, walking the file browser through folders and
importing a spreadsheet — and skip themselves when there is no display.

### Layout

```
main.py                   entry point; also --selftest and --version
measurelog/
  catalog.py              the test library taken from the laboratory SOPs
  config.py               where the data folder is, and daily backups
  db.py                   SQLite schema, migrations, and every read and write
  models.py               Location, Test, Run, Cell, Attachment
  stats.py                mean, SD, %RSD, range checks, spread check
  exporters.py            CSV and Excel writers
  importers.py            reading measurements back out of CSV and Excel
  files.py                copying added files into the data folder, and naming types
  ui/
    app.py                main window, menus, shortcuts, event bus
    entry_tab.py          the data entry grid
    runs_tab.py           browse and edit past runs
    review_tab.py         one run as a tests-by-locations matrix
    files_tab.py          add files to a run, and import readings
    browser.py            the file explorer built into the app
    import_dialog.py      column matching and the preview before an import
    export_tab.py         exports, backups, data file location
    setup_tab.py          locations, tests and preferences
    dialogs.py            add/edit dialogs
    widgets.py            scrolling frame, number entry, tooltips
    theme.py              colours and ttk styling
packaging/
  make_icon.py            draws the app icon from the Green Era Campus mark
  icon.ico / icon.png     the committed icon, embedded in the .exe
  fonts/                  Montserrat Bold (SIL OFL), used to set the icon
  MeasureLog.spec         PyInstaller recipe
  build_windows.bat       one-click local build
tests/                    unit tests and interface tests
```
