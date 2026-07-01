"""工具函数：图片处理、番号解析、封面URL获取等"""

import asyncio
import base64
import io

from PIL import Image as PILImage

from astrbot.api import logger

from .constants import USER_AGENT


def parse_javid(content_id: str) -> str:
    """从 content.id 提取番号，如 ofje00512 -> ofje-512"""
    return content_id.replace("00", "-", 1)


def get_cover_url(package_image: dict) -> str:
    """获取封面图 URL，优先 largeUrl"""
    if package_image and package_image.get("largeUrl"):
        return package_image["largeUrl"]
    if package_image and package_image.get("mediumUrl"):
        return package_image["mediumUrl"]
    return ""


def resize_image_sync(image_bytes: bytes, width: int) -> bytes:
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


async def url_to_base64(session, semaphore: asyncio.Semaphore, url: str, referer: str = "", width: int = 0) -> str:
    """下载图片并转为 Base64 (支持本地缩放)"""
    if not url:
        return ""

    headers = {
        "User-Agent": USER_AGENT
    }
    if referer:
        headers["Referer"] = referer

    try:
        async with semaphore:  # 限制并发
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    mime_type = resp.headers.get("Content-Type", "image/jpeg")

                    # --- 图片缩放逻辑 Start ---
                    if width > 0:
                        try:
                            # 将CPU密集型的PIL操作放到线程池中执行，避免阻塞事件循环
                            content = await asyncio.to_thread(
                                resize_image_sync,
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
    except Exception as e:
        logger.warning(f"棒棒糖的每日晨报：图片下载失败 {url}: {e}")

    return ""
