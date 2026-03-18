#!/Users/evanleleux/Desktop/workspace/eng/praetorian-cli/.venv/bin/python3
"""
Webpage Screenshot Viewer

A Flask web UI that displays webpage screenshots from Guard/Chariot,
sorted by perceptual hash to cluster visually similar pages together.

Usage:
    python3 tools/webpage_viewer.py [--port 5001] [--cache-dir ~/.cache/webpage_viewer]
"""

import argparse
import hashlib
import io
import json
import os
import sys
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, render_template_string, send_file

# Add the project root so we can import the SDK
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.keychain import Keychain

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

state = {
    'pages': [],           # list of webpage dicts with screenshot info
    'pages_lock': threading.Lock(),
    'loading_done': False,
    'hashing_done': False,
    'sorted': False,
    'total_loaded': 0,
    'total_hashed': 0,
    'cache_dir': None,
    'sdk': None,
}


# ---------------------------------------------------------------------------
# Background threads
# ---------------------------------------------------------------------------

def loader_thread():
    """Paginate through all webpages, filter for ones with screenshots."""
    sdk = state['sdk']
    offset = None
    page_num = 0

    while True:
        try:
            results, offset = sdk.search.by_key_prefix('#webpage#', offset=offset, pages=1)
        except Exception as e:
            print(f'[loader] Error fetching page {page_num}: {e}')
            break

        page_num += 1
        batch = []
        for entry in results:
            screenshot_path = entry.get('screenshot') or entry.get('metadata', {}).get('screenshot', '')
            if not screenshot_path:
                continue

            page_id = hashlib.md5(entry['key'].encode()).hexdigest()
            batch.append({
                'id': page_id,
                'key': entry['key'],
                'url': entry.get('url', entry['key']),
                'screenshot_path': screenshot_path,
                'details': entry,
                'phash': None,
                'hashed': False,
            })

        if batch:
            with state['pages_lock']:
                state['pages'].extend(batch)
                state['total_loaded'] += len(batch)

        print(f'[loader] Page {page_num}: {len(results)} results, {len(batch)} with screenshots (total: {state["total_loaded"]})')

        if offset is None:
            break

    state['loading_done'] = True
    print(f'[loader] Done. {state["total_loaded"]} webpages with screenshots.')


HASH_WORKERS = 8
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # seconds, doubles each retry


def hash_one_entry(entry):
    """Download, thumbnail, and pHash a single entry. Called from thread pool."""
    from PIL import Image
    import imagehash

    cache_dir = state['cache_dir']
    thumbnail_path = cache_dir / f'{entry["id"]}.jpg'

    if thumbnail_path.exists():
        try:
            img = Image.open(thumbnail_path)
            entry['phash'] = str(imagehash.phash(img))
            entry['hashed'] = True
            return
        except Exception:
            pass

    for attempt in range(MAX_RETRIES):
        try:
            data = state['sdk'].files.get(entry['screenshot_path'])
            img = Image.open(io.BytesIO(data))
            img.thumbnail((400, 400))
            img.save(str(thumbnail_path), 'JPEG', quality=80)
            entry['phash'] = str(imagehash.phash(img))
            entry['hashed'] = True
            return
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                backoff = RETRY_BACKOFF * (2 ** attempt)
                time.sleep(backoff)
            else:
                print(f'[hasher] Failed after {MAX_RETRIES} retries for {entry["url"]}: {e}')
                entry['hashed'] = True
                entry['phash'] = 'ffffffffffffffff'


