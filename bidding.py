#!/usr/bin/env python3
"""
每周自动搜索各省医学影像三维重建、3D打印相关招投标信息，生成简报并发送邮件。
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic

# ──────────────────────────── 配置 ────────────────────────────

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "liyingxi49@gmail.com")

MODEL = "claude-haiku-4-5-20251001"
TODAY = datetime.now().strftime("%Y-%m-%d")
ONE_MONTH_AGO = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

# ──────────────────────── Stage 1: 搜索 ──────────────────────

SEARCH_PROMPT = f"""今天是 {TODAY}。
请搜索 **{ONE_MONTH_AGO} 至 {TODAY}** 期间，中国各省市关于"医学影像三维重建"和"3D打印"相关的招投标信息（包括招标公告、中标公告、采购需求公示等）。

请依次使用以下搜索关键词（每组至少搜索一次）：
1. "医学影像三维重建 招标 {datetime.now().year}"
2. "3D打印 骨科 招标公告 中标"
3. "医学3D打印 采购 招投标"
4. "三维重建 手术导板 3D打印 招标"
5. "个性化骨科器械 3D打印 中标公告"
6. "医学影像 三维建模 采购公告"
7. "PEEK 3D打印 医疗 招标"
8. "后装放疗模具 3D打印 采购"
9. "数字骨科 3D打印 招标 医院"
10. "医疗3D打印服务 招投标 中标 {datetime.now().year}"

严格规则：
- 只包含 {ONE_MONTH_AGO} 之后发布的内容
- 每条结果必须附带真实的来源链接（来自搜索结果）
- 如果某组搜索没有近期结果，跳过即可
- 重点关注以下区域的信息：内蒙古、上海、天津、四川（广元/绵阳）、安徽（阜阳/淮南/安庆）

请输出一个 JSON 数组（不要 markdown 代码块包裹），每个元素格式如下：
{{
  "province": "省份或城市",
  "date": "YYYY-MM-DD",
  "title": "招投标项目名称",
  "type": "招标公告/中标公告/采购需求/结果公示",
  "hospital": "采购单位（医院/机构名称）",
  "budget": "预算金额（如有）",
  "summary": "核心内容摘要，100字以内",
  "url": "原文链接"
}}

如果确实没有任何近一个月的招投标信息，请输出空数组 []。

重要：你的回复必须只包含一个 JSON 数组，不要包含任何解释文字、分析或说明。如果搜索结果中有相关内容（即使发布日期不完全精确），也应该包含在输出中。直接以 [ 开头输出。"""


def search_bidding() -> list[dict]:
    """调用 Claude API + web_search 工具搜索近期招投标信息。"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": SEARCH_PROMPT}],
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text

    print(f"[DEBUG] Claude 原始返回 ({len(text)} 字符): {text[:300]}")
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
            print(f"[WARN] 无法解析 Claude 返回的 JSON，原文:\n{text[:500]}")
            items = []

    print(f"[INFO] 搜索到 {len(items)} 条近期招投标信息")
    return items


# ──────────────────── Stage 2: 生成 HTML ─────────────────────

TYPE_COLORS = {
    "招标公告": "#e74c3c",
    "中标公告": "#27ae60",
    "采购需求": "#2980b9",
    "结果公示": "#8e44ad",
}


