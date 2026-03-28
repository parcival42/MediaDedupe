# MediaDedupe

Web-based duplicate finder for images & videos — perceptual hashing, ffmpeg-powered, with smart intro/outro detection and a parallel scan engine.

## Features

- **Exact duplicates** — byte-identical files detected via MD5
- **Visual duplicates** — same image at different resolutions or compression levels, detected via perceptual hashing (pHash, configurable Hamming threshold)
- **Video duplicates** — frame sampling at 5 positions across the video timeline; optional intensive mode that also compares intro/outro blocks to catch re-encoded or trimmed copies
- **Two-directory comparison** — find files from directory A that are duplicates of files in directory B (useful for consolidating backups)
- **SQLite cache** — hashes are stored so repeat scans are near-instant for already-processed files
- **Web UI** — interactive browser interface with real-time scan progress, inline previews, and one-click deletion
- **CLI mode** — generates a self-contained HTML report, no server required
- **Multilingual UI** — German and English, switchable at runtime

## Supported formats

| Type | Extensions |
|---|---|
| Images | `.jpg` `.jpeg` `.png` `.gif` `.webp` `.bmp` `.tiff` `.tif` `.heic` `.heif` |
| Videos | `.mp4` `.mkv` `.avi` `.mov` `.m4v` `.webm` `.wmv` `.flv` |

HEIC/HEIF support requires the optional `pillow-heif` package. Video scanning requires `ffmpeg` and `ffprobe`.

## Quick start

### Docker (recommended)

```yaml
# docker-compose.yml
services:
  mediadedupe:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - /path/to/your/media:/media
      - /path/to/data:/data        # database & working files
    command: ["-d", "/media"]
    restart: unless-stopped
    environment:
      - AUTH_SECRET=a_long_random_secret_string
```

```bash
docker-compose up -d
```

Then open `http://localhost:8080` in your browser.

### Python (web UI)

```bash
pip install -r requirements.txt
# ffmpeg must be available in PATH for video scanning

python app.py -d /path/to/your/media
python app.py -d /path/to/your/media --port 8080 --host 0.0.0.0  # default port
```

### Python (CLI — HTML report only)

```bash
pip install Pillow imagehash pillow-heif   # pillow-heif optional

python cli.py -d /path/to/your/media -t images
python cli.py -d /path/to/your/media -t videos
python cli.py -d /path/to/your/media -t both -o my_report.html --workers 8
```

The report is written to the working directory (`$DUPFINDER_DATA`, default `/tmp/mediadedupe/`).

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `AUTH_SECRET` | *(random)* | HMAC key for session cookies. Set a fixed value so sessions survive restarts. |
| `DUPFINDER_DATA` | `/tmp/mediadedupe` | Directory for the SQLite database and HTML reports. Set this via the `volumes` mount in docker-compose. |

## First-run setup

When you open the web UI for the first time, you will be redirected to a setup page where you create the initial **admin account** (username + password). This account is created once — the setup page is only accessible as long as no user exists in the database.

After the initial setup, log in with those credentials. Additional users can be managed from within the app. Sessions are valid for 30 days and are signed with `AUTH_SECRET` (set a fixed value via the environment variable so sessions survive restarts).

## Language / Localization

The web UI is available in **German** and **English**. The language can be switched at any time via the language selector at the bottom of the sidebar — no restart required. All UI labels, messages, and scan log output switch instantly.

The CLI report (`cli.py`) is rendered in English.

## Scan settings (web UI)

| Setting | Description |
|---|---|
| **Media type** | Images, videos, or both |
| **Compare mode** | Enable a second directory to find cross-directory duplicates |
| **pHash threshold** | Hamming distance for visual image matching (0 = pixel-identical, ≤ 8 recommended) |
| **Frame threshold** | Hamming distance per video frame (default 10) |
| **Min frame matches** | How many of the 5 sampled frames must match (default 4) |
| **Duration tolerance** | Videos whose durations differ by more than this (seconds) are never compared |
| **Intensive mode** | Also samples intro and outro blocks to catch re-encoded copies |
| **Workers** | Parallel threads for hashing (default: up to 4, auto-detected) |

## Database schema

All data is stored in a single SQLite file inside `DUPFINDER_DATA`. The schema is created automatically on first start.

### `images`
Scan cache for image files. One row per file, keyed on `path`.

| Column | Type | Description |
|---|---|---|
| `path` | TEXT | Absolute file path (unique) |
| `filename` | TEXT | Filename only |
| `size` | INTEGER | File size in bytes |
| `mtime` | REAL | File modification time (Unix timestamp) — used to detect changes |
| `md5` | TEXT | MD5 hash for exact-duplicate detection |
| `phash` | TEXT | Perceptual hash for visual-duplicate detection |
| `width` / `height` | INTEGER | Image dimensions in pixels |
| `error` | TEXT | Error message if processing failed, otherwise NULL |
| `processed_at` | REAL | When this row was last written |
| `thumbnail_b64` | TEXT | Base64-encoded JPEG thumbnail for the web UI |

### `videos`
Scan cache for video files. One row per file, keyed on `path`.

| Column | Type | Description |
|---|---|---|
| `path` | TEXT | Absolute file path (unique) |
| `filename` | TEXT | Filename only |
| `size` | INTEGER | File size in bytes |
| `mtime` | REAL | File modification time — used to detect changes |
| `md5` | TEXT | MD5 hash for exact-duplicate detection |
| `duration` | REAL | Duration in seconds |
| `width` / `height` | INTEGER | Video dimensions in pixels |
| `codec` | TEXT | Video codec (e.g. `h264`) |
| `bitrate` | INTEGER | Bitrate in bps |
| `frame_hashes` | TEXT | JSON array of pHashes sampled at 10/30/50/70/90 % of the timeline |
| `frames_b64` | TEXT | Base64-encoded JPEG thumbnails of those frames |
| `thumbnail_b64` | TEXT | Cover thumbnail for the web UI |
| `intensive_start` / `intensive_end` | TEXT | JSON arrays of pHashes from intro/outro blocks (intensive mode only) |
| `intensive_n` | INTEGER | Number of frames sampled per intensive block |
| `error` | TEXT | Error message if processing failed, otherwise NULL |
| `processed_at` | REAL | When this row was last written |

### `delete_history`
Log of every file deleted through the web UI.

| Column | Description |
|---|---|
| `path` | Original absolute path |
| `filename` | Filename |
| `size` | File size in bytes at deletion time |
| `deleted_at` | Unix timestamp of deletion |

### `directory_scans`
Tracks the last scan timestamp per directory path.

| Column | Description |
|---|---|
| `path` | Scanned directory (primary key) |
| `last_scan` | Unix timestamp of the most recent scan |

### `scan_jobs`
Persists scan job state so the frontend can poll for progress.

| Column | Description |
|---|---|
| `job_id` | UUID (primary key) |
| `status` | `pending` / `running` / `done` / `error` |
| `dir1` | Primary scan directory |
| `started_at` / `ended_at` | Unix timestamps |
| `results` | JSON-serialised result payload |
| `settings` | JSON-serialised scan settings |

### `users`
Accounts for web UI authentication.

| Column | Description |
|---|---|
| `username` | Unique login name |
| `password_hash` | PBKDF2-SHA256 hash |
| `salt` | Per-user salt |
| `created_at` | Unix timestamp of account creation |

## License

[MIT](LICENSE)
