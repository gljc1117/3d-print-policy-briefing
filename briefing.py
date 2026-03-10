#!/usr/bin/env python3
"""
每周自动搜索各省医保局3D打印医疗服务收费政策，生成简报并发送邮件。
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

MODEL = "claude-3-5-haiku-20241022"
TODAY = datetime.now().strftime("%Y-%m-%d")
ONE_MONTH_AGO = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

# ──────────────────────── Stage 1: 搜索 ──────────────────────

SEARCH_PROMPT = f"""今天是 {TODAY}。
请搜索 **{ONE_MONTH_AGO} 至 {TODAY}** 期间，中国各省级/市级医保局关于"3D打印医疗服务"定价、收费、立项的最新政策文件、通知和新闻报道。

请依次使用以下搜索关键词（每组至少搜索一次）：
1. "医保局 3D打印 医疗服务 收费 {datetime.now().year}"
2. "3D打印 骨科 导板 医保 定价 收费标准"
3. "增材制造 医疗 收费项目 医保局 新增"
4. "个性化医疗器械 3D打印 定价政策"
5. "生物3D打印 医保 价格项目"

规则：
- 优先包含 {ONE_MONTH_AGO} 之后发布的内容，但如果搜索到高度相关的稍早内容也应包含
- 每条结果必须附带真实的来源链接（来自搜索结果）
- 宁多勿少：只要与3D打印医疗服务收费政策相关，都应包含在输出中

请输出一个 JSON 数组（不要 markdown 代码块包裹），每个元素格式如下：
{{
  "province": "省份或城市",
  "date": "YYYY-MM-DD",
  "title": "政策/新闻标题",
  "summary": "核心内容摘要，100字以内",
  "url": "原文链接"
}}

如果确实没有任何相关结果，请输出空数组 []。但请注意：宁可多输出几条不完全匹配的结果，也不要输出空数组。

重要：你的回复必须只包含一个 JSON 数组，不要包含任何解释文字、分析或说明。如果搜索结果中有相关内容（即使发布日期不完全精确），也应该包含在输出中。直接以 [ 开头输出。"""


def _parse_json(text: str) -> list[dict] | None:
    """尝试从文本中解析 JSON 数组，失败返回 None。"""
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
    """用第二次 API 调用（无 web_search）将原始文本转为 JSON 数组。"""
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


JSON_SCHEMA = '[{"province":"省份","date":"YYYY-MM-DD","title":"标题","summary":"摘要","url":"链接"}]'


def search_policies() -> list[dict]:
    """调用 Claude API + web_search 工具搜索近期政策。"""
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

    policies = _parse_json(text)
    if policies is None or (len(policies) == 0 and len(text) > 200):
        print(f"[INFO] {'直接解析失败' if policies is None else '返回空数组但原文较长'}，使用二次 LLM 提取...")
        policies = _extract_json_via_llm(client, text, JSON_SCHEMA)

    print(f"[INFO] 搜索到 {len(policies)} 条近期政策/新闻")
    return policies


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
