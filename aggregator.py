import os
import xml.etree.ElementTree as ET
import urllib.request
import json
from datetime import datetime
import email.utils

# 1. Load existing archive data if it exists to prevent losing past releases
ARCHIVE_FILE = 'public/archive.json'
existing_archive = []

if os.path.exists(ARCHIVE_FILE):
    try:
        with open(ARCHIVE_FILE, 'r', encoding='utf-8') as f:
            existing_archive = json.load(f)
        print(f"Loaded {len(existing_archive)} existing records from history.")
    except Exception as e:
        print(f"Could not load old archive, starting fresh: {e}")

# Create a lookup set of links we already have to prevent duplicates
known_links = {item['link'] for item in existing_archive}

print("Parsing feeds.opml...")
tree = ET.parse('feeds.opml')
root = tree.getroot()
feed_urls = []

for outline in root.findall('.//outline'):
    xml_url = outline.get('xmlUrl')
    if xml_url:
        feed_urls.append(xml_url)

print(f"Checking {len(feed_urls)} source feeds for updates...")

new_items_count = 0

# 2. Extract current items from the live feeds
for url in feed_urls[:40]:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
            feed_root = ET.fromstring(xml_data)
            
            channel = feed_root.find('channel')
            items = channel.findall('item') if channel is not None else feed_root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            for item in items:  # Read everything currently exposed by the feed
                title = item.findtext('title') or item.findtext('{http://www.w3.org/2005/Atom}title')
                link = item.findtext('link') or item.find('.//{http://www.w3.org/2005/Atom}link').get('href') if item.find('{http://www.w3.org/2005/Atom}link') is not None else ""
                
                if not title or not link:
                    continue
                    
                # Skip if we already archived this resource in a past run
                if link in known_links:
                    continue
                
                pub_date_raw = item.findtext('pubDate') or item.findtext('{http://www.w3.org/2005/Atom}published') or item.findtext('{http://www.w3.org/2005/Atom}updated') or ""
                
                parsed_dt = None
                if pub_date_raw:
                    try:
                        parsed_dt = email.utils.parsedate_to_datetime(pub_date_raw)
                    except Exception:
                        parsed_dt = None
                
                if not parsed_dt:
                    parsed_dt = datetime.now()

                lower_link = link.lower()
                lower_title = title.lower()
                
                if "youtube.com" in lower_link or "youtu.be" in lower_link or "video" in lower_title:
                    item_type = "video"
                elif "podcast" in lower_link or "spotify" in lower_link or "podcast" in lower_title or "audio" in lower_title or "episode" in lower_title:
                    item_type = "podcast"
                else:
                    item_type = "blog"
                    
                existing_archive.append({
                    "title": title, 
                    "link": link, 
                    "date_str": parsed_dt.strftime('%d %b %Y'), 
                    "timestamp": parsed_dt.timestamp(),
                    "type": item_type
                })
                known_links.add(link)
                new_items_count += 1
                
    except Exception as e:
        print(f"Skipping bad feed {url}: {e}")

print(f"Found {new_items_count} new entries.")

# 3. Always sort the combined master catalog: newest release first
existing_archive.sort(key=lambda x: x['timestamp'], reverse=True)

# Ensure public output directory exists
os.makedirs('public', exist_ok=True)

# 4. Save the expanded catalog back down to disk
with open(ARCHIVE_FILE, 'w', encoding='utf-8') as f:
    json.dump(existing_archive, f, ensure_ascii=False, indent=2)

