"""全局常量定义：URL、Headers、GraphQL查询等"""

# 通用 User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# DMM GraphQL 请求头
DMM_HEADERS = {
    "accept": "application/graphql-response+json, application/graphql+json, application/json, text/event-stream, multipart/mixed",
    "accept-language": "zh-CN",
    "content-type": "application/json",
    "fanza-device": "BROWSER",
    "origin": "https://video.dmm.co.jp",
    "referer": "https://video.dmm.co.jp/av/ranking/",
    "sec-ch-ua": '"Microsoft Edge";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# GraphQL 排名查询
RANKING_QUERY = """
query ContentRankingPage($limit: Int!, $offset: Int!, $filter: PPVContentRankingFilterInput, $isAmateur: Boolean = false) {
  ppvContentRanking(limit: $limit, offset: $offset, filter: $filter) {
    items {
      id
      rank
      content {
        title
        releaseStatus
        packageImage {
          mediumUrl
          largeUrl
          __typename
        }
        wishlistCount
        isExclusiveDelivery
        actresses @skip(if: $isAmateur) {
          id
          name
          __typename
        }
        sampleImages {
          number
          largeImageUrl
          __typename
        }
        hasSampleMovie
        review {
          average
          total
          __typename
        }
        __typename
      }
      __typename
    }
    ... on PPVContentTrendingRanking {
      targetWindowEndAt
      __typename
    }
    __typename
  }
}
"""

# API 配置常量
NEWS_API_URL = "https://60s-api.viki.moe/v2/60s"
ITHOME_RANK_URL = "https://www.ithome.com/block/rank.html"
DRAM_PRICE_URL = "https://www.dramx.com/Price/DSD.html"
BANGUMI_CALENDAR_URL = "https://bgm.tv/calendar"
DOUBAN_MOVIE_URL = "https://movie.douban.com/cinema/later/beijing/"
DMM_RANKING_URL = "https://api.video.dmm.co.jp/graphql"

# DMM 排名术语过滤映射
TERM_FILTER_MAP = {
    "daily": {"daily": {"floor": "AV"}},
    "weekly": {"weekly": {"floor": "AV"}},
    "monthly": {"monthly": {"floor": "AV"}},
}

# 模板文件映射
TEMPLATE_FILES = {
    "main": "report.html",
    "animation": "report_animation.html",
    "movie": "report_movie.html",
    "dmm": "report_dmm.html",
}