def build_html(items: list[dict]) -> str:
    """将招投标列表渲染为 HTML 邮件内容。"""
    date_range = f"{ONE_MONTH_AGO} ~ {TODAY}"

    if not items:
        items_html = """
        <div style="padding:20px;background:#fef9e7;border-left:4px solid #f39c12;margin:16px 0;border-radius:4px;">
            <p style="margin:0;color:#7d6608;">本周期内（近一个月）暂未检索到3D打印/三维重建相关招投标信息。
            将持续监测，下周继续推送。</p>
        </div>
        """
    else:
        cards = []
        for item in items:
            bid_type = item.get("type", "招标公告")
            type_color = TYPE_COLORS.get(bid_type, "#95a5a6")
            hospital = item.get("hospital", "")
            budget = item.get("budget", "")

            hospital_line = f'<span style="color:#555;font-size:13px;">采购单位：<b>{hospital}</b></span>' if hospital else ""
            budget_line = f'<span style="background:#f0f0f0;padding:2px 8px;border-radius:4px;font-size:13px;color:#333;">预算：{budget}</span>' if budget else ""

            card = f"""
            <div style="border:1px solid #ddd;border-radius:6px;padding:16px;margin:12px 0;background:#fff;border-left:4px solid {type_color};">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:6px;">
                    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                        <span style="background:{type_color};color:#fff;padding:3px 10px;border-radius:12px;font-size:12px;">{bid_type}</span>
                        <span style="background:#2980b9;color:#fff;padding:3px 10px;border-radius:12px;font-size:12px;">{item.get('province','')}</span>
                        {budget_line}
                    </div>
                    <span style="color:#888;font-size:13px;">{item.get('date','')}</span>
                </div>
                <h3 style="margin:8px 0;font-size:15px;color:#1a5276;">{item.get('title','')}</h3>
                {hospital_line}
                <p style="margin:6px 0;color:#555;font-size:14px;line-height:1.6;">{item.get('summary','')}</p>
                <a href="{item.get('url','#')}" style="color:#2980b9;font-size:13px;text-decoration:none;">查看原文 →</a>
            </div>
            """
            cards.append(card)
        items_html = "\n".join(cards)

    # 统计
    type_counts = {}
    province_counts = {}
    for item in items:
        t = item.get("type", "其他")
        p = item.get("province", "未知")
        type_counts[t] = type_counts.get(t, 0) + 1
        province_counts[p] = province_counts.get(p, 0) + 1

    stats_rows = ""
    if type_counts:
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            color = TYPE_COLORS.get(t, "#95a5a6")
            stats_rows += f'<span style="background:{color};color:#fff;padding:3px 12px;border-radius:12px;font-size:13px;margin:4px;">{t} {c}条</span>'

    province_rows = ""
    if province_counts:
        for p, c in sorted(province_counts.items(), key=lambda x: -x[1]):
            province_rows += f'<span style="background:#ecf0f1;padding:3px 12px;border-radius:12px;font-size:13px;margin:4px;color:#333;">{p} {c}条</span>'

    html = f"""<html><body style="font-family:'Microsoft YaHei',Arial,sans-serif;max-width:720px;margin:0 auto;color:#333;line-height:1.8;background:#f5f6fa;">

<div style="background:linear-gradient(135deg,#1a5276,#148f77);padding:24px 32px;border-radius:8px 8px 0 0;">
  <h1 style="color:#fff;margin:0;font-size:22px;">3D打印/三维重建·招投标周报</h1>
  <p style="color:#a3e4d7;margin:8px 0 0;font-size:14px;">内蒙古子殷科技有限公司 | {TODAY}</p>
</div>

<div style="padding:24px 32px;border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px;background:#fff;">

<h2 style="color:#1a5276;border-bottom:2px solid #148f77;padding-bottom:8px;">监测时段：{date_range}</h2>
<p style="font-size:14px;color:#666;">共检索到 <b>{len(items)}</b> 条招投标信息</p>

<div style="margin:12px 0;">
  <p style="font-size:13px;color:#888;margin:4px 0;">按类型：</p>
  <div style="display:flex;flex-wrap:wrap;gap:4px;">{stats_rows}</div>
</div>
<div style="margin:12px 0 20px;">
  <p style="font-size:13px;color:#888;margin:4px 0;">按地区：</p>
  <div style="display:flex;flex-wrap:wrap;gap:4px;">{province_rows}</div>
</div>

{items_html}

<h2 style="color:#1a5276;border-bottom:2px solid #148f77;padding-bottom:8px;margin-top:28px;">重点关注区域</h2>
<table style="width:100%;border-collapse:collapse;font-size:14px;margin:12px 0;">
  <tr style="background:#148f77;color:#fff;">
    <th style="padding:8px;text-align:left;">区域</th>
    <th style="padding:8px;text-align:left;">关注原因</th>
  </tr>
  <tr style="background:#f8f9fa;"><td style="padding:8px;border-bottom:1px solid #ddd;">内蒙古</td><td style="padding:8px;border-bottom:1px solid #ddd;">公司注册地 + 内蒙古医科大二附院/国际蒙医医院</td></tr>
  <tr><td style="padding:8px;border-bottom:1px solid #ddd;">上海</td><td style="padding:8px;border-bottom:1px solid #ddd;">工厂所在地 + 上海六院（60%科研项目）</td></tr>
  <tr style="background:#f8f9fa;"><td style="padding:8px;border-bottom:1px solid #ddd;">天津</td><td style="padding:8px;border-bottom:1px solid #ddd;">天津医院·数智骨科临床转化中心</td></tr>
  <tr><td style="padding:8px;border-bottom:1px solid #ddd;">四川（广元/绵阳）</td><td style="padding:8px;border-bottom:1px solid #ddd;">目标开拓城市 + 广元市第一人民医院</td></tr>
  <tr style="background:#f8f9fa;"><td style="padding:8px;border-bottom:1px solid #ddd;">安徽（阜阳/淮南/安庆）</td><td style="padding:8px;border-bottom:1px solid #ddd;">目标开拓城市</td></tr>
</table>

<hr style="border:none;border-top:1px solid #ddd;margin:20px 0;">
<p style="font-size:12px;color:#999;">本简报由 AI 自动搜集并生成，仅供内部参考。数据来源为公开网络搜索，可能存在遗漏。<br>
建议对感兴趣的项目及时查看原文确认投标截止时间。<br>
如需调整监测关键词或增加关注区域，请回复本邮件告知。</p>
</div>
</body></html>"""

    return html


# ──────────────────── Stage 3: 发送邮件 ─────────────────────


def send_email(html: str):
    """通过 Gmail SMTP 发送 HTML 邮件。"""
    subject = f"【子殷科技·招投标简报】3D打印/三维重建招投标周报（{TODAY}）"

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
    print(f"[INFO] 开始生成招投标简报 | 时段: {ONE_MONTH_AGO} ~ {TODAY}")

    try:
        items = search_bidding()
    except Exception as e:
        print(f"[ERROR] 搜索失败: {e}")
        items = []

    html = build_html(items)

    try:
        send_email(html)
    except Exception as e:
        print(f"[ERROR] 邮件发送失败: {e}")
        sys.exit(1)

    print("[INFO] 招投标简报流程完成")


if __name__ == "__main__":
    main()
