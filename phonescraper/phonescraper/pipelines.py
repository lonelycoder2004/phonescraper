from itemadapter import ItemAdapter
import re
from scrapy.exceptions import DropItem

class PhonescraperPipeline:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # Remove phones missing any required fields
        required_fields = ["name", "price", "specifications"]
        for field in required_fields:
            if not adapter.get(field):  # Skip if any required field is missing
                raise DropItem(f"Missing required field: {field} in {item}")

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
            
            adapter["specifications"] = cleaned_specs
        else:
            raise DropItem(f"Missing specifications in {item}")

        # Clean and format the name field (remove bracketed part)
        name = adapter.get("name")
        if name:
            name = re.sub(r"\s*\(.*?\)", "", name).strip()
            adapter["name"] = name
        
        # Format price field (add ₹ symbol and ensure numeric value)
        price = adapter.get("price")
        if price:
            price = re.sub(r"[^\d]", "", price)  # Keep only digits
            adapter["price"] = price
        
        # Clean image URL field (remove trailing spaces)
        image = adapter.get("image")
        if image:
            adapter["image"] = image.strip()

        return item

