#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — Interactive web interface for the duplicate finder.

Usage:
  python app.py -d /my/media/directory
  python app.py -d /my/media/directory --port 8080

Dependencies: pip install fastapi uvicorn pillow imagehash
"""

import argparse
import asyncio
import hashlib
import hmac
import io
import json
import os
import secrets
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
    from pydantic import BaseModel, Field, field_validator
    import uvicorn
except ImportError:
    print('Error: FastAPI/uvicorn not installed.')
    print('Install: pip install fastapi uvicorn')
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print('Error: Pillow not installed. pip install Pillow imagehash')
    sys.exit(1)

# engine.py must be in the same directory
_DIR = Path(__file__).parent
sys.path.insert(0, str(_DIR))
try:
    import engine as fd
except ImportError:
    print('Error: engine.py not found in the same directory.')
    sys.exit(1)


# ===========================================================================
# Scan log messages (DE/EN)
# ===========================================================================

SCAN_MESSAGES = {
    'de': {
        'db_connect':        'Verbinde mit Datenbank…',
        'scan_images_dir':   'Scanne {dir} nach Bildern…',
        'images_found':      '{n1} Bilder in {d1}, {n2} in {d2}. Verarbeite…',
        'images_found_one':  '{n} Bilder gefunden. Verarbeite…',
        'img_progress':      '{dir} Bild {i}/{total}: {name}',
        'search_exact_img':  'Suche exakte Cross-Dir Bild-Duplikate…',
        'search_visual_img': 'Suche visuelle Cross-Dir Bild-Duplikate (pHash ≤ {t})…',
        'no_images':         'Keine Bilddateien gefunden.',
        'scan_videos':       'Scanne Verzeichnis nach Videos…',
        'vid_progress':      'Video {i}/{total}: {name}',
        'search_intensive':  'Suche Intensiv-Video-Duplikate (Start/End-Block)…',
        'scan_complete':     'Scan abgeschlossen!',
        'scan_cancelled':    '⏹ Scan abgebrochen.',
        'scan_error':        'FEHLER: {msg}',
    },
    'en': {
        'db_connect':        'Connecting to database…',
        'scan_images_dir':   'Scanning {dir} for images…',
        'images_found':      '{n1} images in {d1}, {n2} in {d2}. Processing…',
        'images_found_one':  '{n} images found. Processing…',
        'img_progress':      '{dir} image {i}/{total}: {name}',
        'search_exact_img':  'Searching for exact cross-dir image duplicates…',
        'search_visual_img': 'Searching for visual cross-dir image duplicates (pHash ≤ {t})…',
        'no_images':         'No image files found.',
        'scan_videos':       'Scanning directory for videos…',
        'vid_progress':      'Video {i}/{total}: {name}',
        'search_intensive':  'Searching for intensive video duplicates (start/end block)…',
        'scan_complete':     'Scan complete!',
        'scan_cancelled':    '⏹ Scan cancelled.',
        'scan_error':        'ERROR: {msg}',
    }
}


# ===========================================================================
# App & global state
# ===========================================================================

app = FastAPI(title='Duplicate Finder')

BASEDIR: Path = None  # set at startup
VERBOSE: bool = False

# job_id → { status, log, results, error }
JOBS: dict = {}
JOBS_LOCK = threading.Lock()


def log_action(text: str) -> None:
    """Prints an important action with timestamp to the console."""
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {text}', flush=True)


# ===========================================================================
# Authentication
# ===========================================================================

def _random_secret() -> str:
    s = secrets.token_hex(32)
    log_action('WARNING: AUTH_SECRET not set — using random key. '
               'Sessions will be invalidated after restart. Please set AUTH_SECRET as an env variable.')
    return s


AUTH_SECRET: str = os.environ.get('AUTH_SECRET', '') or _random_secret()
COOKIE_NAME = 'dupfinder_session'
SESSION_DAYS = 30

# Paths accessible without a cookie
_PUBLIC_PATHS = {'/', '/api/login', '/api/auth/check', '/api/auth/initial-setup', '/translations.js', '/styles.css'}


def create_session(username: str) -> str:
    """Returns a signed cookie value: '{user}:{ts}:{hmac}'."""
    ts = int(time.time())
    msg = f'{username}:{ts}'.encode()
    sig = hmac.new(AUTH_SECRET.encode(), msg, hashlib.sha256).hexdigest()
    return f'{username}:{ts}:{sig}'


def verify_session(cookie_value: str) -> Optional[str]:
    """Returns the username if the cookie is valid, otherwise None."""
    try:
        user, ts_str, sig = cookie_value.split(':', 2)
        msg = f'{user}:{ts_str}'.encode()
        expected = hmac.new(AUTH_SECRET.encode(), msg, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        if time.time() - int(ts_str) > SESSION_DAYS * 86400:
            return None
        return user
    except Exception:
        return None


@app.middleware('http')
async def auth_middleware(request: Request, call_next):
    if request.url.path in _PUBLIC_PATHS:
        return await call_next(request)
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie or not verify_session(cookie):
        return JSONResponse({'detail': 'Not logged in.'}, status_code=401)
    return await call_next(request)


# ===========================================================================
# Pydantic models
# ===========================================================================

class ScanRequest(BaseModel):
    dir1: str
    dir2: Optional[str] = None
    media_type: str = 'images'
    phash_threshold: int = Field(8, ge=0, le=16)
    video_frame_threshold: int = Field(10, ge=0, le=64)
    video_min_matches: int = Field(4, ge=1, le=5)
    video_duration_tolerance: float = Field(3.0, ge=0.0, le=3600.0)
    video_intensive: bool = False
    video_intensive_seconds: int = Field(30, ge=5, le=120)
    video_intensive_threshold: int = Field(10, ge=0, le=64)
    video_intensive_min_ratio: float = Field(0.3, ge=0.1, le=1.0)
    workers: int = Field(4, ge=1, le=32)
    lang: str = 'de'


class DeleteRequest(BaseModel):
    paths: list[str]


class LoginRequest(BaseModel):
    username: str
    password: str


class UserRequest(BaseModel):
    username: str
    password: str

    @field_validator('username')
    @classmethod
    def no_colon(cls, v):
        v = v.strip()
        if ':' in v:
            raise ValueError('Username must not contain a colon.')
        if not v:
            raise ValueError('Username must not be empty.')
        return v


class PasswordRequest(BaseModel):
    password: str


# ===========================================================================
# Job management
# ===========================================================================

def _cleanup_jobs():
    """Removes completed jobs from the in-memory dict that are older than 2 hours."""
    cutoff = time.time() - 7200
    with JOBS_LOCK:
        to_delete = [
            jid for jid, j in JOBS.items()
            if j['status'] in ('done', 'error', 'cancelled')
            and j.get('_started_at', 0) < cutoff
        ]
        for jid in to_delete:
            del JOBS[jid]


def _start_next_job():
    """Starts the oldest queued job from the DB queue."""
    try:
        with fd.db_context(fd.DB_PATH) as db:
            row = db.execute(
                'SELECT job_id, settings, started_at FROM scan_jobs '
                'WHERE status = ? ORDER BY started_at ASC LIMIT 1',
                ['queued']
            ).fetchone()
        if not row:
            return
        job_id = row['job_id']
        request = ScanRequest(**json.loads(row['settings']))
        started_at = row['started_at']
        with JOBS_LOCK:
            JOBS[job_id] = {
                'status': 'running', 'log': [], 'results': None, 'error': None,
                'stop_event': threading.Event(), '_started_at': started_at,
            }
        with fd.db_context(fd.DB_PATH) as db:
            db.execute('UPDATE scan_jobs SET status = ? WHERE job_id = ?', ['running', job_id])
            db.commit()
        log_action(f'QUEUE           Job [{job_id}] started')
        threading.Thread(target=scan_worker, args=(job_id, request), daemon=True).start()
    except Exception as exc:
        log_action(f'QUEUE ERROR     {exc}')


# ===========================================================================
# Scan worker
# ===========================================================================

def scan_worker(job_id: str, request: ScanRequest) -> None:
    stop_event: threading.Event = JOBS[job_id]['stop_event']

    # Retrieve lang from job settings stored in DB
    try:
        with fd.db_context(fd.DB_PATH) as _db:
            _row = _db.execute(
                'SELECT settings FROM scan_jobs WHERE job_id = ?', [job_id]
            ).fetchone()
        if _row and _row['settings']:
            _settings = json.loads(_row['settings'])
            _lang = _settings.get('lang', 'de')
        else:
            _lang = request.lang
    except Exception:
        _lang = request.lang

    m = SCAN_MESSAGES.get(_lang, SCAN_MESSAGES['de'])

    def log(text: str, percent: Optional[int] = None) -> None:
        with JOBS_LOCK:
            JOBS[job_id]['log'].append({'text': text, 'percent': percent})

    def check_stop():
        if stop_event.is_set():
            raise InterruptedError('Scan cancelled by user.')

    db = None
    try:
        dir1 = Path(request.dir1).resolve()
        if not dir1.is_dir():
            raise ValueError(f'"{dir1}" is not a valid directory.')

        log_action(f'SCAN started    [{job_id}]  {dir1}  (type: {request.media_type})')
        log(m['db_connect'], 2)
        db = fd.db_connect(fd.DB_PATH)

        exact_groups: list = []
        visual_groups: list = []
        error_files: list = []
        video_exact_groups: list = []
        video_visual_groups: list = []
        video_intensive_groups: list = []
        video_errors: list = []

        compare_mode = bool(request.dir2)
        dir2 = Path(request.dir2).resolve() if compare_mode else None

        if compare_mode:
            log_action(f'SCAN compare    [{job_id}]  Dir1={dir1}  Dir2={dir2}')

        # --- Image pipeline ---
        if request.media_type in ('images', 'both'):
            check_stop()
            if compare_mode:
                log(m['scan_images_dir'].format(dir='Dir 1'), 5)
                paths_a = fd.scan_directory(dir1)
                log(m['scan_images_dir'].format(dir='Dir 2'), 7)
                paths_b = fd.scan_directory(dir2)
                log(m['images_found'].format(n1=len(paths_a), d1='Dir 1', n2=len(paths_b), d2='Dir 2'), 10)

                def img_cb_a(i, total, name):
                    check_stop()
                    pct = 10 + int(25 * i / max(total, 1))
                    if i % max(1, total // 20) == 0 or i == total:
                        log(m['img_progress'].format(dir='Dir1', i=i, total=total, name=name), pct)

                def img_cb_b(i, total, name):
                    check_stop()
                    pct = 35 + int(25 * i / max(total, 1))
                    if i % max(1, total // 20) == 0 or i == total:
                        log(m['img_progress'].format(dir='Dir2', i=i, total=total, name=name), pct)

                rows_a = fd.process_files(paths_a, db, progress_cb=img_cb_a, workers=request.workers) if paths_a else []
                rows_b = fd.process_files(paths_b, db, progress_cb=img_cb_b, workers=request.workers) if paths_b else []
                error_files = [z for z in rows_a + rows_b if z.get('error')]
                valid_a = [z for z in rows_a if not z.get('error')]
                valid_b = [z for z in rows_b if not z.get('error')]

                check_stop()
                log(m['search_exact_img'], 62)
                exact_groups = fd.find_cross_dir_exact_duplicates(valid_a, valid_b)

                exact_paths = {z['path'] for g in exact_groups for z in g}
                check_stop()
                log(m['search_visual_img'].format(t=request.phash_threshold), 68)
                visual_groups = fd.find_cross_dir_visual_duplicates(
                    valid_a, valid_b, exact_paths, request.phash_threshold
                )
                log(
                    f'Images: {len(exact_groups)} exact, '
                    f'{len(visual_groups)} visual cross-dir groups.',
                    72,
                )
            else:
                log(m['scan_images_dir'].format(dir='directory'), 5)
                paths = fd.scan_directory(dir1)

                if paths:
                    log(m['images_found_one'].format(n=len(paths)), 10)

                    def img_cb(i, total, name):
                        check_stop()
                        pct = 10 + int(50 * i / total)
                        if i % max(1, total // 20) == 0 or i == total:
                            log(m['img_progress'].format(dir='', i=i, total=total, name=name).strip(), pct)

                    rows = fd.process_files(paths, db, progress_cb=img_cb, workers=request.workers)
                    error_files = [z for z in rows if z.get('error')]
                    valid = [z for z in rows if not z.get('error')]

                    check_stop()
                    log('Searching for exact image duplicates…', 62)
                    exact_groups = fd.find_exact_duplicates(valid)

                    exact_paths = {z['path'] for g in exact_groups for z in g}
                    check_stop()
                    log(m['search_visual_img'].format(t=request.phash_threshold), 68)
                    visual_groups = fd.find_visual_duplicates(
                        valid, exact_paths, request.phash_threshold
                    )
                    log(
                        f'Images: {len(exact_groups)} exact, '
                        f'{len(visual_groups)} visual groups.',
                        72,
                    )
                else:
                    log(m['no_images'], 72)

        # --- Video pipeline ---
        if request.media_type in ('videos', 'both'):
            check_stop()
            if not fd.ffmpeg_available():
                raise RuntimeError('ffprobe/ffmpeg not available.')

            if compare_mode:
                log(m['scan_videos'], 73)
                video_paths_a = fd.scan_videos(dir1)
                log(m['scan_videos'], 74)
                video_paths_b = fd.scan_videos(dir2)
                log(
                    f'{len(video_paths_a)} videos in Dir 1, {len(video_paths_b)} in Dir 2. Processing…',
                    75,
                )

                def video_cb_a(i, total, name):
                    check_stop()
                    pct = 75 + int(8 * i / max(total, 1))
                    if i % max(1, total // 10) == 0 or i == total:
                        log(m['vid_progress'].format(i=i, total=total, name=name), pct)

                def video_cb_b(i, total, name):
                    check_stop()
                    pct = 83 + int(8 * i / max(total, 1))
                    if i % max(1, total // 10) == 0 or i == total:
                        log(m['vid_progress'].format(i=i, total=total, name=name), pct)

                _intensive_sec = request.video_intensive_seconds if request.video_intensive else 0
                video_rows_a = fd.process_videos(video_paths_a, db, progress_cb=video_cb_a, workers=request.workers, intensive_seconds=_intensive_sec) if video_paths_a else []
                video_rows_b = fd.process_videos(video_paths_b, db, progress_cb=video_cb_b, workers=request.workers, intensive_seconds=_intensive_sec) if video_paths_b else []
                video_errors = [z for z in video_rows_a + video_rows_b if z.get('error')]
                video_valid_a = [z for z in video_rows_a if not z.get('error')]
                video_valid_b = [z for z in video_rows_b if not z.get('error')]

                check_stop()
                log('Searching for exact cross-dir video duplicates…', 91)
                video_exact_groups = fd.find_cross_dir_exact_video_duplicates(video_valid_a, video_valid_b)

                v_exact_paths = {z['path'] for g in video_exact_groups for z in g}
                check_stop()
                log('Searching for visual cross-dir video duplicates (frame sampling)…', 93)
                video_visual_groups = fd.find_cross_dir_visual_video_duplicates(
                    video_valid_a, video_valid_b, v_exact_paths,
                    request.video_frame_threshold,
                    request.video_min_matches,
                    request.video_duration_tolerance,
                )
                if request.video_intensive:
                    check_stop()
                    log(m['search_intensive'], 94)
                    all_video_valid = video_valid_a + video_valid_b
                    video_intensive_groups = fd.find_intensive_video_duplicates(
                        all_video_valid, v_exact_paths,
                        request.video_intensive_threshold,
                        request.video_intensive_min_ratio,
                    )
                log(
                    f'Videos: {len(video_exact_groups)} exact, '
                    f'{len(video_visual_groups)} visual, '
                    f'{len(video_intensive_groups)} intensive cross-dir groups.',
                    95,
                )
            else:
                log(m['scan_videos'], 73)
                video_paths = fd.scan_videos(dir1)

                if video_paths:
                    log(f'{len(video_paths)} video files found. Processing (this may take a while)…', 75)

                    def video_cb(i, total, name):
                        check_stop()
                        pct = 75 + int(15 * i / total)
                        if i % max(1, total // 10) == 0 or i == total:
                            log(m['vid_progress'].format(i=i, total=total, name=name), pct)

                    video_rows = fd.process_videos(
                        video_paths, db, progress_cb=video_cb, workers=request.workers,
                        intensive_seconds=request.video_intensive_seconds if request.video_intensive else 0,
                    )
                    video_errors = [z for z in video_rows if z.get('error')]
                    video_valid = [z for z in video_rows if not z.get('error')]

                    check_stop()
                    log('Searching for exact video duplicates…', 91)
                    video_exact_groups = fd.find_exact_video_duplicates(video_valid)

                    v_exact_paths = {z['path'] for g in video_exact_groups for z in g}
                    check_stop()
                    log('Searching for visual video duplicates (frame sampling)…', 93)
                    video_visual_groups = fd.find_visual_video_duplicates(
                        video_valid, v_exact_paths,
                        request.video_frame_threshold,
                        request.video_min_matches,
                        request.video_duration_tolerance,
                    )
                    if request.video_intensive:
                        check_stop()
                        log(m['search_intensive'], 94)
                        video_intensive_groups = fd.find_intensive_video_duplicates(
                            video_valid, v_exact_paths,
                            request.video_intensive_threshold,
                            request.video_intensive_min_ratio,
                        )
                    log(
                        f'Videos: {len(video_exact_groups)} exact, '
                        f'{len(video_visual_groups)} visual, '
                        f'{len(video_intensive_groups)} intensive groups.',
                        95,
                    )
                else:
                    log('No video files found.', 95)

        def sort_all(groups):
            return [fd.sort_group(g) for g in groups]

        log(m['scan_complete'], 100)
        total_groups = (len(exact_groups) + len(visual_groups) +
                        len(video_exact_groups) + len(video_visual_groups) +
                        len(video_intensive_groups))
        log_action(f'SCAN done       [{job_id}]  {total_groups} group(s) found')

        try:
            with fd.db_context(fd.DB_PATH) as db:
                db.execute(
                    'INSERT OR REPLACE INTO directory_scans (path, last_scan) VALUES (?,?)',
                    (str(dir1), time.time())
                )
                db.commit()
        except Exception:
            pass

        results_for_db = {
            'dir1': str(dir1),
            'dir2': str(dir2) if dir2 else None,
            'image_exact': sort_all(exact_groups),
            'image_visual': sort_all(visual_groups),
            'video_exact': sort_all(video_exact_groups),
            'video_visual': sort_all(video_visual_groups),
            'video_intensive': sort_all(video_intensive_groups),
            'error': error_files,
            'video_error': video_errors,
            'settings': request.model_dump(),
        }
        try:
            results_json = json.dumps(results_for_db, ensure_ascii=False)
            with fd.db_context(fd.DB_PATH) as db:
                db.execute(
                    '''INSERT OR REPLACE INTO scan_jobs
                       (job_id, status, dir1, started_at, ended_at, results, settings)
                       VALUES (?, 'done', ?, ?, ?, ?, ?)''',
                    (job_id, str(dir1),
                     JOBS[job_id]['_started_at'], time.time(),
                     results_json, json.dumps(request.model_dump()))
                )
                db.commit()
        except Exception as exc:
            log_action(f'JOB-DB ERROR    {exc}')

        with JOBS_LOCK:
            JOBS[job_id]['status'] = 'done'
            JOBS[job_id]['results'] = {
                'dir1': str(dir1),
                'dir2': str(dir2) if dir2 else None,
                'image_exact': sort_all(exact_groups),
                'image_visual': sort_all(visual_groups),
                'video_exact': sort_all(video_exact_groups),
                'video_visual': sort_all(video_visual_groups),
                'video_intensive': sort_all(video_intensive_groups),
                'error': error_files,
                'video_error': video_errors,
                'settings': request.model_dump(),
            }

    except InterruptedError:
        log_action(f'SCAN cancelled  [{job_id}]')
        with JOBS_LOCK:
            JOBS[job_id]['status'] = 'cancelled'
            JOBS[job_id]['log'].append({'text': m['scan_cancelled'], 'percent': None})
        try:
            with fd.db_context(fd.DB_PATH) as _db:
                _db.execute(
                    '''INSERT OR REPLACE INTO scan_jobs
                       (job_id, status, dir1, started_at, ended_at)
                       VALUES (?, 'cancelled', ?, ?, ?)''',
                    (job_id, request.dir1,
                     JOBS[job_id]['_started_at'], time.time())
                )
                _db.commit()
        except Exception:
            pass

    except Exception as exc:
        log_action(f'SCAN ERROR      [{job_id}]  {exc}')
        with JOBS_LOCK:
            JOBS[job_id]['status'] = 'error'
            JOBS[job_id]['log'].append({'text': m['scan_error'].format(msg=exc), 'percent': None})
            JOBS[job_id]['error'] = str(exc)
        try:
            with fd.db_context(fd.DB_PATH) as _db:
                _db.execute(
                    '''INSERT OR REPLACE INTO scan_jobs
                       (job_id, status, dir1, started_at, ended_at)
                       VALUES (?, 'error', ?, ?, ?)''',
                    (job_id, request.dir1,
                     JOBS[job_id]['_started_at'], time.time())
                )
                _db.commit()
        except Exception:
            pass
    finally:
        if db:
            db.close()
        _start_next_job()


# ===========================================================================
# API routes
# ===========================================================================

@app.get('/api/directories')
def api_directories() -> JSONResponse:
    """Lists subdirectories of BASEDIR (1 level deep)."""
    entries = []
    try:
        for p in sorted(BASEDIR.iterdir(), key=lambda p: p.name.lower()):
            if p.is_dir() and not p.name.startswith('.'):
                entries.append({'name': p.name, 'path': str(p)})
    except PermissionError:
        pass
    return JSONResponse({'basedir': str(BASEDIR), 'directories': entries})


@app.get('/api/scan/timestamps')
def api_scan_timestamps() -> JSONResponse:
    try:
        with fd.db_context(fd.DB_PATH) as db:
            rows = db.execute('SELECT path, last_scan FROM directory_scans').fetchall()
        return JSONResponse({z['path']: z['last_scan'] for z in rows})
    except Exception as e:
        log_action(f'ERROR scan_timestamps: {e}')
        return JSONResponse({})


@app.get('/api/subdirectories')
def api_subdirectories(path: str) -> JSONResponse:
    """Lists subdirectories of a given path."""
    p = Path(path).resolve()
    if not _path_allowed(p):
        raise HTTPException(403, 'Path outside BASEDIR.')
    entries = []
    try:
        for sub in sorted(p.iterdir(), key=lambda p: p.name.lower()):
            if sub.is_dir() and not sub.name.startswith('.'):
                entries.append({'name': sub.name, 'path': str(sub)})
    except PermissionError:
        pass
    return JSONResponse({'directories': entries})


@app.post('/api/scan')
def api_scan_start(request: ScanRequest) -> JSONResponse:
    """Starts a new scan job or queues it."""
    dir1 = Path(request.dir1).resolve()
    if not _path_allowed(dir1):
        raise HTTPException(403, 'Path outside BASEDIR.')
    if not dir1.is_dir():
        raise HTTPException(400, f'Not a directory: {dir1}')
    if request.dir2:
        v2 = Path(request.dir2).resolve()
        if not _path_allowed(v2):
            raise HTTPException(403, 'Directory 2 outside BASEDIR.')
        if not v2.is_dir():
            raise HTTPException(400, f'Not a directory: {v2}')

    _cleanup_jobs()
    job_id = str(uuid.uuid4())[:8]
    now = time.time()

    with JOBS_LOCK:
        running = any(j['status'] == 'running' for j in JOBS.values())

    if running:
        # Enqueue in DB — not yet in JOBS
        try:
            with fd.db_context(fd.DB_PATH) as db:
                db.execute(
                    '''INSERT INTO scan_jobs
                       (job_id, status, dir1, started_at, settings)
                       VALUES (?, 'queued', ?, ?, ?)''',
                    (job_id, request.dir1, now, json.dumps(request.model_dump()))
                )
                db.commit()
        except Exception as exc:
            raise HTTPException(500, f'Queue error: {exc}')
        log_action(f'QUEUE           Job [{job_id}] enqueued: {request.dir1}')
        return JSONResponse({'job_id': job_id, 'queued': True})

    # Normal start
    with JOBS_LOCK:
        JOBS[job_id] = {
            'status': 'running', 'log': [], 'results': None, 'error': None,
            'stop_event': threading.Event(), '_started_at': now,
        }
    threading.Thread(target=scan_worker, args=(job_id, request), daemon=True).start()
    return JSONResponse({'job_id': job_id, 'queued': False})


@app.get('/api/scan/list')
def api_scan_list(limit: int = 20) -> JSONResponse:
    """Lists the most recently completed scan jobs from the DB."""
    try:
        with fd.db_context(fd.DB_PATH) as db:
            rows = db.execute(
                '''SELECT job_id, status, dir1, started_at, ended_at
                   FROM scan_jobs ORDER BY started_at DESC LIMIT ?''',
                [min(limit, 100)]
            ).fetchall()
        return JSONResponse({'jobs': [dict(z) for z in rows]})
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post('/api/scan/{job_id}/stop')
def api_scan_stop(job_id: str) -> JSONResponse:
    """Sets the stop flag for the running scan."""
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, 'Job not found.')
    if job['status'] != 'running':
        raise HTTPException(409, 'Scan is not running.')
    job['stop_event'].set()
    return JSONResponse({'ok': True})


@app.get('/api/scan/{job_id}/events')
async def api_scan_events(job_id: str):
    """SSE stream: progress log of the scan job. Also supports queue wait time."""
    if job_id not in JOBS:
        try:
            with fd.db_context(fd.DB_PATH) as db:
                row = db.execute('SELECT status FROM scan_jobs WHERE job_id = ?', [job_id]).fetchone()
        except Exception:
            row = None
        if not row:
            raise HTTPException(404, 'Job not found.')

    async def generator():
        # Phase 1: job still in DB queue — wait until it appears in JOBS
        while job_id not in JOBS:
            try:
                with fd.db_context(fd.DB_PATH) as db:
                    row = db.execute(
                        'SELECT status FROM scan_jobs WHERE job_id = ?', [job_id]
                    ).fetchone()
                if not row or row['status'] not in ('queued', 'running'):
                    yield f'data: {json.dumps({"status": "error"})}\n\n'
                    return
            except Exception:
                pass
            yield f'data: {json.dumps({"status": "queued"})}\n\n'
            await asyncio.sleep(2)

        # Phase 2: normal progress streaming
        cursor = 0
        while True:
            with JOBS_LOCK:
                job = JOBS.get(job_id, {})
                log = job.get('log', [])
                status = job.get('status', 'running')
                new_entries = log[cursor:]
                cursor += len(new_entries)

            for entry in new_entries:
                yield f'data: {json.dumps(entry)}\n\n'

            if status in ('done', 'error', 'cancelled'):
                yield f'data: {json.dumps({"status": status})}\n\n'
                return

            await asyncio.sleep(0.4)

    return StreamingResponse(
        generator(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@app.get('/api/scan/{job_id}/results')
def api_scan_results(job_id: str) -> JSONResponse:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if job:
        if job['status'] == 'running':
            raise HTTPException(425, 'Scan not yet complete.')
        if job['status'] == 'error':
            raise HTTPException(500, job.get('error', 'Unknown error'))
        return JSONResponse(job['results'])
    # Fallback: look up in DB (e.g. after server restart)
    try:
        with fd.db_context(fd.DB_PATH) as db:
            row = db.execute(
                'SELECT status, results FROM scan_jobs WHERE job_id = ?', [job_id]
            ).fetchone()
    except Exception as exc:
        raise HTTPException(500, str(exc))
    if not row:
        raise HTTPException(404, 'Job not found.')
    if row['status'] == 'error':
        raise HTTPException(500, 'Scan failed.')
    if row['status'] == 'cancelled':
        raise HTTPException(410, 'Scan was cancelled.')
    if not row['results']:
        raise HTTPException(404, 'No results available.')
    return JSONResponse(json.loads(row['results']))


@app.get('/api/thumbnail')
def api_thumbnail(path: str) -> Response:
    """Generates a JPEG thumbnail for the given path."""
    p = Path(path).resolve()
    if not _path_allowed(p) or not p.is_file():
        raise HTTPException(404, 'File not found or not allowed.')
    try:
        # Videos: fetch thumbnail_b64 from DB
        if p.suffix.lower() in fd.VIDEO_EXTENSIONS:
            with fd.db_context(fd.DB_PATH) as db:
                row = db.execute(
                    'SELECT thumbnail_b64 FROM videos WHERE path = ?', [str(p)]
                ).fetchone()
            if row and row['thumbnail_b64']:
                import base64
                data = row['thumbnail_b64']
                if ',' in data:
                    data = data.split(',', 1)[1]
                return Response(content=base64.b64decode(data), media_type='image/jpeg')
            raise HTTPException(404, 'No thumbnail available.')
        else:
            # Cache check: thumbnail_b64 from DB
            try:
                import base64
                with fd.db_context(fd.DB_PATH) as db:
                    row = db.execute(
                        'SELECT thumbnail_b64 FROM images WHERE path = ?', [str(p)]
                    ).fetchone()
                if row and row['thumbnail_b64']:
                    return Response(content=base64.b64decode(row['thumbnail_b64']),
                                    media_type='image/jpeg')
            except Exception:
                pass
            # Generate fresh
            with Image.open(p) as img:
                img.thumbnail((300, 300), Image.LANCZOS)
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=80)
                thumb_bytes = buf.getvalue()
            # Store in DB (fire-and-forget)
            try:
                import base64
                with fd.db_context(fd.DB_PATH) as db:
                    db.execute('UPDATE images SET thumbnail_b64 = ? WHERE path = ?',
                               [base64.b64encode(thumb_bytes).decode(), str(p)])
                    db.commit()
            except Exception:
                pass
            return Response(content=thumb_bytes, media_type='image/jpeg')
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get('/api/image')
def api_image(path: str) -> Response:
    """Delivers the original image (max. 1920x1440) for the lightbox."""
    p = Path(path).resolve()
    if not _path_allowed(p) or not p.is_file():
        raise HTTPException(404, 'File not found.')
    try:
        with Image.open(p) as img:
            img.thumbnail((1920, 1440), Image.LANCZOS)
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=92)
            return Response(content=buf.getvalue(), media_type='image/jpeg')
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get('/api/video')
def api_video(path: str):
    """Delivers the video file for the browser player (supports HTTP range requests)."""
    import mimetypes
    import subprocess
    p = Path(path).resolve()
    if not _path_allowed(p) or not p.is_file():
        raise HTTPException(404, 'File not found.')

    # Formats without native browser support → transcode live to MP4
    _TRANSCODE_FORMATS = {'.avi', '.wmv', '.flv'}
    if p.suffix.lower() in _TRANSCODE_FORMATS:
        cmd = [
            'ffmpeg', '-i', str(p),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-f', 'mp4',
            '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
            'pipe:1'
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        def _stream():
            try:
                while True:
                    chunk = proc.stdout.read(65536)
                    if not chunk:
                        break
                    yield chunk
            finally:
                proc.stdout.close()
                proc.wait()

        return StreamingResponse(_stream(), media_type='video/mp4')

    _MIME = {
        '.mkv':  'video/x-matroska',
        '.mov':  'video/quicktime',
        '.m4v':  'video/mp4',
        '.webm': 'video/webm',
    }
    mime = _MIME.get(p.suffix.lower()) or mimetypes.guess_type(str(p))[0] or 'video/mp4'
    return FileResponse(p, media_type=mime)


@app.post('/api/delete')
def api_delete(request: DeleteRequest) -> JSONResponse:
    """Deletes the specified files and writes them to the delete history."""
    deleted = []
    errors = []
    history_entries = []
    for path_str in request.paths:
        p = Path(path_str).resolve()
        if not _path_allowed(p):
            errors.append({'path': path_str, 'error': 'Outside BASEDIR'})
            continue
        try:
            size = p.stat().st_size  # read size BEFORE deleting
            p.unlink()
            deleted.append(path_str)
            history_entries.append((path_str, p.name, size, time.time()))
        except Exception as exc:
            errors.append({'path': path_str, 'error': str(exc)})
    if deleted:
        log_action(f'DELETED         {len(deleted)} file(s)')
        if VERBOSE:
            for p in deleted:
                print(f'  - {p}', flush=True)
        try:
            with fd.db_context(fd.DB_PATH) as db:
                db.executemany(
                    'INSERT INTO delete_history (path, filename, size, deleted_at) VALUES (?,?,?,?)',
                    history_entries,
                )
                db.commit()
        except Exception as exc:
            log_action(f'HISTORY ERROR   {exc}')
    if errors:
        log_action(f'DELETE ERROR    {len(errors)} file(s) could not be deleted')
        for f in errors:
            print(f'  ! {f["path"]}: {f["error"]}', flush=True)
    return JSONResponse({'deleted': deleted, 'errors': errors})


@app.get('/api/history')
def api_history() -> JSONResponse:
    """Returns the delete history with the total amount of freed space."""
    try:
        with fd.db_context(fd.DB_PATH) as db:
            rows = db.execute(
                'SELECT path, filename, size, deleted_at '
                'FROM delete_history ORDER BY deleted_at DESC'
            ).fetchall()
        entries = [dict(z) for z in rows]
        total_freed = sum(z['size'] for z in entries)
        return JSONResponse({'entries': entries, 'total_freed': total_freed})
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post('/api/history/clear')
def api_history_clear() -> JSONResponse:
    """Deletes the entire delete history from the database."""
    try:
        with fd.db_context(fd.DB_PATH) as db:
            db.execute('DELETE FROM delete_history')
            db.commit()
        log_action('HISTORY         History cleared')
        return JSONResponse({'ok': True})
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get('/api/database/stats')
def api_db_stats() -> JSONResponse:
    """Returns statistics about the scan cache (number of cached images/videos, DB size)."""
    try:
        with fd.db_context(fd.DB_PATH) as db:
            image_count = db.execute('SELECT COUNT(*) FROM images').fetchone()[0]
            video_count = db.execute('SELECT COUNT(*) FROM videos').fetchone()[0]
        db_size = fd.DB_PATH.stat().st_size if fd.DB_PATH.exists() else 0
        return JSONResponse({
            'images': image_count,
            'videos': video_count,
            'db_size': db_size,
            'db_path': str(fd.DB_PATH),
        })
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post('/api/database/reset')
def api_db_reset() -> JSONResponse:
    """Clears the scan cache (images + videos). The delete history is preserved."""
    try:
        with fd.db_context(fd.DB_PATH) as db:
            db.execute('DELETE FROM images')
            db.execute('DELETE FROM videos')
            db.commit()
            db.execute('VACUUM')
        log_action('DATABASE        Scan cache reset')
        return JSONResponse({'ok': True})
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post('/api/database/cleanup')
def api_db_cleanup() -> JSONResponse:
    """Removes cache entries for files that no longer exist on the filesystem."""
    try:
        with fd.db_context(fd.DB_PATH) as db:
            result = fd.db_cleanup(db)
        log_action(f'DATABASE        Cleaned: {result["images"]} images, {result["videos"]} videos removed')
        return JSONResponse(result)
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.get('/api/media-library')
def api_media_library(path: str) -> JSONResponse:
    """Lists all image and video files in a directory (non-recursive)."""
    p = Path(path).resolve()
    if not _path_allowed(p):
        raise HTTPException(403, 'Path outside BASEDIR.')
    if not p.is_dir():
        raise HTTPException(404, 'Directory not found.')
    all_extensions = fd.IMAGE_EXTENSIONS | fd.VIDEO_EXTENSIONS
    files = []
    try:
        for f in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            if f.is_file() and f.suffix.lower() in all_extensions:
                stat = f.stat()
                file_type = 'video' if f.suffix.lower() in fd.VIDEO_EXTENSIONS else 'image'
                files.append({
                    'path': str(f), 'filename': f.name,
                    'type': file_type, 'size': stat.st_size, 'mtime': stat.st_mtime,
                })
    except PermissionError:
        pass
    return JSONResponse({'path': str(p), 'files': files})


@app.get('/', response_class=HTMLResponse)
def frontend() -> str:
    return (_DIR / 'frontend.html').read_text(encoding='utf-8')


@app.get('/translations.js')
def translations_js() -> Response:
    content = (_DIR / 'translations.js').read_text(encoding='utf-8')
    return Response(content=content, media_type='application/javascript; charset=utf-8')


@app.get('/styles.css')
def styles_css() -> Response:
    content = (_DIR / 'styles.css').read_text(encoding='utf-8')
    return Response(content=content, media_type='text/css; charset=utf-8')


# ===========================================================================
# Auth endpoints
# ===========================================================================

@app.get('/api/auth/check')
def api_auth_check(request: Request) -> JSONResponse:
    """Returns whether the user is logged in and whether initial setup is needed."""
    cookie = request.cookies.get(COOKIE_NAME)
    username = verify_session(cookie) if cookie else None
    try:
        with fd.db_context(fd.DB_PATH) as db:
            count = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        first_setup = (count == 0)
    except Exception:
        first_setup = True
    return JSONResponse({
        'logged_in': username is not None,
        'username': username,
        'first_setup': first_setup,
    })


@app.post('/api/auth/initial-setup')
def api_initial_setup(request: UserRequest) -> JSONResponse:
    """Creates the first user — only allowed when no users exist yet."""
    try:
        with fd.db_context(fd.DB_PATH) as db:
            count = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            if count > 0:
                raise HTTPException(403, 'Initial setup already completed.')
            if not request.username.strip():
                raise HTTPException(400, 'Username must not be empty.')
            if len(request.password) < 6:
                raise HTTPException(400, 'Password must be at least 6 characters.')
            h, s = fd.hash_password(request.password)
            db.execute(
                'INSERT INTO users (username, password_hash, salt, created_at) VALUES (?,?,?,?)',
                (request.username.strip(), h, s, time.time())
            )
            db.commit()
        log_action(f'SETUP           User "{request.username}" created')
        return JSONResponse({'ok': True})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post('/api/login')
def api_login(request: LoginRequest) -> Response:
    """Verifies credentials and sets the session cookie."""
    try:
        with fd.db_context(fd.DB_PATH) as db:
            row = db.execute(
                'SELECT password_hash, salt FROM users WHERE username = ?',
                [request.username]
            ).fetchone()
    except Exception as exc:
        raise HTTPException(500, str(exc))
    if not row or not fd.verify_password(request.password, row['password_hash'], row['salt']):
        raise HTTPException(401, 'Username or password incorrect.')
    response = JSONResponse({'ok': True})
    response.set_cookie(
        COOKIE_NAME, create_session(request.username),
        httponly=True, max_age=SESSION_DAYS * 86400, samesite='lax'
    )
    log_action(f'LOGIN           User "{request.username}"')
    return response


@app.post('/api/logout')
def api_logout() -> Response:
    """Deletes the session cookie."""
    response = JSONResponse({'ok': True})
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get('/api/users')
def api_user_list() -> JSONResponse:
    """Lists all users (without password hashes)."""
    try:
        with fd.db_context(fd.DB_PATH) as db:
            rows = db.execute(
                'SELECT username, created_at FROM users ORDER BY created_at'
            ).fetchall()
        return JSONResponse({'users': [dict(z) for z in rows]})
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post('/api/users')
def api_user_create(request: UserRequest) -> JSONResponse:
    """Creates a new user."""
    if not request.username.strip():
        raise HTTPException(400, 'Username must not be empty.')
    if len(request.password) < 6:
        raise HTTPException(400, 'Password must be at least 6 characters.')
    try:
        h, s = fd.hash_password(request.password)
        with fd.db_context(fd.DB_PATH) as db:
            db.execute(
                'INSERT INTO users (username, password_hash, salt, created_at) VALUES (?,?,?,?)',
                (request.username.strip(), h, s, time.time())
            )
            db.commit()
        log_action(f'USER            Created: "{request.username}"')
        return JSONResponse({'ok': True})
    except Exception as exc:
        if 'UNIQUE' in str(exc):
            raise HTTPException(409, f'User "{request.username}" already exists.')
        raise HTTPException(500, str(exc))


@app.delete('/api/users/{name}')
def api_user_delete(name: str, request: Request) -> JSONResponse:
    """Deletes a user. Deleting one's own account is not allowed."""
    current = verify_session(request.cookies.get(COOKIE_NAME, ''))
    if current == name:
        raise HTTPException(400, 'Cannot delete your own account.')
    try:
        with fd.db_context(fd.DB_PATH) as db:
            result = db.execute('DELETE FROM users WHERE username = ?', [name])
            db.commit()
        if result.rowcount == 0:
            raise HTTPException(404, f'User "{name}" not found.')
        log_action(f'USER            Deleted: "{name}"')
        return JSONResponse({'ok': True})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc))


