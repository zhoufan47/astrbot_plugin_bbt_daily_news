import asyncio
import datetime
import os
from typing import Dict, List, Any
import re
import traceback
import io
from dataclasses import dataclass
from datetime import timedelta

from PIL import Image as PILImage
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup
import aiohttp
import base64

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.message.components import Image
from astrbot.core.message.message_event_result import MessageChain

from apscheduler.schedulers.asyncio import AsyncIOScheduler

user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# API配置常量
NEWS_API_URL = "https://60s-api.viki.moe/v2/60s"
ITHOME_RANK_URL = "https://www.ithome.com/block/rank.html"
DRAM_PRICE_URL = "https://www.dramx.com/Price/DSD.html"
BANGUMI_CALENDAR_URL = "https://bgm.tv/calendar"
DOUBAN_MOVIE_URL = "https://movie.douban.com/cinema/later/beijing/"
DMM_RANKING_URL = "https://www.dmm.co.jp/digital/videoa/-/ranking/=/term=daily/"

@dataclass
class CacheEntry:
    """缓存条目"""
    data: Any
    timestamp: datetime.datetime
    
    def is_expired(self, ttl_minutes: int = 10) -> bool:
        """检查缓存是否过期"""
        return datetime.datetime.now() > self.timestamp + timedelta(minutes=ttl_minutes)

