from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem


class DeduplicationPipeline:
    """Drops duplicate RTI records within a crawl run based on their UUID."""

    def __init__(self):
        self.seen_ids = set()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        record_id = adapter.get("id")

        if not record_id:
            spider.logger.warning("Dropping item without an ID.")
            raise DropItem("Item missing ID")

        if record_id in self.seen_ids:
            spider.logger.debug(f"Dropping duplicate item: {record_id}")
            raise DropItem(f"Duplicate item found: {record_id}")

        self.seen_ids.add(record_id)
        return item


class DataCleaningPipeline:
    """Cleans, normalizes, and strips whitespace from text and list fields."""

    STRING_FIELDS = [
        "title",
        "department",
        "ministry",
        "state",
        "district",
        "area",
        "subject",
        "response_summary",
        "response_status",
        "response_full_text",
        "extracted_text",
        "date_filed",
        "date_of_response",
        "language",
        "filer_name",
        "filer_email",
        "file_url",
        "admin_pdf_url",
        "original_filename",
        "file_type",
    ]

    LIST_FIELDS = [
        "tags",
        "questions",
        "rti_act_sections",
        "response_tables",
    ]

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # 1. Clean String Fields
        for field in self.STRING_FIELDS:
            val = adapter.get(field)
            if isinstance(val, str):
                cleaned = val.strip()
                if cleaned in ("", "null", "None", "undefined"):
                    adapter[field] = None
                else:
                    adapter[field] = cleaned

        # 2. Clean List Fields
        for field in self.LIST_FIELDS:
            val = adapter.get(field)
            if isinstance(val, list):
                cleaned_list = []
                seen = set()
                for element in val:
                    if isinstance(element, str):
                        s = element.strip()
                        if s and s not in seen:
                            cleaned_list.append(s)
                            seen.add(s)
                    elif element is not None:
                        cleaned_list.append(element)
                adapter[field] = cleaned_list
            elif val is None:
                adapter[field] = []

        # 3. Normalize Status
        status = adapter.get("response_status")
        if status and isinstance(status, str):
            adapter["response_status"] = status.lower().strip()

        return item
