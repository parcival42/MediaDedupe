#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine.py — Core library: finds duplicate images and videos.

Imported by cli.py (CLI scan) and app.py (web server).

Detects:
  - Exact duplicates (identical bytes, same MD5)
  - Visual duplicates (same image, different resolution or compression)

Output: HTML report with preview thumbnails (via cli.py)
Database: SQLite cache so repeated scans are fast

Work directory: /tmp/mediadedupe/ (override with DUPFINDER_DATA env var)

Dependencies: pip install Pillow imagehash pillow-heif
"""

import base64
import concurrent.futures
import hashlib
import hmac
import io
import json
import os
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from report_template import REPORT_TEMPLATE

# --- Check optional dependencies ---
try:
    from PIL import Image
    import imagehash
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False

# --- Constants ---
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp',
                    '.tiff', '.tif', '.heic', '.heif'}

# pHash Hamming threshold:
#   0     = pixel-identical
#   1–5   = same image, different resolution or minimal JPEG compression
#   6–8   = same image, stronger compression or small crop
#   > 10  = thematically similar (burst shots) — intentionally excluded
PHASH_THRESHOLD = 8

THUMBNAIL_MAX = 300
WORK_DIR = Path(os.environ.get('DUPFINDER_DATA', '/tmp/mediadedupe'))
DB_PATH = WORK_DIR / 'findDuplicates.db'
HTML_OUTPUT = WORK_DIR / 'duplicates_report.html'

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.m4v', '.webm', '.wmv', '.flv'}
# Frame positions as fraction of total duration (10%, 30%, 50%, 70%, 90%)
VIDEO_FRAME_POSITIONS = [0.10, 0.30, 0.50, 0.70, 0.90]
# Hamming threshold per frame comparison
VIDEO_FRAME_THRESHOLD = 10
# How many frames must match for it to be a duplicate
VIDEO_MIN_MATCHES = 4
# Tolerance for the duration pre-filter in seconds
VIDEO_DURATION_TOLERANCE = 3.0

# Parallel workers for hash computation (0 = auto)
WORKER_COUNT: int = min(4, os.cpu_count() or 2)


# ===========================================================================
# Database functions
# ===========================================================================

def db_connect(db_path: Path) -> sqlite3.Connection:
    """Connects to the SQLite database and creates the schema if needed."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    db_create_schema(db)
    return db


def db_create_schema(db: sqlite3.Connection) -> None:
    """Creates tables and indexes if they do not yet exist."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS images (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            path             TEXT UNIQUE NOT NULL,
            filename         TEXT NOT NULL,
            size             INTEGER NOT NULL,
            mtime            REAL NOT NULL,
            md5              TEXT,
            phash            TEXT,
            width            INTEGER,
            height           INTEGER,
            error            TEXT,
            processed_at     REAL NOT NULL,
            thumbnail_b64    TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_md5      ON images(md5);
        CREATE INDEX IF NOT EXISTS idx_size     ON images(size);

        CREATE TABLE IF NOT EXISTS videos (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            path             TEXT UNIQUE NOT NULL,
            filename         TEXT NOT NULL,
            size             INTEGER NOT NULL,
            mtime            REAL NOT NULL,
            md5              TEXT,
            duration         REAL,
            width            INTEGER,
            height           INTEGER,
            codec            TEXT,
            bitrate          INTEGER,
            frame_hashes     TEXT,
            frames_b64       TEXT,
            thumbnail_b64    TEXT,
            error            TEXT,
            processed_at     REAL NOT NULL,
            intensive_start  TEXT,
            intensive_end    TEXT,
            intensive_n      INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_videos_duration ON videos(duration);

        CREATE TABLE IF NOT EXISTS delete_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            path         TEXT NOT NULL,
            filename     TEXT NOT NULL,
            size         INTEGER NOT NULL,
            deleted_at   REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_history_date ON delete_history(deleted_at);

        CREATE TABLE IF NOT EXISTS directory_scans (
            path         TEXT PRIMARY KEY,
            last_scan    REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scan_jobs (
            job_id       TEXT PRIMARY KEY,
            status       TEXT NOT NULL,
            dir1         TEXT NOT NULL,
            started_at   REAL NOT NULL,
            ended_at     REAL,
            results      TEXT,
            settings     TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_scan_jobs_started ON scan_jobs(started_at DESC);

        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt          TEXT NOT NULL,
            created_at    REAL NOT NULL
        );
    """)
    db.commit()


# ===========================================================================
# Password helper functions
# ===========================================================================

def hash_password(password: str) -> tuple[str, str]:
    """Returns (hash_hex, salt_hex). Uses PBKDF2-HMAC-SHA256."""
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
    return h.hex(), salt.hex()


def verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
    """Checks a password against a stored hash and salt."""
    salt = bytes.fromhex(salt_hex)
    h = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
    return hmac.compare_digest(h.hex(), hash_hex)


def db_cleanup(db: sqlite3.Connection) -> dict:
    """Removes cache entries for files that no longer exist on the filesystem."""
    image_paths = [row[0] for row in db.execute('SELECT path FROM images').fetchall()]
    video_paths = [row[0] for row in db.execute('SELECT path FROM videos').fetchall()]

    stale_images = [p for p in image_paths if not Path(p).exists()]
    stale_videos = [p for p in video_paths if not Path(p).exists()]

    if stale_images:
        db.executemany('DELETE FROM images WHERE path = ?', [(p,) for p in stale_images])
    if stale_videos:
        db.executemany('DELETE FROM videos WHERE path = ?', [(p,) for p in stale_videos])
    db.commit()
    return {'images': len(stale_images), 'videos': len(stale_videos)}


