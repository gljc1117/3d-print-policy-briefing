# Codex Task: ZY-Brief 手机音频播报 MVP

> 目标：把现有/待创建的 ZY-Brief 情报简报流程升级为“每天自动生成 Markdown + JSON + MP3 音频，并把手机可播放入口推送到企业微信/飞书”。

## 1. 背景

子殷科技业务方向：医疗3D打印 + 医疗AI/数据平台 + 科研项目申报与成果转化。系统只处理公开信息源，不接医院内网、不接患者数据、不接敏感病例数据。

核心输出：

- 每日 Markdown 简报
- 结构化 JSON
- 3-5 分钟 MP3 音频晨报
- 手机端推送入口：企业微信/飞书消息，点击即可播放音频

## 2. 交付物

请在仓库中实现以下文件/能力：

```text
.github/workflows/daily-zy-brief.yml
requirements.txt
.env.example
config.example.yaml
sources_zy_brief.csv
scripts/zy_brief_daily.py
scripts/render_audio_page.py
scripts/send_mobile_push.py
public/index.html
public/latest.json
tests/test_config.py
README.md
```

如果仓库已有同名或同类文件，请优先兼容与增量修改，不要破坏现有功能。

## 3. 功能要求

### 3.1 自动生成日报

`scripts/zy_brief_daily.py` 需要支持：

```bash
python scripts/zy_brief_daily.py --sources sources_zy_brief.csv --config config.yaml --output out
```

生成：

```text
out/zy_brief_YYYY-MM-DD.md
out/zy_brief_YYYY-MM-DD.json
out/zy_brief_YYYY-MM-DD.mp3
```

### 3.2 音频生成

使用 OpenAI Text-to-Speech API。

环境变量：

```text
OPENAI_API_KEY=
TTS_MODEL=gpt-4o-mini-tts
TTS_VOICE=cedar
```

音频脚本要求：

- 中文播报
- 3-5 分钟
- 董事长晨报语气
- 不读长链接
- 不读表格
- 重点读：今日必读、对子殷影响、今日建议动作

### 3.3 手机播放页

生成 `public/latest.json`：

```json
{
  "date": "YYYY-MM-DD",
  "title": "子殷科技医疗AI与临床转化情报简报",
  "audio_url": "https://.../audio/zy_brief_YYYY-MM-DD.mp3",
  "markdown_url": "https://.../briefs/zy_brief_YYYY-MM-DD.md",
  "summary": "今日三条重点..."
}
```

生成 `public/index.html`：

- 移动端友好
- 显示日期、摘要、播放按钮
- 使用 `<audio controls>` 播放
- 不强制自动播放，因为移动端浏览器通常会拦截未由用户点击触发的有声播放

### 3.4 推送到手机

`scripts/send_mobile_push.py` 支持：

```bash
python scripts/send_mobile_push.py --latest public/latest.json
```

环境变量：

```text
WECOM_WEBHOOK_URL=
FEISHU_WEBHOOK_URL=
PUBLIC_BASE_URL=
```

推送内容：

```text
【ZY-Brief 晨报】YYYY-MM-DD
今日必读：3条
▶ 点击播放音频：{audio_url 或播放页 URL}
📄 查看全文：{markdown_url 或播放页 URL}
```

优先支持企业微信 Markdown webhook；飞书可作为第二优先级。

### 3.5 GitHub Actions

新增 `.github/workflows/daily-zy-brief.yml`：

- 支持 `workflow_dispatch`
- 每天北京时间 06:00 运行：`0 22 * * *` UTC
- 安装 Python 依赖
- 运行日报生成
- 将 `public/` 作为 GitHub Pages 静态目录或 artifact 输出
- 推送企业微信/飞书消息

Secrets：

```text
OPENAI_API_KEY
WECOM_WEBHOOK_URL
FEISHU_WEBHOOK_URL
PUBLIC_BASE_URL
```

### 3.6 数据安全要求

- 不接入患者数据
- 不接入医院内网
- 不把 API Key 或 webhook 打印到日志
- 出错时日志只显示错误类型，不显示 secret 值
- 输出中必须保留公开来源 URL
- 政策/招采内容提示“需人工复核”

## 4. 验收标准

1. `python scripts/zy_brief_daily.py --sources sources_zy_brief.csv --config config.example.yaml --output out` 可以跑通。
2. 无 API Key 时，脚本用 mock 模式生成样例 Markdown/JSON，不失败。
3. 有 `OPENAI_API_KEY` 时，生成 MP3。
4. `public/index.html` 可以在手机浏览器打开并播放音频。
5. `python scripts/send_mobile_push.py --latest public/latest.json` 可以向企业微信/飞书推送文本和播放链接。
6. GitHub Actions 支持手动触发。
7. README 写清楚：如何配置 Secrets、如何手动运行、如何在手机上播放。

## 5. 建议实现顺序

1. 先补齐仓库结构和 README。
2. 实现 mock 模式，确保无 key 也可测试。
3. 接入 OpenAI TTS，生成 mp3。
4. 生成 `public/latest.json` 和 `public/index.html`。
5. 接入企业微信 webhook。
6. 最后加 GitHub Actions。

## 6. 不要做

- 不要加入任何真实患者数据样例。
- 不要把 key 写死在代码里。
- 不要直接声明可用于诊疗。
- 不要把未核验的政策/招采信息作为确定事实对外发布。

## 7. PR 要求

请创建一个 PR，标题：

```text
feat: add ZY-Brief mobile audio broadcast MVP
```

PR 描述中请包含：

- 修改文件清单
- 本地测试命令和结果
- GitHub Actions 配置说明
- 手机播放测试方式
- 需要用户配置的 Secrets
