from itemadapter import ItemAdapter
import re
import pymongo
from scrapy.exceptions import DropItem
import os
import requests

class PhonescraperPipeline:
    def __init__(self):
        self.seen_names = set()  # To track unique phone names
        self.youtube_api_keys = [
            'AIzaSyDpqT3epjFtgUhvIRghtPJRvXWrIspKRQA',
            'AIzaSyBDnBtqnhOaqhctrl3ACti2hU4Ys1OdXDM',
            'AIzaSyD3CN6fVVskaduf8lfLgn-jLH2D0qWApfo' 
        ]
        self.current_api_key_index = 0  # Start with the first API key

    def fetch_top_video(self, phone_name, channel_id=None):
        """Fetch the top video for a given phone name from YouTube."""
        url = 'https://www.googleapis.com/youtube/v3/search'
        params = {
            'part': 'snippet',
            'q': f'"{phone_name} review unboxing"',
            'type': 'video',
            'order': 'relevance',
            'key': self.youtube_api_keys[self.current_api_key_index],  # Use current API key
            'videoDuration': 'medium',
            'relevanceLanguage': 'en',
            'regionCode': 'US',
            'maxResults': 5
        }
        if channel_id:
            params['channelId'] = channel_id

        response = requests.get(url, params=params)
        return response

    def process_response(self, response, phone_name):
        """Process the YouTube API response to find the most relevant video."""
        if response.status_code != 200:
            # If the API key quota is exhausted, switch to the next key
            if response.status_code == 403 and "quotaExceeded" in response.text:
                self.current_api_key_index = (self.current_api_key_index + 1) % len(self.youtube_api_keys)
                return None
            return None

        data = response.json()
        if not data.get('items'):
            return None

        phone_name_lower = phone_name.lower()
        for item in data['items']:
            title_lower = item['snippet']['title'].lower()

            if f" {phone_name_lower} " in f" {title_lower} ":
                return f'https://www.youtube.com/watch?v={item["id"]["videoId"]}'

        return None

    def get_youtube_link(self, phone_name):
        """Get the top YouTube video link for a given phone name."""
        video_url = None

        # Preferred YouTube channels for reviews
        preferred_channels = {
            "MKBHD": "UCBJycsmduvYEL83R_U4JriQ",
            "MrWhoseTheBoss": "UCMiJRAwDNSNzuYeN2uWa0pA",
            "Unbox Therapy": "UCsTcErHg8oDvUnTzoqsYeNw",
            "Dave2D": "UCVYamHliCI9rw1tHR1xbkfw",
            "Linus Tech Tips": "UCXuqSBlHAE6Xw-yeJA0Tunw"
        }

        for channel_id in preferred_channels.values():
            response = self.fetch_top_video(phone_name, channel_id)
            video_url = self.process_response(response, phone_name)
            if video_url:
                break

        if not video_url:
            response = self.fetch_top_video(phone_name)
            video_url = self.process_response(response, phone_name)

        return video_url

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Remove phones missing any required fields
        required_fields = ["name", "price", "specifications", "product_url"]
        for field in required_fields:
            if not adapter.get(field):  # Skip if any required field is missing
                raise DropItem(f"Missing required field: {field} in {item}")

        # Clean and format the name field
        name = adapter.get("name")
        if name:
            # Remove common additional descriptors like "With Charger"
            name = re.sub(r"\s*With\s+Charger\s*", "", name, flags=re.IGNORECASE)
            name = re.sub(r"\s*\(.*?\)", "", name)  # Remove brackets and their contents
            name = re.sub(r"\s*\[.*?\]", "", name)  # Remove square brackets and their contents
            name = name.strip()

            # For iPhones, remove storage and color details
            if "iPhone" in name:
                name = re.sub(r"\d+GB\s*", "", name)  # Remove storage (e.g., 128GB)
                name = re.sub(r"\s*(Black|Blue|Natural Titanium|Red|Green|etc\.?)\s*", "", name, flags=re.IGNORECASE)  # Remove colors

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

        # Fetch and add YouTube video link as a key-value pair
        youtube_link = self.get_youtube_link(name)
        adapter["youtube_link"] = youtube_link if youtube_link else "No relevant videos found."

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