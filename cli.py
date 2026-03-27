#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cli.py — Command-line entry point for the duplicate finder.

Usage:
  python cli.py -d /my/media/directory
  python cli.py -d /my/media/directory -t both
  python cli.py -d /my/media/directory -o report.html

Creates an HTML report with all found duplicates.

Dependencies: pip install Pillow imagehash pillow-heif
"""

import argparse
import sys
from pathlib import Path

_DIR = Path(__file__).parent
sys.path.insert(0, str(_DIR))
import engine as eng


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Finds duplicate images and/or videos in a directory.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'Output: {eng.WORK_DIR}/'
    )
    parser.add_argument(
        '-d', '--directory',
        required=True,
        metavar='DIRECTORY',
        help='Directory to scan'
    )
    parser.add_argument(
        '-t', '--type',
        choices=['images', 'videos', 'both'],
        default='images',
        help='What to scan: images, videos or both (default: images)'
    )
    parser.add_argument(
        '-o', '--output',
        metavar='FILENAME',
        default=None,
        help='Name of the HTML report file (default: duplicates_report.html)'
    )
    parser.add_argument(
        '--workers', type=int, default=None, metavar='N',
        help='Parallel workers for image/video processing (default: automatic)',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Check dependencies
    if not eng.PILLOW_AVAILABLE:
        print(
            'Error: Pillow and/or imagehash not installed.\n'
            'Install: pip install Pillow imagehash',
            file=sys.stderr
        )
        sys.exit(1)

    if args.workers is not None:
        eng.WORKER_COUNT = max(1, args.workers)

    directory = Path(args.directory).resolve()
    if not directory.is_dir():
        print(f'Error: "{directory}" is not a valid directory.', file=sys.stderr)
        sys.exit(1)

    if args.type in ('videos', 'both') and not eng.ffmpeg_available():
        print('Error: ffprobe/ffmpeg not found — required for video scanning.', file=sys.stderr)
        sys.exit(1)

    if not eng.HEIF_AVAILABLE and args.type in ('images', 'both'):
        print('Note: pillow-heif not installed — HEIC/HEIF files will be skipped.')
        print('      Install: pip install pillow-heif')

    print(f'Scanning directory: {directory} (type: {args.type})')

    db = eng.db_connect(eng.DB_PATH)

    # --- Image pipeline ---
    exact_groups = []
    visual_groups = []
    error_files = []

    if args.type in ('images', 'both'):
        paths = eng.scan_directory(directory)
        if paths:
            print(f'{len(paths)} image files found.')
            rows = eng.process_files(paths, db)
            error_files = [r for r in rows if r.get('error')]
            valid_rows = [r for r in rows if not r.get('error')]
            if error_files:
                print(f'  {len(error_files)} images could not be processed.')

            print('Searching for exact image duplicates...')
            exact_groups = eng.find_exact_duplicates(valid_rows)
            print(f'  {len(exact_groups)} group(s) found.')

            exact_paths = {r['path'] for g in exact_groups for r in g}
            print('Searching for visual image duplicates (pHash)...')
            visual_groups = eng.find_visual_duplicates(valid_rows, exact_paths)
            print(f'  {len(visual_groups)} group(s) found.')
        else:
            print('No image files found.')

    # --- Video pipeline ---
    video_exact_groups = None
    video_visual_groups = None
    video_error_files = None

    if args.type in ('videos', 'both'):
        video_paths = eng.scan_videos(directory)
        if video_paths:
            print(f'{len(video_paths)} video files found.')
            video_rows = eng.process_videos(video_paths, db)
            video_error_files = [r for r in video_rows if r.get('error')]
            video_valid = [r for r in video_rows if not r.get('error')]
            if video_error_files:
                print(f'  {len(video_error_files)} videos could not be processed.')

            print('Searching for exact video duplicates...')
            video_exact_groups = eng.find_exact_video_duplicates(video_valid)
            print(f'  {len(video_exact_groups)} group(s) found.')

            v_exact_paths = {r['path'] for g in video_exact_groups for r in g}
            print('Searching for visual video duplicates (frame sampling)...')
            video_visual_groups = eng.find_visual_video_duplicates(video_valid, v_exact_paths)
            print(f'  {len(video_visual_groups)} group(s) found.')
        else:
            print('No video files found.')
            video_exact_groups = []
            video_visual_groups = []
            video_error_files = []

    db.close()

    # HTML report
    output_path = (
        eng.WORK_DIR / args.output
        if args.output
        else eng.HTML_OUTPUT
    )
    print('Creating HTML report...')
    eng.create_html_report(
        directory=directory,
        exact_groups=exact_groups,
        visual_groups=visual_groups,
        error_files=error_files,
        output_path=output_path,
        video_exact_groups=video_exact_groups,
        video_visual_groups=video_visual_groups,
        video_error=video_error_files,
    )

    total_groups = (len(exact_groups) + len(visual_groups) +
                    len(video_exact_groups or []) + len(video_visual_groups or []))
    print(f'\nDone. {total_groups} duplicate group(s) found.')
    if not total_groups:
        print('No duplicates found in this directory.')


if __name__ == '__main__':
    main()
