#!/usr/bin/env python3
"""
每周自动搜索全球医学+人工智能+3D打印领域新闻，生成子殷科技专属行业简报。
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "liyingxi49@gmail.com")

MODEL = "claude-haiku-4-5-20251001"
TODAY = datetime.now().strftime("%Y-%m-%d")
ONE_WEEK_AGO = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

# ──────────────────────── Stage 1: 搜索 ──────────────────────

SEARCH_PROMPT = f"""今天是 {TODAY}。
请搜索 **{ONE_WEEK_AGO} 至 {TODAY}** 期间，全球范围内与"医学 + 人工智能 + 3D打印"交叉领域相关的最新新闻、论文、产品发布、融资、行业动态。

搜索范围覆盖以下细分方向（中英文都要搜）：

【医学3D打印】
1. "医学3D打印 最新进展 {datetime.now().year}"
2. "3D printed implant orthopedic 2026"
3. "3D打印 骨科植入物 PEEK 最新"
4. "3D打印 手术导板 手术模型 临床应用"
5. "bioprinting organ tissue 2026"
6. "生物3D打印 组织器官 最新突破"

【医学AI / 医学影像AI】
7. "医学影像 AI 人工智能 最新 {datetime.now().year}"
8. "medical imaging AI radiology 2026"
9. "AI 辅助诊断 骨科 影像 最新"
10. "AI surgical planning 3D reconstruction"
11. "医学影像三维重建 AI 深度学习"

【AI + 3D打印融合】
12. "AI 3D printing medical personalized 2026"
13. "人工智能 3D打印 个性化医疗 最新"
14. "AI驱动 医疗器械 智能制造"
15. "digital twin orthopedic 3D printing"

【行业融资与商业化】
16. "3D printing medical startup funding 2026"
17. "医疗3D打印 融资 商业化 {datetime.now().year}"
18. "medical AI company funding Series 2026"

【监管与标准】
19. "FDA 3D printed medical device approval 2026"
20. "NMPA 3D打印 医疗器械 注册审批 {datetime.now().year}"

严格规则：
- 只包含 {ONE_WEEK_AGO} 之后发布的内容
- 每条结果必须附带真实的来源链接
- 如果某组搜索没有近一周结果，跳过
- 中文和英文新闻都要覆盖

请输出一个 JSON 数组（不要 markdown 代码块包裹），每个元素格式如下：
{{
  "category": "医学3D打印/医学AI/AI+3D打印融合/行业融资/监管标准",
  "region": "国家或地区",
  "date": "YYYY-MM-DD",
  "title": "新闻标题（中文）",
  "title_original": "原始标题（如英文则保留英文）",
  "source": "来源媒体/期刊",
  "summary": "核心内容摘要，150字以内，用中文",
  "relevance": "与子殷科技业务的关联分析，50字以内",
  "url": "原文链接"
}}

关于"与子殷科技业务的关联分析"，参考以下业务背景：
- 核心业务：医疗3D打印（定制骨科器械、PEEK材料、后装放疗模具）、医疗AI平台
- 战略项目：盘古计划（医学影像Agent操作系统）、数智骨科临床转化中心（与天津医院合作）
- 合作医院：上海六院、内蒙古医科大二附院、天津医院、广元市第一人民医院、内蒙古国际蒙医医院
- 资质：二类医疗器械注册证
- 工厂：上海松江泗泾400㎡

