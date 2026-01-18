
<div align="center">

# AstrBot 每日简报插件 (Daily Report Plugin)

![Visitor Count](https://visitor-badge.laobi.icu/badge?page_id=zhoufan47.astrbot_plugin_bbt_daily_report)
![AstrBot Plugin](https://img.shields.io/badge/AstrBot-Plugin-green)
![Python](https://img.shields.io/badge/Python-3.13+-blue)
![License](https://img.shields.io/badge/License-AGPLv3-orange)


</div>

这是一个为 [AstrBot](https://github.com/Soulter/AstrBot) 开发的综合日报生成插件。它能够每天定时抓取新闻、科技热点、硬件价格、汇率以及 AI 服务的额度信息，自动渲染成精美的 HTML 图片并发送到指定的 QQ 群。

## ✨ 功能特性

* **定时推送**：支持自定义每日发送时间。
* **多源聚合**：整合了新闻、科技、娱乐、金融等多个领域的数据。
* **AI 额度监控**：实时查询 DeepSeek、OpenRouter、Moonshot 等主流 AI 服务的剩余额度。
* **精美排版**：使用 Jinja2 模板引擎渲染 HTML，并转换为图片发送，支持 CSS Grid/Flex 布局。
* **模块化设计**：各数据源抓取互不干扰，支持异步并发。

## 📊 数据来源说明 (Data Sources)

本插件的数据来源于互联网公开接口及网页抓取，具体如下：

| 模块 | 数据内容 | 数据来源 | 来源网址 | 获取方式 |
| :--- | :--- | :--- | :--- | :--- |
| **新闻速读** | 每日 60 秒读懂世界 | Viki API | `https://60s-api.viki.moe/` | API 调用 |
| **科技热点** | IT之家热榜 (日榜) | IT之家 (ITHome) | `https://www.ithome.com/block/rank.html` | 网页抓取 |
| **硬件价格** | 国际 DRAM 颗粒现货价格 | 全球半导体观察 | `https://www.dramx.com/Price/DSD.html` | 网页抓取 |
| **新番放送** | 每日动画更新及封面 | 番组计划 (Bangumi) | `https://bgm.tv/calendar` | 网页抓取 |
| **实时汇率** | 法币汇率 (CNY 基准) | ExchangeRate-API | `https://www.exchangerate-api.com/` | API 调用 |
| **AI 额度** | 账户余额/用量 | OpenRouter | `https://openrouter.ai/` | 官方 API |
| **AI 额度** | 账户余额 | DeepSeek | `https://platform.deepseek.com/` | 官方 API |
| **AI 额度** | 账户余额 | Moonshot (Kimi) | `https://platform.moonshot.cn/` | 官方 API |
| **AI 额度** | 账户余额 | 硅基流动 (SiliconFlow) | `https://siliconflow.cn/` | 官方 API |
| **娱乐/其他** | 榜单数据 (视模板而定) | 微博/头条/DMM | 对应官网 | 网页抓取 |

> **注意**：网页抓取功能（如 IT之家、DRAMx、Bangumi）可能会因为目标网站改版而失效，请留意插件更新。

## 🛠️ 安装与依赖

1.  将本插件文件夹 `astrbot_plugin_daily_report` 放入 AstrBot 的 `plugins` 目录下。
2.  安装 Python 依赖库：
3.   参数设置 进入AstrBot webui进行相关参数设置。
```bash
pip install -r requirements.txt
```

## 👥 贡献指南

- 🌟 Star 这个项目！（点右上角的星星，感谢支持！）
- 🐛 提交 Issue 报告问题
- 💡 提出新功能建议
- 🔧 提交 Pull Request 改进代码


## ❤️ 鸣谢
- 感谢 **AstrBot** 框架和 **AstrBot T2I Service** 。
