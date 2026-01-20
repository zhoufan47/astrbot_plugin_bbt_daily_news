import asyncio
import datetime
import os
from typing import Dict, List, Any
import re
import traceback
import io

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

@register("daily_report", "棒棒糖", "每日综合简报插件", "1.5.0")
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
        url = "https://60s-api.viki.moe/v2/60s"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # 返回新闻列表，通常在 data['data'] 里
                    return {"news": data.get("data", {"news:":[]}).get("news", [])}
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：抓取60秒新闻失败: {e}")
        return {"news": ["获取失败"]}

    async def fetch_ithome_news(self, session) -> List[str]:
        """抓取IT之家热榜"""
        url = "https://www.ithome.com/block/rank.html"
        headers = {
            "User-Agent": user_agent
        }
        news_list = []
        try:
            async with session.get(url, headers=headers) as resp:
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

        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：抓取IT之家热榜失败: {e}")
            news_list.append("抓取失败")

        # 返回前 10 条，避免太长
        return news_list[:10]

    async def fetch_dram_price(self, session) -> List[Dict]:
        """抓取DRAM价格 """
        url = "https://www.dramx.com/Price/DSD.html"
        headers = {
            "User-Agent": user_agent
        }
        data = []
        try:
            async with session.get(url, headers=headers) as resp:
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

        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：抓取DRAM价格失败: {e}")
        return data

    async def fetch_bangumi_today(self, session) -> List[Dict]:
        """ 抓取今日番剧 (基于用户提供的层级优化)"""
        url = "https://bgm.tv/calendar"
        headers = {
            "User-Agent": user_agent
        }
        anime_list = []
        # Bangumi 页面使用英文简写作为 class 名
        weekday_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
        today_key = weekday_map[datetime.datetime.today().weekday()]

        try:
            async with session.get(url, headers=headers) as resp:
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

        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：抓取今日番剧失败: {e}")

        return anime_list

    async def fetch_douban_movies(self, session) -> List[Dict]:
        """12. 获取豆瓣近期上映电影 (转 Base64 版)"""
        url = "https://movie.douban.com/cinema/later/beijing/"
        # 豆瓣对 Referer 检查非常严格
        headers = {
            "User-Agent": user_agent,
            "Referer": "https://movie.douban.com/",
        }

        movie_list = []
        try:
            async with session.get(url, headers=headers) as resp:
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

        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：抓取豆瓣近期上映电影失败: {e}")

        return movie_list

    async def fetch_openrouter_credits(self, session) -> Dict:
        """ 获取OpenRouter余额"""
        if not self.openrouter_key:
            return {"error": "未配置Key"}

        url = "https://openrouter.ai/api/v1/auth/key"
        headers = {"Authorization": f"Bearer {self.openrouter_key}"}

        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # data format: {'data': {'label': '...', 'usage': 1.23, 'limit': 100, 'is_free_tier': False}}
                    info = data.get("data", {})
                    # OpenRouter通常返回 usage (已用) 和 limit (额度)，剩余需要计算或直接显示
                    usage = info.get("usage", 0)
                    limit_remaining = info.get("limit_remaining", 0)
                    usage_daily = info.get("usage_daily", 0)
                    # 注意：OpenRouter API返回结构可能变化，建议根据实际返回调试
                    return {
                        "usage_daily": f"${usage_daily:.4f}",
                        "usage": f"${usage:.4f}",
                        "limit_remaining": f"${limit_remaining:.4f}" if limit_remaining else "No Limit",
                    }
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：获取OpenRouter余额失败: {e}")
        return {"error": "API请求失败"}

    async def fetch_deepseek_balance(self, session) -> Dict:
        """ 获取 DeepSeek 余额"""
        if not self.deepseek_key:
            return {"name": "DeepSeek", "error": "未配置Key"}

        url = "https://api.deepseek.com/user/balance"
        headers = {"Authorization": f"Bearer {self.deepseek_key}"}

        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # DeepSeek 返回结构: {"is_available": true, "balance_infos": [{"currency": "CNY", "total_balance": "10.00"}]}
                    infos = data.get("balance_infos", [])
                    balance_str = "0.00"
                    currency = "CNY"

                    if infos:
                        # 通常取第一个货币单位，或根据 currency == "CNY" 筛选
                        item = infos[0]
                        balance_str = item.get("total_balance", "0.00")
                        currency = item.get("currency", "CNY")

                    return {
                        "name": "DeepSeek",
                        "balance": f"{balance_str} {currency}",
                        "status": "正常" if data.get("is_available") else "已停用"
                    }
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：获取DeepSeek余额失败: {e}")
        return {"name": "DeepSeek", "status": "API请求失败","balance":"0.00"}

    async def fetch_moonshot_balance(self, session) -> Dict:
        """9. 获取 Moonshot (Kimi) 余额"""
        if not self.moonshot_key:
            return {"name": "Moonshot", "error": "未配置Key"}

        url = "https://api.moonshot.cn/v1/users/me/balance"
        headers = {"Authorization": f"Bearer {self.moonshot_key}"}

        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Moonshot 返回结构: {"data": {"available_balance": 100.0, "cash_balance": 90.0, "voucher_balance": 10.0}}
                    info = data.get("data", {})
                    available = info.get("available_balance", 0)
                    return {
                        "name": "Moonshot",
                        "balance": f"¥{available:.2f}",
                        "status": "正常" if data.get("status") else "已停用"
                    }
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：获取Moonshot余额失败: {e}")
        return {"name": "Moonshot", "status": "API请求失败","balance":"¥0.00"}

    async def fetch_siliconflow_balance(self, session) -> Dict:
        """10. 获取 硅基流动 (SiliconFlow) 余额"""
        if not self.siliconflow_key:
            return {"name": "SiliconFlow", "error": "未配置Key"}

        url = "https://api.siliconflow.cn/v1/user/info"
        headers = {"Authorization": f"Bearer {self.siliconflow_key}"}

        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # SF 返回结构: {"data": {"id": "...", "name": "...", "image": "...", "balance": "14.05", ...}}
                    info = data.get("data", {})
                    balance = info.get("balance", "0")
                    return {
                        "name": "SiliconFlow",
                        "balance": f"¥{balance}",
                        "status": "Active"
                    }
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：获取SiliconFlow余额失败: {e}")
        return {"name": "SiliconFlow", "status": "API请求失败","balance":"¥0.00"}

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
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    info = data.get("data", [])
                    for item in info:
                        results.append(item["title"])
                    return results

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
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    info = data.get("data", [])
                    for item in info:
                        results.append(item["title"])
                    return results
        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：获取今日头条热榜失败: {e}")
        return []

    async def fetch_exchange_rates(self, session) -> Dict:
        """获取汇率 (基准 CNY)"""
        if not self.exchangerate_key:
            return {"error": "未配置Key"}

        url = f"https://v6.exchangerate-api.com/v6/{self.exchangerate_key}/latest/CNY"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    rates = data.get("conversion_rates", {})

                    # 只有 API 返回成功才处理
                    if data.get("result") == "success":
                        return {
                            "USD": f"{rates.get('USD', 0):.4f}",
                            "JPY": f"{rates.get('JPY', 0):.4f}",
                            "EUR": f"{rates.get('EUR', 0):.4f}",
                            "GBP": f"{rates.get('GBP', 0):.4f}",
                            "TWD": f"{rates.get('TWD', 0):.4f}",
                            "HKD": f"{rates.get('HKD', 0):.4f}"
                        }
                    else:
                        return {"error": "获取失败"}
                return {"error": "获取失败"}

        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：获取汇率失败: {e}")
            return {"error": "获取失败"}

    async def fetch_dmm_top(self, session) -> List[Dict]:
        if not self.r18_mode:
            return []
        url = "https://www.dmm.co.jp/digital/videoa/-/ranking/=/term=daily/"
        headers = {
            "User-Agent": user_agent
        }
        # 需要为cookies 设置 age_check_done=1，否则会返回年龄检查页面
        try:
            async with session.get(url, headers=headers,cookies={"age_check_done": "1"}) as resp:
                # 获取网页内容文本
                html_text = await resp.text()
                #解析 HTML
                soup = BeautifulSoup(html_text, 'html.parser')
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

        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：获取RAWG游戏数据失败: {e}")

        return games_list

    async def generate_html(self) -> Image:
        """聚合数据并渲染HTML"""
        # 创建一个异步会话（不走代理）
        async with aiohttp.ClientSession(trust_env=False) as session:
            # 并发执行所有抓取任务
            results = await asyncio.gather(
                self.fetch_60s_news(session),
                self.fetch_ithome_news(session),
                self.fetch_dram_price(session),
                self.fetch_bangumi_today(session),
                self.fetch_openrouter_credits(session),       # 4 openrouter余额查询
                self.fetch_deepseek_balance(session),         # 5 DS余额查询
                self.fetch_moonshot_balance(session),         # 6 Moonshot余额查询
                self.fetch_siliconflow_balance(session),      # 7 硅基流动余额查询
                self.fetch_toutiao_hot(session),                # 8 今日头条热榜
                self.fetch_weibo_hot(session),              # 9 微博热榜
                self.fetch_exchange_rates(session),         # 10 汇率数据
                self.fetch_douban_movies(session),          # 11 豆瓣电影
                self.fetch_rawg_games(session)
            )
        # 创建一个异步会话（走代理）
        async with aiohttp.ClientSession(trust_env=True,timeout=ClientTimeout(30)) as sessionProxy:
            # 并发执行所有抓取任务
            dmm_top_list = await asyncio.gather(
                self.fetch_dmm_top(sessionProxy),
            )
        # 整理 AI 余额数据列表
        ai_balances = {
            "OpenRouter": results[4],
            "DeepSeek": results[5],
            "MoonShot": results[6],
            "SiliconFlow": results[7],
        }
        show_adult = 0
        if self.r18_mode:
            show_adult = "1"
        # 整理常规数据
        context_data = {
            "r18_mode":show_adult,
            "date": datetime.datetime.now().strftime("%Y-%m-%d %A"),
            "news_60s": results[0].get("news", []),
            "news_ithome": results[1],
            "dram_prices": results[2],
            "bangumi_list": results[3],
            "ai_balances": ai_balances,
            "dmm_top_list": dmm_top_list[0],
            "toutiao_hot": results[8],
            "weibo_hot": results[9],
            "exchange_rates": results[10],
            "movie_list": results[11],
            "game_list": results[12]
        }
        logger.info(f"棒棒糖的每日晨报：渲染数据: {context_data}")
        options = {"quality": 99, "device_scale_factor_level": "ultra", "viewport_width": 505}
        img_result = await self.html_render(self.html_template, context_data, options=options)
        return img_result

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
                await self.context.send_message(group_id,message_chain)
                await asyncio.sleep(2)  # 防风控延迟

            logger.info("棒棒糖的每日晨报：每日报告广播完成。")

        except Exception as e:
            logger.error(f"棒棒糖的每日晨报：广播失败: {e}", exc_info=True)

    async def _url_to_base64(self, session, url: str, referer: str = "", width: int = 0) -> str:
        """辅助方法：下载图片并转为 Base64 (支持本地缩放)"""
        if not url:
            return ""

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if referer:
            headers["Referer"] = referer

        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    mime_type = resp.headers.get("Content-Type", "image/jpeg")

                    # --- 图片缩放逻辑 Start ---
                    if width > 0:
                        try:
                            # 理论上最好asyncio，不过就三四张图，懒得搞了
                            # 1. 打开图片
                            img = PILImage.open(io.BytesIO(content))

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

                            img.save(buffer, format="JPEG", quality=95)  # 压缩质量 85
                            content = buffer.getvalue()
                            mime_type = "image/jpeg"  # 缩放后统一转为 JPEG
                        except Exception as e:
                            logger.warning(f"I棒棒糖的每日晨报：图片缩放失败 {url}: {e}")
                            # 缩放失败则使用原图，不中断流程
                    # --- 图片缩放逻辑 End ---

                    b64_str = base64.b64encode(content).decode("utf-8")
                    return f"data:{mime_type};base64,{b64_str}"
        except Exception as e:
            logger.warning(f"棒棒糖的每日晨报：图片下载失败 {url}: {e}")

        return ""

    # 也可以添加一个手动指令用于测试
    @filter.command("看看日报")
    async def manual_report(self, event: AstrMessageEvent):
        # 生成HTML图片
        html = await self.generate_html()
        yield event.image_result(html)

    @filter.llm_tool(name="today_news")
    async def report_today_news(self, event: AstrMessageEvent):
        """
        发送今天的早报，看看今天发生了什么。


        """
        html = await self.generate_html()
        yield event.image_result(html)

    async def terminate(self):
        logger.info("棒棒糖的每日晨报：开始卸载...")
        self.scheduler.remove_all_jobs()
        self.scheduler.shutdown(wait=False)
        logger.info("棒棒糖的每日晨报：定时任务已清理")
        logger.info("棒棒糖的每日晨报：完成卸载...")