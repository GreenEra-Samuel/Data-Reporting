MeasureLog {VERSION} for Windows.

**Download `MeasureLog.exe` below and double-click it.** There is nothing to
install — no Python, no setup program, no admin rights. Copy the file onto any
Windows 10 or 11 machine and it runs.

### First time you open it

Windows may show a blue *"Windows protected your PC"* box. Click **More info**,
then **Run anyway**. That warning appears because the file is newly built and
not commercially code-signed — not because anything is wrong with it. The
SHA256 checksum is attached if you want to confirm your download is intact.

### Where your data goes

Everything you enter is saved in a single file, with any files you have added to
a run kept beside it:

```
Documents\MeasureLog\measurelog.db
Documents\MeasureLog\files\
```

Copy those to move your records to another computer, or point the app at a
network drive so a team works from the same records, one person at a time.

**Keep it out of OneDrive, Google Drive and Dropbox.** Sync clients copy the
whole database and ignore the locks the app relies on, so a synced folder can
end up corrupted. Exports are fine there - it is only the live database that
minds. The **Export** tab shows the exact path, warns you if it is somewhere
risky, and can back it up for you.
