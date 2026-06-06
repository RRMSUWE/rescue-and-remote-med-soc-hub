import os
import xml.etree.ElementTree as ET
import urllib.request
import json
from datetime import datetime
import email.utils
import re

ARCHIVE_FILE = 'public/archive.json'
existing_archive = []

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

for url in feed_urls[:40]:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
            
            try:
                feed_root = ET.fromstring(xml_data)
            except Exception as xml_err:
                print(f"Skipping feed {url} due to bad XML formatting: {xml_err}")
                continue
            
            channel = feed_root.find('channel')
            items = channel.findall('item') if channel is not None else feed_root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            if not items:
                items = feed_root.findall('item')
                
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
                    
                    pub_date_raw = item.findtext('pubDate') or item.findtext('{http://www.w3.org/2005/Atom}published') or ""
                    timestamp, date_display_str = robust_parse_date(pub_date_raw)

                    # Extract dynamic text categories/tags embedded by the creators
                    item_tags = []
                    for cat in item.findall('category') + item.findall('.//{http://www.w3.org/2005/Atom}category'):
                        tag_text = cat.text or cat.get('term') or ""
                        tag_text = tag_text.strip().title()
                        # Screen out unhelpful generic system tags if any exist
                        if tag_text and len(tag_text) < 20 and tag_text not in ["Uncategorized", "Post"]:
                            item_tags.append(tag_text)

                    lower_link = link_str.lower()
                    lower_title = str(title).lower()
                    
                    if "youtube.com" in lower_link or "youtu.be" in lower_link or "video" in lower_title:
                        item_type = "video"
                    elif "podcast" in lower_link or "spotify" in lower_link or "podcast" in lower_title or "audio" in lower_title or "episode" in lower_title:
                        item_type = "podcast"
                    else:
                        item_type = "blog"
                        
                    existing_archive.append({
                        "title": str(title), 
                        "link": link_str, 
                        "date_str": str(date_display_str), 
                        "timestamp": float(timestamp),
                        "type": item_type,
                        "tags": list(set(item_tags)) # Remove duplicate tags on a single post
                    })
                    known_links.add(link_str)
                    new_items_count += 1
                except Exception as item_err:
                    continue
                
    except Exception as e:
        print(f"Skipping feed {url}: {e}")
        continue

print(f"Archived {new_items_count} brand-new resources.")
existing_archive = [i for i in existing_archive if i.get('title') and i.get('link')]

try:
    existing_archive.sort(key=lambda x: float(x.get('timestamp', 0)), reverse=True)
except Exception:
    pass

# Collect every unique category tag across the whole history pool to build the menu options dynamically
master_tags_set = set()
for item in existing_archive:
    # Ensure backward compatibility if an old item object lacks the tags key
    if "tags" not in item:
        item["tags"] = []
    for t in item["tags"]:
        master_tags_set.add(t)

