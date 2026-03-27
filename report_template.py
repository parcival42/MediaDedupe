# -*- coding: utf-8 -*-
"""
report_template.py — HTML template for the duplicate report.

Placeholders (for str.format_map / .format()):
  {directory}         Scanned directory
  {now}               Creation timestamp
  {n_exact}           Number of exact image duplicate groups
  {n_visual}          Number of visual image duplicate groups
  {total_files}       Total affected files
  {wasted_str}        Wasted storage (formatted string)
  {heif_notice}       Optional HEIF notice HTML
  {exact_html}        HTML block: exact image duplicates
  {visual_html}       HTML block: visual image duplicates
  {error_html}        HTML block: failed images
  {video_report_html} HTML block: video duplicates (empty if not scanned)
  {video_groups_br}   '<br>' if videos were scanned, else ''
  {video_exact_line}  Line for exact video groups (or '')
  {video_visual_line} Line for visual video groups (or '')
  {THUMBNAIL_MAX}     Maximum thumbnail width/height in pixels
  {card_width}        THUMBNAIL_MAX + 20 (card width)
  {PHASH_THRESHOLD}   pHash threshold value
"""

REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Duplicate Report</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    margin: 0;
    padding: 20px 20px 100px;
  }}
  h1 {{ color: #a0c4ff; margin-bottom: 5px; }}
  h2 {{ color: #c0d8ff; border-bottom: 1px solid #334; padding-bottom: 6px; margin-top: 40px; }}
  h3 {{ color: #b0c8e8; font-size: 0.95em; margin: 10px 0 8px; }}
  .summary {{
    background: #16213e;
    border: 1px solid #334;
    border-radius: 6px;
    padding: 14px 20px;
    margin: 16px 0 30px;
    font-size: 0.95em;
    line-height: 1.8;
  }}
  .summary b {{ color: #a0c4ff; }}
  .group {{
    background: #16213e;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 20px;
    border-left: 4px solid #555;
  }}
  .group.exact {{ border-left-color: #e05c5c; }}
  .group.visual {{ border-left-color: #e0c050; }}
  .images-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    margin-top: 10px;
  }}
  /* Image cards */
  .image-card {{
    border-radius: 8px;
    padding: 10px;
    width: {card_width}px;
    font-size: 0.85em;
    word-break: break-all;
    position: relative;
    border: 2px solid transparent;
  }}
  .image-card.original {{
    background: #0d2b1a;
    border-color: #2ea84a;
  }}
  .image-card.delete-candidate {{
    background: #2b0d0d;
    border-color: #a83030;
  }}
  .image-card.delete-candidate.deselected {{
    background: #1a1a2e;
    border-color: #555;
    opacity: 0.6;
  }}
  .image-card.original.marked {{
    background: #2b0d0d;
    border-color: #a83030;
  }}
  .original-cb-label {{ color: #7a9a7a; }}
  .original-cb-label:has(input:checked) {{ color: #cc8888; }}
  .image-card img {{
    display: block;
    max-width: {THUMBNAIL_MAX}px;
    max-height: {THUMBNAIL_MAX}px;
    border-radius: 4px;
    margin-bottom: 8px;
  }}
  .no-preview {{
    width: {THUMBNAIL_MAX}px;
    height: 80px;
    background: #222;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #666;
    font-size: 0.9em;
    margin-bottom: 8px;
  }}
  /* Badge */
  .badge {{
    display: inline-block;
    font-size: 0.75em;
    font-weight: bold;
    padding: 2px 8px;
    border-radius: 4px;
    margin-bottom: 6px;
    letter-spacing: 0.03em;
  }}
  .badge.keep   {{ background: #1a5c30; color: #5ddb82; }}
  .badge.delete {{ background: #5c1a1a; color: #db5d5d; }}
  /* Filename + path */
  .filename {{
    font-weight: bold;
    color: #d0e8ff;
    margin: 4px 0 2px;
    font-size: 1.0em;
    word-break: break-word;
  }}
  .dir-path {{
    color: #7090a0;
    font-family: monospace;
    font-size: 0.82em;
    margin: 0 0 4px;
    word-break: break-all;
    white-space: pre-wrap;
  }}
  .meta {{ color: #aaa; margin: 0 0 6px; font-size: 0.88em; }}
  .distance {{ display: block; color: #e0c050; margin-top: 2px; }}
  /* Checkbox */
  .cb-label {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.82em;
    color: #cc8888;
    cursor: pointer;
    margin-top: 4px;
  }}
  .cb-label input {{ cursor: pointer; accent-color: #e05c5c; width: 15px; height: 15px; }}
  /* Misc */
  .empty  {{ color: #666; font-style: italic; }}
  .notice {{ background: #3a2a00; border: 1px solid #665500; border-radius: 4px;
              padding: 8px 14px; color: #e0c050; margin: 10px 0; }}
  .error-table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; margin-top: 10px; }}
  .error-table th {{ background: #223; color: #aaa; text-align: left;
                      padding: 6px 10px; border-bottom: 1px solid #334; }}
  .error-table td {{ padding: 5px 10px; border-bottom: 1px solid #223; }}
  .error-table td.path {{ font-family: monospace; color: #888; }}
  code {{ background: #223; padding: 2px 6px; border-radius: 3px;
          font-family: monospace; font-size: 0.9em; }}
  /* Action bar (sticky at bottom) */
  #action-bar {{
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: #0d1b2e;
    border-top: 2px solid #334;
    padding: 10px 20px;
    display: flex;
    align-items: center;
    gap: 14px;
    z-index: 100;
  }}
  #action-bar span {{ color: #aaa; font-size: 0.9em; }}
  #btn-script {{
    background: #c0392b;
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 0.95em;
    font-weight: bold;
    cursor: pointer;
  }}
  #btn-script:hover {{ background: #e74c3c; }}
  #btn-all {{ background: #2c3e50; color: #ccc; border: 1px solid #445;
               border-radius: 6px; padding: 6px 14px; font-size: 0.88em; cursor: pointer; }}
  #btn-all:hover {{ background: #3d5166; }}
  /* Script modal */
  #script-modal {{
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.75);
    z-index: 200;
    align-items: center;
    justify-content: center;
  }}
  #script-modal.active {{ display: flex; }}
  #script-box {{
    background: #0d1b2e;
    border: 1px solid #446;
    border-radius: 10px;
    padding: 24px;
    width: 80%;
    max-width: 860px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  #script-box h3 {{ color: #a0c4ff; margin: 0; }}
  #script-output {{
    flex: 1;
    background: #060f1a;
    color: #7ddf8f;
    font-family: monospace;
    font-size: 0.9em;
    border: 1px solid #334;
    border-radius: 6px;
    padding: 12px;
    resize: none;
    min-height: 200px;
    max-height: 50vh;
    overflow-y: auto;
  }}
  .modal-buttons {{ display: flex; gap: 10px; justify-content: flex-end; }}
  .modal-buttons button {{
    border-radius: 6px; padding: 7px 18px; font-size: 0.9em;
    cursor: pointer; border: none; font-weight: bold;
  }}
  #btn-copy {{ background: #1a6e36; color: #fff; }}
  #btn-copy:hover {{ background: #2ea84a; }}
  #btn-close {{ background: #3a3a4a; color: #ccc; }}
  #btn-close:hover {{ background: #555; }}
</style>
</head>
<body>
<h1>Duplicate Report</h1>
<div class="summary">
  <b>Directory:</b> {directory}<br>
  <b>Created:</b> {now}<br>
  <b>Exact duplicate groups (images):</b> {n_exact}<br>
  <b>Visual duplicate groups (images):</b> {n_visual}<br>{video_groups_br}
  {video_exact_line}{video_visual_line}<b>Total affected files:</b> {total_files}<br>
  <b>Wasted storage (approx.):</b> {wasted_str}
</div>
{heif_notice}

<h2>Exact Duplicates ({n_exact} groups)</h2>
{exact_html}

<h2>Visual Duplicates ({n_visual} groups)
    <small style="font-weight:normal;font-size:0.75em;color:#888;">
    (pHash distance &le; {PHASH_THRESHOLD}, excluding exact duplicates)
    </small>
</h2>
{visual_html}

{error_html}

{video_report_html}

<!-- Sticky action bar -->
<div id="action-bar">
  <span id="delete-counter">0 files marked for deletion</span>
  <button id="btn-all" onclick="toggleAll()">Select / deselect all</button>
  <button id="btn-script" onclick="showScript()">Generate shell script</button>
</div>

<!-- Script modal -->
<div id="script-modal">
  <div id="script-box">
    <h3>Shell script &mdash; delete marked files</h3>
    <p style="color:#aaa;font-size:0.85em;margin:0;">
      Copy the commands and run them on the server.<br>
      <strong style="color:#e05c5c;">Warning: Deletion is irreversible. Please review before running!</strong>
    </p>
    <textarea id="script-output" readonly></textarea>
    <div class="modal-buttons">
      <button id="btn-copy" onclick="copyScript()">Copy to clipboard</button>
      <button id="btn-close" onclick="closeModal()">Close</button>
    </div>
  </div>
</div>

<script>
  function updateCounter() {{
    const active = document.querySelectorAll('.delete-cb:checked').length;
    document.getElementById('delete-counter').textContent =
      active + ' file' + (active === 1 ? '' : 's') + ' marked for deletion';
  }}

  function updateCard(checkbox) {{
    const card = checkbox.closest('.image-card');
    if (card.classList.contains('original')) {{
      // Original: checked = mark red, unchecked = back to green
      card.classList.toggle('marked', checkbox.checked);
    }} else {{
      // Delete candidate: unchecked = dim
      card.classList.toggle('deselected', !checkbox.checked);
    }}
    updateCounter();
  }}

  // Initialize all checkboxes
  document.querySelectorAll('.delete-cb').forEach(cb => {{
    cb.addEventListener('change', () => updateCard(cb));
  }});
  updateCounter();

  let allMarked = true;
  function toggleAll() {{
    allMarked = !allMarked;
    document.querySelectorAll('.delete-cb').forEach(cb => {{
      cb.checked = allMarked;
      updateCard(cb);
    }});
  }}

  function showScript() {{
    const paths = [];
    document.querySelectorAll('.delete-cb:checked').forEach(cb => {{
      paths.push(cb.dataset.path);
    }});
    if (paths.length === 0) {{
      alert('No files selected.');
      return;
    }}
    const lines = ['#!/bin/bash', '# Auto-generated by findDuplicates.py', '# Please review before running!', ''];
    paths.forEach(p => lines.push('rm ' + JSON.stringify(p)));
    document.getElementById('script-output').value = lines.join('\\n');
    document.getElementById('script-modal').classList.add('active');
  }}

  function closeModal() {{
    document.getElementById('script-modal').classList.remove('active');
  }}

  function copyScript() {{
    const ta = document.getElementById('script-output');
    ta.select();
    navigator.clipboard.writeText(ta.value).then(() => {{
      document.getElementById('btn-copy').textContent = '\u2713 Copied!';
      setTimeout(() => document.getElementById('btn-copy').textContent = 'Copy to clipboard', 2000);
    }});
  }}

  // Close modal on outside click
  document.getElementById('script-modal').addEventListener('click', function(e) {{
    if (e.target === this) closeModal();
  }});
</script>
</body>
</html>"""