@app.post('/api/users/{name}/password')
def api_password_change(name: str, request: PasswordRequest) -> JSONResponse:
    """Changes the password of a user."""
    if len(request.password) < 6:
        raise HTTPException(400, 'Password must be at least 6 characters.')
    try:
        h, s = fd.hash_password(request.password)
        with fd.db_context(fd.DB_PATH) as db:
            result = db.execute(
                'UPDATE users SET password_hash=?, salt=? WHERE username=?',
                (h, s, name)
            )
            db.commit()
        if result.rowcount == 0:
            raise HTTPException(404, f'User "{name}" not found.')
        log_action(f'USER            Password changed: "{name}"')
        return JSONResponse({'ok': True})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc))


# ===========================================================================
# Helper functions
# ===========================================================================

def _path_allowed(p: Path) -> bool:
    """Checks whether the path is under BASEDIR."""
    if BASEDIR is None:
        return False
    try:
        p.resolve().relative_to(BASEDIR.resolve())
        return True
    except ValueError:
        return False


# ===========================================================================
# Startup helpers
# ===========================================================================

def _cleanup_jobs_at_startup() -> None:
    """Marks all jobs still stored as 'running' as 'cancelled'."""
    try:
        with fd.db_context(fd.DB_PATH) as db:
            db.execute(
                "UPDATE scan_jobs SET status='cancelled', ended_at=? WHERE status='running'",
                (time.time(),)
            )
            db.commit()
    except Exception as e:
        log_action(f'JOBS ERROR       Startup cleanup: {e}')