# Convert to list and sort alphabetically for a neat directory look
sorted_master_tags = sorted(list(master_tags_set))

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
        :root {{
            --brand-navy: #0f223d;
            --brand-crimson: #cf2027;
            --brand-crimson-hover: #b0181e;
            --brand-bg: #f5f7fa;
            --brand-slate: #475569;
        }}

        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--brand-bg); color: #222; margin: 0; padding: 20px; }}
        .container {{ max-width: 950px; margin: 0 auto; }}
        
        header {{ 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            gap: 25px; 
            margin-bottom: 30px; 
            background: var(--brand-navy); 
            color: white; 
            padding: 35px 25px; 
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(15, 34, 61, 0.15);
        }}
        .header-logo {{ width: 110px; height: 110px; border-radius: 50%; box-shadow: 0 0 0 4px rgba(255,255,255,0.1); flex-shrink: 0; }}
        .header-text {{ text-align: left; }}
        header h1 {{ margin: 0; font-size: 28px; letter-spacing: -0.5px; line-height: 1.2; }}
        header p {{ color: #cbd5e1; margin: 6px 0 0 0; font-size: 15px; font-weight: 500; }}
        
        @media(max-width: 600px) {{
            header {{ flex-direction: column; text-align: center; padding: 30px 15px; }}
            .header-text {{ text-align: center; }}
        }}

        .subheading {{ font-size: 20px; font-weight: bold; color: var(--brand-navy); margin: 35px 0 15px 0; border-bottom: 2px solid #cbd5e1; padding-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}
        
        /* Dynamic Category Pills Menu Styling */
        .tags-container {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 15px 0 25px 0; max-height: 145px; overflow-y: auto; padding: 8px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; }}
        .tag-pill {{ background: #f1f5f9; color: #475569; padding: 6px 14px; font-size: 13px; font-weight: 600; border-radius: 20px; cursor: pointer; border: 1px solid #cbd5e1; transition: all 0.15s; user-select: none; }}
        .tag-pill:hover {{ background: #e2e8f0; color: var(--brand-navy); }}
        .tag-pill.active {{ background: var(--brand-navy); color: white; border-color: var(--brand-navy); box-shadow: 0 2px 5px rgba(15,34,61,0.2); }}

        .fruit-machine-box {{ background: #fff; border: 3px dashed var(--brand-crimson); border-radius: 12px; padding: 25px; margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); }}
        .machine-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--brand-bg); padding-bottom: 12px; margin-bottom: 20px; }}
        .machine-title {{ font-weight: 800; font-size: 21px; color: var(--brand-navy); }}
        .spin-btn {{ background: var(--brand-crimson); color: white; border: none; padding: 12px 24px; font-weight: bold; border-radius: 6px; cursor: pointer; text-transform: uppercase; font-size: 13px; letter-spacing: 0.7px; transition: background 0.2s; }}
        .spin-btn:hover {{ background: var(--brand-crimson-hover); }}
        
        .slots-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }}
        @media(max-width: 768px) {{ .slots-grid {{ grid-template-columns: 1fr; }} }}
        .slot-column {{ background: var(--brand-bg); border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; }}
        .column-header {{ font-weight: bold; text-transform: uppercase; font-size: 12px; margin-bottom: 12px; color: var(--brand-slate); border-bottom: 2px solid #cbd5e1; padding-bottom: 5px; letter-spacing: 0.5px; }}
        
        .slot-item {{ background: #fff; padding: 12px; border-radius: 6px; margin-bottom: 8px; border: 1px solid #e2e8f0; font-size: 13px; display: flex; align-items: center; gap: 12px; text-decoration: none; color: #334155; font-weight: 600; line-height: 1.4; transition: border-color 0.15s, color 0.15s; }}
        .slot-item:hover {{ border-color: var(--brand-crimson); color: var(--brand-crimson); }}
        
        .media-icon-container {{ width: 42px; height: 42px; border-radius: 6px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
        .media-icon-container.video {{ background: #fef2f2; color: var(--brand-crimson); }}
        .media-icon-container.podcast {{ background: #eff6ff; color: #3b82f6; }}
        .media-icon-container.blog {{ background: #ecfdf5; color: #10b981; }}
        .media-icon-container svg {{ width: 22px; height: 22px; fill: currentColor; }}

        .card {{ background: white; padding: 18px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.02); display: flex; gap: 18px; align-items: center; text-decoration: none; color: inherit; border-left: 6px solid var(--brand-slate); transition: transform 0.15s, box-shadow 0.15s; }}
        .card.video {{ border-left-color: var(--brand-crimson); }}
        .card.podcast {{ border-left-color: #3b82f6; }}
        .card.blog {{ border-left-color: #10b981; }}
        .card:hover {{ transform: translateY(-1px); box-shadow: 0 4px 10px rgba(0,0,0,0.04); }}
        
        .card .media-icon-container {{ width: 52px; height: 52px; border-radius: 8px; }}
        .card .media-icon-container svg {{ width: 26px; height: 26px; }}
        
        .search-bar {{ width: 100%; padding: 15px 20px; font-size: 16px; border: 2px solid #cbd5e1; border-radius: 8px; box-sizing: border-box; outline: none; margin-bottom: 10px; background: white; }}
        .search-bar:focus {{ border-color: var(--brand-navy); }}
        .card-body {{ flex-grow: 1; }}
        .card h3 {{ margin: 0 0 6px 0; font-size: 18px; color: var(--brand-navy); font-weight: 700; line-height: 1.3; }}
        .meta {{ font-size: 12px; color: var(--brand-slate); display: flex; gap: 12px; align-items: center; font-weight: 500; }}
        .card-tags {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }}
        .card-tag-inline {{ font-size: 11px; background: #f1f5f9; color: #64748b; padding: 1px 6px; border-radius: 4px; border: 1px solid #e2e8f0; font-weight: bold; }}
        
        .badge {{ text-transform: uppercase; font-weight: bold; font-size: 10px; padding: 3px 7px; border-radius: 4px; color: white; }}
        .badge.video {{ background: var(--brand-crimson); }}
        .badge.podcast {{ background: #3b82f6; }}
        .badge.blog {{ background: #10b981; }}
    </style>
</head>
<body>
    <div class="container">
        
        <header>
            <img class="header-logo" src="logo.png" alt="RRMS UWE Logo">
            <div class="header-text">
                <h1>Rescue &amp; Remote Medicine Society Hub</h1>
                <p>University of the West of England Student Union Branch • Active Pool: {len(existing_archive)} Resources</p>
            </div>
        </header>

        <div class="fruit-machine-box">
            <div class="machine-header">
                <div class="machine-title">🎰 The CPD Fruit Machine</div>
                <button class="spin-btn" onclick="spinMachine()">Pull Lever to Randomise</button>
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

        <div class="subheading">Search the Archive</div>
        <input type="text" id="searchInput" class="search-bar" placeholder="🔍 Search resource library by keywords..." onkeyup="masterFilter()">

        <div class="subheading">Browse by Category</div>
        <div class="tags-container" id="tagMenuBox">
            <div class="tag-pill active" onclick="toggleTagFilter(this, 'ALL')">All Categories</div>
"""

# Render out the unique source tags as interactive buttons
for tag in sorted_master_tags:
    # Escape single quotes out of medical tag names for standard javascript safety
    safe_js_tag = tag.replace("'", "\\'")
    html_content += f"""            <div class="tag-pill" onclick="toggleTagFilter(this, '{safe_js_tag}')">{tag}</div>\n"""

html_content += f"""        </div>

        <div class="subheading">Archive</div>
        <main id="archiveTimeline">
"""

icons = {
    "video": '<svg viewBox="0 0 24 24"><path d="M21 6h-7.59l3.29-3.29L16 1.41 11.59 5.82 11.41 6H3c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h18c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm0 14H3V8h18v12zM9 10v8l7-4z"/></svg>',
    "podcast": '<svg viewBox="0 0 24 24"><path d="M12 2c-4.97 0-9 4.03-9 9v7c0 1.66 1.34 3 3 3h3v-8H5v-2c0-3.87 3.13-7 7-7s7 3.13 7 7v2h-4v8h3c1.66 0 3-1.34 3-3v-7c0-4.97-4.03-9-9-9z"/></svg>',
    "blog": '<svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-1 16H6c-.55 0-1-.45-1-1V6c0-.55.45-1 1-1h12c.55 0 1 .45 1 1v12c0 .55-.45 1-1 1zm-4-4H7v-2h7v2zm3-4H7V9h10v2z"/></svg>'
}

for item in existing_archive:
    clean_title = item['title'].replace('"', '&quot;').replace("'", "&#39;")
    tags_list_str = json.dumps(item.get('tags', []))
    
    # Inline rendering block of the individual tags inside the card
    inline_tags_html = "".join([f'<span class="card-tag-inline">{t}</span>' for t in item.get('tags', [])])
    
    html_content += f"""
            <a href="{item['link']}" target="_blank" class="card {item['type']}" data-title="{clean_title.lower()}" data-tags='{tags_list_str}'>
                <div class="media-icon-container {item['type']}">
                    {icons[item['type']]}
                </div>
                <div class="card-body">
                    <h3>{item['title']}</h3>
                    <div class="meta">
                        <span class="badge {item['type']}">{item['type']}</span>
                        <span>Published: {item['date_str']}</span>
                    </div>
                    <div class="card-tags">{inline_tags_html}</div>
                </div>
            </a>
    """

html_content += f"""
        </main>
    </div>

    <script>
        const archiveItems = {json.dumps(existing_archive)};
        const svgIcons = {json.dumps(icons)};
        let activeSelectedTag = "ALL";

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

            vSlots.innerHTML = videos.map(v => `
                <a class="slot-item" href="${{v.link}}" target="_blank">
                    <div class="media-icon-container video">${{svgIcons.video}}</div>
                    <span>${{v.title}}</span>
                </a>
            `).join('');

            pSlots.innerHTML = podcasts.map(p => `
                <a class="slot-item" href="${{p.link}}" target="_blank">
                    <div class="media-icon-container podcast">${{svgIcons.podcast}}</div>
                    <span>${{p.title}}</span>
                </a>
            `).join('');

            bSlots.innerHTML = blogs.map(b => `
                <a class="slot-item" href="${{b.link}}" target="_blank">
                    <div class="media-icon-container blog">${{svgIcons.blog}}</div>
                    <span>${{b.title}}</span>
                </a>
            `).join('');
        }}

        // Handle category selection toggles
        function toggleTagFilter(element, tagValue) {{
            document.querySelectorAll('.tag-pill').forEach(pill => pill.classList.remove('active'));
            element.classList.add('active');
            activeSelectedTag = tagValue;
            masterFilter(); // Trigger combined filter evaluate
        }}

        // Combined filtering machine (Handles Search Keywords + Category Pills simultaneously)
        function masterFilter() {{
            const query = document.getElementById('searchInput').value.toLowerCase();
            const cards = document.querySelectorAll('#archiveTimeline .card');

            cards.forEach(card => {{
                const title = card.getAttribute('data-title');
                const cardTags = JSON.parse(card.getAttribute('data-tags') || "[]");
                
                const matchesKeyword = title.includes(query);
                const matchesCategory = (activeSelectedTag === "ALL") || cardTags.includes(activeSelectedTag);

                if(matchesKeyword && matchesCategory) {{
                    card.style.display = 'flex';
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

print("Dynamic operational indexing categorized completely!")