@contextmanager
def db_context(path: Path):
    """Opens a DB connection and guarantees it is closed even on exceptions."""
    db = db_connect(path)
    try:
        yield db
    finally:
        db.close()


# ===========================================================================
# Scan & processing
# ===========================================================================

def scan_directory(directory: Path) -> list[Path]:
    """Collects all image files in the directory (recursively)."""
    found = []
    for entry in directory.rglob('*'):
        if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS:
            found.append(entry)
    return sorted(found)


def compute_md5(path: Path) -> Optional[str]:
    """Computes the MD5 hash of a file in chunks."""
    hasher = hashlib.md5()
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None


def compute_phash_and_meta(
    path: Path
) -> tuple[Optional[str], Optional[int], Optional[int], Optional[str]]:
    """
    Opens an image with Pillow and computes pHash + resolution.
    Returns (phash_hex, width, height, error).
    """
    try:
        with Image.open(path) as img:
            width, height = img.size
            h = imagehash.phash(img)
            return str(h), width, height, None
    except Exception as e:
        return None, None, None, str(e)


def process_files(
    paths: list[Path],
    db: sqlite3.Connection,
    progress_cb=None,
    workers: int = None,
) -> list[dict]:
    """
    Processes all image files: computes MD5 + pHash and writes to DB.
    Uses cache: files with unchanged mtime + size are skipped.
    Returns all rows for the processed files.

    3-phase approach for thread safety:
      Phase 1 (serial):   cache check in DB context
      Phase 2 (parallel): MD5 + pHash computation (DB not touched)
      Phase 3 (serial):   write results to DB
    """
    if workers is None:
        workers = WORKER_COUNT
    total = len(paths)

    # Phase 1: cache check (serial)
    stat_map: dict[str, os.stat_result] = {}
    cache_hits: dict[str, dict] = {}
    to_process: list[Path] = []

    for path in paths:
        try:
            stat = path.stat()
        except PermissionError as e:
            print(f'\nWarning: no access to {path}: {e}', file=sys.stderr)
            continue
        stat_map[str(path)] = stat
        row = db.execute('SELECT * FROM images WHERE path = ?', [str(path)]).fetchone()
        if row and row['mtime'] == stat.st_mtime and row['size'] == stat.st_size:
            cache_hits[str(path)] = dict(row)
        else:
            to_process.append(path)

    # Phase 2: parallel computation (MD5 + pHash)
    results_map: dict[str, dict] = {}

    def _process_one(path: Path) -> dict:
        stat = stat_map[str(path)]
        md5 = compute_md5(path)
        phash, width, height, error = compute_phash_and_meta(path)
        return {
            'path': str(path), 'filename': path.name,
            'size': stat.st_size, 'mtime': stat.st_mtime,
            'md5': md5, 'phash': phash,
            'width': width, 'height': height, 'error': error,
        }

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        future_map = {ex.submit(_process_one, p): p for p in to_process}
        for future in concurrent.futures.as_completed(future_map):
            done += 1
            path = future_map[future]
            pct_total = len(cache_hits) + done
            print(f'\r\033[KProcessing {pct_total}/{total}: {path.name}', end='', flush=True)
            if progress_cb:
                progress_cb(pct_total, total, path.name)
            try:
                results_map[str(path)] = future.result()
            except Exception as e:
                stat = stat_map[str(path)]
                results_map[str(path)] = {
                    'path': str(path), 'filename': path.name,
                    'size': stat.st_size, 'mtime': stat.st_mtime,
                    'error': str(e),
                }

    # Phase 3: serial DB write
    db.execute('BEGIN')
    for path in to_process:
        r = results_map.get(str(path))
        if not r:
            continue
        db.execute(
            """INSERT OR REPLACE INTO images
               (path, filename, size, mtime, md5, phash, width, height, error, processed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [r['path'], r['filename'], r['size'], r['mtime'],
             r.get('md5'), r.get('phash'), r.get('width'), r.get('height'),
             r.get('error'), time.time()]
        )
    db.execute('COMMIT')

    print()  # newline after progress output

    # Assemble results in original order
    results = []
    for path in paths:
        k = str(path)
        if k in cache_hits:
            results.append(cache_hits[k])
        elif k in results_map:
            results.append(results_map[k])
    return results


# ===========================================================================
# Duplicate detection
# ===========================================================================

def find_exact_duplicates(rows: list[dict]) -> list[list[dict]]:
    """
    Finds exact duplicates via MD5.
    Pre-filter: only files with the same file size are compared.
    """
    # Step 1: keep only candidates with the same file size
    size_counter = Counter(z['size'] for z in rows)
    candidates = [z for z in rows if size_counter[z['size']] >= 2]

    # Step 2: group by MD5
    groups: dict[str, list[dict]] = defaultdict(list)
    for z in candidates:
        if z['md5']:
            groups[z['md5']].append(z)

    return [g for g in groups.values() if len(g) >= 2]


def find_visual_duplicates(
    all_rows: list[dict],
    exact_paths: set[str],
    threshold: int = PHASH_THRESHOLD,
) -> list[list[dict]]:
    """
    Finds visual duplicates via pHash Hamming distance.
    Files already identified as exact duplicates are skipped.
    """
    # Only rows with a valid pHash that are not already in exact groups
    valid = [
        z for z in all_rows
        if z['phash'] is not None and z['path'] not in exact_paths
    ]

    if not valid:
        return []

    hashes = [(z, imagehash.hex_to_hash(z['phash'])) for z in valid]

    visited: set[str] = set()
    groups = []

    for i, (row_i, hash_i) in enumerate(hashes):
        if row_i['path'] in visited:
            continue
        group = [row_i]
        visited.add(row_i['path'])

        for j in range(i + 1, len(hashes)):
            row_j, hash_j = hashes[j]
            if row_j['path'] in visited:
                continue
            distance = hash_i - hash_j  # imagehash __sub__ = Hamming distance
            if distance <= threshold:
                row_j_with_dist = dict(row_j)
                row_j_with_dist['_phash_distanz'] = int(distance)
                group.append(row_j_with_dist)
                visited.add(row_j['path'])

        if len(group) >= 2:
            groups.append(group)

    return groups


# ===========================================================================
# Video — scan & processing
# ===========================================================================

def ffmpeg_available() -> bool:
    """Checks whether ffprobe is available on the system."""
    try:
        subprocess.run(['ffprobe', '-version'], capture_output=True, timeout=15)
        return True
    except FileNotFoundError:
        return False
    except subprocess.TimeoutExpired:
        return True  # ffprobe is present, just slow right now


def ffprobe_metadata(path: Path) -> dict:
    """
    Reads video metadata via ffprobe.
    Returns dict with duration, width, height, codec, bitrate.
    On error: dict with 'error' key.
    """
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_streams', '-show_format', str(path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        data = json.loads(result.stdout)
    except Exception as e:
        return {'error': f'ffprobe: {e}'}

    duration = float(data.get('format', {}).get('duration') or 0)
    bitrate = int(int(data.get('format', {}).get('bit_rate') or 0) / 1000)

    width = height = codec = None
    for stream in data.get('streams', []):
        if stream.get('codec_type') == 'video':
            width = stream.get('width')
            height = stream.get('height')
            codec = stream.get('codec_name')
            break

    return {'duration': duration, 'width': width, 'height': height,
            'codec': codec, 'bitrate': bitrate}


def extract_frame(path: Path, position_sec: float) -> Optional[bytes]:
    """Extracts a frame at the given position as PNG bytes via ffmpeg."""
    cmd = [
        'ffmpeg', '-ss', str(position_sec), '-i', str(path),
        '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0 or not result.stdout:
            return None
        return result.stdout
    except Exception:
        return None


def extract_frame_hash(path: Path, position_sec: float) -> Optional[str]:
    """Computes the pHash of a frame at the given position."""
    png_bytes = extract_frame(path, position_sec)
    if not png_bytes:
        return None
    try:
        with Image.open(io.BytesIO(png_bytes)) as img:
            return str(imagehash.phash(img))
    except Exception:
        return None


def frame_thumbnail_b64(path: Path, position_sec: float) -> str:
    """
    Extracts a frame and returns it as a base64-JPEG thumbnail.
    Returns empty string on error.
    """
    png_bytes = extract_frame(path, position_sec)
    if not png_bytes:
        return ''
    try:
        with Image.open(io.BytesIO(png_bytes)) as img:
            img.thumbnail((THUMBNAIL_MAX, THUMBNAIL_MAX), Image.LANCZOS)
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=75)
            return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ''


def _frame_bytes_to_hash(frame_bytes: bytes) -> Optional[str]:
    """Computes pHash from already-extracted frame bytes."""
    try:
        with Image.open(io.BytesIO(frame_bytes)) as img:
            return str(imagehash.phash(img))
    except Exception:
        return None


def _frame_bytes_to_b64(frame_bytes: bytes) -> str:
    """Creates a base64-JPEG thumbnail from already-extracted frame bytes."""
    try:
        with Image.open(io.BytesIO(frame_bytes)) as img:
            img.thumbnail((THUMBNAIL_MAX, THUMBNAIL_MAX), Image.LANCZOS)
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=75)
            return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ''


def _frame_bytes_to_preview(frame_bytes: bytes) -> str:
    """Creates a small base64-JPEG preview (160×120) for the frame strip."""
    try:
        with Image.open(io.BytesIO(frame_bytes)) as img:
            img.thumbnail((160, 120), Image.LANCZOS)
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=55)
            return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ''


def _split_png_stream(data: bytes) -> list[bytes]:
    """Splits a concatenated PNG stream (ffmpeg image2pipe) into individual PNG files."""
    PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
    frames, pos = [], 0
    while True:
        idx = data.find(PNG_MAGIC, pos)
        if idx == -1:
            break
        next_idx = data.find(PNG_MAGIC, idx + 8)
        frames.append(data[idx:next_idx] if next_idx != -1 else data[idx:])
        if next_idx == -1:
            break
        pos = next_idx
    return frames


def extract_video_edge_hashes(path: Path, n_seconds: int, duration: float = 0.0) -> tuple[list[str], list[str]]:
    """
    Extracts n_seconds frames each from the start and end of the video (1fps).
    Returns (start_hashes, end_hashes) as lists of pHash strings.
    Uses one ffmpeg call each for start and end.
    If duration is not provided, ffprobe is called.
    """
    if duration <= 0:
        meta = ffprobe_metadata(path)
        duration = meta.get('duration') or 0
    if duration <= 0:
        return [], []

    def _extract_block(start: float) -> list[str]:
        cmd = [
            'ffmpeg', '-ss', str(max(0.0, start)), '-i', str(path),
            '-t', str(n_seconds), '-vf', 'fps=1',
            '-f', 'image2pipe', '-vcodec', 'png', '-'
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode != 0 or not result.stdout:
                return []
            return [h for b in _split_png_stream(result.stdout)
                    if (h := _frame_bytes_to_hash(b)) is not None]
        except Exception:
            return []

    start_hashes = _extract_block(0.0)
    end_hashes = _extract_block(max(0.0, duration - n_seconds))
    return start_hashes, end_hashes


def scan_videos(directory: Path) -> list[Path]:
    """Collects all video files in the directory (recursively)."""
    found = []
    for entry in directory.rglob('*'):
        if entry.is_file() and entry.suffix.lower() in VIDEO_EXTENSIONS:
            found.append(entry)
    return sorted(found)


def process_videos(
    paths: list[Path],
    db: sqlite3.Connection,
    progress_cb=None,
    workers: int = None,
    intensive_seconds: int = 0,
) -> list[dict]:
    """
    Processes all video files: reads metadata + frame hashes and writes to DB.
    Uses cache: files with unchanged mtime + size are skipped.

    3-phase approach for thread safety:
      Phase 1 (serial):   cache check in DB context
      Phase 2 (parallel): ffprobe + 5x extract_frame (DB not touched)
      Phase 3 (serial):   write results to DB
    """
    if workers is None:
        workers = WORKER_COUNT
    total = len(paths)

    # Phase 1: cache check (serial)
    stat_map: dict[str, os.stat_result] = {}
    cache_hits: dict[str, dict] = {}
    to_process: list[Path] = []

    for path in paths:
        try:
            stat = path.stat()
        except PermissionError as e:
            print(f'\nWarning: no access to {path}: {e}', file=sys.stderr)
            continue
        stat_map[str(path)] = stat
        row = db.execute('SELECT * FROM videos WHERE path = ?', [str(path)]).fetchone()
        if row and row['mtime'] == stat.st_mtime and row['size'] == stat.st_size:
            if intensive_seconds > 0 and row['intensive_n'] != intensive_seconds:
                to_process.append(path)
            else:
                cache_hits[str(path)] = dict(row)
        else:
            to_process.append(path)

    # Phase 2: parallel processing (ffprobe + frame extraction)
    results_map: dict[str, dict] = {}

    def _process_video(path: Path) -> dict:
        stat = stat_map[str(path)]
        meta = ffprobe_metadata(path)
        if 'error' in meta:
            return {
                'path': str(path), 'filename': path.name,
                'size': stat.st_size, 'mtime': stat.st_mtime,
                'error': meta['error'],
            }
        md5 = compute_md5(path)
        duration = meta['duration'] or 0
        frame_hashes = []
        frames_b64 = []
        thumbnail_b64 = ''
        for fraction in VIDEO_FRAME_POSITIONS:
            pos = duration * fraction
            frame_bytes = extract_frame(path, pos)
            frame_hashes.append(_frame_bytes_to_hash(frame_bytes) if frame_bytes else None)
            frames_b64.append(_frame_bytes_to_preview(frame_bytes) if frame_bytes else '')
            if fraction == 0.50 and not thumbnail_b64:
                thumbnail_b64 = _frame_bytes_to_b64(frame_bytes) if frame_bytes else ''
        intensive_start_hashes: list[str] = []
        intensive_end_hashes: list[str] = []
        if intensive_seconds > 0:
            intensive_start_hashes, intensive_end_hashes = extract_video_edge_hashes(path, intensive_seconds, duration)
        return {
            'path': str(path), 'filename': path.name,
            'size': stat.st_size, 'mtime': stat.st_mtime,
            'md5': md5, 'duration': meta['duration'],
            'width': meta['width'], 'height': meta['height'],
            'codec': meta['codec'], 'bitrate': meta['bitrate'],
            'frame_hashes': json.dumps(frame_hashes),
            'thumbnail_b64': thumbnail_b64,
            'frames_b64': json.dumps(frames_b64),
            'intensive_start': json.dumps(intensive_start_hashes),
            'intensive_end': json.dumps(intensive_end_hashes),
            'intensive_n': intensive_seconds if intensive_seconds > 0 else None,
            'error': None,
        }

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        future_map = {ex.submit(_process_video, p): p for p in to_process}
        for future in concurrent.futures.as_completed(future_map):
            done += 1
            path = future_map[future]
            pct_total = len(cache_hits) + done
            print(f'\r\033[KProcessing video {pct_total}/{total}: {path.name}', end='', flush=True)
            if progress_cb:
                progress_cb(pct_total, total, path.name)
            try:
                results_map[str(path)] = future.result()
            except Exception as e:
                stat = stat_map[str(path)]
                results_map[str(path)] = {
                    'path': str(path), 'filename': path.name,
                    'size': stat.st_size, 'mtime': stat.st_mtime,
                    'error': str(e),
                }

    # Phase 3: serial DB write
    db.execute('BEGIN')
    for path in to_process:
        r = results_map.get(str(path))
        if not r:
            continue
        if r.get('error') and r.get('duration') is None:
            db.execute(
                """INSERT OR REPLACE INTO videos
                   (path, filename, size, mtime, error, processed_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [r['path'], r['filename'], r['size'], r['mtime'],
                 r['error'], time.time()]
            )
        else:
            db.execute(
                """INSERT OR REPLACE INTO videos
                   (path, filename, size, mtime, md5, duration, width, height,
                    codec, bitrate, frame_hashes, thumbnail_b64, frames_b64,
                    intensive_start, intensive_end, intensive_n, error, processed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [r['path'], r['filename'], r['size'], r['mtime'],
                 r.get('md5'), r.get('duration'), r.get('width'), r.get('height'),
                 r.get('codec'), r.get('bitrate'),
                 r.get('frame_hashes'), r.get('thumbnail_b64'), r.get('frames_b64'),
                 r.get('intensive_start'), r.get('intensive_end'), r.get('intensive_n'),
                 r.get('error'), time.time()]
            )
    db.execute('COMMIT')

    print()

    # Assemble results in original order
    results = []
    for path in paths:
        k = str(path)
        if k in cache_hits:
            results.append(cache_hits[k])
        elif k in results_map:
            results.append(results_map[k])
    return results


# ===========================================================================
# Video — duplicate detection
# ===========================================================================

def find_exact_video_duplicates(rows: list[dict]) -> list[list[dict]]:
    """Finds exact video duplicates via MD5 (with size pre-filter)."""
    size_counter = Counter(z['size'] for z in rows)
    candidates = [z for z in rows if size_counter[z['size']] >= 2]

    groups: dict[str, list[dict]] = defaultdict(list)
    for z in candidates:
        if z['md5']:
            groups[z['md5']].append(z)

    return [g for g in groups.values() if len(g) >= 2]


def _compare_frames(hashes_a: list, hashes_b: list) -> list:
    """
    Compares two frame-hash lists and returns the Hamming distance per frame position.
    None if a hash is missing or invalid.
    """
    distances = []
    for h_a, h_b in zip(hashes_a, hashes_b):
        if h_a is None or h_b is None:
            distances.append(None)
            continue
        try:
            distances.append(int(imagehash.hex_to_hash(h_a) - imagehash.hex_to_hash(h_b)))
        except Exception:
            distances.append(None)
    return distances


def find_visual_video_duplicates(
    all_rows: list[dict],
    exact_paths: set[str],
    frame_threshold: int = VIDEO_FRAME_THRESHOLD,
    min_matches: int = VIDEO_MIN_MATCHES,
    duration_tolerance: float = VIDEO_DURATION_TOLERANCE,
) -> list[list[dict]]:
    """
    Finds visual video duplicates.
    Stage 1: duration pre-filter (±VIDEO_DURATION_TOLERANCE seconds)
    Stage 2: frame-hash comparison — at least VIDEO_MIN_MATCHES of 5 frames must match
    """
    valid = [
        z for z in all_rows
        if z.get('error') is None
        and z['path'] not in exact_paths
        and z.get('frame_hashes') is not None
        and z.get('duration') is not None
    ]

    if not valid:
        return []

    # Parse frame hashes from JSON
    for z in valid:
        if isinstance(z['frame_hashes'], str):
            z['_fh_parsed'] = json.loads(z['frame_hashes'])
        else:
            z['_fh_parsed'] = z['frame_hashes'] or []

    visited: set[str] = set()
    groups = []

    for i, z_i in enumerate(valid):
        if z_i['path'] in visited:
            continue
        group = [z_i]
        visited.add(z_i['path'])

        for j in range(i + 1, len(valid)):
            z_j = valid[j]
            if z_j['path'] in visited:
                continue

            # Stage 1: duration pre-filter
            if abs((z_i['duration'] or 0) - (z_j['duration'] or 0)) > duration_tolerance:
                continue

            # Stage 2: frame-hash comparison
            distances = _compare_frames(z_i['_fh_parsed'], z_j['_fh_parsed'])
            matches = sum(1 for d in distances if d is not None and d <= frame_threshold)
            if matches >= min_matches:
                z_j_copy = dict(z_j)
                z_j_copy['_treffer_anzahl'] = matches
                z_j_copy['_frame_distances'] = distances
                z_j_copy['_frame_matches'] = [
                    (d is not None and d <= frame_threshold) for d in distances
                ]
                group.append(z_j_copy)
                visited.add(z_j['path'])

        if len(group) >= 2:
            groups.append(group)

    return groups


def find_intensive_video_duplicates(
    all_rows: list[dict],
    exact_paths: set[str],
    threshold: int = 10,
    min_fraction: float = 0.3,
) -> list[list[dict]]:
    """
    Compares videos using their start and end blocks (intensive mode).
    All-pairs comparison: every frame from block A is compared against every frame in block B.
    No duration pre-filter. A block matches if min_fraction of frames find a counterpart.
    Duplicate detected if start block OR end block matches.
    """
    valid = [
        z for z in all_rows
        if not z.get('error') and z['path'] not in exact_paths
        and z.get('intensive_start') and z.get('intensive_end')
    ]

    for z in valid:
        z['_is'] = json.loads(z['intensive_start']) if isinstance(z['intensive_start'], str) else (z['intensive_start'] or [])
        z['_ie'] = json.loads(z['intensive_end']) if isinstance(z['intensive_end'], str) else (z['intensive_end'] or [])

    def _count_block_matches(hashes_a: list[str], hashes_b: list[str]) -> tuple[int, int]:
        """All-pairs: how many frames from hashes_a find a match in hashes_b?"""
        if not hashes_a or not hashes_b:
            return 0, 0
        parsed_b = []
        for hb in hashes_b:
            try:
                parsed_b.append(imagehash.hex_to_hash(hb))
            except Exception:
                pass
        matches = 0
        for ha in hashes_a:
            if not ha:
                continue
            try:
                hash_a = imagehash.hex_to_hash(ha)
                if any(int(hash_a - hb) <= threshold for hb in parsed_b):
                    matches += 1
            except Exception:
                continue
        return matches, len(hashes_a)

    visited: set[str] = set()
    groups = []

    for i, z_i in enumerate(valid):
        if z_i['path'] in visited:
            continue
        group = [z_i]
        visited.add(z_i['path'])

        for j in range(i + 1, len(valid)):
            z_j = valid[j]
            if z_j['path'] in visited:
                continue

            start_matches, start_n = _count_block_matches(z_i['_is'], z_j['_is'])
            end_matches, end_n = _count_block_matches(z_i['_ie'], z_j['_ie'])

            start_ok = start_n > 0 and (start_matches / start_n) >= min_fraction
            end_ok = end_n > 0 and (end_matches / end_n) >= min_fraction

            if start_ok or end_ok:
                z_j_copy = dict(z_j)
                z_j_copy['_intensive_start_treffer'] = start_matches
                z_j_copy['_intensive_end_treffer'] = end_matches
                z_j_copy['_intensive_start_n'] = start_n
                z_j_copy['_intensive_end_n'] = end_n
                group.append(z_j_copy)
                visited.add(z_j['path'])

        if len(group) >= 2:
            groups.append(group)

    return groups


# ===========================================================================
# Cross-dir duplicate detection (comparison mode)
# ===========================================================================

def find_cross_dir_exact_duplicates(rows_a: list[dict], rows_b: list[dict]) -> list[list[dict]]:
    """Finds files that are identical in dir A and dir B (same MD5)."""
    md5_to_a: dict[str, list[dict]] = defaultdict(list)
    for z in rows_a:
        if z.get('md5') and not z.get('error'):
            md5_to_a[z['md5']].append(z)
    groups = []
    seen_b: set[str] = set()
    for z_b in rows_b:
        if z_b.get('error') or not z_b.get('md5') or z_b['path'] in seen_b:
            continue
        matches = md5_to_a.get(z_b['md5'], [])
        if matches:
            groups.append([*matches, z_b])
            seen_b.add(z_b['path'])
    return groups


def find_cross_dir_visual_duplicates(
    rows_a: list[dict],
    rows_b: list[dict],
    exact_paths: set[str],
    threshold: int = PHASH_THRESHOLD,
) -> list[list[dict]]:
    """Finds visually similar images between dir A and dir B (pHash)."""
    valid_a = [z for z in rows_a if not z.get('error') and z.get('phash') and z['path'] not in exact_paths]
    valid_b = [z for z in rows_b if not z.get('error') and z.get('phash') and z['path'] not in exact_paths]
    seen_b: set[str] = set()
    groups = []
    for z_b in valid_b:
        if z_b['path'] in seen_b:
            continue
        try:
            h_b = imagehash.hex_to_hash(z_b['phash'])
        except Exception:
            continue
        matches = []
        for z_a in valid_a:
            try:
                dist = int(imagehash.hex_to_hash(z_a['phash']) - h_b)
            except Exception:
                continue
            if dist <= threshold:
                z_a_copy = dict(z_a)
                z_a_copy['_phash_distanz'] = dist
                matches.append(z_a_copy)
        if matches:
            z_b_copy = dict(z_b)
            z_b_copy['_phash_distanz'] = min(m['_phash_distanz'] for m in matches)
            groups.append([*matches, z_b_copy])
            seen_b.add(z_b['path'])
    return groups


def find_cross_dir_exact_video_duplicates(rows_a: list[dict], rows_b: list[dict]) -> list[list[dict]]:
    """Finds videos that are identical in dir A and dir B (same MD5)."""
    md5_to_a: dict[str, list[dict]] = defaultdict(list)
    for z in rows_a:
        if z.get('md5') and not z.get('error'):
            md5_to_a[z['md5']].append(z)
    groups = []
    seen_b: set[str] = set()
    for z_b in rows_b:
        if z_b.get('error') or not z_b.get('md5') or z_b['path'] in seen_b:
            continue
        matches = md5_to_a.get(z_b['md5'], [])
        if matches:
            groups.append([*matches, z_b])
            seen_b.add(z_b['path'])
    return groups


def find_cross_dir_visual_video_duplicates(
    rows_a: list[dict],
    rows_b: list[dict],
    exact_paths: set[str],
    frame_threshold: int = VIDEO_FRAME_THRESHOLD,
    min_matches: int = VIDEO_MIN_MATCHES,
    duration_tolerance: float = VIDEO_DURATION_TOLERANCE,
) -> list[list[dict]]:
    """Finds visually similar videos between dir A and dir B (frame hashes)."""
    valid_a = [z for z in rows_a if not z.get('error') and z.get('frame_hashes') and z['path'] not in exact_paths]
    valid_b = [z for z in rows_b if not z.get('error') and z.get('frame_hashes') and z['path'] not in exact_paths]
    for z in valid_a + valid_b:
        if isinstance(z.get('frame_hashes'), str):
            z['_fh_parsed'] = json.loads(z['frame_hashes'])
        else:
            z['_fh_parsed'] = z.get('frame_hashes') or []
    seen_b: set[str] = set()
    groups = []
    for z_b in valid_b:
        if z_b['path'] in seen_b:
            continue
        matches = []
        for z_a in valid_a:
            if abs((z_a.get('duration') or 0) - (z_b.get('duration') or 0)) > duration_tolerance:
                continue
            distances = _compare_frames(z_a['_fh_parsed'], z_b['_fh_parsed'])
            hits = sum(1 for d in distances if d is not None and d <= frame_threshold)
            if hits >= min_matches:
                z_a_copy = dict(z_a)
                z_a_copy['_treffer_anzahl'] = hits
                z_a_copy['_frame_distances'] = distances
                z_a_copy['_frame_matches'] = [d is not None and d <= frame_threshold for d in distances]
                matches.append(z_a_copy)
        if matches:
            z_b_copy = dict(z_b)
            groups.append([*matches, z_b_copy])
            seen_b.add(z_b['path'])
    return groups


# ===========================================================================
# Helper functions
# ===========================================================================

def sort_group(group: list[dict]) -> list[dict]:
    """
    Sorts a duplicate group so that the best original is at position 0.
    Criteria (descending):
      1. Highest resolution (width × height)
      2. Largest file size
      3. Oldest mtime (= most likely the original)
    """
    def sort_key(z: dict) -> tuple:
        pixels = (z.get('width') or 0) * (z.get('height') or 0)
        return (-pixels, -z.get('size', 0), z.get('mtime', 0))

    return sorted(group, key=sort_key)


# ===========================================================================
# HTML report
# ===========================================================================

def create_thumbnail_b64(path: Path) -> str:
    """
    Creates a base64-encoded JPEG thumbnail (max. THUMBNAIL_MAX pixels).
    Returns empty string on error.
    """
    try:
        with Image.open(path) as img:
            img.thumbnail((THUMBNAIL_MAX, THUMBNAIL_MAX), Image.LANCZOS)
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=75)
            return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ''


def _format_duration(seconds: float) -> str:
    """Formats seconds as M:SS or H:MM:SS."""
    s = int(seconds)
    h, rest = divmod(s, 3600)
    m, s = divmod(rest, 60)
    if h:
        return f'{h}:{m:02d}:{s:02d}'
    return f'{m}:{s:02d}'


def _format_filesize(byte_count: int) -> str:
    """Formats bytes as a human-readable size."""
    for unit in ('B', 'KB', 'MB', 'GB'):
        if byte_count < 1024:
            return f'{byte_count:.1f} {unit}'
        byte_count /= 1024
    return f'{byte_count:.1f} TB'


def _image_card_html(
    row: dict,
    card_id: str,
    is_original: bool = False,
    show_distance: bool = False,
) -> str:
    """Renders a single image card as an HTML string.

    is_original=True  → green border, no checkbox, badge "Keep"
    is_original=False → red border, checkbox (pre-checked), badge "Delete"
    """
    path = Path(row['path'])
    thumbnail = create_thumbnail_b64(path)

    if thumbnail:
        image_html = f'<img src="{thumbnail}" alt="{row["filename"]}">'
    else:
        image_html = '<div class="no-preview">Preview not available</div>'

    resolution = (
        f'{row["width"]}×{row["height"]}px'
        if row.get('width') and row.get('height')
        else 'unknown'
    )
    size_str = _format_filesize(row['size'])

    # Split path: show directory and filename separately
    dir_part = str(path.parent)
    file_part = path.name

    distance_html = ''
    if show_distance and '_phash_distanz' in row:
        distance_html = f'<span class="distance">pHash distance: {row["_phash_distanz"]}</span>'

    path_escaped = str(path).replace('"', '&quot;')
    if is_original:
        card_class = 'image-card original'
        badge = f'<span class="badge keep" id="badge_{card_id}">✓ Best Quality</span>'
        checkbox_html = f'<label class="cb-label original-cb-label"><input type="checkbox" class="delete-cb original-cb" id="{card_id}" data-path="{path_escaped}"> Also delete</label>'
    else:
        card_class = 'image-card delete-candidate'
        badge = '<span class="badge delete">✗ Delete</span>'
        checkbox_html = f'<label class="cb-label"><input type="checkbox" class="delete-cb" id="{card_id}" data-path="{path_escaped}" checked> Marked for deletion</label>'

    return f"""
        <div class="{card_class}">
            {badge}
            {image_html}
            <p class="filename">{file_part}</p>
            <p class="dir-path" title="{dir_part}">{dir_part}/</p>
            <p class="meta">{resolution} | {size_str}{distance_html}</p>
            {checkbox_html}
        </div>"""


def _video_card_html(
    row: dict,
    card_id: str,
    is_original: bool = False,
    show_matches: bool = False,
) -> str:
    """Renders a video card for the HTML report."""
    path = Path(row['path'])
    dir_part = str(path.parent)
    file_part = path.name

    thumbnail = row.get('thumbnail_b64') or ''
    if thumbnail:
        image_html = f'<img src="{thumbnail}" alt="{file_part}">'
    else:
        image_html = '<div class="no-preview">Preview not available</div>'

    resolution = (
        f'{row["width"]}×{row["height"]}px'
        if row.get('width') and row.get('height')
        else 'unknown'
    )
    duration_str = _format_duration(row['duration']) if row.get('duration') else '?'
    size_str = _format_filesize(row['size'])
    codec = row.get('codec') or '?'
    bitrate = f'{row["bitrate"]} kbps' if row.get('bitrate') else ''
    meta_parts = [duration_str, resolution, codec]
    if bitrate:
        meta_parts.append(bitrate)
    meta_parts.append(size_str)

    matches_html = ''
    if show_matches and '_treffer_anzahl' in row:
        matches_html = f'<span class="distance">{row["_treffer_anzahl"]}/5 frames identical</span>'

    path_escaped = str(path).replace('"', '&quot;')
    if is_original:
        card_class = 'image-card original'
        badge = '<span class="badge keep">✓ Best Quality</span>'
        checkbox_html = f'<label class="cb-label original-cb-label"><input type="checkbox" class="delete-cb original-cb" id="{card_id}" data-path="{path_escaped}"> Also delete</label>'
    else:
        card_class = 'image-card delete-candidate'
        badge = '<span class="badge delete">✗ Delete</span>'
        checkbox_html = f'<label class="cb-label"><input type="checkbox" class="delete-cb" id="{card_id}" data-path="{path_escaped}" checked> Marked for deletion</label>'

    return f"""
        <div class="{card_class}">
            {badge}
            {image_html}
            <p class="filename">{file_part}</p>
            <p class="dir-path" title="{dir_part}">{dir_part}/</p>
            <p class="meta">{' | '.join(meta_parts)}{matches_html}</p>
            {checkbox_html}
        </div>"""


def create_html_report(
    directory: Path,
    exact_groups: list[list[dict]],
    visual_groups: list[list[dict]],
    error_files: list[dict],
    output_path: Path,
    video_exact_groups: Optional[list[list[dict]]] = None,
    video_visual_groups: Optional[list[list[dict]]] = None,
    video_errors: Optional[list[dict]] = None,
) -> None:
    """Creates the self-contained HTML report."""

    video_exact_groups = video_exact_groups or []
    video_visual_groups = video_visual_groups or []
    video_errors = video_errors or []

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total_files = (sum(len(g) for g in exact_groups) +
                   sum(len(g) for g in visual_groups) +
                   sum(len(g) for g in video_exact_groups) +
                   sum(len(g) for g in video_visual_groups))

    all_groups = exact_groups + visual_groups + video_exact_groups + video_visual_groups
    wasted = sum(
        sum(z['size'] for z in g[1:])
        for g in all_groups
    )

    # HTML for exact duplicates
    exact_html = ''
    for idx, group in enumerate(exact_groups, 1):
        group = sort_group(group)
        cards = ''
        for k_idx, z in enumerate(group):
            card_id = f'e{idx}_{k_idx}'
            cards += _image_card_html(z, card_id=card_id, is_original=(k_idx == 0))
        exact_html += f"""
        <div class="group exact">
            <h3>Group #{idx} — MD5: <code>{group[0].get('md5', '?')}</code>
                — {len(group)} files
                — {_format_filesize(group[0]['size'])} each</h3>
            <div class="images-row">{cards}</div>
        </div>"""

    if not exact_html:
        exact_html = '<p class="empty">No exact duplicates found.</p>'

    # HTML for visual duplicates
    visual_html = ''
    for idx, group in enumerate(visual_groups, 1):
        group = sort_group(group)
        max_distance = max(z.get('_phash_distanz', 0) for z in group)
        cards = ''
        for k_idx, z in enumerate(group):
            card_id = f'v{idx}_{k_idx}'
            cards += _image_card_html(z, card_id=card_id, is_original=(k_idx == 0), show_distance=True)
        visual_html += f"""
        <div class="group visual">
            <h3>Group #{idx} — max. pHash distance: {max_distance}
                — {len(group)} files</h3>
            <div class="images-row">{cards}</div>
        </div>"""

    if not visual_html:
        visual_html = '<p class="empty">No visual duplicates found.</p>'

    # HTML for video duplicates (only if videos were scanned)
    video_report_html = ''
    if video_exact_groups is not None or video_visual_groups is not None:
        v_exact_html = ''
        for idx, group in enumerate(video_exact_groups, 1):
            group = sort_group(group)
            cards = ''
            for k_idx, z in enumerate(group):
                card_id = f've{idx}_{k_idx}'
                cards += _video_card_html(z, card_id=card_id, is_original=(k_idx == 0))
            v_exact_html += f"""
        <div class="group exact">
            <h3>Group #{idx} — MD5: <code>{group[0].get('md5', '?')}</code>
                — {len(group)} files</h3>
            <div class="images-row">{cards}</div>
        </div>"""
        if not v_exact_html:
            v_exact_html = '<p class="empty">No exact video duplicates found.</p>'

        v_visual_html = ''
        for idx, group in enumerate(video_visual_groups, 1):
            group = sort_group(group)
            cards = ''
            for k_idx, z in enumerate(group):
                card_id = f'vv{idx}_{k_idx}'
                cards += _video_card_html(z, card_id=card_id, is_original=(k_idx == 0), show_matches=True)
            v_visual_html += f"""
        <div class="group visual">
            <h3>Group #{idx} — {len(group)} Videos</h3>
            <div class="images-row">{cards}</div>
        </div>"""
        if not v_visual_html:
            v_visual_html = '<p class="empty">No visual video duplicates found.</p>'

        v_error_html = ''
        if video_errors:
            v_rows = ''.join(
                f'<tr><td class="path">{z["path"]}</td><td>{z.get("error", "")}</td></tr>'
                for z in video_errors
            )
            v_error_html = f"""
        <h2>Failed videos ({len(video_errors)})</h2>
        <table class="error-table">
            <thead><tr><th>Path</th><th>Error</th></tr></thead>
            <tbody>{v_rows}</tbody>
        </table>"""

        video_report_html = f"""
<h2>Videos — Exact Duplicates ({len(video_exact_groups)} groups)</h2>
{v_exact_html}

<h2>Videos — Visual Duplicates ({len(video_visual_groups)} groups)
    <small style="font-weight:normal;font-size:0.75em;color:#888;">
    (≥{VIDEO_MIN_MATCHES}/5 frames identical, duration tolerance ±{VIDEO_DURATION_TOLERANCE:.0f}s)
    </small>
</h2>
{v_visual_html}
{v_error_html}"""

    # HTML for erroneous image files
    error_html = ''
    if error_files:
        rows = ''.join(
            f'<tr><td class="path">{z["path"]}</td><td>{z.get("error", "")}</td></tr>'
            for z in error_files
        )
        error_html = f"""
        <h2>Failed files ({len(error_files)})</h2>
        <table class="error-table">
            <thead><tr><th>Path</th><th>Error</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>"""

    heif_notice = '' if HEIF_AVAILABLE else \
        '<p class="notice">Note: pillow-heif not installed — HEIC/HEIF files are not supported.</p>'

    n_exact = len(exact_groups)
    n_visual = len(visual_groups)
    card_width = THUMBNAIL_MAX + 20
    wasted_str = _format_filesize(wasted)
    video_groups_br = '<br>' if (video_exact_groups or video_visual_groups) else ''
    video_exact_line = (
        f'<b>Exact duplicate groups (videos):</b> {len(video_exact_groups)}<br>'
        if video_exact_groups is not None else ''
    )
    video_visual_line = (
        f'<b>Visual duplicate groups (videos):</b> {len(video_visual_groups)}<br>'
        if video_visual_groups is not None else ''
    )

    html = REPORT_TEMPLATE.format(
        directory=directory, now=now,
        n_exact=n_exact, n_visual=n_visual,
        total_files=total_files, wasted_str=wasted_str,
        heif_notice=heif_notice, exact_html=exact_html, visual_html=visual_html,
        error_html=error_html, video_report_html=video_report_html,
        video_groups_br=video_groups_br,
        video_exact_line=video_exact_line, video_visual_line=video_visual_line,
        THUMBNAIL_MAX=THUMBNAIL_MAX, card_width=card_width,
        PHASH_THRESHOLD=PHASH_THRESHOLD,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding='utf-8')
    print(f'HTML report saved: {output_path}')
