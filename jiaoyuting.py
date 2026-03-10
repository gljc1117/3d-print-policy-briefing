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

MODEL = "claude-haiku-4-5-20251001"
TODAY = datetime.now().strftime("%Y-%m-%d")
ONE_MONTH_AGO = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

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

严格规则：
- 只包含 {ONE_MONTH_AGO} 之后发布的内容
- 每条结果必须附带真实的来源链接
- 如果某组搜索没有近期结果，跳过即可
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

如果没有任何近一个月的相关通知，请输出空数组 []。"""


def _call_with_tool_loop(client, prompt: str, max_turns: int = 25) -> str:
    """手动处理 web_search 多轮 tool_use，每轮只保留必要上下文。"""
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20250305", "name": "web_search"}]
    final_text = ""
    for turn in range(max_turns):
        response = client.messages.create(
            model=MODEL, max_tokens=8192, tools=tools, messages=messages,
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


def search_projects() -> list[dict]:
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
