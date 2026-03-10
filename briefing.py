#!/usr/bin/env python3
"""
每周自动搜索各省医保局3D打印医疗服务收费政策，生成简报并发送邮件。
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
YEAR = datetime.now().year

SEARCH_QUERIES = [
    f"医保局 3D打印 医疗服务 收费 {YEAR}",
    "3D打印 骨科 导板 医保 定价 收费标准",
    "增材制造 医疗 收费项目 医保局 新增",
    "个性化医疗器械 3D打印 定价政策",
    "生物3D打印 医保 价格项目",
]

JSON_SCHEMA = '[{"province":"省份","date":"YYYY-MM-DD","title":"标题","summary":"摘要100字内","url":"链接"}]'

SUMMARIZE_PROMPT = f"""从以下搜索结果中筛选与"3D打印医疗服务收费定价政策"相关的内容。
时段 {PERIOD_START} ~ {TODAY}，优先近期内容，高度相关的稍早内容也可包含。
宁多勿少，只要相关都应包含。"""


def search_policies() -> list[dict]:
    results = apify_google_search(SEARCH_QUERIES)
    items = summarize_with_claude(
        results,
        system_prompt="你是一个JSON格式化工具，只输出JSON数组。",
        user_prompt=SUMMARIZE_PROMPT,
        json_schema=JSON_SCHEMA,
    )
    print(f"[INFO] 搜索到 {len(items)} 条近期政策/新闻")
    return items


# ──────────────────── Stage 2: 生成 HTML ─────────────────────


def build_html(policies: list[dict]) -> str:
    """将政策列表渲染为 HTML 邮件内容。"""
    date_range = f"{ONE_MONTH_AGO} ~ {TODAY}"

    if not policies:
        items_html = """
        <div style="padding:20px;background:#fef9e7;border-left:4px solid #f39c12;margin:16px 0;border-radius:4px;">
            <p style="margin:0;color:#7d6608;">本周期内（近一个月）暂未检索到新增3D打印医保收费政策。
            将持续跟踪，下周继续推送。</p>
        </div>
        """
    else:
        cards = []
        for p in policies:
            card = f"""
            <div style="border:1px solid #ddd;border-radius:6px;padding:16px;margin:12px 0;background:#fff;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <span style="background:#2980b9;color:#fff;padding:3px 10px;border-radius:12px;font-size:13px;">{p.get('province','未知')}</span>
                    <span style="color:#888;font-size:13px;">{p.get('date','')}</span>
                </div>
                <h3 style="margin:8px 0;font-size:16px;color:#1a5276;">{p.get('title','')}</h3>
                <p style="margin:6px 0;color:#555;font-size:14px;line-height:1.6;">{p.get('summary','')}</p>
                <a href="{p.get('url','#')}" style="color:#2980b9;font-size:13px;text-decoration:none;">查看原文 →</a>
            </div>
            """
            cards.append(card)
        items_html = "\n".join(cards)

    html = f"""<html><body style="font-family:'Microsoft YaHei',Arial,sans-serif;max-width:720px;margin:0 auto;color:#333;line-height:1.8;background:#f5f6fa;">

<div style="background:linear-gradient(135deg,#1a5276,#2980b9);padding:24px 32px;border-radius:8px 8px 0 0;">
  <h1 style="color:#fff;margin:0;font-size:22px;">3D打印医保定价政策·周报</h1>
  <p style="color:#d4e6f1;margin:8px 0 0;font-size:14px;">内蒙古子殷科技有限公司 | {TODAY}</p>
</div>

<div style="padding:24px 32px;border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px;background:#fff;">

<h2 style="color:#1a5276;border-bottom:2px solid #2980b9;padding-bottom:8px;">监测时段：{date_range}</h2>
<p style="font-size:14px;color:#666;">共检索到 <b>{len(policies)}</b> 条近期政策/新闻</p>

{items_html}

<h2 style="color:#1a5276;border-bottom:2px solid #2980b9;padding-bottom:8px;margin-top:28px;">重点关注区域</h2>
<table style="width:100%;border-collapse:collapse;font-size:14px;margin:12px 0;">
  <tr style="background:#2980b9;color:#fff;">
    <th style="padding:8px;text-align:left;">区域</th>
    <th style="padding:8px;text-align:left;">关注原因</th>
  </tr>
  <tr style="background:#f8f9fa;"><td style="padding:8px;border-bottom:1px solid #ddd;">内蒙古</td><td style="padding:8px;border-bottom:1px solid #ddd;">公司注册地 + 核心合作医院</td></tr>
  <tr><td style="padding:8px;border-bottom:1px solid #ddd;">上海</td><td style="padding:8px;border-bottom:1px solid #ddd;">工厂所在地 + 六院合作</td></tr>
  <tr style="background:#f8f9fa;"><td style="padding:8px;border-bottom:1px solid #ddd;">四川（广元/绵阳）</td><td style="padding:8px;border-bottom:1px solid #ddd;">目标开拓城市</td></tr>
  <tr><td style="padding:8px;border-bottom:1px solid #ddd;">安徽（阜阳/淮南/安庆）</td><td style="padding:8px;border-bottom:1px solid #ddd;">目标开拓城市</td></tr>
  <tr style="background:#f8f9fa;"><td style="padding:8px;border-bottom:1px solid #ddd;">天津</td><td style="padding:8px;border-bottom:1px solid #ddd;">天津医院·数智骨科临床转化中心</td></tr>
</table>

<hr style="border:none;border-top:1px solid #ddd;margin:20px 0;">
<p style="font-size:12px;color:#999;">本简报由 AI 自动搜集并生成，仅供内部参考。数据来源为公开网络搜索，可能存在遗漏。<br>
如需调整监测关键词或增加关注省份，请回复本邮件告知。</p>
</div>
</body></html>"""

    return html


# ──────────────────── Stage 3: 发送邮件 ─────────────────────


def send_email(html: str):
    """通过 Gmail SMTP 发送 HTML 邮件。"""
    subject = f"【子殷科技·政策简报】3D打印医保定价政策周报（{TODAY}）"

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
    print(f"[INFO] 开始生成简报 | 时段: {ONE_MONTH_AGO} ~ {TODAY}")

    try:
        policies = search_policies()
    except Exception as e:
        print(f"[ERROR] 搜索失败: {e}")
        policies = []

    html = build_html(policies)

    try:
        send_email(html)
    except Exception as e:
        print(f"[ERROR] 邮件发送失败: {e}")
        sys.exit(1)

    print("[INFO] 简报流程完成")


if __name__ == "__main__":
    main()
