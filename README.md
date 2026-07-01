<div align="center">

# 棒棒糖的每日晨报

AstrBot 每日综合日报插件 (Daily Report Plugin)

![Visitor Count](https://visitor-badge.laobi.icu/badge?page_id=zhoufan47.astrbot_plugin_bbt_daily_report)
![AstrBot Plugin](https://img.shields.io/badge/AstrBot-Plugin-green)
![Version](https://img.shields.io/badge/Version-v1.6.1-blue)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-AGPLv3-orange)

</div>

这是一个为 [AstrBot](https://github.com/Soulter/AstrBot) 开发的综合日报生成插件。它能够每天定时抓取新闻、科技热点、硬件价格、汇率、AI服务额度、油价、金价、影视动漫、游戏发售等多维度数据，通过 Jinja2 模板引擎渲染为精美的 HTML 图片，并自动推送到指定群聊。

## ✨ 功能特性

* **定时推送**：支持自定义每日发送时间，到点自动生成并推送日报。
* **多源聚合**：整合新闻、科技、娱乐、金融、影视、游戏等十余个数据源。
* **多模板渲染**：支持主报告 + 子报告（动画 / 电影 / DMM）多图拆分发送。
* **AI 额度监控**：实时查询 OpenRouter、DeepSeek、Moonshot (Kimi)、硅基流动 (SiliconFlow) 的账户余额。
* **油价与金价**：获取国内各省份成品油价格及国际/国内黄金价格。
* **数据缓存**：内置缓存机制，减少重复请求，避免 API 频率超限。
* **LLM 工具集成**：注册为 AstrBot LLM 工具，可通过 AI 对话触发生成日报。
* **独立开关**：每个数据模块（动画、电影、IT之家、DRAM、DMM等）均可单独开启/关闭。
* **代理支持**：可选通过代理服务器访问外部 API。
* **精美排版**：使用 CSS Grid/Flex 布局，自动渲染为高清图片。
* **异步并发**：基于 asyncio + aiohttp 实现数据并发抓取，高效快速。

## 📊 数据来源说明 (Data Sources)

本插件的数据来源于互联网公开接口及网页抓取，具体如下：

| 模块 | 数据内容 | 数据来源 | 来源网址 | 获取方式 |
|:----------|:----------------|:---------------------|:-----------------------------------------------|:-----------|
| **新闻速读** | 每日 60 秒读懂世界 | Viki API | `https://60s-api.viki.moe/v2/60s` | API 调用 |
| **科技热点** | IT之家热榜 (日榜) | IT之家 (ITHome) | `https://www.ithome.com/block/rank.html` | 网页抓取 |
| **硬件价格** | 国际 DRAM 颗粒现货价格 | 全球半导体观察 (DRAMeXchange) | `https://www.dramx.com/Price/DSD.html` | 网页抓取 |
| **实时汇率** | 法币汇率 (CNY 基准) | ExchangeRate-API | `https://www.exchangerate-api.com/` | API 调用 |
| **AI 额度** | 账户余额/用量 | OpenRouter | `https://openrouter.ai/` | 官方 API |
| **AI 额度** | 账户余额 | DeepSeek | `https://platform.deepseek.com/` | 官方 API |
| **AI 额度** | 账户余额 | Moonshot (Kimi) | `https://platform.moonshot.cn/` | 官方 API |
| **AI 额度** | 账户余额 | 硅基流动 (SiliconFlow) | `https://siliconflow.cn/` | 官方 API |
| **新番放送** | 每日动画更新及封面 | 番组计划 (Bangumi) | `https://bgm.tv/calendar` | 网页抓取 |
| **电影** | 近期上映电影及封面 | 豆瓣电影 | `https://movie.douban.com/cinema/later/beijing/` | 网页抓取 |
| **游戏发售** | 近期发售新游及平台 | RAWG | `https://rawg.io/` | API 调用 |
| **油价** | 各省份成品油价格 | Viki API | `https://60s-api.viki.moe/v2/fuel-price` | API 调用 |
| **金价** | 国际与国内黄金价格 | Viki API | `https://60s-api.viki.moe/v2/gold-price` | API 调用 |
| **微博热榜** | 微博热搜榜 | 枫雨API | `https://api-v2.yuafeng.cn/` | API 调用 |
| **头条热榜** | 今日头条热榜 | 枫雨API | `https://api-v2.yuafeng.cn/` | API 调用 |
| **DMM R18** | DMM AV 排行榜 | DMM GraphQL API | `https://api.video.dmm.co.jp/graphql` | API 调用 |

> **注意**：
> - **IT之家、DRAMx、Bangumi** 等基于网页抓取的源可能因目标网站改版而失效，请留意插件更新。
> - **ExchangeRate-API、RAWG、枫雨API** 需要自行注册并获取 API 密钥。
> - **AI 额度查询** 使用各平台官方 API，需在配置页面填写 API 密钥。
> - **DMM 排行榜** 仅在 `r18_mode` 开启时生效，请注意合规性。
> - 目前支持 **aiocqhttp** 等 AstrBot 平台。

## 💬 支持的指令

| 指令 | 描述 |
|:---|:---|
| `看看日报` | 手动触发日报生成并发送 |
| `清除日报缓存` | 手动清除数据缓存，下次查询重新获取最新数据 |

> 插件同时注册了 `today_news` 和 `clear_daily_report_cache` LLM 工具，可在 AI 对话中通过自然语言触发。

## ⚙️ 配置项说明

在 AstrBot WebUI 或 `cmd_config.json` 中配置以下参数：

| 配置项 | 类型 | 默认值 | 说明 |
|:--------|:------|:--------|:------|
| `target_groups` | list | `["platform:GroupMessage:group_id"]` | 接收日报的群组标识符列表 |
| `send_time` | string | `"08:00"` | 每日定时推送时间 (HH:MM) |
| `openrouter_key` | string | `""` | OpenRouter API 密钥 |
| `deepseek_key` | string | `""` | DeepSeek API 密钥 |
| `moonshot_key` | string | `""` | Moonshot (Kimi) API 密钥 |
| `siliconflow_key` | string | `""` | 硅基流动 API 密钥 |
| `yuafeng_key` | string | `""` | 枫雨API 密钥 (用于微博/头条热榜) |
| `exchangerate_key` | string | `""` | ExchangeRate-API 密钥 (汇率查询) |
| `rawg_key` | string | `""` | RAWG API 密钥 (游戏发售查询) |
| `game_release_date_threshold` | int | `14` | 游戏发售查询未来天数 |
| `fuel_province` | string | `"北京"` | 油价查询省份 |
| `r18_mode` | bool | `false` | 开启 DMM 成人内容排行 |
| `movie_mode` | bool | `true` | 展示豆瓣近期上映电影 |
| `animation_mode` | bool | `true` | 展示番组计划今日动画 |
| `dram_mode` | bool | `true` | 展示 DRAM 内存价格涨跌 |
| `ithome_mode` | bool | `true` | 展示 IT之家热榜 |
| `fuel_mode` | bool | `true` | 展示各省油价数据 |
| `gold_mode` | bool | `true` | 展示国际/国内金价数据 |
| `proxy_mode` | bool | `false` | 使用 AstrBot 代理服务器 |
| `report_jpeg_quality` | int | `80` | 生成图片质量 (1-100) |
| `max_concurrent_requests` | int | `5` | 最大并发请求数 |
| `cache_ttl_minutes` | int | `10` | 数据缓存有效时间 (分钟) |

## 🛠️ 安装与依赖

### 手动安装

1. 将本插件文件夹 `astrbot_plugin_bbt_daily_news` 放入 AstrBot 的 `plugins` 目录下。
2. 安装 Python 依赖库：

```bash
cd plugins/astrbot_plugin_bbt_daily_news
pip install -r requirements.txt
```

3. 进入 AstrBot WebUI 进行参数配置（或编辑 `cmd_config.json`）。

### 依赖项

| 依赖 | 版本要求 | 用途 |
|:---|:---|:---|
| aiohttp | >=3.10.0 | 异步 HTTP 请求 |
| apscheduler | >=3.11.0 | 定时任务调度 |
| Pillow | >=12.0.0 | 图片缩放处理 |
| beautifulsoup4 | >=4.14.0 | HTML 解析 (网页抓取) |
| lxml | >=4.9.0 | 快速 XML/HTML 解析 |

> 插件依赖 AstrBot 内置的 T2I (Text-to-Image) 服务将 HTML 渲染为图片。

## 👥 贡献指南

- 🌟 Star 这个项目！（点右上角的星星，感谢支持！）
- 🐛 提交 Issue 报告问题
- 💡 提出新功能建议
- 🔧 提交 Pull Request 改进代码

## ❤️ 鸣谢

- 感谢 **AstrBot** 框架和 **AstrBot T2I Service**。
- 感谢所有数据源提供方（Viki API、IT之家、DRAMeXchange、番组计划、豆瓣、ExchangeRate-API、RAWG、枫雨API、DMM 等）。
