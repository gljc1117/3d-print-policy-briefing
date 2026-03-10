#!/usr/bin/env python3
"""
每周自动搜索各省财政厅与3D打印/医疗器械/科技创新相关的资金扶持和申报通知。
"""

import os
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from search_utils import apify_google_search, summarize_with_claude

GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "liyingxi49@gmail.com")

TODAY = datetime.now().strftime("%Y-%m-%d")
PERIOD_START = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
YEAR = datetime.now().year

SEARCH_QUERIES = [
    f"财政厅 3D打印 增材制造 资金 补贴 {YEAR}",
    f"财政厅 医疗器械 专项资金 申报 {YEAR}",
    "财政厅 科技创新 专项资金 申报通知",
    f"财政厅 专精特新 奖励 补贴 申报 {YEAR}",
    "财政厅 高新技术企业 奖励 申报",
    f"财政厅 产业发展基金 医疗 生物医药 {YEAR}",
    "财政厅 技术改造 设备补贴 智能制造 申报",
    f"内蒙古 上海 四川 财政厅 专项资金 申报 {YEAR}",
    "安徽 天津 财政厅 中小企业 科技 补贴 申报",
]

JSON_SCHEMA = '[{"province":"省份","date":"YYYY-MM-DD","title":"项目名称","department":"发布部门","deadline":"截止日期","funding":"资助额度","summary":"摘要","url":"链接"}]'

SUMMARIZE_PROMPT = f"""从以下搜索结果中筛选与"财政厅资金扶持申报（3D打印/医疗器械/科技创新/专精特新/高新技术/产业基金）"相关的内容。
时段 {PERIOD_START} ~ {TODAY}，优先近期内容，高度相关的稍早内容也可包含。
重点关注：内蒙古、上海、天津、四川、安徽。
宁多勿少，只要相关都应包含。"""


def search_projects() -> list[dict]:
    results = apify_google_search(SEARCH_QUERIES)
    items = summarize_with_claude(
        results,
        system_prompt="你是一个JSON格式化工具，只输出JSON数组。",
        user_prompt=SUMMARIZE_PROMPT,
        json_schema=JSON_SCHEMA,
    )
    print(f"[INFO] 搜索到 {len(items)} 条财政厅资金申报信息")
    return items


def build_html(items: list[dict]) -> str:
    date_range = f"{PERIOD_START} ~ {TODAY}"
    ACCENT = "#1e8449"

    if not items:
        items_html = """
        <div style="padding:20px;background:#fef9e7;border-left:4px solid #f39c12;margin:16px 0;border-radius:4px;">
            <p style="margin:0;color:#7d6608;">本周期内（近一个月）暂未检索到财政厅相关资金申报通知。将持续监测。</p>
        </div>"""
    else:
        cards = []
        for item in items:
            deadline = item.get("deadline", "")
            funding = item.get("funding", "")
            dept = item.get("department", "")
            deadline_line = f'<span style="background:#e74c3c;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">截止：{deadline}</span>' if deadline else ""
            funding_line = f'<span style="background:#d5f5e3;padding:2px 8px;border-radius:4px;font-size:13px;color:#1e8449;font-weight:bold;">资助：{funding}</span>' if funding else ""
            dept_line = f'<span style="color:#666;font-size:13px;">{dept}</span>' if dept else ""
            card = f"""
            <div style="border:1px solid #ddd;border-radius:6px;padding:16px;margin:12px 0;background:#fff;border-left:4px solid {ACCENT};">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:6px;">
                    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                        <span style="background:{ACCENT};color:#fff;padding:3px 10px;border-radius:12px;font-size:12px;">{item.get('province','')}</span>
                        {deadline_line} {funding_line}
                    </div>
                    <span style="color:#888;font-size:13px;">{item.get('date','')}</span>
                </div>
                <h3 style="margin:8px 0;font-size:15px;color:#1a5276;">{item.get('title','')}</h3>
                {dept_line}
                <p style="margin:6px 0;color:#555;font-size:14px;line-height:1.6;">{item.get('summary','')}</p>
                <a href="{item.get('url','#')}" style="color:{ACCENT};font-size:13px;text-decoration:none;">查看原文 →</a>
            </div>"""
            cards.append(card)
        items_html = "\n".join(cards)

    html = f"""<html><body style="font-family:'Microsoft YaHei',Arial,sans-serif;max-width:720px;margin:0 auto;color:#333;line-height:1.8;background:#f5f6fa;">
<div style="background:linear-gradient(135deg,#145a32,{ACCENT});padding:24px 32px;border-radius:8px 8px 0 0;">
  <h1 style="color:#fff;margin:0;font-size:22px;">财政厅·资金扶持与申报通知周报</h1>
  <p style="color:#a9dfbf;margin:8px 0 0;font-size:14px;">内蒙古子殷科技有限公司 | {TODAY}</p>
</div>
<div style="padding:24px 32px;border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px;background:#fff;">
<h2 style="color:#1a5276;border-bottom:2px solid {ACCENT};padding-bottom:8px;">监测时段：{date_range}</h2>
<p style="font-size:14px;color:#666;">共检索到 <b>{len(items)}</b> 条资金申报信息</p>
{items_html}
<hr style="border:none;border-top:1px solid #ddd;margin:20px 0;">
<p style="font-size:12px;color:#999;">本简报由 AI 自动搜集，仅供内部参考。建议对感兴趣的项目及时确认申报截止时间和资金额度。</p>
</div></body></html>"""
    return html


def send_email(html: str):
    subject = f"【子殷科技·财政厅简报】资金扶持与申报通知周报（{TODAY}）"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print(f"[INFO] 邮件已发送至 {RECIPIENT_EMAIL}")


def main():
    print(f"[INFO] 财政厅简报 | {PERIOD_START} ~ {TODAY}")
    try:
        items = search_projects()
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
