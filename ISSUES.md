# Trackster2 — Issue Tracker & Fix Log

Goal: fix the app's bugs one by one and replace the scattered plain-text state files
(`failed_downloads.txt`, `mismatched_downloads.txt`, `synced.txt`, `synced_updated.txt`,
`downloaded.txt`, `song_names.txt`, `.env`) with a SQLite-managed database.

## Status key

- [ ] open (unresolved)
- [x] fixed

---

## Oversight: app capabilities (for reference)

1. **YouTube playlist** download → each video pulled as audio and converted to MP3.
2. **Spotify playlist / album / single-track** download → metadata fetched from Spotify API, audio pulled from YouTube (default) or JioSaavn (high-quality toggle).
3. **Apple Music playlist** download → parses `music:song` meta tags and downloads via the same engine.
4. **Search tab** → JioSaavn search for artists/albums, then async batch-download (aiohttp).
5. **High-quality audio** toggle → uses JioSaavn (DES-decrypted `_320.mp4` URLs) with artist/title fuzzy matching.
6. **"Download only failed songs"** toggle → only redownloads names recorded in the failure log.
7. **Metadata tagging** via mutagen: artist, album, title, year, track #, ISRC, lyrics + album art.
8. **Settings drawer** → Spotify Client ID/Secret.
9. **Folder picker** to choose output directory.
10. **Tab navigation / gesture switching** between YouTube, Spotify, Apple Music, Search.

---

## Issues

### Critical (crashes / freezes)

- [x] **#1 — `ThreadPoolExecutor` never imported.** `get_album_info()` used it but
      `concurrent.futures` was never imported → Spotify album downloads raised `NameError`.
      **Fixed:** added the import. Note: `main-mac.py` / `main copy.py` (which had it) were removed
      in #13, consolidating on `main.py`.
- [x] **#2 — `download_high_quality()` indexed a string.** Accessed `song['url']` before
      verifying `isinstance(song, dict)`. **Fixed:** dict check runs first.
- [x] **#3 — Blocking `input()` inside the GUI.** The Spotify downloader called `input(...)`
      → froze the app. **Fixed:** `song_names.txt` is dead (never written); now loaded silently.

### High

- [x] **#4 — Mixed return types.** `search_song()` returned a `dict` or `str`;
      `get_songs_from_artist()` returned a `list` or `str`. **Fixed:** `search_song()` returns
      `None` on failure (dict otherwise); `get_songs_from_artist()`/`get_songs_from_album()`
      return `[]` on failure. Callers updated. The "file already exists" case now returns the
      sentinel string `"File already exists."` and callers check it explicitly.
- [x] **#5 — `set_metadata` duplicates album-art tagging.** Identical `APIC` block ran twice.
      **Fixed:** single block saving with `v2_version=3`.
- [x] **#6 — Startup dummy loop.** `for i in range(101)` + sleeps burned ~10s at launch.
      **Fixed:** removed.
- [x] **#7 — `search.py main()` dead code.** Called `result.get('type')` on the new result shape.
      **Fixed:** demo rewritten to print topresult/artists/albums correctly.
- [x] **#8 — GUI download logic blocking.** Downloaders and the search-tab
      `asyncio.run()` ran on the Flet UI thread → progress froze. **Fixed:** all downloaders now
      run their heavy work via `page.run_thread()`; the search tab runs the aiohttp loop inside a
      worker thread.

### State management → SQLite (main goal)

- [x] **#9 — Replace scattered plain-text state files with a SQLite DB.**
      **Fixed:** new `db.py` creates `trackster.db` with `settings`, `downloaded_songs`,
      `failed_songs`, `mismatched_songs`, `synced_tracks` tables. All reads/writes previously
      hitting `failed_downloads.txt`, `mismatched_downloads.txt`, `synced.txt`,
      `synced_updated.txt`, `downloaded.txt`, `song_names.txt` now use the DB.
- [x] **#10 — `.env` written inside the app.** **Fixed:** settings now live in the `settings`
      table. `migrate_env()` imports existing `.env` credentials into the DB once; the settings
      drawer reads/writes the DB (`.env` is left untouched).

### Code cleanliness

- [x] **#11 — Massive duplicate imports.** **Fixed:** `main.py` now has one clean, non-starring
      import block.
- [x] **#12 — Mixed/global module state.** `music_folder_path`, `file_exists_action`.
      **Fixed:** moved into an `AppState` class (`state` singleton). Also dropped dead
      `progress_bar()` / `drop_down()` / unused globals.
- [x] **#13 — Redundant/extraneous files.** `main-mac.py` (no mac-specific code) and
      `main copy.py` (untracked backup) duplicated `main.py` and caused drift.
      **Fixed:** both removed; `main.py` is the single source of truth.

### Minor

- [x] **#14 — Album-art frames written twice / format.** **Fixed:** `set_metadata()` writes the
      `APIC` frame once with `v2_version=3`, matching `search.py`.
- [x] **#15 — No structured logging.** **Fixed:** added `logging` with `basicConfig` for
      warnings/errors; download progress is surfaced in the UI (text + progress bar) instead of
      only the console.

---

## New: `db.py` schema

```
trackster.db
├── settings           (key PK, value)
├── downloaded_songs   (id, title, file_path, source, downloaded_at)
├── failed_songs       (id, title UNIQUE, reason, failed_at)
├── mismatched_songs   (id, title, original_artist, downloaded_artist, created_at)
└── synced_tracks      (id, spotify_id UNIQUE, synced_at)
```

API: `init_db()`, `get_setting/set_setting`, `add_downloaded/is_downloaded/get_downloaded_titles`,
`add_failed/remove_failed/get_failed_titles/clear_failed`, `add_mismatch/get_mismatches`,
`add_synced/get_synced_ids`, `migrate_env()`.

