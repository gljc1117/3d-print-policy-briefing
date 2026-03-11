#!/usr/bin/env python3
"""
子殷科技·每日政策播客简报（双主播对话版）
数据 → Claude 生成双人对话文稿 → Edge TTS 双声道合成 → 拼接输出
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import edge_tts

# ──────────────────────────── 配置 ────────────────────────────

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-haiku-4-5-20251001"

TODAY = datetime.now().strftime("%Y-%m-%d")
DATA_DIR = Path(__file__).parent / "docs" / "data"
OUTPUT_DIR = Path(__file__).parent / "audio"

# 双主播语音
HOST_A_VOICE = "zh-CN-XiaoxiaoNeural"   # 女声（晓晓）— 主持人A
HOST_B_VOICE = "zh-CN-YunxiNeural"      # 男声（云希）— 主持人B
HOST_A_NAME = "晓晓"
HOST_B_NAME = "云希"

# 模块配置
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


# ──────────────────── Stage 2: 生成对话文稿 ──────────────────


def generate_podcast_script(data: dict) -> list[dict]:
    """用 Claude 生成双主播对话文稿，返回 [{speaker, text}, ...] 列表。"""

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
                line += f" [关联: {relevance}]"
            data_text += line + "\n"

    prompt = f"""你是播客编剧。请将以下政策数据编写成一段两人对话的播客文稿。

两位主播：
- {HOST_A_NAME}（女，主持人，负责引导话题、提问、做总结）
- {HOST_B_NAME}（男，分析师，负责解读政策含义、分析对公司的影响）

背景：这是"子殷科技政策早报"播客，面向公司管理层。子殷科技是医疗3D打印公司，做PEEK骨科器械和医学影像AI。

要求：
1. 对话自然生动，像两个熟悉的同事在聊天，有互动、有追问、有感叹
2. 不要念URL链接
3. 每个板块自然过渡，不要生硬切换
4. 重要信息要有分析和解读，不是简单复述
5. 适当加入口语化表达，如"对""没错""这个很有意思""说到这个"等
6. 全文2000-3000字，约8-12分钟
7. 开头要有轻松的开场白，结尾要有总结展望

输出格式严格遵守：
每一句对话独占一行，格式为：
{HOST_A_NAME}：对话内容
{HOST_B_NAME}：对话内容

不要加任何其他标记（*、#、括号动作描述等），只要"名字：内容"的纯文本。

今天是{TODAY}，以下是数据：
{data_text}"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system="你是顶级播客编剧，擅长将枯燥数据变成引人入胜的对话。只输出对话文稿，不要任何说明。",
        messages=[{"role": "user", "content": prompt}],
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text

    print(f"[INFO] 对话文稿生成完成，{len(text)} 字")

    # 解析对话
    dialogues = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith(f"{HOST_A_NAME}：") or line.startswith(f"{HOST_A_NAME}:"):
            content = re.split(r"[：:]", line, maxsplit=1)[1].strip()
            dialogues.append({"speaker": "A", "text": content})
        elif line.startswith(f"{HOST_B_NAME}：") or line.startswith(f"{HOST_B_NAME}:"):
            content = re.split(r"[：:]", line, maxsplit=1)[1].strip()
            dialogues.append({"speaker": "B", "text": content})

    print(f"[INFO] 解析出 {len(dialogues)} 段对话（A: {sum(1 for d in dialogues if d['speaker']=='A')}, B: {sum(1 for d in dialogues if d['speaker']=='B')}）")

    # 保存文稿
    script_path = OUTPUT_DIR / f"podcast-{TODAY}.txt"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[INFO] 文稿已保存: {script_path}")

    return dialogues


# ──────────────────── Stage 3: TTS 合成 ──────────────────────


async def synthesize_segment(text: str, voice: str, output_path: str):
    """合成单段语音。"""
    communicate = edge_tts.Communicate(text, voice, rate="+5%")
    await communicate.save(output_path)


async def synthesize_podcast(dialogues: list[dict], output_path: str):
    """逐段合成并用 ffmpeg 拼接。"""
    tmp_dir = OUTPUT_DIR / "tmp_segments"
    tmp_dir.mkdir(exist_ok=True)

    segment_files = []

    for i, d in enumerate(dialogues):
        voice = HOST_A_VOICE if d["speaker"] == "A" else HOST_B_VOICE
        seg_path = str(tmp_dir / f"seg_{i:04d}.mp3")

        print(f"  [{i+1}/{len(dialogues)}] {HOST_A_NAME if d['speaker']=='A' else HOST_B_NAME}: {d['text'][:30]}...")
        await synthesize_segment(d["text"], voice, seg_path)
        segment_files.append(seg_path)

    # 生成 ffmpeg 拼接列表
    list_path = str(tmp_dir / "segments.txt")
    with open(list_path, "w") as f:
        for seg in segment_files:
            f.write(f"file '{seg}'\n")

    # 拼接 + 转为标准 MP3
    cmd = (
        f"ffmpeg -y -f concat -safe 0 -i '{list_path}' "
        f"-ar 44100 -ab 128k -ac 1 '{output_path}' 2>&1"
    )
    result = os.popen(cmd).read()

    # 清理临时文件
    for seg in segment_files:
        os.remove(seg)
    os.remove(list_path)
    try:
        tmp_dir.rmdir()
    except OSError:
        pass

    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"[INFO] 播客音频生成完成: {output_path} ({size_mb:.1f} MB)")


# ──────────────────────── Main ───────────────────────────────


def main():
    print(f"[INFO] === 子殷科技·政策播客简报 === {TODAY}")

    # 1. 加载数据
    data = load_all_data()
    if not data:
        print("[ERROR] 无数据可用，请先运行 run_all_search.py")
        sys.exit(1)
    print(f"[INFO] 已加载 {len(data)} 个模块的数据")

    # 2. 生成对话文稿
    OUTPUT_DIR.mkdir(exist_ok=True)
    dialogues = generate_podcast_script(data)
    if not dialogues:
        print("[ERROR] 对话解析失败")
        sys.exit(1)

    # 3. TTS 合成
    audio_path = str(OUTPUT_DIR / f"podcast-{TODAY}.mp3")
    print(f"[INFO] 开始合成 {len(dialogues)} 段语音...")
    asyncio.run(synthesize_podcast(dialogues, audio_path))

    # 4. 播放时长
    duration_cmd = f"ffprobe -i '{audio_path}' -show_entries format=duration -v quiet -of csv='p=0'"
    duration = float(os.popen(duration_cmd).read().strip() or "0")
    minutes = int(duration // 60)
    seconds = int(duration % 60)
    print(f"[INFO] 播客时长: {minutes}分{seconds}秒")
    print(f"[INFO] === 播客生成完成 ===")


if __name__ == "__main__":
    main()
