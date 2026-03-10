"""
共享搜索工具：Apify Google Search + Claude 总结
"""

import json
import os
import time

import anthropic
import urllib.request
import urllib.error

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
APIFY_TOKEN = os.environ["APIFY_TOKEN"]
MODEL = "claude-3-5-haiku-20241022"

APIFY_ACTOR = "apify~google-search-scraper"
APIFY_ENDPOINT = f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/run-sync-get-dataset-items"


def apify_google_search(queries: list[str], max_results_per_query: int = 5) -> list[dict]:
    """用 Apify Google Search 批量搜索，返回去重后的结果列表。"""
    all_results = []
    seen_urls = set()

    for query in queries:
        print(f"[SEARCH] 搜索: {query}")
        payload = json.dumps({
            "queries": query,
            "maxPagesPerQuery": 1,
            "resultsPerPage": max_results_per_query,
            "languageCode": "zh-CN",
            "countryCode": "cn",
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{APIFY_ENDPOINT}?token={APIFY_TOKEN}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                items = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"[WARN] Apify 搜索失败: {e}")
            continue

        for item in items:
            # Apify Google Search 返回 organicResults
            organic = item.get("organicResults", [])
            for r in organic:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append({
                        "title": r.get("title", ""),
                        "url": url,
                        "description": r.get("description", ""),
                    })

        # 避免触发速率限制
        time.sleep(1)

    print(f"[INFO] Apify 共搜索到 {len(all_results)} 条去重结果")
    return all_results


def _parse_json(text: str) -> list[dict] | None:
    """尝试从文本中解析 JSON 数组。"""
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


def summarize_with_claude(
    search_results: list[dict],
    system_prompt: str,
    user_prompt: str,
    json_schema: str,
    max_tokens: int = 8192,
) -> list[dict]:
    """将 Apify 搜索结果传给 Claude 进行总结和 JSON 格式化。"""
    if not search_results:
        print("[WARN] 无搜索结果，跳过 Claude 总结")
        return []

    # 构建搜索结果文本
    results_text = ""
    for i, r in enumerate(search_results, 1):
        results_text += f"\n{i}. 标题: {r['title']}\n   链接: {r['url']}\n   摘要: {r['description']}\n"

    full_prompt = f"""{user_prompt}

以下是搜索引擎返回的结果，请从中筛选相关内容并整理为JSON数组：
{results_text}

输出格式：{json_schema}
只输出JSON数组，以[开头，以]结尾。不要输出任何其他文字。"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=MODEL,
        system=system_prompt,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": full_prompt}],
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text

    print(f"[DEBUG] Claude 返回 ({len(text)} 字符): {text[:200]}")

    items = _parse_json(text)
    if items is None:
        print("[WARN] JSON 解析失败")
        return []

    return items
