import os
import xml.etree.ElementTree as ET
import urllib.request
import json
from datetime import datetime
import email.utils
import re

ARCHIVE_FILE = 'public/archive.json'
existing_archive = []

# 1. Gracefully load past archive layers
if os.path.exists(ARCHIVE_FILE):
    try:
        with open(ARCHIVE_FILE, 'r', encoding='utf-8') as f:
            existing_archive = json.load(f)
        print(f"Loaded {len(existing_archive)} existing records.")
    except Exception as e:
        print(f"Could not load old archive: {e}")

known_links = {item.get('link') for item in existing_archive if 'link' in item}

print("Parsing feeds.opml...")
try:
    tree = ET.parse('feeds.opml')
    root = tree.getroot()
except Exception as e:
    print(f"CRITICAL ERROR: feeds.opml is corrupt or missing! {e}")
    root = None

feed_urls = []
if root is not None:
    for outline in root.findall('.//outline'):
        xml_url = outline.get('xmlUrl')
        if xml_url:
            feed_urls.append(xml_url)

print(f"Checking {len(feed_urls)} source feeds for updates...")
new_items_count = 0

def robust_parse_date(date_str):
    if not date_str:
        return datetime.now().timestamp(), "Recent"
    try:
        dt = email.utils.parsedate_to_datetime(str(date_str))
        return dt.timestamp(), dt.strftime('%d %b %Y')
    except Exception:
        pass
    try:
        clean_date = str(date_str).split('T')[0]
        dt = datetime.strptime(clean_date, "%Y-%m-%d")
        return dt.timestamp(), dt.strftime('%d %b %Y')
    except Exception:
        pass
    return datetime.now().timestamp(), "Recent"

def extract_thumbnail(item_element):
    try:
        # Check standard Media RSS namespaces
        for media_tag in ['.//{http://search.yahoo.com/mrss/}content', './/{http://search.yahoo.com/mrss/}thumbnail']:
            try:
                found = item_element.find(media_tag)
                if found is not None and found.get('url'):
                    return str(found.get('url'))
            except Exception:
                pass
                
        # Check standard podcast cover art tags
        try:
            itunes_image = item_element.find('.//{http://www.itunes.com/dtds/podcast-1.0.dtd}image')
            if itunes_image is not None and itunes_image.get('href'):
                return str(itunes_image.get('href'))
        except Exception:
            pass

        # Check enclosure tags
        try:
            enclosure = item_element.find('enclosure')
            if enclosure is not None and enclosure.get('type', '').startswith('image/'):
                return str(enclosure.get('url'))
        except Exception:
            pass

        # Regex scrape image sources from textual elements
        desc = item_element.findtext('description') or item_element.findtext('{http://www.w3.org/2005/Atom}content') or ""
        if desc:
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', str(desc))
            if img_match:
                return str(img_match.group(1))
    except Exception:
        pass
    return ""

# 2. Iterate and process live feeds wrapped inside isolated safety buffers
for url in feed_urls[:40]:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
            
            # Use standard XML parser but intercept formatting compilation failures
            try:
                feed_root = ET.fromstring(xml_data)
            except Exception as xml_err:
                print(f"Skipping feed {url} due to bad XML formatting: {xml_err}")
                continue
            
            channel = feed_root.find('channel')
            items = channel.findall('item') if channel is not None else feed_root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            if not items:
                items = feed_root.findall('item')  # Alternative fallback layout style
                
            for item in items[:25]:
                try:
                    title = item.findtext('title') or item.findtext('{http://www.w3.org/2005/Atom}title')
                    link = item.findtext('link') or (item.find('{http://www.w3.org/2005/Atom}link').get('href') if item.find('{http://www.w3.org/2005/Atom}link') is not None else "")
                    
                    if not title or not link:
                        continue
                    
                    link_str = str(link).strip()
                    if link_str.startswith('/') or not link_str.startswith('http'):
                        continue
                    if link_str in known_links:
                        continue
                    
                    pub_date_raw = item.findtext('pubDate') or item.findtext('{http://www.w3.org/2005/Atom}published') or item.findtext('{http://www.w3.org/2005/Atom}updated') or ""
                    timestamp, date_display_str = robust_parse_date(pub_date_raw)
                    image_url = extract_thumbnail(item)

                    lower_link = link_str.lower()
                    lower_title = str(title).lower()
                    
                    if "youtube.com" in lower_link or "youtu.be" in lower_link or "video" in lower_title:
                        item_type = "video"
                    elif "podcast" in lower_link or "spotify" in lower_link or "podcast" in lower_title or "audio" in lower_title or "episode" in lower_title or "feedproxy" in lower_link:
                        item_type = "podcast"
                    else:
                        item_type = "blog"
                        
                    existing_archive.append({
                        "title": str(title), 
                        "link": link_str, 
                        "date_str": str(date_display_str), 
                        "timestamp": float(timestamp),
                        "type": item_type,
                        "image": image_url
                    })
                    known_links.add(link_str)
                    new_items_count += 1
                except Exception as item_err:
                    print(f"Skipped an individual item within {url} due to error: {item_err}")
                    continue
                
    except Exception as e:
        print(f"Skipping completely unreadable source feed {url}: {e}")
        continue