如果没有任何近一周的新闻，请输出空数组 []。"""


def _call_with_tool_loop(client, prompt: str, max_turns: int = 25) -> str:
    """手动处理 web_search 多轮 tool_use，每轮只保留必要上下文。"""
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20250305", "name": "web_search"}]
    final_text = ""
    for turn in range(max_turns):
        response = client.messages.create(
            model=MODEL, max_tokens=16384, tools=tools, messages=messages,
        )
        for block in response.content:
            if block.type == "text":
                final_text += block.text
        if response.stop_reason == "end_turn":
            break
        tool_results = [b for b in response.content if b.type == "tool_use"]
        if not tool_results:
            break
        assistant_msg = {"role": "assistant", "content": response.content}
        tool_result_blocks = [
            {"type": "tool_result", "tool_use_id": t.id, "content": "搜索完成，请继续下一个搜索或输出最终结果。"}
            for t in tool_results
        ]
        messages = [
            {"role": "user", "content": prompt},
            assistant_msg,
            {"role": "user", "content": tool_result_blocks},
        ]
        print(f"[INFO] web_search 第 {turn + 1} 轮完成")
    return final_text


def search_news() -> list[dict]:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    text = _call_with_tool_loop(client, SEARCH_PROMPT)
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
        text = text.strip()
    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            items = json.loads(text[start:end])
        else:
            print(f"[WARN] JSON解析失败:\n{text[:500]}")
            items = []
    print(f"[INFO] 搜索到 {len(items)} 条全球行业新闻")
    return items


# ──────────────────── Stage 2: 生成 HTML ─────────────────────

CATEGORY_STYLE = {
    "医学3D打印": {"color": "#2980b9", "icon": "🏥"},
    "医学AI": {"color": "#8e44ad", "icon": "🧠"},
    "AI+3D打印融合": {"color": "#d35400", "icon": "⚡"},
    "行业融资": {"color": "#27ae60", "icon": "💰"},
    "监管标准": {"color": "#c0392b", "icon": "📋"},
}


def build_html(items: list[dict]) -> str:
    date_range = f"{ONE_WEEK_AGO} ~ {TODAY}"

    if not items:
        items_html = """
        <div style="padding:20px;background:#fef9e7;border-left:4px solid #f39c12;margin:16px 0;border-radius:4px;">
            <p style="margin:0;color:#7d6608;">本周暂未检索到相关行业新闻。将持续监测。</p>
        </div>"""
    else:
        # 按分类分组
        grouped: dict[str, list[dict]] = {}
        for item in items:
            cat = item.get("category", "其他")
            grouped.setdefault(cat, []).append(item)

        sections = []
        for cat, cat_items in grouped.items():
            style = CATEGORY_STYLE.get(cat, {"color": "#7f8c8d", "icon": "📰"})
            cards = []
            for item in cat_items:
                relevance = item.get("relevance", "")
                source = item.get("source", "")
                region = item.get("region", "")
                title_orig = item.get("title_original", "")

                relevance_line = f"""
                <div style="background:#fef9e7;border-left:3px solid #f39c12;padding:8px 12px;margin:8px 0;border-radius:0 4px 4px 0;">
                    <span style="font-size:12px;color:#7d6608;font-weight:bold;">与子殷关联：</span>
                    <span style="font-size:13px;color:#7d6608;">{relevance}</span>
                </div>""" if relevance else ""

                title_orig_line = f'<p style="margin:2px 0;font-size:12px;color:#999;font-style:italic;">{title_orig}</p>' if title_orig and title_orig != item.get("title", "") else ""

                card = f"""
                <div style="border:1px solid #eee;border-radius:6px;padding:14px;margin:10px 0;background:#fff;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;flex-wrap:wrap;gap:4px;">
                        <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
                            <span style="background:#ecf0f1;padding:2px 8px;border-radius:4px;font-size:12px;color:#555;">{region}</span>
                            <span style="color:#999;font-size:12px;">{source}</span>
                        </div>
                        <span style="color:#888;font-size:12px;">{item.get('date','')}</span>
                    </div>
                    <h3 style="margin:6px 0;font-size:15px;color:#1a5276;">{item.get('title','')}</h3>
                    {title_orig_line}
                    <p style="margin:6px 0;color:#555;font-size:14px;line-height:1.7;">{item.get('summary','')}</p>
                    {relevance_line}
                    <a href="{item.get('url','#')}" style="color:{style['color']};font-size:13px;text-decoration:none;">阅读原文 →</a>
                </div>"""
                cards.append(card)

            section = f"""
            <div style="margin:24px 0;">
                <h2 style="color:{style['color']};border-bottom:2px solid {style['color']};padding-bottom:8px;font-size:18px;">
                    {style['icon']} {cat}
                    <span style="font-size:13px;color:#999;font-weight:normal;margin-left:8px;">({len(cat_items)}条)</span>
                </h2>
                {''.join(cards)}
            </div>"""
            sections.append(section)

        items_html = "\n".join(sections)

    # 统计
    total = len(items)
    cat_summary = ""
    if items:
        cat_counts: dict[str, int] = {}
        for item in items:
            c = item.get("category", "其他")
            cat_counts[c] = cat_counts.get(c, 0) + 1
        tags = []
        for c, n in cat_counts.items():
            style = CATEGORY_STYLE.get(c, {"color": "#7f8c8d", "icon": "📰"})
            tags.append(f'<span style="background:{style["color"]};color:#fff;padding:3px 12px;border-radius:12px;font-size:13px;margin:3px;">{style["icon"]} {c} {n}</span>')
        cat_summary = f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin:12px 0;">{"".join(tags)}</div>'

    html = f"""<html><body style="font-family:'Microsoft YaHei',Arial,sans-serif;max-width:760px;margin:0 auto;color:#333;line-height:1.8;background:#f5f6fa;">

