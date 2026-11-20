import scrapy


class RtiItem(scrapy.Item):
    """Data model representing a Right to Information (RTI) entry."""

    id = scrapy.Field()
    title = scrapy.Field()
    department = scrapy.Field()
    ministry = scrapy.Field()
    state = scrapy.Field()
    district = scrapy.Field()
    area = scrapy.Field()
    subject = scrapy.Field()
    questions = scrapy.Field()
    response_summary = scrapy.Field()
    response_status = scrapy.Field()
    response_full_text = scrapy.Field()
    extracted_text = scrapy.Field()
    response_tables = scrapy.Field()
    date_filed = scrapy.Field()
    date_of_response = scrapy.Field()
    rti_act_sections = scrapy.Field()
    tags = scrapy.Field()
    language = scrapy.Field()
    filer_name = scrapy.Field()
    filer_email = scrapy.Field()
    is_anonymous = scrapy.Field()
    upvotes = scrapy.Field()
    view_count = scrapy.Field()
    file_url = scrapy.Field()
    admin_pdf_url = scrapy.Field()
    original_filename = scrapy.Field()
    file_type = scrapy.Field()
    created_at = scrapy.Field()


# Keep backward compatibility with default Scrapy name
RtiScraperItem = RtiItem
