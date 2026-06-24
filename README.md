# Zoom Toolkit

A bilingual (English / العربية) desktop app for managing audio recordings pulled off Zoom field recorders. It extracts files from SD-card folder structures, cleans out accidental short clips, and organizes recordings into date-based folders — with a dark "Field Console" interface and a live level-meter progress indicator.

![Zoom Toolkit](app_icon.ico)

## Features

- **Audio Extractor** — pulls `.wav`/`.mp3` (and more) out of nested sub-folders (e.g. Zoom `FOLDER01` SD-card layouts) into one directory, renaming to avoid overwrites, with optional auto-sort by date.
- **Audio Cleaner** — moves exceptionally short clips (misclicks) into a `short_audio/` folder, with a configurable duration threshold.
- **Auto-Sorter** — organizes a messy folder of recordings into clean date-based sub-folders.
- **Bilingual + RTL** — full English and Arabic UI, with Gregorian and **Hijri** calendar support.
- **Safe by design** — dry-run preview, a plan summary before sorting, stop/cancel mid-run, and an automatic per-run log saved to the output folder.
- **Quality of life** — drag-and-drop folders, remembered settings, configurable file types, recursive scanning, and an "open output folder" shortcut.

## Requirements

- Python 3.10+
- See [`requirements.txt`](requirements.txt):
  - `customtkinter==5.2.2`, `mutagen`, `arabic-reshaper`, `python-bidi`, `hijridate`, `tkinterdnd2`

## Running from source

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python zoom_extractor.py
```

## Building the Windows executable

```bash
pip install pyinstaller
pyinstaller "Zoom Toolkit.spec" --noconfirm --clean
```

The standalone `Zoom Toolkit.exe` is produced in `dist/`. The spec bundles the app icon and the native `tkinterdnd2` drag-and-drop binaries.

## Settings

Preferences (language, last-used folders, file types, threshold, calendar/format, sort options) are stored in:

```
%APPDATA%\ZoomToolkit\config.json
```

Delete that file to reset to defaults.

## License

See [LICENSE](LICENSE).
