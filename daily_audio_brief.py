#!/usr/bin/env python3
"""
子殷科技·每日政策语音简报
从 JSON 数据生成播客风格文稿 → TTS 合成音频 → 邮件推送
"""

import asyncio
import json
import os
import smtplib
import sys
from datetime import datetime
from email.mime.audio import MIMEAudio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import anthropic
import edge_tts

# ──────────────────────────── 配置 ────────────────────────────

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-haiku-4-5-20251001"

TODAY = datetime.now().strftime("%Y-%m-%d")
DATA_DIR = Path(__file__).parent / "docs" / "data"
OUTPUT_DIR = Path(__file__).parent / "audio"

# 中文语音选项（edge-tts 微软语音）
# zh-CN-XiaoxiaoNeural: 女声，温暖专业
# zh-CN-YunxiNeural: 男声，稳重
# zh-CN-XiaoyiNeural: 女声，活泼
VOICE = os.environ.get("TTS_VOICE", "zh-CN-XiaoxiaoNeural")

# 模块配置：名称 + 文件 + 每模块最多播报条数
MODULES = [
    ("医保定价政策", "briefing.json", 5),
    ("招投标信息", "bidding.json", 5),
    ("科技厅项目", "kejitin.json", 3),
    ("工信厅政策", "gongxinting.json", 3),
    ("发改委动态", "fagaiwei.json", 3),
    ("财政厅补贴", "caizhengtng.json", 3),
    ("教育厅产学研", "jiaoyuting.json", 3),
    ("全球行业新闻", "global_news.json", 5),
]


# ──────────────────── Stage 1: 读取数据 ──────────────────────


def load_all_data() -> dict:
    """读取所有模块的 JSON 数据。"""
    data = {}
    for name, filename, max_items in MODULES:
        filepath = DATA_DIR / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                raw = json.load(f)
            items = raw.get("items", [])[:max_items]
            if items:
                data[name] = {
                    "items": items,
                    "total": raw.get("count", len(items)),
                    "updated": raw.get("updated", "未知"),
                }
    return data


# ──────────────────── Stage 2: 生成文稿 ──────────────────────


