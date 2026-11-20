import time
import logging
from scrapy import signals
from scrapy.http import Response

logger = logging.getLogger(__name__)


class RtiRateLimitMiddleware:
    """Downloader middleware to handle Vercel / API rate limits automatically.

    Inspects `ratelimit-remaining`, `ratelimit-reset`, and HTTP 429 responses.
    Automatically sleeps and reschedules requests when the rate limit window is hit.
    """

    def process_response(self, request, response, spider):
        # Handle 429 Too Many Requests
        if response.status == 429:
            reset_header = response.headers.get(b"ratelimit-reset") or response.headers.get(b"Retry-After")
            try:
                wait_seconds = int(reset_header.decode("utf-8")) if reset_header else 60
            except (ValueError, AttributeError):
                wait_seconds = 60

            # Add buffer
            wait_seconds = max(wait_seconds, 5) + 2
            spider.logger.warning(
                f"[RateLimit] 429 Too Many Requests on {request.url}. "
                f"Backing off for {wait_seconds}s before retry..."
            )
            time.sleep(wait_seconds)

            # Re-queue the exact request
            retry_req = request.copy()
            retry_req.dont_filter = True
            retry_req.priority = request.priority + 10
            return retry_req

        # Proactive throttle warning when quota is almost depleted
        remaining = response.headers.get(b"ratelimit-remaining")
        if remaining:
            try:
                rem_val = int(remaining.decode("utf-8"))
                if rem_val <= 2:
                    reset_header = response.headers.get(b"ratelimit-reset")
                    wait_sec = int(reset_header.decode("utf-8")) if reset_header else 10
                    spider.logger.warning(
                        f"[RateLimit] Quota almost exhausted ({rem_val} remaining). "
                        f"Proactively pacing for {wait_sec}s..."
                    )
                    time.sleep(wait_sec)
            except (ValueError, AttributeError):
                pass

        return response


class RtiScraperSpiderMiddleware:
    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        return None

    def process_spider_output(self, response, result, spider):
        for i in result:
            yield i

    def spider_opened(self, spider):
        spider.logger.info(f"Spider opened: {spider.name}")


class RtiScraperDownloaderMiddleware:
    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def spider_opened(self, spider):
        spider.logger.info(f"Downloader opened: {spider.name}")
