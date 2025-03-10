from itemadapter import ItemAdapter
import re
import pymongo
from scrapy.exceptions import DropItem
import os

class PhonescraperPipeline:
    def __init__(self):
        self.seen_names = set()  # To track unique phone names

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Remove phones missing any required fields
        required_fields = ["name", "price", "specifications"]
        for field in required_fields:
            if not adapter.get(field):  # Skip if any required field is missing
                raise DropItem(f"Missing required field: {field} in {item}")

        # Clean and format the name field (remove color and storage details for iPhones)
        name = adapter.get("name")
        if name:
            if "iPhone" in name:
                # Remove storage and color details from the name
                name = re.sub(r"\d+GB\s*", "", name)  # Remove storage (e.g., 128GB)
                name = re.sub(r"\s*(Black|Blue|Natural Titanium|Red|Green|etc\.?)\s*", "", name, flags=re.IGNORECASE)  # Remove colors
                name = name.strip()
            else:
                # For non-iPhones, just remove bracketed parts
                name = re.sub(r"\s*\(.*?\)", "", name).strip()
            adapter["name"] = name

            # Check if this name has already been seen
            if name in self.seen_names:
                raise DropItem(f"Duplicate phone name found: {name}, ignoring.")
            else:
                self.seen_names.add(name)  # Add new name to the set

        # Check that all required specifications are present
        required_specs = [
            'Battery', 'Primary Camera', 'Secondary Camera',
            'Processor', 'Operating System', 'RAM', 'Storage'
        ]
        
        specs = adapter.get("specifications")
        if specs:
            # Ensure all required specification keys are present
            if not all(key in specs for key in required_specs):
                raise DropItem(f"Missing one or more required specifications in {item}")
            
            # Clean and format specifications
            cleaned_specs = {}
            for key, value in specs.items():
                key = key.strip()
                value = value.strip()

                # Remove unwanted characters and symbols
                value = re.sub(r'\[u\+200e\]', '', value)  # Remove invisible characters
                value = re.sub(r'[^\x00-\x7F]+', '', value)  # Remove non-ASCII characters
                
                # Exclude camera features beyond the main information
                if key == 'Primary Camera' or key == 'Secondary Camera':
                    value = re.sub(r'Features?.*', '', value).strip()

                # Simplify processor name if it starts with "Snapdragon"
                if key == 'Processor' and value.startswith("Snapdragon"):
                    value = "Snapdragon"

                if key in required_specs:
                    cleaned_specs[key] = value
            
            # Explicitly set RAM to 4GB for iPhones
            if "iPhone" in name and 'RAM' in cleaned_specs:
                cleaned_specs['RAM'] = "4 GB"

            adapter["specifications"] = cleaned_specs
        else:
            raise DropItem(f"Missing specifications in {item}")

        # Format price field (keep only digits)
        price = adapter.get("price")
        if price:
            price = re.sub(r"[^\d]", "", price)  # Keep only digits
            adapter["price"] = price
        
        # Clean image URL field (remove trailing spaces)
        image = adapter.get("image")
        if image:
            adapter["image"] = image.strip()

        return item


class MongoPipeline:
    def __init__(self):
        # Get MongoDB URI from environment variable
        self.mongo_uri = os.getenv("MONGO_URI")
        self.mongo_db = "scraping"  # Database name
        self.collection_name = "phonescraper"  # Collection name

    def open_spider(self, spider):
        """Open MongoDB Atlas connection and clear existing data"""
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]
        self.collection = self.db[self.collection_name]

        # Delete all existing records before inserting new ones
        self.collection.delete_many({})
        spider.logger.info("Cleared existing data in MongoDB Atlas.")

    def close_spider(self, spider):
        """Close MongoDB connection"""
        self.client.close()

    def process_item(self, item, spider):
        """Insert the scraped item into MongoDB Atlas"""
        self.collection.insert_one(dict(item))  # Directly insert the cleaned item
        spider.logger.info(f"Inserted item: {item['name']}")
        return item
