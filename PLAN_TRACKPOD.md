# Trackpod — Local Music Manager + Device Sync

**Working spec & architecture.** A brand-new desktop application (codename **Trackpod**)
that turns the proven download/search logic of the existing **Trackster2** app into a
full music library manager — the "iTunes without a store" experience iOpenPod aims at,
but shaped around *your* device workflow (old iPod Classic, Android phone).

This document is the source of truth for scoping, architecture, and build order.

---

## 1. Vision

Trackpod is a **local-first music library** app. The user does **not** browse a store;
instead they **feed it music sources** (a Spotify playlist URL, a YouTube playlist, an
Apple Music playlist, or a favorite artist on JioSaavn), it **resolves every track to a
downloadable file** (JioSaavn first, YouTube fallback, with a user toggle to disable
Saavn), downloads into a managed folder, stores a **SQLite library**, and **syncs the
Library to a connected device** (old iPod / Android).

It deliberately copies the *device-first* mindset of [iOpenPod](https://github.com/TheRealSavi/iOpenPod)
(iTunesDB read/write, sync review, transcoding) while borrowing the *source resolution +
download* logic already working in Trackster2.

---

### 1.1 Target devices

| Device | Connection | Storage model | Reality check |
|---|---|---|---|
| **iPod Classic (5th–7th) — target: 6th gen** | Mounted as a USB drive | **classic chunked `iTunesDB`** (`iPod_Control/iTunes/iTunesDB`, media in `iPod_Control/Music/F00...F49/`, artwork in `iPod_Control/Artwork/*.ithmb`) | Complex binary DB; **6G requires the `hash58` checksum**. iOpenPod's `itunesdb_writer`/`artworkdb_writer` are the model. iTunesDB alone is enough to list/play; artwork is optional. |
| **Android phone / Android music player** | **MTP** over USB (no root), or **ADB push** | MTP is a Shell namespace (no drive letter; no random access) | On Windows use **WPD/COM** (native, Explorer route); `pymtp`/`libmtp` don't work on Windows. **ADB `adb push`** is the reliable fallback. |

**v1 scope decision:** implement **two sync backends**
- `ipod` — reads/writes iTunesDB (classic chunked) + copies files (see §4 Device sync).
- `android` — via **WPD/COM MTP backend** (primary, native on Windows) with an **ADB** fallback backend.

Both are behind one **`Device` interface**; iPod Shuffle / iPod Touch are out of scope (different DBs).

---

## 2. Core concepts

### 2.1 The source-resolution pipeline (reused from Trackster2)

A **track** has a *logical identity* (from a playlist) and zero-or-more *media files*.

```
Playlist (Spotify/YouTube/Apple/Saavn)
   │  fetch track list
   ▼
normative Tracks (title, artist, album, artwork, duration)
   │  resolve each
   ▼
resolver:
   ├─ Saavn (enabled) → HighQuality URL  (JioSaavn search_song)     ── primary
   └─ YouTube          → mp3 via yt-dlp FFmpegExtractAudio          ── fallback
   ▼
download → local folder → metadata tag (ID3) → library row
```

Key Trackster2 pieces we **reuse verbatim or near-verbatim**:
- `search.search_song`, `DownloadSong.download_song(_async)`, `search.Song` (+ `enrich_song`),
- `main.download_yt` (yt-dlp FFmpegExtractAudio path),
- `main.set_metadata` (ID3 + APIC album art),
- `main.sanitize_filename`, `ensure_folder_path_ends_with_slash`,
- `apple.get_playlist` (native Apple Music page parsing),
- `spotipy` metadata (artist/title/album), `get_synced_ids` semantics.

These become a new **`sources/`** package, decoupled from any UI.

### 2.2 "Sink" — the library & library DB

A **SQLite3 database** (`library.db`) is the single source of truth. No more `*.txt` bookkeeping

```
tables:
  sources            id, name, kind('spotify'|'youtube'|'apple'|'artist')
  source_items       id, source_id, ref (url/id), external_id, added_at   -- raw playlist rows
  tracks             id, title, artist, album, year, duration, artwork,
                     resolved_from ('saavn'|'youtube'|None), state
  track_files        track_id, file_path, source_qual('HQ'|'PL'), size, created_at
  artists            id, name              -- "favorites" from artist search
  favorites          artist_id, source ref
  device_sync        id, device_id, track_id, synced_at    -- which track is on which device
  sync_events        id, device_id, kind('add'|'remove'|'error'), track_id, ts
  settings           key, value
```

- **Library = a folder** chosen by the user (managed from the UI: set path, see space, open).
- A track is "in library" when it has an entry in `tracks` **and** a real file in `track_files`.
- DB is written transactionally; every mutation is recorded in a `sync_events` log feeding the
  per-device sync review.

### 2.3 Playlists & "sync for playlists"

- Add a **source** (paste a URL): the app fetches the normative track list and stores it
  in `source_items`. This is **lightweight; no download yet**.
- **Sync source** = re-fetch the current list and **diff** against stored `source_items`:
  - added → mark `state=pending_download`
  - removed → optionally remove files
  - changed ordering → ignore
- Tracks that are already downloaded in the library are skipped (dedup by normalized
  `title_id`).

### 2.4 Artist favorites

- From the app's *Search* view, search JioSaavn → pick an artist → **Add to favorites**
  (stored in `artists` + `favorites`).
- On **Sync**, the app lists that artist's current songs (`get_songs_from_artist`) and adds
  any new ones to the "pending" set (same resolver-pipeline; they join the normal download queue).

## 3. Download queue & folder manager

- A **managed queue**: each pending track appears with a resolution status
  (`pending → resolving → downloading → done | failed | mismatch`).
- Per–track override: *"Saavn preferred; try YouTube"* toggle; **global "disable Saavn"** setting.
- A **Folder manager view** reads the user's selected folder: shows files, lets the user
  open, delete, rename, and bulk-rearrange (by artist/album) — all reflected in DB.

## 4. Device sync

- A **Device Manager** panel lists connected devices (ADB, MTP, mounted iPod) and lets you:
  - choose which playlist / artists / whole library to sync,
  - see a **sync review** (add/remove/update plan) before writing,
  - run the sync (copy/transcode), then **update the device index** (iTunesDB for iPod, plain
    folder layout for Android).
- Transcoding happens through **FFmpeg** (iPod Classic needs M4A/AAC or MP3 128/256; Android accepts
  the library MP3).
- Sync is **incremental**: `device_sync` rows prevent re-copying unchanged files.

---

## 5. Tech stack / framework choice

> **LOCKED: PySide6 (official Qt for Python) + SQLAlchemy + pytest + a thin CLI.**
>
> PySide6 is the official LGPL Python binding for Qt 6 (vs PyQt6, a third-party binding). It is
> PySide6 is the official LGPL Python binding for Qt 6 (vs PyQt6, a third-party binding). It is
> chosen because it is the most **pythonic** binding — pythonic signal/slot and clean enum usage
> free up the most time to build the iTunes-style library UI (sortable
> model/view tables, album-art browser, drag-drop), the same class of tooling iOpenPod uses
> (PyQt6) — and it ships standalone binaries via PyInstaller and supports broad LGPL-friendly reuse.
>
> The core stays **UI-agnostic**: the entire domain (sources, library, queue, device sync) lives in
> a plain-Python **core** package with no Qt/Flet imports; only the presentation layer uses PySide6.
> This lets every flow be unit-tested and reused from the CLI.

**Skeleton (PySide6 primary, UI-agnostic core):**

```
trackpod/                       # new monorepo (reuse logic, new app)
├── src/
│   ├── trackpod/
│   │   ├── __init__.py
│   │   ├── core/                # UI-agnostic domain  (pure Python)
│   │   │   ├── config.py        # app-wide settings + library.folder
│   │   │   ├── db.py            # SQLAlchemy models + migrations (replaces trackster.db)
│   │   │   ├── models.py        # Track, Source, SourceItem, Artist, Favorite, SyncTrack...
│   │   │   ├── sources/         # REUSED + packaged from trackster2/search.py, main.py, apple.py
│   │   │   │   ├── jiosaavn.py  # search_song, search, DownloadSong, enrich_song
│   │   │   │   ├── youtube.py   # download_yt (yt-dlp FFmpegExtractAudio), find_youtube
│   │   │   │   ├── spotify.py   # Spotify metadata / playlist / album fetch
│   │   │   │   ├── apple.py     # Apple Music playlist parse
│   │   │   │   ├── resolver.py  # the resolve pipeline (saver→yt, disable toggles)
│   │   │   │   └── metadata.py  # ID3 tagging + APIC
│   │   │   ├── pipeline.py      # download queue, threading/concurrency
│   │   │   ├── libmgr.py        # folder manager + library scan
│   │   │   └── devices/         # device abstraction
│   │   │       ├── base.py      # Device interface
│   │   │       ├── mtp.py       # WPD/COM MTP backend (android)
│   │   │       ├── adb.py       # adb push fallback backend (android)
│   │   │       └── ipod/        # iTunesDB read/write + artDB (based on iOpenPod's)
│   │   │           └── itunesdb.py
│   │   ├── cli.py                # `python -m trackpod cli ...` (headless)
│   │   └── app/
│   │       └── qt_ui/            # PySide6 presentation
│   │           ├── mainwindow.py
│   │           ├── library.py   # track table + artwork browser
│   │           ├── queue.py     # download queue
│   │           ├── search.py    # artist search + favorites
│   │           ├── devices.py   # device manager + sync review
│   │           └── settings.py  # Saavn on/off, dirs, ffmpeg path
│   ├── db/ (sqlite at user data dir)
│   └── tests/
└── pyproject.toml
```

**Dependencies (target):** `PySide6`, `SQLAlchemy`, `requests`, `aiohttp`, `bs4`, `mutagen`,
`yt-dlp`, `spotipy`, `pyDes`, `moviepy` (`AudioFileClip` 2.x), `tqdm`; dev: `pytest`, `ruff`,
`mypy`. Device: `pymtp`/`libmtp` bindings (subp), `subprocess` + `adb`, and a vendored iTunesDB
writer (port of iOpenPod's `itunesdb_writer`).

---

## 6. Architecture layering (core contract)

```
┌──────────────────────────  Presentation (PySide6)  ──────────────────────────┐
   │  Library │ Queue │ Search │ Devices │ Settings                              │
   └───────────▲────────▲────────┬───────▲───────────────────────────────────────┘
               │        │        │        │  (UI calls core methods; UI never calls
               │        │        │        │   requests/yt-dlp/ffmpeg directly)
   ┌───────────┴────────┴─────┬──┴────────┴────────────────────────────────────────┐
   │                            CORE (pure python, unit-testable)                    │
   │  resolver (saavn→yt)  • library (sqlite)  • pipeline (thread pool)             │
   │  sources (spotify/yt/apple) • libmgr (folder) • devices (ipod/android)        │
   └───────────────┬──────────────────────▲─────────────────────────────▲──────────┘
                   │ (writes files)       │ (FFmpeg transcode)          │ (WPD/MTP)
           ┌───────┴──────────────────────┴─────────────────────────────┴──────────┐
           │                       Work / device storage                            │
           │  <library folder>        <iPod drive>          <Android MTP/ADB>       │
           └─────────────────────────────────────────────────────────────────────────┘
```

- **UI → core is all JSON-able data calls**; `core` raises typed exceptions (e.g. `ResolveFailed`, `DeviceBusy`).
- **Threading:** pipeline runs in a `concurrent.futures.ThreadPoolExecutor` (like `page.run_thread` today),
  `async` path for the Saavn concurrent downloads (aiohttp) as in `DownloadSong.download_song_async`.

---

## 7. Key user flows (numbered)

### Flow A — "Sync my Spotify playlist"
1. **Add source**: paste `https://open.spotify.com/playlist/...`.
2. App fetches track list (spotify) → stores `source_items`.
3. User presses **queue all new** → Resolver marks `pending`.
4. **Download**: each in queue → saavn match → if none / disabled → YouTube → tag + move → DB row.
5. **Result**: library table now shows the tracks; status = done.
6. Re-opening later → **Sync** re-fetches list; diff shows only new; dedupe already-present.

### Flow B — "Favorite an artist, get their new songs on demand"
1. Search Tab → type artist → choose → **Add to favorites**.
2. Creator list shows the source; **Sync** fetches `get_songs_from_artist`, queues any tracks
   that aren't already in library (by `title_id`).
3. Download normally.

### Flow C — "Old iPod Classic, wire it up"
1. Connect iPod (shows as a drive).
2. Device Manager → **Add iPod**; app detects iTunesDB path.
3. Choose scope: *Library* or *Favorites+Playlist X*.
4. **Sync review** lists adds/removes/art updates → **Apply**.
5. iTunesDB + ArtworkDB written; device ejected clean.

### Flow D — "Android by ADB"
1. Enable USB debugging; `adb devices`.
2. Device Manager → **Add Android** (connection = ADB).
3. Scope choose; **Sync** → `adb push` each mp3 into `/sdcard/Music/<artist>/`, create/update
   `playlists` if needed; metadata tags copied (mutagen already in file).
4. Devices pick up files on next media rescan.

---

## 8. Data-integrity & invariants

- **Library single source of truth** = `tracks`+`track_files` in SQLite; files are just cache.
- Normalized `title_id` used for dedupe: `lowercase(sanitize(title) + "||" + lowercase(artist))`.
- **Idempotency**: downloading an already-present track returns "already exists" (reuse
  `prompt_exists_action` logic, default = Skip).
- **Retries** per source (network retry w/ backoff) — port from DownloadSong.
- **Sync review before destructive writes** (device). No silent delete.
- Settings persisted in DB; **Saavn toggle** (`settings.enable_saavn`) defaults ON.

---

## 9. Reuse map (code lifted from Trackster2)

| Trackster2 file | New package | Notes |
|---|---|---|
| `search.search_song`, `Search`, `Song`, `DownloadSong`, `enrich_song` | `core/sources/jiosaavn.py` | refactor imports to new package; keep the working logic |
| `main.download_yt`, `find_youtube` | `core/sources/youtube.py` | keep yt-dlp FFmpegExtractAudio path |
| `main.get_track_info*`, `search_spotify`, `get_playlist_info` | `core/sources/spotify.py` | Spotify metadata + fetchers |
| `main.set_metadata`, `sanitize_filename`, `make_alpha_numeric` | `core/sources/metadata.py`, `core/util.py` | ID3 + APIC, filename safety |
| `apple.get_playlist` | `core/sources/apple.py` | Apple Music playlist parse |
| `main.AppState` globals | `core/config.py` | replaced by explicit Settings object |
| `db.py` (rows) | `core/db.py` (SQLAlchemy) | richer model, migrations via Alembic |

**Do NOT copy** the verb actions tied to `page.*` (Flet globals) — extract to explicit functions.

---

## 10. Testing

- `pytest`: unit tests per core module (mock `requests`, yt-dlp, ffmpeg).
- **Device tests**: a fake `Device` implementation; iTunesDB reader/writer golden-file tests
  (port iOpenPod test patterns); MTP/ADB integration marked `@pytest.mark.integration`, skipped
  unless FFmpeg/adb present.
- **UI smoke**: construct each screen with a headless fixture (like Trackster2's `test_ui_smoke`).
- **Golden flows**: Flow A–D as parametrized scenario tests with the pipeline mocked out.

---

## 11. Milestones

### M0 — Extraction & foundation
- Create `src/trackpod` package; move reused logic into `core/sources`; write `pyproject.toml`.
- `core/db.py` schema + migrations; `core/config.py`.
- CLI `python -m trackpod resolve <url>`, `add-source`, `download`, `list`.
- Unit tests import ✅ (replaces the 50 Trackster2 tests with real subpackages).

### M1 — Library + resolution (pure core, PySide6 UI)
- PySide6 screens: Library, Queue, Source add/list, Artist search & favorites.
- Resolver loops + `ThreadPoolExecutor`.
- Folder manager basics.

### M2 — Device sync
- Android via **WPD/COM MTP** backend; ADB as fallback.
- iPod via vendored iTunesDB writer (read existing first, then write) for 6G + hash58.
- Sync review UI (add/remove/art/transcode plan) — following iOpenPod's model.

### M3 — Polish
- Full PySide6 polish: artwork browser, drag-drop library, transcode settings,
  backup/rollback of device snapshot.

---

## 12. Decisions to lock before coding

**Locked (user):**
0. **UI framework** = **PySide6** (official Qt-for-Python, LGPL). Chosen over PyQt6 for its more pythonic, easier-to-develop API and lighter licensing.
1. **iPod target model** = **Classic 6th gen**. Uses the classic chunked `iTunesDB` (mhbd/mhlt/mhit/mhod/mhsd), dbVersion 0x17/0x1A, **requires the `hash58` checksum** written into the MHBD header + `iPod_Control/Device/HashInfo`. NOT the SQLite `.itdb` format. → port iOpenPod's `itunesdb_writer.py` + `artworkdb_writer.py`, verify against libgpod `itdb_itunesdb.c`.
2. **Android transport** = **MTP via Windows Portable Devices (WPD) COM** using `comtypes` (native route Explorer uses, no extra drivers). **Do NOT use `pymtp`/`libmtp`/`libusb` on Windows** (POSIX-only, unstable, steals the device from Explorer). Keep **ADB (`adb push`)** as a coexistence/fallback backend for devices that prefer USB-debugging mode.
3. **Saavn always-fallback to YouTube**: automatic, as today + a global **"disable Saavn"** toggle drives it to always YouTube.
4. **Sync scope granularity:** whole library vs per-source (playlist/artist) — implement both; default "selected".

**Still open (recommend):**
1. **iPod DB golden fixture**: capture a real iTunesDB from your 6G to write regression tests.
2. **DB file location**: switch from repo-local `trackster.db` to per-user platform data dir.

---

## Appendix — Dependencies

- `yt-dlp` for YouTube extraction; `ffmpeg`/`ffprobe` required for transcode.
- `spotipy` for Spotify; optional (skip if no creds) — UI warns.
- `mutagen` for ID3/APIC.
- `moviepy` only for legacy non-ffmpeg convert path; prefer yt-dlp postprocessor.
- System tools: `ffmpeg` (transcode/probe), optionally `adb` (Android fallback sync).

## Reference research (from iOpenPod + libgpod)

**iOpenPod build (learned from its repo):**
- **PyQt6** GUI (`pyqt6>=6.9.1,<7`); python ≥3.11; tooling `uv` + `hatchling`, built with **PyInstaller**/**Nuitka** for native binaries.
- Deps: `numpy`, `pillow` (art work resize), `pycryptodome` (DB checksums), `mutagen`, `pyusb` (USB/devices), `wasmtime` (WASM runner for Apple firmware code), `feedparser` (podcasts), `requests`, `tqdm`.
- **iPod comms:** bespoke `itunesdb_writer.py` + `artworkdb_writer.py` (no libgpod bindings; libgpod is the reference).
- Structure: `gui/`, `sync/`, `device/`, `itunesdb_parser/`, `itunesdb_writer/`, `artworkdb_*`, `sqlitedb_writer/` (Nano 6/7G).

**iPod Classic 6G technical (needed to build the `ipod` backend):**
- Layout: `iPod_Control/iTunes/iTunesDB`, `iPod_Control/Music/F00...F49/`, `iPod_Control/iTunes/iTunesPreferences`, `iPod_Control/Device/SysInfo(+Extended)`, `HashInfo`.
- Chunked `mhbd/mhsd/mhlt/mhit/mhod/mhat` binary; little-endian; UTF-16LE strings (length-prefixed, not NUL-terminated); MHBD/MHLT size encodings (off4=0x68/0xBC for Classic dbVersion 0x17; off8=file size or child count).
- 6G requires **hash58 checksum** (over whole DB) in MHBD ~off88 + `HashInfo`; dbVersion >=0x17; field @48 = 0x01.
- Media filenames exactly 4 uppercase hex + ext in an `Fxx` folder; media type 0x01 (audio); each track needs a Location (`dataobject`) mhod or it lists but won't play.

**Android MTP (Windows, needed to build `android` backend):**
- Windows mounts MTP as a Shell namespace (not a drive letter); `os.open`/`shutil.copy` fail.
- `pymtp`/`libmtp`/`libusb-win32` = POSIX-only, breaks Explorer, fragile sessions. **Avoid.**
- **Windows-native route:** WPD via COM — `PortableDeviceManager` → `IPortableDevice` → `IPortableDeviceContent(Content)` → `IPortableDeviceResources::GetStream`, implemented in Python via `comtypes`. Mirrors Explorer reliability.
- Coexistence fallback: bundle `adb.exe` (platform-tools), `adb push -Z` to `/sdcard/Music/<artist>/`; needs USB-debugging once, no MTP driver at all.

**Explicitly NOT in scope now:** music playback of DRM, iTunes-capable match syncing to *iPod Touch*,
cloud account migration, DRM download. Keep as future roadmap.