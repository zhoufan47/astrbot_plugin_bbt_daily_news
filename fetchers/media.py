"""媒体数据抓取：今日番剧、豆瓣近期上映电影、RAWG游戏发售"""

import asyncio
import datetime
import re
from typing import Dict, List

import aiohttp
from bs4 import BeautifulSoup

from astrbot.api import logger

from ..constants import USER_AGENT, BANGUMI_CALENDAR_URL, DOUBAN_MOVIE_URL
from ..config import PluginConfig
from ..utils import url_to_base64


async def fetch_bangumi_today(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> List[Dict]:
    """抓取今日番剧"""
    if not config.animation_mode:
        return []

    headers = {
        "User-Agent": USER_AGENT
    }
    anime_list = []
    weekday_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
    today_key = weekday_map[datetime.datetime.today().weekday()]

    try:
        async with semaphore:  # 限制并发
            async with session.get(BANGUMI_CALENDAR_URL, headers=headers) as resp:
                text = await resp.text()
                soup = BeautifulSoup(text, 'lxml')

                # 策略：直接利用 class 名定位当天的数据
                day_section = soup.find("dd", class_=today_key)

                if day_section:
                    items = day_section.find_all("li")

                    for item in items:
                        data = {"title": "未知", "cover": ""}

                        # 1. 获取标题
                        link_tag = item.find("a")
                        if link_tag:
                            title = link_tag.get_text(strip=True)
                            if not title:
                                continue
                            data["title"] = title

                        style_attr = item.get('style', '')
                        # 2. 获取图片 (双重策略)
                        url_match = re.search(r"url\('?(.*?)'?\)", style_attr)

                        img_url = "https://bgm.tv/img/no_icon_subject.png"
                        if url_match:
                            raw_url = url_match.group(1)
                            img_url = "https://" + raw_url.lstrip('/')

                        data["cover"] = await url_to_base64(session,semaphore,img_url,referer=BANGUMI_CALENDAR_URL)
                        anime_list.append(data)

    except asyncio.TimeoutError:
        logger.error("棒棒糖的每日晨报：获取今日番剧超时")
    except aiohttp.ClientError as e:
        logger.error(f"棒棒糖的每日晨报：获取今日番剧网络错误: {e}")
    except Exception as e:
        logger.error(f"棒棒糖的每日晨报：抓取今日番剧失败: {e}")

    return anime_list


async def fetch_douban_movies(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> List[Dict]:
    """获取豆瓣近期上映电影 (转 Base64 版)"""
    if not config.movie_mode:
        return []

    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://movie.douban.com/",
    }

    movie_list = []
    try:
        async with semaphore:  # 限制并发
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

                            # 2. 封面处理
                            img_tag = item.find("a", class_="thumb").find("img")
                            raw_cover_url = ""
                            if img_tag:
                                raw_cover_url = img_tag.get("src", "")

                            # 下载并转 Base64
                            if raw_cover_url:
                                movie["cover"] = await url_to_base64(
                                    session,
                                    semaphore,
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


async def fetch_rawg_games(session, semaphore: asyncio.Semaphore, config: PluginConfig) -> List[Dict]:
    """获取RAWG游戏发售数据"""
    if not config.rawg_key:
        return []

    # 计算日期范围：未来 N 天
    today = datetime.date.today()
    future = today + datetime.timedelta(days=config.game_release_date_threshold)
    dates_str = f"{today},{future}"

    # stores=1(Steam), 3(PlayStation Store), 6(Nintendo Store)
    url = f"https://api.rawg.io/api/games?key={config.rawg_key}&dates={dates_str}&stores=1,3,6&ordering=released&page_size=9"

    games_list = []
    try:
        async with semaphore:  # 限制并发
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
                            game["cover"] = await url_to_base64(session, semaphore, raw_bg, width=512)
                        else:
                            game["cover"] = ""

                        # 3. 平台信息
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
