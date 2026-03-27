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
- **DE / EN UI**

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

The report is written to the working directory (`$DUPFINDER_DATA`, default `/dpool/tmp/findDuplicates/`).

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `AUTH_SECRET` | *(random)* | HMAC key for session cookies. Set a fixed value so sessions survive restarts. |
| `DUPFINDER_DATA` | `/dpool/tmp/findDuplicates` | Directory for the SQLite database and HTML reports. |

## Authentication

On first launch, navigate to the web UI to create the initial admin account. Subsequent logins use username and password. Sessions are valid for 30 days and are signed with `AUTH_SECRET`.

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

## License

[MIT](LICENSE)