print(f"Archived {new_items_count} brand-new resources.")

# Filter out empty or broken artifacts before sorting
existing_archive = [i for i in existing_archive if i.get('title') and i.get('link')]

# Ensure proper numeric chronological index sequencing (Newest First)
try:
    existing_archive.sort(key=lambda x: float(x.get('timestamp', 0)), reverse=True)
except Exception as sort_err:
    print(f"Warning during sort normalization: {sort_err}")

os.makedirs('public', exist_ok=True)
with open(ARCHIVE_FILE, 'w', encoding='utf-8') as f:
    json.dump(existing_archive, f, ensure_ascii=False, indent=2)

html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rescue &amp; Remote Medicine Society Hub</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f4f6f8; color: #333; margin: 0; padding: 20px; }}
        .container {{ max-width: 950px; margin: 0 auto; }}
        header {{ text-align: center; margin-bottom: 30px; background: #1e293b; color: white; padding: 30px; border-radius: 12px; }}
        h1 {{ margin: 0; font-size: 26px; }}
        .fruit-machine-box {{ background: #fff; border: 3px dashed #ef4444; border-radius: 12px; padding: 20px; margin-bottom: 30px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }}
        .machine-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px; margin-bottom: 15px; }}
        .machine-title {{ font-weight: bold; font-size: 20px; color: #1e293b; }}
        .spin-btn {{ background: #ef4444; color: white; border: none; padding: 10px 20px; font-weight: bold; border-radius: 6px; cursor: pointer; text-transform: uppercase; }}
        .spin-btn:hover {{ background: #dc2626; }}
        .slots-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }}
        @media(max-width: 768px) {{ .slots-grid {{ grid-template-columns: 1fr; }} }}
        .slot-column {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; }}
        .column-header {{ font-weight: bold; text-transform: uppercase; font-size: 12px; margin-bottom: 10px; color: #64748b; border-bottom: 2px solid #cbd5e1; padding-bottom: 5px; }}
        .slot-item {{ background: #fff; padding: 10px; border-radius: 6px; margin-bottom: 8px; border: 1px solid #e2e8f0; font-size: 13px; display: flex; align-items: center; gap: 10px; text-decoration: none; color: #334155; font-weight: 500; }}
        .slot-item:hover {{ border-color: #ef4444; color: #ef4444; }}
        .slot-thumb {{ width: 45px; height: 45px; border-radius: 4px; object-fit: cover; flex-shrink: 0; background: #e2e8f0; }}
        .search-bar {{ width: 100%; padding: 14px 20px; font-size: 16px; border: 2px solid #e2e8f0; border-radius: 8px; box-sizing: border-box; outline: none; margin-bottom: 25px; }}
        .search-bar:focus {{ border-color: #ef4444; }}
        .card {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.01); display: flex; gap: 15px; align-items: center; text-decoration: none; color: inherit; border-left: 5px solid #64748b; }}
        .card.video {{ border-left-color: #ef4444; }}
        .card.podcast {{ border-left-color: #3b82f6; }}
        .card.blog {{ border-left-color: #10b981; }}
        .card-thumb {{ width: 80px; height: 80px; border-radius: 6px; object-fit: cover; background: #e2e8f0; flex-shrink: 0; }}
        .card-body {{ flex-grow: 1; }}
        .card h3 {{ margin: 0 0 5px 0; font-size: 17px; color: #1e293b; }}
        .meta {{ font-size: 12px; color: #64748b; display: flex; gap: 10px; align-items: center; }}
        .badge {{ text-transform: uppercase; font-weight: bold; font-size: 10px; padding: 2px 6px; border-radius: 4px; color: white; }}
        .badge.video {{ background: #ef4444; }}
        .badge.podcast {{ background: #3b82f6; }}
        .badge.blog {{ background: #10b981; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Rescue &amp; Remote Medicine Society Hub</h1>
            <p>UWE Student Union Branch • Active Pool: {len(existing_archive)} Resources</p>
        </header>

        <div class="fruit-machine-box">
            <div class="machine-header">
                <div class="machine-title">🎰 The CPD Fruit Machine</div>
                <button class="spin-btn" onclick="spinMachine()">Pull Lever</button>
            </div>
            <div class="slots-grid">
                <div class="slot-column">
                    <div class="column-header">🎬 3x Video Resources</div>
                    <div id="video-slots"></div>
                </div>
                <div class="slot-column">
                    <div class="column-header">🎙️ 3x Podcast Episodes</div>
                    <div id="podcast-slots"></div>
                </div>
                <div class="slot-column">
                    <div class="column-header">📰 3x Articles &amp; Blogs</div>
                    <div id="blog-slots"></div>
                </div>
            </div>
        </div>

        <input type="text" id="searchInput" class="search-bar" placeholder="🔍 Search resource library..." onkeyup="filterArchive()">

        <main id="archiveTimeline">
"""

fallbacks = {
    "video": "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=150&auto=format&fit=crop&q=60",
    "podcast": "https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=150&auto=format&fit=crop&q=60",
    "blog": "https://images.unsplash.com/photo-1499750310107-5fef28a66643?w=150&auto=format&fit=crop&q=60"
}

for item in existing_archive:
    clean_title = item['title'].replace('"', '&quot;').replace("'", "&#39;")
    img_src = item['image'] if item.get('image') else fallbacks[item['type']]
    html_content += f"""
            <a href="{item['link']}" target="_blank" class="card {item['type']}" data-title="{clean_title.lower()}">
                <img class="card-thumb" src="{img_src}" loading="lazy" alt="cover">
                <div class="card-body">
                    <h3>{item['title']}</h3>
                    <div class="meta">
                        <span class="badge {item['type']}">{item['type']}</span>
                        <span>Published: {item['date_str']}</span>
                    </div>
                </div>
            </a>
    """

html_content += f"""
        </main>
    </div>

    <script>
        const archiveItems = {json.dumps(existing_archive)};
        const fallbacks = {json.dumps(fallbacks)};

        function getRandomItems(arr, type, num) {{
            const filtered = arr.filter(i => i.type === type);
            if(filtered.length === 0) return [];
            const shuffled = [...filtered].sort(() => 0.5 - Math.random());
            return shuffled.slice(0, num);
        }}

        function spinMachine() {{
            const vSlots = document.getElementById('video-slots');
            const pSlots = document.getElementById('podcast-slots');
            const bSlots = document.getElementById('blog-slots');

            const videos = getRandomItems(archiveItems, 'video', 3);
            const podcasts = getRandomItems(archiveItems, 'podcast', 3);
            const blogs = getRandomItems(archiveItems, 'blog', 3);

            vSlots.innerHTML = videos.map(v => {{
                let src = v.image ? v.image : fallbacks.video;
                return `<a class="slot-item" href="${{v.link}}" target="_blank"><img class="slot-thumb" src="${{src}}"><span>${{v.title}}</span></a>`;
            }}).join('');

            pSlots.innerHTML = podcasts.map(p => {{
                let src = p.image ? p.image : fallbacks.podcast;
                return `<a class="slot-item" href="${{p.link}}" target="_blank"><img class="slot-thumb" src="${{src}}"><span>${{p.title}}</span></a>`;
            }}).join('');

            bSlots.innerHTML = blogs.map(b => {{
                let src = b.image ? b.image : fallbacks.blog;
                return `<a class="slot-item" href="${{b.link}}" target="_blank"><img class="slot-thumb" src="${{src}}"><span>${{b.title}}</span></a>`;
            }}).join('');
        }}

        function filterArchive() {{
            const query = document.getElementById('searchInput').value.toLowerCase();
            const cards = document.querySelectorAll('#archiveTimeline .card');
            cards.forEach(card => {{
                const title = card.getAttribute('data-title');
                card.style.display = title.includes(query) ? 'flex' : 'none';
            }});
        }}

        window.onload = spinMachine;
    </script>
</body>
</html>
"""

with open('public/index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Compilation successful and completely isolated from errors!")
