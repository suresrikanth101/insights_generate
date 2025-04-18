# Standard library imports
import io
import logging
import mimetypes
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from datetime import datetime
import re
import json

# Third-party imports
import pandas as pd
import requests
from bs4 import BeautifulSoup
import PyPDF2

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
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
            
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

    def _extract_page_metadata(self, soup: BeautifulSoup) -> Dict[str, Optional[str]]:
        """
        Extract metadata from HTML content.
        
        Args:
            soup (BeautifulSoup): BeautifulSoup object of the page
            
        Returns:
            Dict[str, Optional[str]]: Dictionary containing metadata
        """
        page_metadata = {
            'last_modified': None,
            'updated_time': None,
            'published_date': None
        }
        
        try:
            # 1. Check HTTP headers first (highest priority)
            if hasattr(soup, 'response') and soup.response:
                headers = soup.response.headers
                if 'last-modified' in headers:
                    page_metadata['last_modified'] = headers['last-modified']
                    logging.info(f"Found last_modified date from HTTP headers: {headers['last-modified']}")
            
            # 2. Check meta tags (second priority)
            date_patterns = {
                'modified': ['modified', 'last-modified', 'lastmod'],
                'updated': ['updated', 'update-time', 'last-updated'],
                'published': ['published', 'created', 'date', 'pubdate', 'publication']
            }
            
            for meta_tag in soup.find_all('meta'):
                property_value = meta_tag.get('property', '').lower()
                name_value = meta_tag.get('name', '').lower()
                content_value = meta_tag.get('content', '')
                
                # Check for last modified date
                if not page_metadata['last_modified']:
                    if any(pattern in property_value for pattern in date_patterns['modified']):
                        page_metadata['last_modified'] = content_value
                        logging.info(f"Found last_modified date from meta tag: {content_value}")
                    elif any(pattern in name_value for pattern in date_patterns['modified']):
                        page_metadata['last_modified'] = content_value
                        logging.info(f"Found last_modified date from meta name: {content_value}")
                
                # Check for updated time
                if not page_metadata['updated_time']:
                    if any(pattern in property_value for pattern in date_patterns['updated']):
                        page_metadata['updated_time'] = content_value
                        logging.info(f"Found updated_time from meta tag: {content_value}")
                    elif any(pattern in name_value for pattern in date_patterns['updated']):
                        page_metadata['updated_time'] = content_value
                        logging.info(f"Found updated_time from meta name: {content_value}")
                
                # Check for published date
                if not page_metadata['published_date']:
                    if any(pattern in property_value for pattern in date_patterns['published']):
                        page_metadata['published_date'] = content_value
                        logging.info(f"Found published_date from meta tag: {content_value}")
                    elif any(pattern in name_value for pattern in date_patterns['published']):
                        page_metadata['published_date'] = content_value
                        logging.info(f"Found published_date from meta name: {content_value}")
            
            # 3. Check schema.org data (third priority)
            for json_script in soup.find_all('script', type='application/ld+json'):
                try:
                    schema_data = json.loads(json_script.string)
                    if isinstance(schema_data, dict):
                        # Check for last modified date
                        if not page_metadata['last_modified']:
                            if 'dateModified' in schema_data:
                                page_metadata['last_modified'] = schema_data['dateModified']
                                logging.info(f"Found last_modified date from schema.org: {schema_data['dateModified']}")
                            elif 'modifiedDate' in schema_data:
                                page_metadata['last_modified'] = schema_data['modifiedDate']
                                logging.info(f"Found last_modified date from schema.org: {schema_data['modifiedDate']}")
                        
                        # Check for updated time
                        if not page_metadata['updated_time']:
                            if 'dateUpdated' in schema_data:
                                page_metadata['updated_time'] = schema_data['dateUpdated']
                                logging.info(f"Found updated_time from schema.org: {schema_data['dateUpdated']}")
                            elif 'updateTime' in schema_data:
                                page_metadata['updated_time'] = schema_data['updateTime']
                                logging.info(f"Found updated_time from schema.org: {schema_data['updateTime']}")
                        
                        # Check for published date
                        if not page_metadata['published_date']:
                            if 'datePublished' in schema_data:
                                page_metadata['published_date'] = schema_data['datePublished']
                                logging.info(f"Found published_date from schema.org: {schema_data['datePublished']}")
                            elif 'publishedDate' in schema_data:
                                page_metadata['published_date'] = schema_data['publishedDate']
                                logging.info(f"Found published_date from schema.org: {schema_data['publishedDate']}")
                except:
                    continue
            
            # 4. Check article metadata (fourth priority)
            article = soup.find('article')
            if article:
                for time_elem in article.find_all('time'):
                    datetime_value = time_elem.get('datetime')
                    if datetime_value:
                        if not page_metadata['last_modified'] and 'modified' in time_elem.get('class', []):
                            page_metadata['last_modified'] = datetime_value
                            logging.info(f"Found last_modified date from article time: {datetime_value}")
                        elif not page_metadata['updated_time'] and 'updated' in time_elem.get('class', []):
                            page_metadata['updated_time'] = datetime_value
                            logging.info(f"Found updated_time from article time: {datetime_value}")
                        elif not page_metadata['published_date'] and 'published' in time_elem.get('class', []):
                            page_metadata['published_date'] = datetime_value
                            logging.info(f"Found published_date from article time: {datetime_value}")
            
            # 5. Check for common date patterns in text (lowest priority)
            date_text_patterns = {
                'modified': r'(?:last\s+)?(?:modified|changed)\s+(?:on|at)?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
                'updated': r'(?:last\s+)?(?:updated|revised)\s+(?:on|at)?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
                'published': r'(?:published|posted|created)\s+(?:on|at)?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})'
            }
            
            for text in soup.stripped_strings:
                for date_type, pattern in date_text_patterns.items():
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        date_str = match.group(1)
                        if date_type == 'modified' and not page_metadata['last_modified']:
                            page_metadata['last_modified'] = date_str
                            logging.info(f"Found last_modified date from text pattern: {date_str}")
                        elif date_type == 'updated' and not page_metadata['updated_time']:
                            page_metadata['updated_time'] = date_str
                            logging.info(f"Found updated_time from text pattern: {date_str}")
                        elif date_type == 'published' and not page_metadata['published_date']:
                            page_metadata['published_date'] = date_str
                            logging.info(f"Found published_date from text pattern: {date_str}")
            
            # 6. Standardize date formats
            for key in ['last_modified', 'updated_time', 'published_date']:
                if page_metadata[key]:
                    try:
                        # Try to parse and standardize the date
                        parsed_date = pd.to_datetime(page_metadata[key])
                        page_metadata[key] = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                        logging.info(f"Standardized {key} to: {page_metadata[key]}")
                    except:
                        # If parsing fails, keep the original format
                        logging.warning(f"Could not standardize {key} date: {page_metadata[key]}")
            
        except Exception as error:
            logging.error(f"Error extracting metadata: {str(error)}")
        
        return page_metadata

    def _handle_pdf(self, response: requests.Response, url: str, content_name: str) -> Dict:
        """
        Handle PDF file content.
        
        Args:
            response (requests.Response): Response object containing PDF content
            url (str): URL of the PDF file
            content_name (str): Name of the content
            
        Returns:
            Dict: Dictionary containing PDF metadata and content
        """
        try:
            pdf_file = io.BytesIO(response.content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            pdf_metadata = pdf_reader.metadata
            
            extracted_text = ""
            for page in pdf_reader.pages:
                extracted_text += page.extract_text() + "\n"
            
            return {
                'title': pdf_metadata.get('/Title', os.path.basename(url)) if pdf_metadata else os.path.basename(url),
                'text': extracted_text,
                'links': [],
                'content_type': 'application/pdf',
                'last_modified': pdf_metadata.get('/ModDate', None) if pdf_metadata else None,
                'published_date': pdf_metadata.get('/CreationDate', None) if pdf_metadata else None
            }
            
        except Exception as error:
            logging.error(f"Error processing PDF from {url}: {str(error)}")
            return {
                'title': 'Error processing PDF',
                'text': f'Error: {str(error)}',
                'links': [],
                'content_type': 'application/pdf',
                'last_modified': None,
                'published_date': None
            }

    def _is_pdf_url(self, url: str) -> bool:
        """
        Check if the URL points to a PDF file.
        
        Args:
            url (str): URL to check
            
        Returns:
            bool: True if URL points to a PDF file
        """
        if url.lower().endswith('.pdf'):
            return True
        
        content_type, _ = mimetypes.guess_type(url)
        return content_type == 'application/pdf'

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
            is_allowed, robots_status = self._is_allowed_by_robots(url)
            if not is_allowed:
                logging.warning(f"Skipping {url} for content '{content_name}': {robots_status}")
                return None

            # Add random delay between requests (1-3 seconds)
            time.sleep(random.uniform(1, 3))
            
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            # Check if URL is a PDF
            if self._is_pdf_url(url):
                scraped_data = self._handle_pdf(response, url, content_name)
            else:
                # Handle HTML content
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract metadata
                page_metadata = self._extract_page_metadata(soup)
                
                scraped_data = {
                    'title': soup.title.string if soup.title else 'No title found',
                    'text': ' '.join([p.get_text().strip() for p in soup.find_all('p')]),
                    'links': [a.get('href') for a in soup.find_all('a', href=True)],
                    'content_type': 'text/html',
                    'last_modified': page_metadata['last_modified'],
                    'published_date': page_metadata['published_date']
                }
            
            # Add robots.txt status
            scraped_data['robots_status'] = robots_status
            
            # Save content
            self._save_content(content_name, url, scraped_data)
            return scraped_data
            
        except requests.exceptions.RequestException as error:
            logging.error(f"Error scraping {url} for content '{content_name}': {str(error)}")
            return None
        except Exception as error:
            logging.error(f"Unexpected error scraping {url} for content '{content_name}': {str(error)}")
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
            safe_content_name = "".join(c if c.isalnum() else "_" for c in content_name)
            timestamp = int(time.time())
            random_suffix = random.randint(1000, 9999)
            filename = f"{safe_content_name}_{domain}_{timestamp}_{random_suffix}.txt"
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write(f"Content Name: {content_name}\n")
                file.write(f"URL: {url}\n")
                file.write(f"Title: {scraped_data.get('title', 'N/A')}\n")
                file.write(f"Text Content: {scraped_data.get('text', 'N/A')}\n")
                file.write(f"Links: {', '.join(scraped_data.get('links', []))}\n")
                file.write(f"Last Modified: {scraped_data.get('last_modified', 'None')}\n")
                file.write(f"Updated Time: {scraped_data.get('updated_time', 'None')}\n")
                file.write(f"Published Date: {scraped_data.get('published_date', 'None')}\n")
                file.write(f"Robots.txt Status: {scraped_data.get('robots_status', 'N/A')}\n")
            
            logging.info(f"Saved content for '{content_name}' from {url} to {filepath}")
        except Exception as error:
            logging.error(f"Error saving content for {url}: {str(error)}")

def main():
    # Example usage
    scraper = WebScraper(r'C:\Users\Hp\Desktop\source\loopio3\input\websites.xlsx')  # Replace with your Excel file path
    results = scraper.scrape_all()
    logging.info(f"Scraping completed. Successfully scraped {len(results)} URLs.")

if __name__ == "__main__":
    main() 