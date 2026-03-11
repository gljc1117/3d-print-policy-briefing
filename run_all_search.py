#!/usr/bin/env python3
"""批量运行所有模块的搜索+Claude总结，保存JSON结果（不发邮件）。"""

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from search_utils import apify_google_search, summarize_with_claude

TODAY = datetime.now().strftime("%Y-%m-%d")
PERIOD_START_90 = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
PERIOD_START_30 = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
YEAR = datetime.now().year

os.makedirs("docs/data", exist_ok=True)

MODULES = {
    "bidding": {
        "name": "招投标",
        "queries": [
            f"医学影像三维重建 招标 {YEAR}",
            "3D打印 骨科 招标公告 中标",
            "医学3D打印 采购 招投标",
            "三维重建 手术导板 3D打印 招标",
            "个性化骨科器械 3D打印 中标公告",
            "PEEK 3D打印 医疗 招标",
            f"医疗3D打印服务 招投标 中标 {YEAR}",
        ],
        "schema": '[{"province":"省份","date":"YYYY-MM-DD","title":"项目名称","type":"招标公告/中标公告/采购需求/结果公示","hospital":"采购单位","budget":"预算金额","summary":"摘要100字内","url":"链接"}]',
        "prompt": (
            f'从以下搜索结果中筛选与"医学3D打印/三维重建招投标"相关的内容。\n'
            f'时段 {PERIOD_START_90} ~ {TODAY}，优先近期，高度相关的稍早内容也可包含。\n'
            f'重点关注：内蒙古、上海、天津、四川（广元/绵阳）、安徽。宁多勿少。'
        ),
    },
    "kejitin": {
        "name": "科技厅",
        "queries": [
            f"科技厅 3D打印 项目申报 {YEAR}",
            "科技厅 医疗器械 创新 项目 申报通知",
            "科技厅 人工智能 医学影像 课题 申报",
            f"科技厅 生物医学工程 增材制造 {YEAR}",
            "内蒙古 科技厅 医疗 项目 申报",
            "上海 科技 医疗器械 专项 申报",
        ],
        "schema": '[{"province":"省份","date":"YYYY-MM-DD","title":"项目/通知名称","department":"发布部门","deadline":"截止日期","funding":"资助金额","summary":"摘要100字内","url":"链接"}]',
        "prompt": (
            f'从以下搜索结果中筛选与科技厅项目申报（3D打印/医疗器械/AI医学/生物医学工程）相关的内容。\n'
            f'时段 {PERIOD_START_90} ~ {TODAY}，优先近期。宁多勿少。'
        ),
    },
    "gongxinting": {
        "name": "工信厅",
        "queries": [
            f"工信厅 增材制造 智能制造 {YEAR}",
            "工信部 专精特新 小巨人 医疗器械",
            f"工信厅 3D打印 产业政策 {YEAR}",
            "工信部 智能制造 试点示范 医疗",
            "内蒙古 工信厅 专精特新 申报",
            "上海 经信委 智能制造 专项",
        ],
        "schema": '[{"province":"省份","date":"YYYY-MM-DD","title":"政策/通知名称","department":"发布部门","summary":"摘要100字内","url":"链接"}]',
        "prompt": (
            f'从以下搜索结果中筛选与工信厅/工信部（增材制造/智能制造/专精特新/3D打印产业政策）相关的内容。\n'
            f'时段 {PERIOD_START_90} ~ {TODAY}，优先近期。宁多勿少。'
        ),
    },
    "fagaiwei": {
        "name": "发改委",
        "queries": [
            f"发改委 战略性新兴产业 增材制造 {YEAR}",
            "发改委 中央预算内投资 医疗 数字经济",
            f"发改委 生物经济 3D打印 {YEAR}",
            "发改委 产业结构调整 增材制造",
            "内蒙古 发改委 新兴产业 项目",
        ],
        "schema": '[{"province":"省份","date":"YYYY-MM-DD","title":"政策/通知名称","department":"发布部门","summary":"摘要100字内","url":"链接"}]',
        "prompt": (
            f'从以下搜索结果中筛选与发改委（战略性新兴产业/增材制造/数字经济/生物经济）相关的内容。\n'
            f'时段 {PERIOD_START_90} ~ {TODAY}，优先近期。宁多勿少。'
        ),
    },
    "caizhengtng": {
        "name": "财政厅",
        "queries": [
            f"财政厅 专精特新 奖补 {YEAR}",
            "财政 科技创新 资金扶持 医疗器械",
            f"财政厅 中小企业 补贴 3D打印 {YEAR}",
            "财政 技术改造 设备补贴 制造业",
            "内蒙古 财政厅 企业扶持 补贴",
        ],
        "schema": '[{"province":"省份","date":"YYYY-MM-DD","title":"政策/通知名称","department":"发布部门","funding":"资金规模","summary":"摘要100字内","url":"链接"}]',
        "prompt": (
            f'从以下搜索结果中筛选与财政厅（专精特新奖补/科技创新资金/企业补贴/技术改造）相关的内容。\n'
            f'时段 {PERIOD_START_90} ~ {TODAY}，优先近期。宁多勿少。'
        ),
    },
    "jiaoyuting": {
        "name": "教育厅",
        "queries": [
            f"教育厅 医工交叉 产学研 {YEAR}",
            "教育部 新医科 3D打印 人才培养",
            "高校 医学影像 AI 产学研合作 申报",
            f"教育厅 协同创新 生物医学工程 {YEAR}",
            "医工结合 校企合作 3D打印 骨科",
        ],
        "schema": '[{"province":"省份","date":"YYYY-MM-DD","title":"项目/通知名称","department":"发布部门","summary":"摘要100字内","url":"链接"}]',
        "prompt": (
            f'从以下搜索结果中筛选与教育厅/教育部（医工交叉/产学研/校企合作/生物医学工程人才培养）相关的内容。\n'
            f'时段 {PERIOD_START_90} ~ {TODAY}，优先近期。宁多勿少。'
        ),
    },
    "global_news": {
        "name": "全球新闻",
        "queries": [
            "medical 3D printing orthopedic 2026",
            "3D printed bone implant PEEK FDA approval",
            "medical AI radiology 3D reconstruction",
            "bioprinting orthopedic clinical trial",
            "医疗3D打印 骨科 最新进展",
            "PEEK 3D打印 植入物 临床",
        ],
        "schema": '[{"date":"YYYY-MM-DD","title":"标题","source":"来源","region":"国家/地区","category":"技术突破/监管审批/临床应用/市场动态/学术研究","summary":"摘要100字内","relevance":"与子殷科技业务的关联分析","url":"链接"}]',
        "prompt": (
            f'从以下搜索结果中筛选与医疗3D打印/骨科/PEEK/医学AI/增材制造相关的全球行业新闻。\n'
            f'时段 {PERIOD_START_30} ~ {TODAY}。宁多勿少。\n'
            f'请分析每条新闻与子殷科技（医疗3D打印、PEEK骨科器械、医学影像AI）的业务关联。'
        ),
        "max_tokens": 16384,
    },
}


