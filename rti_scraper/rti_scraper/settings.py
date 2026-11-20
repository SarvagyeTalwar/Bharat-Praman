# Scrapy settings for rti_scraper project

BOT_NAME = "rti_scraper"

SPIDER_MODULES = ["rti_scraper.spiders"]
NEWSPIDER_MODULE = "rti_scraper.spiders"

# Realistic User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Default request headers
DEFAULT_REQUEST_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
}

# Concurrency & polite throttling
CONCURRENT_REQUESTS = 4
DOWNLOAD_DELAY = 1.5
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# Cookies disabled
COOKIES_ENABLED = False

# Downloader Middlewares
DOWNLOADER_MIDDLEWARES = {
    "rti_scraper.middlewares.RtiRateLimitMiddleware": 540,
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": 550,
}

# Retry Configuration
RETRY_ENABLED = True
RETRY_TIMES = 5
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]

# Pipelines
ITEM_PIPELINES = {
    "rti_scraper.pipelines.DeduplicationPipeline": 300,
    "rti_scraper.pipelines.DataCleaningPipeline": 400,
}

# AutoThrottle (Adapts dynamically to server latency)
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 15.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.5
AUTOTHROTTLE_DEBUG = False

# Feed exports
FEED_EXPORT_ENCODING = "utf-8"
FEED_EXPORT_INDENT = 2
