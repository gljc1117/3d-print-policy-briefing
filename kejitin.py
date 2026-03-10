#!/usr/bin/env python3
"""
每周自动搜索各省科技厅与3D打印/医疗器械/AI医疗相关的项目申报通知。
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
    f"科技厅 3D打印 增材制造 项目申报 {YEAR}",
    f"科技厅 医疗器械 项目申报通知 {YEAR}",
    "科技厅 医学人工智能 专项 申报指南",
    "科技厅 生物医药 生物材料 项目申报",
    "科技厅 科技成果转化 医疗 申报",
    f"科技厅 数字医疗 智慧医疗 项目 {YEAR}",
    f"内蒙古 上海 四川 科技厅 项目申报 医疗 {YEAR}",
    "安徽 天津 科技厅 高新技术 医疗器械 申报",
]

JSON_SCHEMA = '[{"province":"省份","date":"YYYY-MM-DD","title":"项目名称","department":"发布部门","deadline":"截止日期","funding":"资助额度","summary":"摘要","url":"链接"}]'

SUMMARIZE_PROMPT = f"""从以下搜索结果中筛选与"科技厅项目申报（3D打印/医疗器械/医学AI/生物医药/科技成果转化）"相关的内容。
时段 {PERIOD_START} ~ {TODAY}，优先近期内容，高度相关的稍早内容也可包含。
重点关注：内蒙古、上海、天津、四川、安徽、绵阳、广元。
宁多勿少，只要相关都应包含。"""


def search_projects() -> list[dict]:
    results = apify_google_search(SEARCH_QUERIES)
    items = summarize_with_claude(
        results,
        system_prompt="你是一个JSON格式化工具，只输出JSON数组。",
        user_prompt=SUMMARIZE_PROMPT,
        json_schema=JSON_SCHEMA,
    )
    print(f"[INFO] 搜索到 {len(items)} 条科技厅项目申报信息")
    return items


def build_html(items: list[dict]) -> str:
    date_range = f"{PERIOD_START} ~ {TODAY}"
    ACCENT = "#8e44ad"

    if not items:
        items_html = """
        <div style="padding:20px;background:#fef9e7;border-left:4px solid #f39c12;margin:16px 0;border-radius:4px;">
            <p style="margin:0;color:#7d6608;">本周期内（近一个月）暂未检索到科技厅相关项目申报通知。将持续监测。</p>
        </div>"""
    else:
        cards = []
        for item in items:
            deadline = item.get("deadline", "")
            funding = item.get("funding", "")
            dept = item.get("department", "")
            deadline_line = f'<span style="background:#e74c3c;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">截止：{deadline}</span>' if deadline else ""
            funding_line = f'<span style="background:#f0f0f0;padding:2px 8px;border-radius:4px;font-size:13px;color:#333;">资助：{funding}</span>' if funding else ""
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
<div style="background:linear-gradient(135deg,#6c3483,{ACCENT});padding:24px 32px;border-radius:8px 8px 0 0;">
  <h1 style="color:#fff;margin:0;font-size:22px;">科技厅·项目申报通知周报</h1>
  <p style="color:#d7bde2;margin:8px 0 0;font-size:14px;">内蒙古子殷科技有限公司 | {TODAY}</p>
</div>
<div style="padding:24px 32px;border:1px solid #ddd;border-top:none;border-radius:0 0 8px 8px;background:#fff;">
<h2 style="color:#1a5276;border-bottom:2px solid {ACCENT};padding-bottom:8px;">监测时段：{date_range}</h2>
<p style="font-size:14px;color:#666;">共检索到 <b>{len(items)}</b> 条项目申报信息</p>
{items_html}
<hr style="border:none;border-top:1px solid #ddd;margin:20px 0;">
<p style="font-size:12px;color:#999;">本简报由 AI 自动搜集，仅供内部参考。建议对感兴趣的项目及时确认申报截止时间。</p>
</div></body></html>"""
    return html


def send_email(html: str):
    subject = f"【子殷科技·科技厅简报】项目申报通知周报（{TODAY}）"
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
    print(f"[INFO] 科技厅简报 | {PERIOD_START} ~ {TODAY}")
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
