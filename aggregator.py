import os
import xml.etree.ElementTree as ET
import urllib.request
import json
from datetime import datetime

# 1. Read the OPML file to extract all the RSS/Atom links
print("Parsing feeds.opml...")
tree = ET.parse('feeds.opml')
root = tree.getroot()
feed_urls = []

# Find all feed elements containing URLs
for outline in root.findall('.//outline'):
    xml_url = outline.get('xmlUrl')
    if xml_url:
        feed_urls.append(xml_url)

print(f"Found {len(feed_urls)} source feeds.")

# 2. Fetch data from each feed using basic cross-platform python requests
all_items = []
for url in feed_urls[:40]: # Limit to first 40 sources for speed
    try:
        print(f"Fetching: {url}")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
            feed_root = ET.fromstring(xml_data)
            
            # Look for standard RSS items or Atom entries
            channel = feed_root.find('channel')
            items = channel.findall('item') if channel is not None else feed_root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            for item in items[:5]: # Get latest 5 posts from each source
                title = item.findtext('title') or item.findtext('{http://www.w3.org/2005/Atom}title')
                link = item.findtext('link') or item.find('.//{http://www.w3.org/2005/Atom}link').get('href') if item.find('{http://www.w3.org/2005/Atom}link') is not None else ""
                pub_date = item.findtext('pubDate') or item.findtext('{http://www.w3.org/2005/Atom}published') or "Recent"
                
                if title and link:
                    all_items.append({"title": title, "link": link, "date": pub_date})
    except Exception as e:
        print(f"Skipping bad feed {url}: {e}")

# 3. Create a stunning, responsive public HTML page
os.makedirs('public', exist_ok=True)
html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rescue & Remote Medicine Society Hub</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f4f6f8; color: #333; margin: 0; padding: 20px; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        header {{ text-align: center; margin-bottom: 40px; background: #1e293b; color: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
        h1 {{ margin: 0; font-size: 24px; }}
        p {{ color: #94a3b8; margin-top: 5px; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); border-left: 5px solid #ef4444; transition: transform 0.2s; }}
        .card:hover {{ transform: translateY(-2px); }}
        .card a {{ text-decoration: none; color: #1e293b; font-weight: bold; font-size: 18px; }}
        .card a:hover {{ color: #ef4444; }}
        .meta {{ font-size: 12px; color: #64748b; margin-top: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Rescue & Remote Medicine Society Feed</h1>
            <p>Aggregated Knowledge Base • Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </header>
        <main>
"""

for item in all_items:
    html_content += f"""
            <div class="card">
                <a href="{item['link']}" target="_blank">{item['title']}</a>
                <div class="meta">Published: {item['date']}</div>
            </div>
    """

html_content += """
        </main>
    </div>
</body>
</html>
"""

with open('public/index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)
print("Website generation completely successful!")