@register("daily_report", "棒棒糖", "每日综合简报插件", "1.5.2")
class DailyReportPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config

        # 加载配置
        self.target_groups = config.get("target_groups", [])  # List[str]
        self.send_time = config.get("send_time", "08:00")  # HH:MM
        self.openrouter_key = config.get("openrouter_key", "")
        self.deepseek_key = config.get("deepseek_key", "")
        self.moonshot_key = config.get("moonshot_key", "")
        self.siliconflow_key = config.get("siliconflow_key", "")
        self.yuafeng_key = config.get("yuafeng_key", "")
        self.exchangerate_key = config.get("exchangerate_key", "")
        self.r18_mode = config.get("r18_mode", False)
        self.rawg_key = config.get("rawg_key", "")
        self.game_release_date_threshold = config.get("game_release_date_threshold", 14)
        self.report_jpeg_quality = config.get("report_jpeg_quality", 80)
        self.cache_ttl_minutes = config.get("cache_ttl_minutes", 10)  # 缓存有效时间，默认10分钟
        self.max_concurrent_requests = config.get("max_concurrent_requests", 5)
        
        # 初始化缓存
        self.cache = {}
        
        # 限制并发数
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        # 本地读取模板文件
        # 获取当前文件 (main.py) 所在的目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 拼接模板文件路径: group_summary/templates/report.html
        template_path = os.path.join(current_dir, "templates", "report.html")
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                self.html_template = f.read()
            logger.info(f"棒棒糖的每日晨报：成功加载模板: {template_path}")
        except FileNotFoundError:
            logger.error(f"棒棒糖的每日晨报：未找到模板文件: {template_path}")
            # 设置一个简单的兜底模板，防止崩溃
            self.html_template = "<h1>Template Not Found</h1>"

        # --- 修复部分：自己实例化调度器 ---
        self.scheduler = AsyncIOScheduler()

        # 解析时间
        try:
            hour, minute = self.send_time.split(":")
            # 添加定时任务
            self.scheduler.add_job(
                self.broadcast_report,
                'cron',
                hour=int(hour),
                minute=int(minute),
                id="daily_report_job"
            )
            # 启动调度器
            self.scheduler.start()
            logger.info(f"棒棒糖的每日晨报：定时任务已创建{self.send_time}")
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：定时任务创建失败: {traceback.format_exc()}")
            logger.error(f"棒棒糖的每日晨报：定时任务创建失败: {e}")

    # --- 数据获取模块 ---

    async def fetch_60s_news(self, session) -> Dict:
        """1. 获取60秒读懂世界"""
        try:
            async with self.semaphore:  # 限制并发
                async with session.get(NEWS_API_URL) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # 修复错误的数据访问方式：原代码中"news:"是错误的键名
                        return {"news": data.get("data", {}).get("news", [])}
                    else:
                        logger.warning(f"棒棒糖的每日晨报：获取60秒新闻API返回非200状态码: {resp.status}")
                        return {"news": ["获取失败"]}
        except asyncio.TimeoutError:
            logger.error("棒棒糖的每日晨报：获取60秒新闻超时")
            return {"news": ["获取失败 - 请求超时"]}
        except aiohttp.ClientError as e:
            logger.error(f"棒棒糖的每日晨报：获取60秒新闻网络错误: {e}")
            return {"news": ["获取失败 - 网络错误"]}
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：获取60秒新闻失败: {e}")
        return {"news": ["获取失败"]}

    async def fetch_ithome_news(self, session) -> List[str]:
        """抓取IT之家热榜"""
        headers = {
            "User-Agent": user_agent
        }
        news_list = []
        try:
            async with self.semaphore:  # 限制并发
                async with session.get(ITHOME_RANK_URL, headers=headers) as resp:
                    text = await resp.text()
                    soup = BeautifulSoup(text, 'lxml')

                    # 1. 根据源码，日榜在 id="d-1" 的 ul 标签下
                    # Line 14: <ul class="bd order sel" id="d-1">
                    daily_list = soup.select_one("ul#d-1")

                    if daily_list:
                        # 2. 遍历该 ul 下的所有 a 标签
                        # Line 15: <li><a title="..." ...>标题</a></li>
                        links = daily_list.select("li a")

                        for link in links:
                            title = link.get_text(strip=True)
                            if title:
                                news_list.append(title)
                    else:
                        logger.warning("棒棒糖的每日晨报：未找到IT之家热榜容器(ul#d-1)")

        except asyncio.TimeoutError:
            logger.error("棒棒糖的每日晨报：获取IT之家热榜超时")
            news_list.append("获取失败 - 请求超时")
        except aiohttp.ClientError as e:
            logger.error(f"棒棒糖的每日晨报：获取IT之家热榜网络错误: {e}")
            news_list.append("获取失败 - 网络错误")
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：抓取IT之家热榜失败: {e}")
            news_list.append("获取失败 - 未知错误")

        # 返回前 10 条，避免太长
        return news_list[:10]

    async def fetch_dram_price(self, session) -> List[Dict]:
        """抓取DRAM价格 """
        headers = {
            "User-Agent": user_agent
        }
        data = []
        try:
            async with self.semaphore:  # 限制并发
                async with session.get(DRAM_PRICE_URL, headers=headers) as resp:
                    # 显式指定编码，防止乱码（虽然中文网页通常 utf-8，但以防万一）
                    text = await resp.text(encoding='utf-8')
                    soup = BeautifulSoup(text, 'lxml')

                    # 1. 定位 id="price1" 下的 class="price-table"
                    # 这样更精准，不会误抓到下面的 Flash 或其他表格
                    table = soup.select_one("#price1 table.price-table")

                    if not table:
                        logger.warning("棒棒糖的每日晨报：未找到DRAM价格表格，页面结构可能已变更")
                        return []

                    # 2. 跳过表头，遍历数据行
                    rows = table.find_all("tr")
                    # rows[0] 是表头，从 rows[1] 开始取前 6 行（包含表头通常是7行）
                    for row in rows[1:7]:
                        cols = row.find_all("td")
                        if len(cols) < 5:
                            continue

                        # 3. 提取数据
                        # 第0列: 产品名称 (DDR5...)
                        name = cols[0].get_text(strip=True)

                        # 第3列: 盘平均 (通常看平均价)
                        price = cols[3].get_text(strip=True)

                        # 第4列: 涨幅度 (包含 img 标签和文本)
                        change_td = cols[4]
                        change_text = change_td.get_text(strip=True)

                        # 4. 处理涨跌符号（为了适配 HTML 模板的变色逻辑）
                        img = change_td.find("img")
                        if img:
                            src = img.get("src", "")
                            if "up" in src:  # 图片路径包含 up
                                change_text = f"+{change_text}"
                            elif "down" in src:  # 图片路径包含 down
                                change_text = f"-{change_text}"
                            # stable (平盘) 不做处理

                        data.append({
                            "name": name,
                            "price": price,
                            "change": change_text
                        })

        except asyncio.TimeoutError:
            logger.error("棒棒糖的每日晨报：获取DRAM价格超时")
        except aiohttp.ClientError as e:
            logger.error(f"棒棒糖的每日晨报：获取DRAM价格网络错误: {e}")
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：抓取DRAM价格失败: {e}")
        return data

    async def fetch_bangumi_today(self, session) -> List[Dict]:
        """ 抓取今日番剧 (基于用户提供的层级优化)"""
        headers = {
            "User-Agent": user_agent
        }
        anime_list = []
        # Bangumi 页面使用英文简写作为 class 名
        weekday_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
        today_key = weekday_map[datetime.datetime.today().weekday()]

        try:
            async with self.semaphore:  # 限制并发
                async with session.get(BANGUMI_CALENDAR_URL, headers=headers) as resp:
                    text = await resp.text()
                    soup = BeautifulSoup(text, 'lxml')

                    # 策略：直接利用 class 名定位当天的数据，这比长 XPath 更稳定
                    # 对应你 XPath 中的 .../dl/dd 部分
                    day_section = soup.find("dd", class_=today_key)

                    if day_section:
                        # 对应你 XPath 中的 .../ul/li[...]
                        items = day_section.find_all("li")

                        for item in items:
                            data = {"title": "未知", "cover": ""}

                            # --- 1. 获取标题 ---
                            link_tag = item.find("a")
                            if link_tag:
                                title = link_tag.get_text(strip=True)
                                # 如果标题为空，直接跳过
                                if not title:
                                    continue
                                data["title"] = title

                            style_attr = item.get('style', '')
                            # --- 2. 获取图片 (双重策略) ---
                            url_match = re.search(r"url\('?(.*?)'?\)", style_attr)

                            img_url = "https://bgm.tv/img/no_icon_subject.png"
                            if url_match:
                                raw_url = url_match.group(1)
                                img_url = "https://" + raw_url.lstrip('/')

                            data["cover"] = img_url
                            anime_list.append(data)

        except asyncio.TimeoutError:
            logger.error("棒棒糖的每日晨报：获取今日番剧超时")
        except aiohttp.ClientError as e:
            logger.error(f"棒棒糖的每日晨报：获取今日番剧网络错误: {e}")
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：抓取今日番剧失败: {e}")

        return anime_list

    async def fetch_douban_movies(self, session) -> List[Dict]:
        """12. 获取豆瓣近期上映电影 (转 Base64 版)"""
        # 豆瓣对 Referer 检查非常严格
        headers = {
            "User-Agent": user_agent,
            "Referer": "https://movie.douban.com/",
        }

        movie_list = []
        try:
            async with self.semaphore:  # 限制并发
                async with session.get(DOUBAN_MOVIE_URL, headers=headers) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        soup = BeautifulSoup(text, 'lxml')

                        container = soup.find("div", id="showing-soon")
                        if container:
                            items = container.find_all("div", class_="item")

                            # 限制数量，防止 Base64 导致 HTML 体积过大
                            for item in items[:9]:
                                movie = {}

                                # 1. 标题
                                title_tag = item.find("h3").find("a")
                                movie["title"] = title_tag.get_text(strip=True)

                                # 2. 封面处理 (关键修改)
                                img_tag = item.find("a", class_="thumb").find("img")
                                raw_cover_url = ""
                                if img_tag:
                                    raw_cover_url = img_tag.get("src", "")

                                # 下载并转 Base64
                                if raw_cover_url:
                                    movie["cover"] = await self._url_to_base64(
                                        session,
                                        raw_cover_url,
                                        referer="https://movie.douban.com/"
                                    )
                                else:
                                    movie["cover"] = ""

                                # 3. 信息列表
                                info_ul = item.find("ul")
                                if info_ul:
                                    lis = info_ul.find_all("li")
                                    if len(lis) >= 1:
                                        movie["date"] = lis[0].get_text(strip=True)
                                    if len(lis) >= 2:
                                        movie["type"] = lis[1].get_text(strip=True)

                                movie_list.append(movie)

        except asyncio.TimeoutError:
            logger.error("棒棒糖的每日晨报：获取豆瓣近期上映电影超时")
        except aiohttp.ClientError as e:
            logger.error(f"棒棒糖的每日晨报：获取豆瓣近期上映电影网络错误: {e}")
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：抓取豆瓣近期上映电影失败: {e}")

        return movie_list

    async def fetch_openrouter_credits(self, session) -> Dict:
        """ 获取OpenRouter余额"""
        if not self.openrouter_key:
            return {"error": "未配置Key"}

        url = "https://openrouter.ai/api/v1/auth/key"
        headers = {"Authorization": f"Bearer {self.openrouter_key}"}

        def parse_openrouter_data(data):
            info = data.get("data", {})
            usage = info.get("usage", 0)
            limit_remaining = info.get("limit_remaining", 0)
            usage_daily = info.get("usage_daily", 0)
            return {
                "usage_daily": f"${usage_daily:.4f}",
                "usage": f"${usage:.4f}",
                "limit_remaining": f"${limit_remaining:.4f}" if limit_remaining else "No Limit",
            }

        return await self._fetch_api_balance(session, "OpenRouter", url, headers, parse_openrouter_data)

    async def fetch_deepseek_balance(self, session) -> Dict:
        """ 获取 DeepSeek 余额"""
        if not self.deepseek_key:
            return {"name": "DeepSeek", "error": "未配置Key"}

        url = "https://api.deepseek.com/user/balance"
        headers = {"Authorization": f"Bearer {self.deepseek_key}"}

        def parse_deepseek_data(data):
            infos = data.get("balance_infos", [])
            balance_str = "0.00"
            currency = "CNY"

            if infos:
                item = infos[0]
                balance_str = item.get("total_balance", "0.00")
                currency = item.get("currency", "CNY")

            return {
                "name": "DeepSeek",
                "balance": f"{balance_str} {currency}",
                "status": "正常" if data.get("is_available") else "已停用"
            }

        return await self._fetch_api_balance(session, "DeepSeek", url, headers, parse_deepseek_data)

    async def fetch_moonshot_balance(self, session) -> Dict:
        """9. 获取 Moonshot (Kimi) 余额"""
        if not self.moonshot_key:
            return {"name": "Moonshot", "error": "未配置Key"}

        url = "https://api.moonshot.cn/v1/users/me/balance"
        headers = {"Authorization": f"Bearer {self.moonshot_key}"}

        def parse_moonshot_data(data):
            info = data.get("data", {})
            available = info.get("available_balance", 0)
            return {
                "name": "Moonshot",
                "balance": f"¥{available:.2f}",
                "status": "正常" if data.get("status") else "已停用"
            }

        return await self._fetch_api_balance(session, "Moonshot", url, headers, parse_moonshot_data)

    async def fetch_siliconflow_balance(self, session) -> Dict:
        """10. 获取 硅基流动 (SiliconFlow) 余额"""
        if not self.siliconflow_key:
            return {"name": "SiliconFlow", "error": "未配置Key"}

        url = "https://api.siliconflow.cn/v1/user/info"
        headers = {"Authorization": f"Bearer {self.siliconflow_key}"}

        def parse_siliconflow_data(data):
            info = data.get("data", {})
            balance = info.get("balance", "0")
            return {
                "name": "SiliconFlow",
                "balance": f"¥{balance}",
                "status": "Active"
            }

        return await self._fetch_api_balance(session, "SiliconFlow", url, headers, parse_siliconflow_data)

    async def fetch_weibo_hot(self, session) -> List[Dict]:
        """获取微博热榜"""
        if not self.yuafeng_key:
            return []

        results = []
        url = "https://api-v2.yuafeng.cn/API/jinri_hot.php"
        params = {
            'apikey': self.yuafeng_key,
            'action': '微博热榜',
            'page': '1',
        }
        try:
            async with self.semaphore:  # 限制并发
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        info = data.get("data", [])
                        for item in info:
                            results.append(item["title"])
                        return results
                    else:
                        logger.warning(f"棒棒糖的每日晨报：获取微博热榜API返回非200状态码: {resp.status}")
                        return []

        except asyncio.TimeoutError:
            logger.error("棒棒糖的每日晨报：获取微博热榜超时")
        except aiohttp.ClientError as e:
            logger.error(f"棒棒糖的每日晨报：获取微博热榜网络错误: {e}")
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：获取微博热榜失败: {e}")
        return []

    async def fetch_toutiao_hot(self, session) -> List[Dict]:
        """获取今日头条热榜"""
        if not self.yuafeng_key:
            return []

        results = []
        url = "https://api-v2.yuafeng.cn/API/jinri_hot.php"
        params = {
            'apikey': self.yuafeng_key,
            'action': '今日头条热榜',
            'page': '1',
        }
        try:
            async with self.semaphore:  # 限制并发
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        info = data.get("data", [])
                        for item in info:
                            results.append(item["title"])
                        return results
                    else:
                        logger.warning(f"棒棒糖的每日晨报：获取今日头条热榜API返回非200状态码: {resp.status}")
                        return []
        except asyncio.TimeoutError:
            logger.error("棒棒糖的每日晨报：获取今日头条热榜超时")
        except aiohttp.ClientError as e:
            logger.error(f"棒棒糖的每日晨报：获取今日头条热榜网络错误: {e}")
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：获取今日头条热榜失败: {e}")
        return []

    async def fetch_exchange_rates(self, session) -> Dict:
        """获取汇率 (基准 CNY)"""
        if not self.exchangerate_key:
            return {"error": "未配置Key"}

        url = f"https://v6.exchangerate-api.com/v6/{self.exchangerate_key}/latest/CNY"
        try:
            async with self.semaphore:  # 限制并发
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # 只有 API 返回成功才处理
                        if data.get("result") == "success":
                            rates = data.get("conversion_rates", {})
                            return {
                                "USD": f"{rates.get('USD', 0):.4f}",
                                "JPY": f"{rates.get('JPY', 0):.4f}",
                                "EUR": f"{rates.get('EUR', 0):.4f}",
                                "GBP": f"{rates.get('GBP', 0):.4f}",
                                "TWD": f"{rates.get('TWD', 0):.4f}",
                                "HKD": f"{rates.get('HKD', 0):.4f}"
                            }
                        else:
                            logger.warning("棒棒糖的每日晨报：获取汇率API返回非success结果")
                            return {"error": "获取失败"}
                    else:
                        logger.warning(f"棒棒糖的每日晨报：获取汇率API返回非200状态码: {resp.status}")
                        return {"error": "获取失败"}

        except asyncio.TimeoutError:
            logger.error("棒棒糖的每日晨报：获取汇率超时")
            return {"error": "获取失败 - 请求超时"}
        except aiohttp.ClientError as e:
            logger.error(f"棒棒糖的每日晨报：获取汇率网络错误: {e}")
            return {"error": "获取失败 - 网络错误"}
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：获取汇率失败: {e}")
            return {"error": "获取失败"}

    async def fetch_dmm_top(self, session) -> List[Dict]:
        if not self.r18_mode:
            return []
        headers = {
            "User-Agent": user_agent
        }
        # 需要为cookies 设置 age_check_done=1，否则会返回年龄检查页面
        try:
            async with self.semaphore:  # 限制并发
                async with session.get(DMM_RANKING_URL, headers=headers, cookies={"age_check_done": "1"}) as resp:
                    # 获取网页内容文本
                    html_text = await resp.text()
                    #解析 HTML
                    soup = BeautifulSoup(html_text, 'lxml')
                    results = []

                    # 提取数据
                    # 逻辑：查找所有 id 以 "package-src-" 开头的 img 标签
                    targets = soup.find_all('img', id=re.compile(r'^package-src-'))

                    for img in targets:
                        title = img.get('alt')
                        src = img.get('src')

                        if title and src:
                            results.append({
                                "title": title,
                                "cover": src
                            })
                    return results
        except asyncio.TimeoutError:
            logger.error("棒棒糖的每日晨报：获取DMM数据超时")
        except aiohttp.ClientError as e:
            logger.error(f"棒棒糖的每日晨报：获取DMM数据网络错误: {e}")
        except Exception as e:
            logger.exception(f"棒棒糖的每日晨报：获取DMM数据失败: {e}")
        return []

    async def fetch_rawg_games(self, session) -> List[Dict]:
        if not self.rawg_key:
            return []

        # 计算日期范围：未来 {self.game_release_date_threshold} 天
        today = datetime.date.today()
        future = today + datetime.timedelta(days=self.game_release_date_threshold)
        dates_str = f"{today},{future}"

        # stores=1(Steam), 3(PlayStation Store), 6(Nintendo Store)
        # ordering=-released 表示发售日期倒序，无-表示正序
        url = f"https://api.rawg.io/api/games?key={self.rawg_key}&dates={dates_str}&stores=1,3,6&ordering=released&page_size=9"

        games_list = []
        try:
            async with self.semaphore:  # 限制并发
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])

                        for item in results:
                            game = {}

                            # 1. 标题
                            game["title"] = item.get("name", "Unknown")

                            # 2. 封面 (转 Base64)
                            raw_bg = item.get("background_image", "")
                            if raw_bg:
                                # RAWG 图片支持裁剪参数，可以加 ?width=400 减小体积，但这里直接下原图也不大
                                game["cover"] = await self._url_to_base64(session, raw_bg, width=512)
                            else:
                                game["cover"] = ""

                            # 3. 平台信息
                            # 使用 parent_platforms 获取大类 (PC, PlayStation, Xbox, Nintendo)
                            platforms_data = item.get("parent_platforms", [])
                            p_names = []
                            if platforms_data:
                                for p_wrapper in platforms_data:
                                    p_info = p_wrapper.get("platform", {})
                                    p_name = p_info.get("name", "")
                                    if p_name == "PC":
                                        p_names.append("PC")
                                    elif p_name == "PlayStation":
                                        p_names.append("PlayStation")
                                    elif p_name == "Xbox":
                                        p_names.append("Xbox")
                                    elif p_name == "Nintendo":
                                        p_names.append("NS")
                                    elif p_name == "Apple Macintosh":
                                        p_names.append("Mac")
                                    else:
                                        p_names.append(p_name)

                            game["platforms"] = " / ".join(p_names) if p_names else "多平台"

                            # 4. 发售日期
                            game["release"] = item.get("released", "")[5:]  # 只取 MM-DD

                            games_list.append(game)

        except asyncio.TimeoutError:
            logger.error("棒棒糖的每日晨报：获取RAWG游戏数据超时")
        except aiohttp.ClientError as e:
            logger.error(f"棒棒糖的每日晨报：获取RAWG游戏数据网络错误: {e}")
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：获取RAWG游戏数据失败: {e}")

        return games_list

    async def generate_html(self) -> Image:
        """聚合数据并渲染HTML，使用缓存机制"""
        # 尝试从缓存获取数据
        cache_key = "daily_report_data"
        cached_entry = self.cache.get(cache_key)
        
        if cached_entry and not cached_entry.is_expired(self.cache_ttl_minutes):
            logger.info("棒棒糖的每日晨报：使用缓存数据生成HTML")
            results_dict = cached_entry.data
        else:
            logger.info("棒棒糖的每日晨报：缓存未命中或已过期，开始获取最新数据")
            # 创建一个异步会话（不走代理）
            timeout = ClientTimeout(total=30)  # 明确设置总超时时间
            
            # 定义数据获取任务
            data_fetch_tasks = [
                self.fetch_60s_news,
                self.fetch_ithome_news,
                self.fetch_dram_price,
                self.fetch_bangumi_today,
                self.fetch_openrouter_credits,       # 4 openrouter余额查询
                self.fetch_deepseek_balance,         # 5 DS余额查询
                self.fetch_moonshot_balance,         # 6 Moonshot余额查询
                self.fetch_siliconflow_balance,      # 7 硅基流动余额查询
                self.fetch_toutiao_hot,              # 8 今日头条热榜
                self.fetch_weibo_hot,                # 9 微博热榜
                self.fetch_exchange_rates,           # 10 汇率数据
                self.fetch_douban_movies,            # 11 豆瓣电影
                self.fetch_rawg_games,
            ]
            
            async with aiohttp.ClientSession(trust_env=False, timeout=timeout) as session:
                # 并发执行所有抓取任务
                logger.info("棒棒糖的每日晨报：开始并发获取数据")
                raw_results = await asyncio.gather(*[task(session) for task in data_fetch_tasks], return_exceptions=True)
            
            # 处理gather可能返回的异常对象
            results_dict = self._process_results(raw_results)
            
            # 将结果存入缓存
            self.cache[cache_key] = CacheEntry(data=results_dict, timestamp=datetime.datetime.now())
            logger.info("棒棒糖的每日晨报：数据已存入缓存")
        
        # 仅在启用R18模式时创建代理会话获取DMM数据
        dmm_top_list = []
        if self.r18_mode:
            # DMM数据单独处理，不放入缓存（因为它依赖于R18模式设置）
            timeout = ClientTimeout(total=30)
            async with aiohttp.ClientSession(trust_env=True, timeout=timeout) as session_proxy:
                dmm_results = await asyncio.gather(
                    self.fetch_dmm_top(session_proxy),
                    return_exceptions=True
                )
                dmm_top_list = dmm_results[0] if not isinstance(dmm_results[0], Exception) else []

        # 整理 AI 余额数据列表
        ai_balances = {
            "OpenRouter": results_dict['openrouter_credits'],
            "DeepSeek": results_dict['deepseek_balance'],
            "MoonShot": results_dict['moonshot_balance'],
            "SiliconFlow": results_dict['siliconflow_balance'],
        }
        show_adult = "1" if self.r18_mode else "0"
        
        # 整理常规数据
        context_data = {
            "r18_mode": show_adult,
            "date": datetime.datetime.now().strftime("%Y-%m-%d %A"),
            "news_60s": results_dict['news_60s'].get("news", []) if isinstance(results_dict['news_60s'], dict) else [],
            "news_ithome": results_dict['ithome_news'],
            "dram_prices": results_dict['dram_price'],
            "bangumi_list": results_dict['bangumi_today'],
            "ai_balances": ai_balances,
            "dmm_top_list": dmm_top_list,
            "toutiao_hot": results_dict['toutiao_hot'],
            "weibo_hot": results_dict['weibo_hot'],
            "exchange_rates": results_dict['exchange_rates'],
            "movie_list": results_dict['douban_movies'],
            "game_list": results_dict['rawg_games']
        }
        logger.info(f"棒棒糖的每日晨报：渲染数据: {context_data}")
        options = {"quality": self.report_jpeg_quality, "device_scale_factor_level": "ultra", "viewport_width": 505}
        img_result = await self.html_render(self.html_template, context_data, options=options)
        logger.info("棒棒糖的每日晨报：HTML 生成完成")
        return img_result

    def _process_results(self, raw_results):
        """处理原始结果，将其转换为字典格式"""
        # 定义结果映射
        result_mapping = {
            'news_60s': 0,
            'ithome_news': 1,
            'dram_price': 2,
            'bangumi_today': 3,
            'openrouter_credits': 4,
            'deepseek_balance': 5,
            'moonshot_balance': 6,
            'siliconflow_balance': 7,
            'toutiao_hot': 8,
            'weibo_hot': 9,
            'exchange_rates': 10,
            'douban_movies': 11,
            'rawg_games': 12
        }
        
        results_dict = {}
        for key, index in result_mapping.items():
            result = raw_results[index]
            if isinstance(result, Exception):
                logger.error(f"数据获取任务 {key} 失败: {result}")
                # 根据任务类型返回默认值
                if key in ['news_60s']:
                    results_dict[key] = {"news": ["获取失败 - 网络错误"]}
                elif key in ['ithome_news', 'dram_price', 'bangumi_today', 'toutiao_hot', 'weibo_hot', 'douban_movies', 'rawg_games']:
                    if key == 'dram_price':
                        results_dict[key] = []  # dram_price 返回的是字典列表
                    else:
                        results_dict[key] = []
                elif key == 'exchange_rates':
                    results_dict[key] = {"error": "API请求失败"}
                else:  # 余额数据
                    results_dict[key] = {"error": "API请求失败"}
            else:
                results_dict[key] = result
                
        return results_dict

    async def broadcast_report(self):
        """定时任务入口"""
        logger.info("棒棒糖的每日晨报：开始每日晨报定时任务...")
        try:
            html_content = await self.generate_html()
            logger.info(f"棒棒糖的每日晨报：HTML 生成完成，路径地址: {html_content}")
            message_chain = MessageChain([Image.fromURL(html_content)])
            # 发送到配置的群
            for group_id in self.target_groups:
                logger.info(f"棒棒糖的每日晨报：向群组 {group_id} 发送图片")
                await self.context.send_message(group_id, message_chain)
                await asyncio.sleep(2)  # 防风控延迟

            logger.info("棒棒糖的每日晨报：每日报告广播完成。")

        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：广播失败: {e}", exc_info=True)

    async def _url_to_base64(self, session, url: str, referer: str = "", width: int = 0) -> str:
        """辅助方法：下载图片并转为 Base64 (支持本地缩放)"""
        if not url:
            return ""

        headers = {
            "User-Agent": user_agent
        }
        if referer:
            headers["Referer"] = referer

        try:
            async with self.semaphore:  # 限制并发
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        mime_type = resp.headers.get("Content-Type", "image/jpeg")

                        # --- 图片缩放逻辑 Start ---
                        if width > 0:
                            try:
                                # 将CPU密集型的PIL操作放到线程池中执行，避免阻塞事件循环
                                content = await asyncio.to_thread(
                                    self._resize_image_sync, 
                                    content, 
                                    width
                                )
                                mime_type = "image/jpeg"  # 缩放后统一转为 JPEG
                            except Exception as e:
                                logger.warning(f"棒棒糖的每日晨报：图片缩放失败 {url}: {e}")
                                # 缩放失败则使用原图，不中断流程
                        # --- 图片缩放逻辑 End ---

                        b64_str = base64.b64encode(content).decode("utf-8")
                        return f"data:{mime_type};base64,{b64_str}"
                    else:
                        logger.warning(f"棒棒糖的每日晨报：下载图片失败 {url}, 状态码: {resp.status}")
        except asyncio.TimeoutError:
            logger.warning(f"棒棒糖的每日晨报：图片下载超时 {url}")
        except aiohttp.ClientError as e:
            logger.warning(f"棒棒糖的每日晨报：图片下载网络错误 {url}: {e}")
        except Exception as e:
            logger.warning(f"棒棒糖的每日晨报：图片下载失败 {url}: {e}")

        return ""

    def _resize_image_sync(self, image_bytes: bytes, width: int) -> bytes:
        """同步的图片缩放操作，将在线程池中执行"""
        # 1. 打开图片
        img = PILImage.open(io.BytesIO(image_bytes))

        # 2. 计算缩放高度 (保持比例)
        w_percent = (width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))

        # 3. 执行缩放 (LANCZOS 滤镜质量最高)
        img = img.resize((width, h_size), PILImage.Resampling.LANCZOS)

        # 4. 保存回 bytes
        buffer = io.BytesIO()
        # 转换模式以适配 JPEG (如果是 PNG 带透明通道需转 RGB)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        img.save(buffer, format="JPEG", quality=95)  # 压缩质量 95
        return buffer.getvalue()
    
    # 重构API余额查询方法为通用方法
    async def _fetch_api_balance(self, session, api_name: str, api_url: str, headers: dict, parse_func) -> Dict:
        """通用API余额查询方法"""
        if not headers.get("Authorization"):
            return {"name": api_name, "error": "未配置Key"}
            
        try:
            async with self.semaphore:  # 限制并发
                async with session.get(api_url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return parse_func(data)
                    elif resp.status == 401:
                        logger.warning(f"棒棒糖的每日晨报：{api_name} API认证失败，可能是API密钥无效")
                        return {"name": api_name, "status": "API认证失败 (401)", "balance": "0.00"}
                    elif resp.status == 429:
                        logger.warning(f"棒棒糖的每日晨报：{api_name} API请求频率超限")
                        return {"name": api_name, "status": "请求频率超限 (429)", "balance": "0.00"}
                    else:
                        logger.error(f"棒棒糖的每日晨报：{api_name} API请求失败，状态码: {resp.status}")
                        return {"name": api_name, "status": f"API请求失败 (状态码: {resp.status})", "balance": "0.00"}
        except asyncio.TimeoutError:
            logger.error(f"棒棒糖的每日晨报：获取{api_name}余额超时")
            return {"name": api_name, "status": "API请求超时", "balance": "0.00"}
        except aiohttp.ClientError as e:
            logger.error(f"棒棒糖的每日晨报：获取{api_name}余额网络错误: {e}")
            return {"name": api_name, "status": "网络错误", "balance": "0.00"}
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：获取{api_name}余额失败: {e}")
            return {"name": api_name, "status": "API请求失败", "balance": "0.00"}

    # 也可以添加一个手动指令用于测试
    @filter.command("看看日报")
    async def manual_report(self, event: AstrMessageEvent):
        try:
            # 生成HTML图片
            html = await self.generate_html()
            logger.info("棒棒糖的每日晨报：手动报告生成成功")
            yield event.image_result(html)
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：手动报告生成失败: {e}", exc_info=True)
            yield event.plain_result(f"生成报告失败: {str(e)}")

    @filter.command("清除日报缓存")
    async def clear_cache_command(self, event: AstrMessageEvent):
        """允许用户强制清除缓存"""
        self.cache.clear()
        logger.info("棒棒糖的每日晨报：缓存已被手动清除")
        yield event.plain_result("日报缓存已清除，下次查询将获取最新数据。")

    @filter.llm_tool(name="clear_daily_report_cache")
    async def tool_clear_cache(self, event: AstrMessageEvent):
        '''
        清理日报缓存


        '''
        self.cache.clear()
        logger.info("棒棒糖的每日晨报：缓存已被手动清除")
        return "日报缓存已清除，下次查询将获取最新数据。"


    @filter.llm_tool(name="today_news")
    async def report_today_news(self, event: AstrMessageEvent):
        """
        发送今天的早报，看看今天发生了什么。


        """
        try:
            html = await self.generate_html()
            logger.info("棒棒糖的每日晨报：LLM工具报告生成成功")
            yield event.image_result(html)
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：LLM工具报告生成失败: {e}", exc_info=True)
            yield event.plain_result(f"生成报告失败: {str(e)}")

    async def terminate(self):
        logger.info("棒棒糖的每日晨报：开始卸载...")
        if self.scheduler.running:
            self.scheduler.remove_all_jobs()
            self.scheduler.shutdown(wait=False)
        logger.info("棒棒糖的每日晨报：定时任务已清理")
        logger.info("棒棒糖的每日晨报：完成卸载...")