def run_module(key, cfg):
    print(f"\n{'='*60}")
    print(f"[START] {cfg['name']} ({key})")
    print(f"{'='*60}")

    results = apify_google_search(cfg["queries"])
    if not results:
        print(f"[WARN] {cfg['name']}: Apify 搜索无结果")
        return 0

    max_tokens = cfg.get("max_tokens", 8192)
    items = summarize_with_claude(
        results,
        system_prompt="你是一个JSON格式化工具，只输出JSON数组。",
        user_prompt=cfg["prompt"],
        json_schema=cfg["schema"],
        max_tokens=max_tokens,
    )

    output = {"updated": TODAY, "count": len(items), "items": items}
    path = f"docs/data/{key}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[OK] {cfg['name']}: {len(items)} 条 -> {path}")
    return len(items)


if __name__ == "__main__":
    total = 0
    results_summary = {}

    for key, cfg in MODULES.items():
        try:
            count = run_module(key, cfg)
            results_summary[cfg["name"]] = count
            total += count
        except Exception as e:
            print(f"[ERROR] {cfg['name']}: {e}")
            results_summary[cfg["name"]] = f"ERROR: {e}"

    print(f"\n{'='*60}")
    print(f"汇总结果:")
    print(f"{'='*60}")
    for name, count in results_summary.items():
        status = f"{count} 条" if isinstance(count, int) else count
        print(f"  {name}: {status}")
    print(f"  总计: {total} 条")
