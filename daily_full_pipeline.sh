#!/bin/bash
# ============================================================
# 子殷科技·每日政策播客 全自动流水线
# 凌晨自动执行：搜索 → 总结 → 生成文稿 → TTS合成 → 推送
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/audio/pipeline-$(date +%Y-%m-%d).log"
mkdir -p "$SCRIPT_DIR/audio"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "=========================================="
echo "[$(date)] 开始每日播客流水线"
echo "=========================================="

# 加载环境变量
if [ -f "$HOME/.env" ]; then
    set -a
    source "$HOME/.env"
    set +a
fi

# 确保不走代理（直连内网 TTS 服务）
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY

# ── Step 1: 搜索+总结（Apify + Claude）──
echo "[$(date)] Step 1: 运行数据搜索..."
python3 "$SCRIPT_DIR/run_all_search.py"

# ── Step 2: 生成播客（Claude文稿 + Fish Audio TTS）──
echo "[$(date)] Step 2: 生成播客音频..."
python3 "$SCRIPT_DIR/daily_podcast_brief.py"

# ── Step 3: 更新 RSS Feed ──
echo "[$(date)] Step 3: 更新 RSS Feed..."
TODAY=$(date +%Y-%m-%d)
PODCAST_FILE="$SCRIPT_DIR/audio/podcast-${TODAY}.mp3"

if [ -f "$PODCAST_FILE" ]; then
    # 复制到 docs 目录供 GitHub Pages 托管
    mkdir -p "$SCRIPT_DIR/docs/audio"
    cp "$PODCAST_FILE" "$SCRIPT_DIR/docs/audio/"
    python3 "$SCRIPT_DIR/generate_rss.py"
fi

# ── Step 4: 推送到 GitHub Pages ──
echo "[$(date)] Step 4: 推送到 GitHub..."
cd "$SCRIPT_DIR"
git add docs/data/ docs/audio/ docs/feed.xml
git commit -m "auto: daily briefing ${TODAY}" --allow-empty || true
git push origin main || echo "[WARN] git push 失败，稍后重试"

echo "=========================================="
echo "[$(date)] 流水线完成"
echo "=========================================="