def generate_script(data: dict) -> str:
    """用 Claude 将结构化数据转化为播客风格的语音文稿。"""

    # 构建数据摘要
    data_text = ""
    for module_name, info in data.items():
        data_text += f"\n## {module_name}（共{info['total']}条，展示前{len(info['items'])}条）\n"
        for i, item in enumerate(info["items"], 1):
            title = item.get("title", "")
            summary = item.get("summary", "")
            province = item.get("province", item.get("region", ""))
            date = item.get("date", "")
            relevance = item.get("relevance", "")
            line = f"{i}. "
            if province:
                line += f"【{province}】"
            if date:
                line += f"({date}) "
            line += f"{title}"
            if summary:
                line += f" — {summary}"
            if relevance:
                line += f" [关联分析: {relevance}]"
            data_text += line + "\n"

    prompt = f"""你是"子殷科技政策简报"的AI主播。请将以下政策数据转化为一段自然流畅的语音播报文稿。

要求：
1. 开头用一句话问候，如"各位好，这里是子殷科技每日政策简报，今天是{TODAY}。"
2. 按板块播报，每个板块用一句过渡语引入（如"首先来看医保政策方面..."）
3. 每条信息用口语化方式播报，不要念链接URL
4. 重点突出与子殷科技业务（医疗3D打印、PEEK骨科器械、医学影像AI）直接相关的内容
5. 结尾做简短总结和展望
6. 全文控制在1500-2500字，播报时长约5-8分钟
7. 语气专业但不枯燥，适合早晨通勤收听
8. 不要加任何标记符号（如*、#、【】），纯文字即可

以下是今日数据：
{data_text}"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system="你是专业的商业播客主播，擅长将政策数据转化为生动的语音播报。只输出播报文稿，不要任何其他说明。",
        messages=[{"role": "user", "content": prompt}],
    )

    script = ""
    for block in response.content:
        if block.type == "text":
            script += block.text

    print(f"[INFO] 文稿生成完成，{len(script)} 字")
    return script


# ──────────────────── Stage 3: TTS 合成 ──────────────────────


async def text_to_speech(text: str, output_path: str) -> str:
    """使用 Edge TTS 将文稿转为音频。"""
    communicate = edge_tts.Communicate(text, VOICE, rate="+5%", pitch="+0Hz")
    await communicate.save(output_path)
    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"[INFO] 音频生成完成: {output_path} ({size_mb:.1f} MB)")
    return output_path


# ──────────────────── Stage 4: 邮件推送 ──────────────────────


def send_email_with_audio(audio_path: str, script: str):
    """发送带音频附件的邮件。"""
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("RECIPIENT_EMAIL", "liyingxi49@gmail.com")

    if not gmail_address or not gmail_password:
        print("[WARN] Gmail 未配置，跳过邮件发送")
        return

    msg = MIMEMultipart()
    msg["Subject"] = f"【子殷科技·语音简报】{TODAY} 政策与行业动态"
    msg["From"] = gmail_address
    msg["To"] = recipient

    # HTML 正文（文稿摘要）
    paragraphs = script.split("\n\n")
    summary_html = "<br><br>".join(
        f"<p style='font-size:14px;color:#333;line-height:1.8;'>{p.strip()}</p>"
        for p in paragraphs[:3]
    )

    html = f"""<html><body style="font-family:'Microsoft YaHei',Arial,sans-serif;max-width:680px;margin:0 auto;">
    <div style="background:linear-gradient(135deg,#1a5276,#2980b9);padding:20px 28px;border-radius:8px 8px 0 0;">
        <h1 style="color:#fff;margin:0;font-size:20px;">子殷科技·每日政策语音简报</h1>
        <p style="color:#d4e6f1;margin:6px 0 0;font-size:13px;">{TODAY} | 附件为完整音频</p>
    </div>
    <div style="padding:20px 28px;border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px;background:#fff;">
        <p style="font-size:13px;color:#888;">以下为简报文稿摘要，完整音频请下载附件收听：</p>
        {summary_html}
        <p style="font-size:13px;color:#888;margin-top:16px;">...（完整内容请收听音频附件）</p>
        <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
        <p style="font-size:11px;color:#bbb;">本简报由 AI 自动生成，仅供内部参考。</p>
    </div>
    </body></html>"""

    msg.attach(MIMEText(html, "html", "utf-8"))

    # 附加音频
    with open(audio_path, "rb") as f:
        audio_part = MIMEAudio(f.read(), _subtype="mpeg")
    audio_part.add_header(
        "Content-Disposition", "attachment",
        filename=f"ziyin-brief-{TODAY}.mp3",
    )
    msg.attach(audio_part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_password)
        server.send_message(msg)

    print(f"[INFO] 语音简报邮件已发送至 {recipient}")


# ──────────────────────── Main ───────────────────────────────


def main():
    print(f"[INFO] === 子殷科技·每日政策语音简报 === {TODAY}")

    # 1. 加载数据
    data = load_all_data()
    if not data:
        print("[ERROR] 无数据可用，请先运行 run_all_search.py")
        sys.exit(1)
    print(f"[INFO] 已加载 {len(data)} 个模块的数据")

    # 2. 生成文稿
    script = generate_script(data)

    # 保存文稿
    OUTPUT_DIR.mkdir(exist_ok=True)
    script_path = OUTPUT_DIR / f"brief-{TODAY}.txt"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    print(f"[INFO] 文稿已保存: {script_path}")

    # 3. TTS 合成
    audio_path = str(OUTPUT_DIR / f"brief-{TODAY}.mp3")
    asyncio.run(text_to_speech(script, audio_path))

    # 4. 邮件推送
    try:
        send_email_with_audio(audio_path, script)
    except Exception as e:
        print(f"[WARN] 邮件发送失败: {e}")
        print(f"[INFO] 音频文件在本地: {audio_path}")

    print("[INFO] === 语音简报流程完成 ===")


if __name__ == "__main__":
    main()
