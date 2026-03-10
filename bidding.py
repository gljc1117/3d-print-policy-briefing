#!/usr/bin/env python3
"""
每周自动搜索各省医学影像三维重建、3D打印相关招投标信息，生成简报并发送邮件。
"""

import os
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from search_utils import apify_google_search, summarize_with_claude

# ──────────────────────────── 配置 ────────────────────────────

GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "liyingxi49@gmail.com")

TODAY = datetime.now().strftime("%Y-%m-%d")
PERIOD_START = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

# ──────────────────────── Stage 1: 搜索 ──────────────────────

YEAR = datetime.now().year

SEARCH_QUERIES = [
    f"医学影像三维重建 招标 {YEAR}",
    "3D打印 骨科 招标公告 中标",
    "医学3D打印 采购 招投标",
    "三维重建 手术导板 3D打印 招标",
    "个性化骨科器械 3D打印 中标公告",
    "PEEK 3D打印 医疗 招标",
    f"医疗3D打印服务 招投标 中标 {YEAR}",
]

JSON_SCHEMA = '[{"province":"省份","date":"YYYY-MM-DD","title":"项目名称","type":"招标公告/中标公告/采购需求/结果公示","hospital":"采购单位","budget":"预算金额","summary":"摘要100字内","url":"链接"}]'

SUMMARIZE_PROMPT = f"""从以下搜索结果中筛选与"医学3D打印/三维重建招投标"相关的内容。
时段 {PERIOD_START} ~ {TODAY}，优先近期，高度相关的稍早内容也可包含。
重点关注：内蒙古、上海、天津、四川（广元/绵阳）、安徽。宁多勿少。"""


def search_bidding() -> list[dict]:
    results = apify_google_search(SEARCH_QUERIES)
    items = summarize_with_claude(
        results,
        system_prompt="你是一个JSON格式化工具，只输出JSON数组。",
        user_prompt=SUMMARIZE_PROMPT,
        json_schema=JSON_SCHEMA,
    )
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
    date_range = f"{PERIOD_START} ~ {TODAY}"

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
    print(f"[INFO] 开始生成招投标简报 | 时段: {PERIOD_START} ~ {TODAY}")

    try:
        items = search_bidding()
    except Exception as e:
        print(f"[ERROR] 搜索失败: {e}")
        items = []

    # Save results for web dashboard
    import json
    os.makedirs("docs/data", exist_ok=True)
    with open("docs/data/bidding.json", "w", encoding="utf-8") as f:
        json.dump({"updated": TODAY, "count": len(items), "items": items}, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 已保存 docs/data/bidding.json")

    html = build_html(items)

    try:
        send_email(html)
    except Exception as e:
        print(f"[ERROR] 邮件发送失败: {e}")
        sys.exit(1)

    print("[INFO] 招投标简报流程完成")


if __name__ == "__main__":
    main()
