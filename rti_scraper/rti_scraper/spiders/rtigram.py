import json
import urllib.parse
import scrapy
from rti_scraper.items import RtiItem


class RtigramSpider(scrapy.Spider):
    """Spider for crawling RTI data from RTIgram.

    Features:
    - Configurable search query, mode, start page, and max pages via `-a` flags.
    - Automatic page limit detection from API metadata.
    - Optional full-text enrichment (`enrich=true`) fetching complete response texts,
      questions, OCR transcriptions, and PDF document links from the Supabase backend.
    - Deduplication and data normalization via item pipelines.
    - Built-in rate limiting resilience via RtiRateLimitMiddleware.
    """

    name = "rtigram"
    allowed_domains = ["rtigram.com", "supabase.co"]

    SUPABASE_ANON_KEY = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InV4bHFmY214bXVzdWJzdXp5ZnhrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU0OTcwMzEsImV4cCI6MjA5MTA3MzAzMX0."
        "cECft9lXP8F7ySF7pN3GQugZ5Zni0s8x0zc9lscNh0o"
    )

    def __init__(
        self,
        query: str = "RTI",
        mode: str = "keyword",
        start_page: str = "1",
        max_pages: str = "0",
        enrich: str = "true",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.query = str(query).strip()
        self.mode = str(mode).strip()
        self.start_page = max(1, int(start_page))
        self.max_pages = max(0, int(max_pages))
        self.enrich = str(enrich).lower() in ("true", "1", "yes")

    async def start(self):
        for req in self.start_requests():
            yield req

    def start_requests(self):
        params = {
            "q": self.query,
            "mode": self.mode,
            "page": self.start_page,
        }
        url = f"https://rtigram.com/api/search?{urllib.parse.urlencode(params)}"
        self.logger.info(
            f"Starting RTIgram crawl: query='{self.query}', mode='{self.mode}', "
            f"start_page={self.start_page}, max_pages={self.max_pages or 'all'}, "
            f"enrich={self.enrich}"
        )
        yield scrapy.Request(
            url=url,
            callback=self.parse,
            meta={"page": self.start_page},
        )

    def parse(self, response):
        try:
            data = response.json()
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse JSON response from {response.url}")
            return

        current_page = data.get("page", response.meta.get("page", self.start_page))
        total_pages = data.get("total_pages", 1)
        total_records = data.get("total", "unknown")
        results = data.get("results", [])

        self.logger.info(
            f"[Page {current_page}/{total_pages}] Found {len(results)} items (Total database matches: {total_records})"
        )

        # Process each result on the current page
        for record in results:
            record_id = record.get("id")
            if not record_id:
                continue

            if self.enrich:
                # Fetch full details (questions, response text, OCR, PDF link)
                detail_url = f"https://uxlqfcmxmusubsuzyfxk.supabase.co/rest/v1/rti_entries?id=eq.{record_id}&select=*"
                headers = {
                    "apikey": self.SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {self.SUPABASE_ANON_KEY}",
                }
                yield scrapy.Request(
                    url=detail_url,
                    headers=headers,
                    callback=self.parse_details,
                    meta={"card_record": record},
                )
            else:
                yield self._build_item(record)

        # Calculate target last page
        target_last_page = total_pages
        if self.max_pages > 0:
            target_last_page = min(total_pages, self.start_page + self.max_pages - 1)

        # Pagination: yield request for next page
        if current_page < target_last_page:
            next_page = current_page + 1
            params = {
                "q": self.query,
                "mode": self.mode,
                "page": next_page,
            }
            next_url = f"https://rtigram.com/api/search?{urllib.parse.urlencode(params)}"
            yield scrapy.Request(
                url=next_url,
                callback=self.parse,
                meta={"page": next_page},
            )

    def parse_details(self, response):
        """Parse enriched detail data from PostgREST and yield complete item."""
        card_record = response.meta.get("card_record", {})
        try:
            details_list = response.json()
            full_record = details_list[0] if (isinstance(details_list, list) and details_list) else {}
        except (json.JSONDecodeError, IndexError, KeyError):
            full_record = {}

        # Merge detail record onto card record
        merged = dict(card_record)
        merged.update({k: v for k, v in full_record.items() if v is not None})

        yield self._build_item(merged)

    def _build_item(self, data: dict) -> RtiItem:
        """Helper to instantiate an RtiItem from dictionary data."""
        item = RtiItem()
        for field in item.fields:
            item[field] = data.get(field)
        return item