def hasher_thread():
    """Download screenshots in parallel, compute pHash, cache thumbnails to disk."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cursor = 0

    with ThreadPoolExecutor(max_workers=HASH_WORKERS) as pool:
        while True:
            with state['pages_lock']:
                pending = state['pages'][cursor:]

            if not pending and state['loading_done']:
                break

            if not pending:
                time.sleep(0.5)
                continue

            futures = {pool.submit(hash_one_entry, entry): entry for entry in pending}
            for future in as_completed(futures):
                future.result()
                state['total_hashed'] += 1
                if state['total_hashed'] % 100 == 0:
                    print(f'[hasher] Hashed {state["total_hashed"]}/{state["total_loaded"]}')

            cursor += len(pending)

    # Sort by pHash to cluster similar images
    with state['pages_lock']:
        state['pages'].sort(key=lambda p: p.get('phash') or 'ffffffffffffffff')
        state['sorted'] = True

    state['hashing_done'] = True
    print(f'[hasher] Done. Sorted {state["total_hashed"]} pages by pHash.')


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/status')
def api_status():
    return jsonify({
        'total_loaded': state['total_loaded'],
        'total_hashed': state['total_hashed'],
        'loading_done': state['loading_done'],
        'hashing_done': state['hashing_done'],
        'sorted': state['sorted'],
    })


@app.route('/api/pages')
def api_pages():
    from flask import request
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 50))

    with state['pages_lock']:
        page_slice = state['pages'][offset:offset + limit]

    items = []
    for p in page_slice:
        if not p.get('hashed'):
            continue
        items.append({
            'id': p['id'],
            'url': p['url'],
            'has_thumbnail': (state['cache_dir'] / f'{p["id"]}.jpg').exists(),
        })

    return jsonify({
        'items': items,
        'offset': offset,
        'total': state['total_loaded'],
    })


@app.route('/thumbnail/<page_id>')
def thumbnail(page_id):
    path = state['cache_dir'] / f'{page_id}.jpg'
    if path.exists():
        return send_file(str(path), mimetype='image/jpeg')
    return '', 404


@app.route('/fullimage/<page_id>')
def fullimage(page_id):
    """Serve the original full-resolution screenshot from S3."""
    with state['pages_lock']:
        entry = next((p for p in state['pages'] if p['id'] == page_id), None)
    if not entry:
        return '', 404
    try:
        data = state['sdk'].files.get(entry['screenshot_path'])
        return send_file(io.BytesIO(data), mimetype='image/jpeg')
    except Exception as e:
        print(f'[fullimage] Error for {page_id}: {e}')
        return '', 500


@app.route('/detail/<page_id>')
def detail(page_id):
    with state['pages_lock']:
        for p in state['pages']:
            if p['id'] == page_id:
                return jsonify(p['details'])
    return jsonify({'error': 'not found'}), 404


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Webpage Screenshot Viewer</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #1a1a2e; color: #eee; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }

  #status-bar {
    position: fixed; top: 0; left: 0; right: 0; z-index: 100;
    background: #16213e; padding: 10px 20px; display: flex; align-items: center; gap: 16px;
    border-bottom: 1px solid #0f3460;
  }
  #status-bar .progress-wrap {
    flex: 1; height: 8px; background: #0f3460; border-radius: 4px; overflow: hidden;
  }
  #status-bar .progress-fill {
    height: 100%; background: #e94560; transition: width 0.3s;
  }
  #status-text { font-size: 13px; white-space: nowrap; }

  #grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px;
    padding: 60px 16px 16px;
  }

  .card {
    background: #16213e; border-radius: 8px; overflow: hidden; cursor: pointer;
    transition: transform 0.15s, box-shadow 0.15s;
    border: 1px solid #0f3460;
  }
  .card:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(233,69,96,0.3); }
  .card img { width: 100%; display: block; min-height: 120px; background: #0f3460; }
  .card .label {
    padding: 8px 10px; font-size: 12px; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis; color: #a0a0b8;
  }

  /* Modal — full-screen split view */
  #modal-overlay {
    display: none; position: fixed; inset: 0; z-index: 200;
    background: rgba(0,0,0,0.9);
  }
  #modal-overlay.active { display: flex; }
  #modal {
    display: flex; width: 100%; height: 100%; position: relative;
  }
  #modal-close {
    position: absolute; top: 16px; right: 20px; background: none; border: none;
    color: #e94560; font-size: 28px; cursor: pointer; z-index: 210;
  }
  #modal-image-pane {
    flex: 1; display: flex; align-items: center; justify-content: center;
    padding: 16px; overflow: auto; background: #0a0a1a; min-width: 0;
  }
  #modal-image-pane img {
    width: 100%; height: 100%; object-fit: contain; border-radius: 8px;
    cursor: zoom-in;
  }
  #modal-image-pane img.zoomed {
    width: auto; height: auto; max-width: none; max-height: none;
    cursor: zoom-out; object-fit: unset;
  }
  #modal-detail-pane {
    width: 400px; min-width: 400px; background: #16213e; border-left: 1px solid #0f3460;
    padding: 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px;
  }
  #modal-detail-pane h2 {
    font-size: 15px; word-break: break-all; color: #e94560; margin: 0;
  }
  #modal-detail-pane pre {
    background: #0a0a1a; padding: 16px; border-radius: 8px; font-size: 12px;
    overflow-x: auto; white-space: pre-wrap; word-break: break-word; color: #a0a0b8;
    flex: 1;
  }

  #sentinel { height: 1px; }
</style>
</head>
<body>

<div id="status-bar">
  <span id="status-text">Starting...</span>
  <div class="progress-wrap"><div class="progress-fill" id="progress-fill"></div></div>
</div>

<div id="grid"></div>
<div id="sentinel"></div>

<div id="modal-overlay">
  <div id="modal">
    <button id="modal-close" onclick="closeModal()">&times;</button>
    <div id="modal-image-pane" onclick="if(event.target===this)closeModal()">
      <img id="modal-img" src="" onclick="this.classList.toggle('zoomed')">
    </div>
    <div id="modal-detail-pane">
      <h2 id="modal-url"></h2>
      <pre id="modal-details"></pre>
    </div>
  </div>
</div>

<script>
const grid = document.getElementById('grid');
const sentinel = document.getElementById('sentinel');
const statusText = document.getElementById('status-text');
const progressFill = document.getElementById('progress-fill');

let offset = 0;
let loading = false;
let allLoaded = false;
let lastSorted = false;

async function loadMore() {
  if (loading || allLoaded) return;
  loading = true;

  const resp = await fetch(`/api/pages?offset=${offset}&limit=60`);
  const data = await resp.json();

  for (const item of data.items) {
    if (!item.has_thumbnail) continue;
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `<img src="/thumbnail/${item.id}" loading="lazy"><div class="label">${escapeHtml(item.url)}</div>`;
    card.onclick = () => showDetail(item.id);
    grid.appendChild(card);
  }

  offset += 60;
  if (data.items.length < 60 && data.total <= offset) {
    allLoaded = true;
  }
  loading = false;
}

async function showDetail(id) {
  const resp = await fetch(`/detail/${id}`);
  const detail = await resp.json();
  document.getElementById('modal-img').src = `/fullimage/${id}`;
  document.getElementById('modal-url').textContent = detail.url || detail.key || '';
  document.getElementById('modal-details').textContent = JSON.stringify(detail, null, 2);
  document.getElementById('modal-overlay').classList.add('active');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('active');
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// Infinite scroll
const observer = new IntersectionObserver(entries => {
  if (entries[0].isIntersecting) loadMore();
}, { rootMargin: '600px' });
observer.observe(sentinel);

// Status polling
async function pollStatus() {
  try {
    const resp = await fetch('/api/status');
    const s = await resp.json();

    let text = `Loaded: ${s.total_loaded}`;
    if (s.total_loaded > 0) {
      text += ` | Hashed: ${s.total_hashed}/${s.total_loaded}`;
    }
    if (s.sorted) text += ' | ✓ Sorted by similarity';
    else if (s.hashing_done) text += ' | Sorting...';
    else if (s.loading_done) text += ' | Loading done, hashing...';

    statusText.textContent = text;

    const pct = s.total_loaded > 0 ? (s.total_hashed / s.total_loaded * 100) : 0;
    progressFill.style.width = pct + '%';

    // When sorting completes, reload the grid to show sorted order
    if (s.sorted && !lastSorted) {
      lastSorted = true;
      grid.innerHTML = '';
      offset = 0;
      allLoaded = false;
      loadMore();
    }
  } catch (e) {}
}

setInterval(pollStatus, 2000);
pollStatus();
loadMore();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Webpage Screenshot Viewer')
    parser.add_argument('--port', type=int, default=5001)
    parser.add_argument('--cache-dir', default=os.path.expanduser('~/.cache/webpage_viewer'))
    parser.add_argument('--profile', default=None, help='Chariot keychain profile')
    parser.add_argument('--account', default=None, help='Chariot account to assume (e.g. user@example.com)')
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    state['cache_dir'] = cache_dir

    print(f'Cache directory: {cache_dir}')
    print('Initializing SDK...')

    keychain = Keychain(args.profile, account=args.account) if args.profile else Keychain(account=args.account)
    state['sdk'] = Chariot(keychain)

    # Start background threads
    loader = threading.Thread(target=loader_thread, daemon=True)
    hasher = threading.Thread(target=hasher_thread, daemon=True)
    loader.start()
    hasher.start()

    print(f'Starting server on http://localhost:{args.port}')
    app.run(host='0.0.0.0', port=args.port, debug=False)


if __name__ == '__main__':
    main()
