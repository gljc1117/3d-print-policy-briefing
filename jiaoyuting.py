#!/usr/bin/env python3
"""
每周自动搜索各省教育厅与医工交叉/产学研/校企合作相关的项目申报通知。
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

MODEL = "claude-3-5-haiku-20241022"
TODAY = datetime.now().strftime("%Y-%m-%d")
ONE_MONTH_AGO = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

SEARCH_PROMPT = f"""今天是 {TODAY}。
请搜索 **{ONE_MONTH_AGO} 至 {TODAY}** 期间，中国各省教育厅（教育委员会）发布的与以下领域相关的项目申报通知、课题申报、基金资助、平台建设等：

相关领域：
- 医工交叉 / 医工结合
- 产学研合作 / 校企合作
- 协同创新中心 / 工程研究中心
- 高校科研平台 / 重点实验室
- 3D打印 / 增材制造相关学科
- 生物医学工程 / 医学影像
- 人工智能 + 医学
- 临床医学研究 / 转化医学

请依次使用以下搜索关键词（每组至少搜索一次）：
1. "教育厅 医工交叉 项目申报 {datetime.now().year}"
2. "教育厅 产学研 医疗器械 申报通知 {datetime.now().year}"
3. "教育厅 协同创新中心 生物医学 申报"
4. "教育厅 重点实验室 3D打印 增材制造 申报"
5. "教育厅 高校科研 医学影像 人工智能 项目"
6. "教育厅 校企合作 医疗 申报 {datetime.now().year}"
7. "内蒙古 上海 天津 教育厅 科研项目 医学 申报 {datetime.now().year}"
8. "安徽 四川 教育厅 转化医学 生物医学工程 申报"

规则：
- 优先包含 {ONE_MONTH_AGO} 之后发布的内容，但高度相关的稍早内容也应包含
- 每条结果必须附带真实的来源链接
- 宁多勿少：只要与教育厅项目申报相关，都应包含在输出中
- 重点关注：内蒙古、上海、天津、四川、安徽

请输出一个 JSON 数组（不要 markdown 代码块包裹），每个元素格式如下：
{{
  "province": "省份或城市",
  "date": "YYYY-MM-DD",
  "title": "项目/通知名称",
  "department": "发布部门",
  "deadline": "申报截止日期（如有）",
  "funding": "支持金额/资助额度（如有）",
  "summary": "核心内容摘要，100字以内",
  "url": "原文链接"
}}

如果确实没有任何相关结果，请输出空数组 []。但请注意：宁可多输出几条不完全匹配的结果，也不要输出空数组。

重要：你的回复必须只包含一个 JSON 数组，不要包含任何解释文字、分析或说明。如果搜索结果中有相关内容（即使发布日期不完全精确），也应该包含在输出中。直接以 [ 开头输出。"""


def _parse_json(text: str) -> list[dict] | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0].strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            result = json.loads(text[start:end])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    return None


def _extract_json_via_llm(client, raw_text: str, json_schema: str) -> list[dict]:
    response = client.messages.create(
        model=MODEL,
        system="你是一个JSON格式化工具。用户会给你一段包含搜索结果的文本，你必须将其中的信息提取并转为JSON数组输出。只输出JSON数组，以[开头，以]结尾。不要输出任何其他文字。",
        max_tokens=8192,
        messages=[{"role": "user", "content": f"请将以下搜索结果转为JSON数组，格式：{json_schema}\n\n---\n{raw_text}"}],
    )
    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text
    print(f"[DEBUG] 二次提取返回 ({len(text)} 字符): {text[:200]}")
    result = _parse_json(text)
    return result if result is not None else []


JSON_SCHEMA = '[{"province":"省份","date":"YYYY-MM-DD","title":"项目名称","department":"发布部门","deadline":"截止日期","funding":"资助额度","summary":"摘要","url":"链接"}]'


def search_projects() -> list[dict]:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=MODEL,
        system="你是一个数据采集API，只输出JSON数组。禁止输出任何解释、分析或说明文字。搜索后直接输出以[开头的JSON数组。",
        max_tokens=8192,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": SEARCH_PROMPT}],
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text
    print(f"[DEBUG] Claude 原始返回 ({len(text)} 字符): {text[:500]}")

    items = _parse_json(text)
    if items is None or (len(items) == 0 and len(text) > 200):
        print(f"[INFO] {'直接解析失败' if items is None else '返回空数组但原文较长'}，使用二次 LLM 提取...")
        items = _extract_json_via_llm(client, text, JSON_SCHEMA)

    print(f"[INFO] 搜索到 {len(items)} 条教育厅项目申报信息")
    return items


def build_html(items: list[dict]) -> str:
    date_range = f"{ONE_MONTH_AGO} ~ {TODAY}"
    ACCENT = "#2471a3"

    if not items:
        items_html = """
        <div style="padding:20px;background:#fef9e7;border-left:4px solid #f39c12;margin:16px 0;border-radius:4px;">
            <p style="margin:0;color:#7d6608;">本周期内（近一个月）暂未检索到教育厅相关项目申报通知。将持续监测。</p>
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
<div style="background:linear-gradient(135deg,#1a5276,{ACCENT});padding:24px 32px;border-radius:8px 8px 0 0;">
  <h1 style="color:#fff;margin:0;font-size:22px;">教育厅·项目申报通知周报</h1>
  <p style="color:#aed6f1;margin:8px 0 0;font-size:14px;">内蒙古子殷科技有限公司 | {TODAY}</p>
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
    subject = f"【子殷科技·教育厅简报】项目申报通知周报（{TODAY}）"
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
    print(f"[INFO] 教育厅简报 | {ONE_MONTH_AGO} ~ {TODAY}")
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