# ===========================================================================
# Main program
# ===========================================================================

def main() -> None:
    global BASEDIR, VERBOSE

    parser = argparse.ArgumentParser(
        description='Interactive web interface for the duplicate finder.',
    )
    parser.add_argument(
        '-d', '--directory',
        required=True,
        metavar='BASEDIR',
        help='Media directory (used as the root of the browser)',
    )
    parser.add_argument(
        '--port', type=int, default=8080,
        help='HTTP port (default: 8080)',
    )
    parser.add_argument(
        '--host', default='0.0.0.0',
        help='Bind address (default: 0.0.0.0)',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show all HTTP requests and deleted file paths',
    )
    parser.add_argument(
        '--workers', type=int, default=None, metavar='N',
        help=f'Parallel workers for image/video processing (default: {fd.WORKER_COUNT})',
    )
    args = parser.parse_args()

    VERBOSE = args.verbose
    BASEDIR = Path(args.directory).resolve()
    if not BASEDIR.is_dir():
        print(f'Error: "{BASEDIR}" is not a valid directory.', file=sys.stderr)
        sys.exit(1)

    if args.workers is not None:
        fd.WORKER_COUNT = max(1, args.workers)

    if not fd.PILLOW_AVAILABLE:
        print('Error: Pillow/imagehash not installed.', file=sys.stderr)
        sys.exit(1)

    _cleanup_jobs_at_startup()

    print('Duplicate Finder Web Interface')
    print(f'  Media directory : {BASEDIR}')
    print(f'  Database        : {fd.DB_PATH}')
    print(f'  Available at    : http://localhost:{args.port}')
    print(f'  Workers         : {fd.WORKER_COUNT}')
    print(f'  Mode            : {"verbose (all HTTP requests)" if VERBOSE else "normal (actions & errors only)"}')
    print()

    log_level = 'info' if VERBOSE else 'warning'
    uvicorn.run(app, host=args.host, port=args.port, log_level=log_level)


if __name__ == '__main__':
    main()