<div style="background:linear-gradient(135deg,#0c0c0c,#1a1a2e,#16213e);padding:28px 32px;border-radius:8px 8px 0 0;">
  <h1 style="color:#fff;margin:0;font-size:24px;">全球行业情报·周刊</h1>
  <p style="color:#a29bfe;margin:4px 0 0;font-size:15px;">医学 × 人工智能 × 3D打印</p>
  <p style="color:#636e72;margin:8px 0 0;font-size:13px;">内蒙古子殷科技有限公司 | {TODAY}</p>
</div>

<div style="padding:24px 32px;border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px;background:#fff;">

<div style="background:#f8f9fa;border-radius:6px;padding:16px;margin-bottom:20px;">
  <p style="margin:0;font-size:14px;color:#555;">
    监测时段：<b>{date_range}</b>&nbsp;&nbsp;|&nbsp;&nbsp;
    共收录 <b style="color:#e74c3c;font-size:18px;">{total}</b> 条行业动态
  </p>
  {cat_summary}
</div>

{items_html}

<div style="background:#f0f3f5;border-radius:6px;padding:16px;margin-top:24px;">
  <h3 style="margin:0 0 8px;font-size:15px;color:#1a5276;">子殷科技业务对标</h3>
  <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <tr><td style="padding:4px 8px;color:#888;width:100px;">核心业务</td><td style="padding:4px 8px;">医疗3D打印（骨科器械/PEEK/放疗模具） · 医疗AI平台</td></tr>
    <tr><td style="padding:4px 8px;color:#888;">战略项目</td><td style="padding:4px 8px;">盘古计划（医学影像Agent OS） · 数智骨科临床转化中心</td></tr>
    <tr><td style="padding:4px 8px;color:#888;">合作医院</td><td style="padding:4px 8px;">上海六院 · 天津医院 · 内蒙古医科大二附院 · 广元一院 · 蒙医医院</td></tr>
    <tr><td style="padding:4px 8px;color:#888;">资质/产能</td><td style="padding:4px 8px;">二类医疗器械注册证 · 上海松江工厂400㎡</td></tr>
  </table>
</div>

<hr style="border:none;border-top:1px solid #ddd;margin:20px 0;">
<p style="font-size:12px;color:#999;">本简报由 AI 自动搜集全球公开信息并生成，仅供内部参考。每条新闻均标注了与子殷科技业务的关联分析，供决策参考。</p>
</div>
</body></html>"""
    return html


# ──────────────────── Stage 3: 发送邮件 ─────────────────────


def send_email(html: str):
    subject = f"【子殷科技·全球周刊】医学×AI×3D打印 行业情报（{TODAY}）"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print(f"[INFO] 邮件已发送至 {RECIPIENT_EMAIL}")


# ──────────────────────── Main ───────────────────────────────


def main():
    print(f"[INFO] 全球行业周刊 | {ONE_WEEK_AGO} ~ {TODAY}")
    try:
        items = search_news()
    except Exception as e:
        print(f"[ERROR] 搜索失败: {e}")
        items = []
    html = build_html(items)
    try:
        send_email(html)
    except Exception as e:
        print(f"[ERROR] 邮件发送失败: {e}")
        sys.exit(1)
    print("[INFO] 完成")


if __name__ == "__main__":
    main()