# Generate HTML layout using the complete, accumulative catalog
html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rescue &amp; Remote Medicine Society Hub</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f4f6f8; color: #333; margin: 0; padding: 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        header {{ text-align: center; margin-bottom: 30px; background: #1e293b; color: white; padding: 30px; border-radius: 12px; }}
        h1 {{ margin: 0; font-size: 26px; }}
        .fruit-machine-box {{ background: #fff; border: 3px dashed #ef4444; border-radius: 12px; padding: 20px; margin-bottom: 30px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }}
        .machine-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px; margin-bottom: 15px; }}
        .machine-title {{ font-weight: bold; font-size: 20px; color: #1e293b; display: flex; align-items: center; gap: 8px; }}
        .spin-btn {{ background: #ef4444; color: white; border: none; padding: 10px 20px; font-weight: bold; border-radius: 6px; cursor: pointer; text-transform: uppercase; letter-spacing: 0.5px; }}
        .spin-btn:hover {{ background: #dc2626; }}
        .slots-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }}
        @media(max-width: 768px) {{ .slots-grid {{ grid-template-columns: 1fr; }} }}
        .slot-column {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; }}
        .column-header {{ font-weight: bold; text-transform: uppercase; font-size: 12px; margin-bottom: 10px; padding-bottom: 5px; border-bottom: 2px solid #cbd5e1; color: #64748b; }}
        .slot-item {{ background: #fff; padding: 10px; border-radius: 6px; margin-bottom: 8px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.02); font-size: 13px; display: block; text-decoration: none; color: #334155; font-weight: 500; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }}
        .slot-item:hover {{ border-color: #ef4444; color: #ef4444; }}
        .search-wrapper {{ margin-bottom: 25px; }}
        .search-bar {{ width: 100%; padding: 14px 20px; font-size: 16px; border: 2px solid #e2e8f0; border-radius: 8px; box-sizing: border-box; outline: none; }}
        .search-bar:focus {{ border-color: #ef4444; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.01); border-left: 5px solid #64748b; display: block; text-decoration: none; color: inherit; }}
        .card.video {{ border-left-color: #ef4444; }}
        .card.podcast {{ border-left-color: #3b82f6; }}
        .card.blog {{ border-left-color: #10b981; }}
        .card h3 {{ margin: 0; font-size: 18px; color: #1e293b; }}
        .card h3:hover {{ color: #ef4444; }}
        .meta {{ font-size: 12px; color: #64748b; margin-top: 8px; display: flex; gap: 10px; align-items: center; }}
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
            <p>UWE Student Union Branch • Total Archived Items: {len(existing_archive)}</p>
        </header>

        <div class="fruit-machine-box">
            <div class="machine-header">
                <div class="machine-title">🍒 The CPD Fruit Machine</div>
                <button class="spin-btn" onclick="spinMachine()">🎰 Pull Lever</button>
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

        <div class="search-wrapper">
            <input type="text" id="searchInput" class="search-bar" placeholder="🔍 Search through chronologically sorted archives (e.g., triage, crush, hypoxia)..." onkeyup="filterArchive()">
        </div>

        <main id="archiveTimeline">
"""

for item in existing_archive:
    html_content += f"""
            <div class="card {item['type']}" data-title="{item['title'].lower()}">
                <h3><a href="{item['link']}" target="_blank">{item['title']}</a></h3>
                <div class="meta">
                    <span class="badge {item['type']}">{item['type']}</span>
                    <span>Published: {item['date_str']}</span>
                </div>
            </div>
    """

html_content += f"""
        </main>
    </div>

    <script>
        const archiveItems = {json.dumps(existing_archive)};

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

            vSlots.innerHTML = videos.map(v => `<a class="slot-item" href="${{v.link}}" target="_blank" title="${{v.title}}">📺 ${{v.title}}</a>`).join('');
            pSlots.innerHTML = podcasts.map(p => `<a class="slot-item" href="${{p.link}}" target="_blank" title="${{p.title}}">📻 ${{p.title}}</a>`).join('');
            bSlots.innerHTML = blogs.map(b => `<a class="slot-item" href="${{b.link}}" target="_blank" title="${{b.title}}">📄 ${{b.title}}</a>`).join('');
        }}

        function filterArchive() {{
            const query = document.getElementById('searchInput').value.toLowerCase();
            const cards = document.querySelectorAll('#archiveTimeline .card');

            cards.forEach(card => {{
                const title = card.getAttribute('data-title');
                if(title.includes(query)) {{
                    card.style.display = 'block';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}

        window.onload = spinMachine;
    </script>
</body>
</html>
"""

with open('public/index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Archive master compilation file synchronized successfully!")
