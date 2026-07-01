"""缓存条目数据类"""

import datetime
from dataclasses import dataclass
from datetime import timedelta
from typing import Any


@dataclass
class CacheEntry:
    """缓存条目"""
    data: Any
    timestamp: datetime.datetime

    def is_expired(self, ttl_minutes: int = 10) -> bool:
        """检查缓存是否过期"""
        return datetime.datetime.now() > self.timestamp + timedelta(minutes=ttl_minutes)
