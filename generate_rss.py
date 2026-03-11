#!/usr/bin/env python3
"""生成播客 RSS Feed，支持 Apple Podcasts / 小宇宙等 App 订阅。"""

import os
import re
from datetime import datetime
from email.utils import formatdate
from pathlib import Path
from xml.sax.saxutils import escape

SITE_URL = "https://gljc1117.github.io/3d-print-policy-briefing"
AUDIO_DIR = Path(__file__).parent / "docs" / "audio"
OUTPUT_PATH = Path(__file__).parent / "docs" / "feed.xml"


def get_mp3_duration_seconds(filepath: str) -> int:
    """用 ffprobe 获取音频时长。"""
    cmd = f"ffprobe -i '{filepath}' -show_entries format=duration -v quiet -of csv='p=0'"
    try:
        return int(float(os.popen(cmd).read().strip()))
    except (ValueError, TypeError):
        return 600  # fallback 10 min


def format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def generate_rss():
    # 扫描所有 podcast MP3
    episodes = []
    for mp3 in sorted(AUDIO_DIR.glob("podcast-*.mp3"), reverse=True):
        # 从文件名提取日期 podcast-2026-03-11.mp3
        match = re.search(r"podcast-(\d{4}-\d{2}-\d{2})\.mp3", mp3.name)
        if not match:
            continue
        date_str = match.group(1)
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        size = mp3.stat().st_size
        duration = get_mp3_duration_seconds(str(mp3))

        episodes.append({
            "title": f"子殷科技政策早报 {date_str}",
            "date": formatdate(dt.timestamp(), localtime=True),
            "date_str": date_str,
            "url": f"{SITE_URL}/audio/{mp3.name}",
            "size": size,
            "duration": format_duration(duration),
            "description": f"{date_str} 子殷科技政策与行业动态播客简报，涵盖医保政策、招投标、科技厅、工信厅、发改委、财政厅、教育厅及全球新闻。",
        })

    # 生成 RSS XML
    items_xml = ""
    for ep in episodes:
        items_xml += f"""
    <item>
      <title>{escape(ep['title'])}</title>
      <description>{escape(ep['description'])}</description>
      <pubDate>{ep['date']}</pubDate>
      <enclosure url="{ep['url']}" length="{ep['size']}" type="audio/mpeg"/>
      <itunes:duration>{ep['duration']}</itunes:duration>
      <itunes:episode>{ep['date_str'].replace('-','')}</itunes:episode>
      <guid isPermaLink="true">{ep['url']}</guid>
    </item>"""

    pub_date = episodes[0]["date"] if episodes else formatdate(localtime=True)

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>子殷科技·政策早报</title>
  <link>{SITE_URL}</link>
  <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
  <description>内蒙古子殷科技有限公司政策与行业动态播客简报。AI 自动监测医保政策、招投标、科技厅、工信厅、发改委、财政厅、教育厅及全球医疗3D打印/PEEK/AI行业新闻。</description>
  <language>zh-cn</language>
  <lastBuildDate>{pub_date}</lastBuildDate>
  <itunes:author>子殷科技</itunes:author>
  <itunes:summary>子殷科技政策与行业动态AI播客</itunes:summary>
  <itunes:owner>
    <itunes:name>子殷科技</itunes:name>
    <itunes:email>liyingxi49@gmail.com</itunes:email>
  </itunes:owner>
  <itunes:category text="Business">
    <itunes:category text="Management"/>
  </itunes:category>
  <itunes:explicit>false</itunes:explicit>
  <itunes:type>episodic</itunes:type>
  {items_xml}
</channel>
</rss>"""

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(rss)

    print(f"[INFO] RSS Feed 生成完成: {OUTPUT_PATH}")
    print(f"[INFO] 共 {len(episodes)} 期节目")
    print(f"[INFO] 订阅地址: {SITE_URL}/feed.xml")


if __name__ == "__main__":
    generate_rss()
