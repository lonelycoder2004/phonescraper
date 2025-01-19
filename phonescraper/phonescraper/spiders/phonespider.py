import scrapy
from phonescraper.items import PhonescraperItem

class PhonespiderSpider(scrapy.Spider):
    name = "phonespider"
    allowed_domains = ["www.bigcmobiles.com"]
    start_urls = ["https://www.bigcmobiles.com/mobiles"]

    def parse(self, response):
        phones = response.css('li.product-item')

        # Scrape phones on the current page
        for phone in phones:
            relative_url = phone.css("a.product-item-link::attr(href)").get()
            if relative_url:  # Check if the URL exists
                # Pass the current page URL (listing page) in meta to return later
                yield response.follow(relative_url, callback=self.parse_phone)

        # Pagination: Get the "Next" page URL and follow it if it exists
        next_page = response.css('a.action.next ::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def parse_phone(self, response):
        # Extracting the product name and price
        name = response.css("span.base::text").get()
        price = response.css("span.price::text").get()
        image = response.css("div.gallery-placeholder img::attr(src)").get()
        
        # Extracting specifications from the additional attributes table
        specs = {}
        rows = response.css("table#product-attribute-specs-table tbody tr")
        
        # Loop through rows and extract the name-value pairs for all specifications
        for row in rows:
            spec_name = row.css("th::text").get().strip()
            spec_value = row.css("td::text").get().strip()
            
            # Store specification only if both name and value are found
            if spec_name and spec_value:
                specs[spec_name] = spec_value
        
        # Initialize item to return
        phone_item = PhonescraperItem()
        
        # Assign the extracted data to the item
        phone_item["name"] = name
        phone_item["price"] = price
        phone_item["image"] = image
        phone_item["specifications"] = specs  # Store all specifications
        
        # Yield the phone item with all specifications
        yield phone_item