---

## Fix log (most recent first)

- **#13** (repo) — deleted `main-mac.py` and `main copy.py`; `main.py` is the single script.
- **#9/#10/#11/#12/#14/#15** (main.py, search.py, new db.py) — consolidated imports into one
  block; moved global state into `AppState`; added `db.py` (SQLite) and replaced every read/write
  of the plain-text state files and `.env` with DB calls + one-time `.env` migration; unified
  `APIC` tagging; added structured `logging`.
- **#8** (main.py) — all downloaders (YouTube/Spotify/Apple) and the search-tab async downloader
  now run off the Flet UI thread via `page.run_thread()`, so progress bars update live.
- **#4** (main.py, search.py) — normalized return types (`None`/`[]` on failure) and handled the
  `"File already exists."` path to avoid dict-on-string access.
- **#7** (search.py) — rewrote the `main()` demo to use the actual `topresult/artists/albums`
  result shape.
- **#3** (main.py) — removed the blocking `input()` prompt; `song_names.txt` lists load silently.
- **#6** (main.py) — removed the ~10s startup sleep loop.
- **#5** (main.py) — `set_metadata()` now writes the album-art frame once.
- **#2** (main.py) — `download_high_quality()` checks `isinstance` before indexing.
- **#1** (main.py) — added missing `ThreadPoolExecutor` import.

## Remaining / notes

- Test suite lives in `tests/` (pytest). Run from the repo root:
  `python -m pytest`. It uses a temporary SQLite DB per test (isolated in conftest).
- The runtime deps were installed into a throwaway venv at
  `%TEMP%\opencode\trackster-venv` only for testing; the project itself isn't
  packaged with a venv. Create your own (e.g. `python -m venv .venv`) and
  `pip install -r requirements.txt` before launching `python main.py`.

---

## In-depth test session (read & download paths)

Mechanically ran the app's logic via pytest (44 tests) with mocks and a
full-page build harness, then fixed every issue surfaced. This caught real
**flet 0.86 / moviepy 2.x API drift** and several download-path bugs.

### flet 0.86 API modernization (startup-crashing without these)

- **Icons**: `ft.icons.X` → `ft.Icons.X` (upper-case enum). `CLOSE`, `MENU`,
  `FOLDER_OPEN`, nav-destination icons changed.
- **Colors**: `ft.colors.with_opacity` / `ft.cupertino_colors` →
  `ft.Colors.with_opacity` / `ft.CupertinoColors`.
- **FilePicker**: `on_result=` callback is gone; `get_directory_path()` is now
  `async` and returns the path directly. Folder picker rewritten; button uses an
  async handler.
- **Dropdown**: `on_change` → `on_select`.
- **Buttons**: `ft.ElevatedButton` → `ft.Button` (deprecated in 0.80, removed in 1.0).
- **Dialogs**: `page.open(...)` → `page.show_dialog(...)` (added a `show_dialog()`
  helper that falls back to `page.open` on older flet).

### moviepy 2.x compatibility + dependency fixes

- `from moviepy.editor import AudioFileClip` broke on moviepy 2.x (`requirements.txt`
  installs it). Added a try/except import that works on both 1.x and 2.x.
- `requirements.txt`: removed the bogus `ssl` entry (stdlib; pip couldn't install it)
  and added `aiohttp` (used by `search.py` — was missing).

### Read-path fixes

- **Spotify readers only mark a track `synced` after metadata is actually fetched**
  (previously a failed fetch was still marked synced and never retried).
- Spotify downloader now aborts with a clear message if credentials are missing
  (`sp is None`) instead of crashing when fetching the playlist.
- `apple.get_playlist()` filters out `None` song details (previously appended `None`
  and crashed downstream); added request timeouts; fixed the replace prefix.

### Download-path fixes

- **`download_yt`** rewritten to use yt-dlp's native `FFmpegExtractAudio`
  postprocessor (reliable MP3 output) instead of the fragile `.mp4`→moviepy
  pipeline; scans for the actual output file and falls back to moviepy only if
  ffmpeg isn't available.
- **`download_high_quality`**: the exists-check now uses the *sanitized* filename
  (it previously checked a path that never matched the real output file).
- **`set_metadata`** hardened: `None` `isrc`/`release_date`/`album_art` no longer
  crash mutagen; album art only fetched when a URL is present.
- **Success now clears the failure record** (`remove_failed`), so "download only
  failed songs" won't re-download songs that were just fixed.
- Consistent path separators for the `tmp/` directory (no mixed `/` and `\`).
- `requests` calls in JioSaavn/Apple paths given timeouts so a dead network can't
  hang a download thread. `find_youtube` made network-safe for tests.

### Harness / test coverage added

- `tests/conftest.py` — isolated temp SQLite DB + a `music_dir` fixture per test.
- `test_db.py` — settings, failed/downloaded/synced/mismatch CRUD, `.env` migration.
- `test_helpers.py` — filename sanitizing, path normalization, DES decrypt
  round-trip, `download_yt` skip/replace logic (mocked yt-dlp).
- `test_search_download.py` — `search_song` parsing (topquery/fallback/none),
  `download_high_quality` flow, and the full `DownloadSong` end-to-end
  (decrypt → download → convert → tag → move) used by the Search tab.
- `test_apple.py` — Apple Music playlist parsing incl. `None` filtering.
- `test_spotify_read.py` — playlist/album reads: pagination, synced tracking,
  private-playlist rejection, track-info parsing, missing-credential handling.
- `test_metadata.py` — real mutagen writes incl. missing-optional-fields and lyrics.
- `test_ui_smoke.py` — constructs every UI control, plus `main(page)` against a
  `FakePage` to catch any remaining flet API drift at build time.