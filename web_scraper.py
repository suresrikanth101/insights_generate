import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import logging
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, urljoin
import random
from concurrent.futures import ThreadPoolExecutor
import os
from urllib.robotparser import RobotFileParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)

class WebScraper:
    def __init__(self, excel_path: str, output_dir: str = 'scraped_data'):
        """
        Initialize the web scraper with Excel file path and output directory.
        
        Args:
            excel_path (str): Path to the Excel file containing URLs
            output_dir (str): Directory to save scraped content
        """
        self.excel_path = excel_path
        self.output_dir = output_dir
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.robot_parsers = {}  # Cache for robot parsers
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Load URLs and content names from Excel
        self.content_data = self._load_content_data()
        
    def _load_content_data(self) -> List[Dict[str, str]]:
        """
        Load content names and URLs from Excel file.
        
        Returns:
            List[Dict[str, str]]: List of dictionaries containing content name and URL
        """
        try:
            df = pd.read_excel(self.excel_path)
            
            # Verify column names
            if len(df.columns) < 2:
                raise ValueError("Excel file must have at least 2 columns")
                
            # Get column names (assuming first two columns are content name and URL)
            content_name_col = df.columns[0]  # First column
            url_col = df.columns[1]  # Second column
            
            # Create list of dictionaries with content name and URL
            content_entries = []
            for _, row in df.iterrows():
                if pd.notna(row[url_col]):  # Only include rows with valid URLs
                    content_entries.append({
                        'content_name': str(row[content_name_col]),
                        'url': str(row[url_col])
                    })
            
            logging.info(f"Successfully loaded {len(content_entries)} content entries from Excel")
            return content_entries
            
        except Exception as e:
            logging.error(f"Error loading data from Excel: {str(e)}")
            raise

    def _get_robot_parser(self, domain: str) -> RobotFileParser:
        """
        Get or create a RobotFileParser for a domain.
        
        Args:
            domain (str): Domain to get robot parser for
            
        Returns:
            RobotFileParser: Configured robot parser
        """
        if domain not in self.robot_parsers:
            parser = RobotFileParser()
            robots_url = f"https://{domain}/robots.txt"
            try:
                parser.set_url(robots_url)
                parser.read()
                self.robot_parsers[domain] = parser
                logging.info(f"Successfully loaded robots.txt for {domain}")
            except Exception as e:
                logging.warning(f"Could not load robots.txt for {domain}: {str(e)}")
                # Create a default parser that allows everything if robots.txt is not accessible
                parser.allow_all = True
                self.robot_parsers[domain] = parser
        return self.robot_parsers[domain]

    def _is_allowed_by_robots(self, url: str) -> Tuple[bool, str]:
        """
        Check if a URL is allowed by robots.txt.
        
        Args:
            url (str): URL to check
            
        Returns:
            Tuple[bool, str]: (is_allowed, reason)
        """
        try:
            domain = self._get_domain(url)
            parser = self._get_robot_parser(domain)
            
            if parser.allow_all:
                return True, "No robots.txt restrictions found"
                
            if parser.can_fetch(self.headers['User-Agent'], url):
                return True, "Allowed by robots.txt"
            else:
                return False, "Disallowed by robots.txt"
                
        except Exception as e:
            logging.error(f"Error checking robots.txt for {url}: {str(e)}")
            return True, "Error checking robots.txt, proceeding with caution"

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL for rate limiting."""
        return urlparse(url).netloc

    def _save_content(self, content_name: str, url: str, scraped_data: Dict) -> None:
        """
        Save scraped content to a file.
        
        Args:
            content_name (str): Name of the content from Excel
            url (str): URL that was scraped
            scraped_data (Dict): Content to save
        """
        try:
            domain = self._get_domain(url)
            # Use content name in filename for better organization
            safe_content_name = "".join(c if c.isalnum() else "_" for c in content_name)
            filename = f"{safe_content_name}_{domain}_{int(time.time())}_{random.randint(1000, 9999)}.txt"
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Content Name: {content_name}\n")
                f.write(f"URL: {url}\n")
                f.write(f"Title: {scraped_data.get('title', 'N/A')}\n")
                f.write(f"Text Content: {scraped_data.get('text', 'N/A')}\n")
                f.write(f"Links: {', '.join(scraped_data.get('links', []))}\n")
                f.write(f"Robots.txt Status: {scraped_data.get('robots_status', 'N/A')}\n")
            
            logging.info(f"Saved content for '{content_name}' from {url} to {filepath}")
        except Exception as e:
            logging.error(f"Error saving content for {url}: {str(e)}")

    def _scrape_url(self, content_entry: Dict[str, str]) -> Optional[Dict]:
        """
        Scrape a single URL with error handling and rate limiting.
        
        Args:
            content_entry (Dict[str, str]): Dictionary containing content name and URL
            
        Returns:
            Optional[Dict]: Dictionary containing scraped content or None if failed
        """
        content_name = content_entry['content_name']
        url = content_entry['url']
        
        try:
            # Check robots.txt first
            is_allowed, reason = self._is_allowed_by_robots(url)
            if not is_allowed:
                logging.warning(f"Skipping {url} for content '{content_name}': {reason}")
                return None

            # Add random delay between requests (1-3 seconds)
            time.sleep(random.uniform(1, 3))
            
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract content
            scraped_data = {
                'title': soup.title.string if soup.title else 'No title found',
                'text': ' '.join([p.get_text().strip() for p in soup.find_all('p')]),
                'links': [a.get('href') for a in soup.find_all('a', href=True)],
                'robots_status': reason
            }
            
            # Save content
            self._save_content(content_name, url, scraped_data)
            return scraped_data
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Error scraping {url} for content '{content_name}': {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error scraping {url} for content '{content_name}': {str(e)}")
            return None

    def scrape_all(self, max_workers: int = 5) -> List[Dict]:
        """
        Scrape all URLs using multiple threads.
        
        Args:
            max_workers (int): Maximum number of concurrent threads
            
        Returns:
            List[Dict]: List of scraped content dictionaries
        """
        scraped_results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            scraping_tasks = {
                executor.submit(self._scrape_url, content_entry): content_entry 
                for content_entry in self.content_data
            }
            
            for scraping_task in scraping_tasks:
                content_entry = scraping_tasks[scraping_task]
                try:
                    scraped_data = scraping_task.result()
                    if scraped_data:
                        scraped_results.append({
                            'content_name': content_entry['content_name'],
                            'url': content_entry['url'],
                            'content': scraped_data
                        })
                except Exception as e:
                    logging.error(f"Error processing {content_entry['url']} for content '{content_entry['content_name']}': {str(e)}")
        
        return scraped_results

def main():
    # Example usage
    scraper = WebScraper(r'C:\Users\Hp\Desktop\source\loopio3\input\websites.xlsx')  # Replace with your Excel file path
    results = scraper.scrape_all()
    logging.info(f"Scraping completed. Successfully scraped {len(results)} URLs.")

if __name__ == "__main__":
    main() 