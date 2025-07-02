import os
import uuid
import io
import logging
import mimetypes
import random
import time
import json
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from datetime import datetime
from pathlib import Path

# Third-party imports
import pandas as pd
import requests
from bs4 import BeautifulSoup
import PyPDF2
import pdfplumber

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)

class CombinedScraper:
    def __init__(self, excel_path: str, output_dir: str = 'scraped_data', folder_path: str = None):
        """
        Initialize the web scraper with Excel file path and output directory.
        
        Args:
            excel_path (str): Path to the Excel file containing URLs
            output_dir (str): Directory to save scraped content
            folder_path (str, optional): Path to folder containing local files to process
        """
        self.excel_path = excel_path
        self.output_dir = output_dir
        self.folder_path = folder_path
        self.html_dir = os.path.join(output_dir, "html")
        self.pdf_dir = os.path.join(output_dir, "pdf")
        
        # Create output directories
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.html_dir, exist_ok=True)
        os.makedirs(self.pdf_dir, exist_ok=True)
        
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.robot_parsers = {}  # Cache for robot parsers
        
        # Load URLs and content names from Excel
        self.content_data = self._load_content_data()
        
        # Load local files from folder if specified
        self.local_files_data = self._load_local_files_data() if folder_path else []
        
    def _load_content_data(self) -> List[Dict[str, str]]:
        """Load content names and URLs from Excel file."""
        try:
            df = pd.read_excel(self.excel_path)
            
            if len(df.columns) < 2:
                raise ValueError("Excel file must have at least 2 columns")
                
            content_name_col = df.columns[0]
            url_col = df.columns[1]
            
            content_entries = []
            for _, row in df.iterrows():
                if pd.notna(row[url_col]):
                    content_entries.append({
                        'content_name': str(row[content_name_col]),
                        'url': str(row[url_col])
                    })
            
            logging.info(f"Successfully loaded {len(content_entries)} content entries from Excel")
            return content_entries
            
        except Exception as e:
            logging.error(f"Error loading data from Excel: {str(e)}")
            raise

    def _load_local_files_data(self) -> List[Dict[str, str]]:
        """Load local files from the specified folder."""
        if not self.folder_path or not os.path.exists(self.folder_path):
            logging.warning(f"Folder path {self.folder_path} does not exist or is not specified")
            return []
        
        local_files = []
        supported_extensions = {'.pdf', '.html', '.htm', '.ppt', '.pptx', '.doc', '.docx', '.txt'}
        
        try:
            for file_path in Path(self.folder_path).rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                    # Use filename without extension as content name
                    content_name = file_path.stem
                    local_files.append({
                        'content_name': content_name,
                        'file_path': str(file_path),
                        'file_type': file_path.suffix.lower()
                    })
            
            logging.info(f"Successfully loaded {len(local_files)} local files from folder {self.folder_path}")
            return local_files
            
        except Exception as e:
            logging.error(f"Error loading local files from folder {self.folder_path}: {str(e)}")
            return []

    def _get_robot_parser(self, domain: str) -> RobotFileParser:
        """Get or create a RobotFileParser for a domain."""
        if domain not in self.robot_parsers:
            parser = RobotFileParser()
            robots_url = f"https://{domain}/robots.txt"
            try:
                parser.set_url(robots_url)
                parser.read()
                self.robot_parsers[domain] = parser
            except Exception as e:
                logging.warning(f"Could not load robots.txt for {domain}: {str(e)}")
                parser.allow_all = True
                self.robot_parsers[domain] = parser
        return self.robot_parsers[domain]

    def _is_allowed_by_robots(self, url: str) -> Tuple[bool, str]:
        """Check if a URL is allowed by robots.txt."""
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
        """Extract domain from URL."""
        return urlparse(url).netloc

    def _extract_page_metadata(self, soup: BeautifulSoup) -> Dict[str, Optional[str]]:
        """Extract metadata from HTML content."""
        page_metadata = {
            'last_modified': None,
            'updated_time': None,
            'published_date': None
        }
        
        try:
            # Check meta tags
            date_patterns = {
                'modified': ['modified', 'last-modified', 'lastmod'],
                'updated': ['updated', 'update-time', 'last-updated'],
                'published': ['published', 'created', 'date', 'pubdate']
            }
            
            for meta_tag in soup.find_all('meta'):
                property_value = meta_tag.get('property', '').lower()
                name_value = meta_tag.get('name', '').lower()
                content_value = meta_tag.get('content', '')
                
                if not page_metadata['last_modified']:
                    if any(pattern in property_value for pattern in date_patterns['modified']):
                        page_metadata['last_modified'] = content_value
                    elif any(pattern in name_value for pattern in date_patterns['modified']):
                        page_metadata['last_modified'] = content_value
                
                if not page_metadata['updated_time']:
                    if any(pattern in property_value for pattern in date_patterns['updated']):
                        page_metadata['updated_time'] = content_value
                    elif any(pattern in name_value for pattern in date_patterns['updated']):
                        page_metadata['updated_time'] = content_value
                
                if not page_metadata['published_date']:
                    if any(pattern in property_value for pattern in date_patterns['published']):
                        page_metadata['published_date'] = content_value
                    elif any(pattern in name_value for pattern in date_patterns['published']):
                        page_metadata['published_date'] = content_value
            
            # Check article metadata if meta tags not found
            if not any([page_metadata['last_modified'], page_metadata['updated_time'], page_metadata['published_date']]):
                article = soup.find('article')
                if article:
                    for time_elem in article.find_all('time'):
                        datetime_value = time_elem.get('datetime')
                        if datetime_value:
                            if 'modified' in time_elem.get('class', []):
                                page_metadata['last_modified'] = datetime_value
                            elif 'updated' in time_elem.get('class', []):
                                page_metadata['updated_time'] = datetime_value
                            elif 'published' in time_elem.get('class', []):
                                page_metadata['published_date'] = datetime_value
            
            # Standardize date formats
            for key in ['last_modified', 'updated_time', 'published_date']:
                if page_metadata[key]:
                    try:
                        parsed_date = pd.to_datetime(page_metadata[key])
                        page_metadata[key] = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
            
        except Exception as error:
            logging.error(f"Error extracting metadata: {str(error)}")
        
        return page_metadata

    def _is_pdf_url(self, url: str) -> bool:
        """Check if the URL points to a PDF file."""
        # Check URL path ending
        if url.lower().endswith('.pdf'):
            return True
        
        try:
            # Make a HEAD request to check content type
            head_response = self.session.head(url, headers=self.headers, timeout=10)
            content_type = head_response.headers.get('content-type', '').lower()
            return 'application/pdf' in content_type
        except:
            # Fallback to checking URL and mime type
            content_type, _ = mimetypes.guess_type(url)
            return content_type == 'application/pdf'

    def _save_html_file(self, content: str, content_name: str) -> str:
        """Save HTML content to a file and return the filepath. Overwrites if file exists."""
        uid = str(uuid.uuid4())
        filename = f"{content_name}_{uid}.html".replace(" ", "_")
        filepath = os.path.join(self.html_dir, filename)
        # Overwrite if file exists (default behavior of 'w' mode)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def _save_pdf_file(self, content: bytes, content_name: str) -> str:
        """Save PDF content to a file and return the filepath. Overwrites if file exists."""
        uid = str(uuid.uuid4())
        filename = f"{content_name}_{uid}.pdf".replace(" ", "_")
        filepath = os.path.join(self.pdf_dir, filename)
        # Overwrite if file exists (default behavior of 'wb' mode)
        with open(filepath, "wb") as f:
            f.write(content)
        return filepath

    def _handle_pdf(self, response: requests.Response, url: str, content_name: str) -> Dict:
        """Handle PDF file content."""
        try:
            # Save PDF content
            pdf_content = response.content
            if not pdf_content:
                raise ValueError("Empty PDF content received")

            logging.info(f"Processing PDF from {url}")
            
            # Save PDF file
            pdf_filepath = self._save_pdf_file(pdf_content, content_name)
            
            # Extract text using pdfplumber (more reliable than PyPDF2 for text extraction)
            extracted_text = ""
            with pdfplumber.open(pdf_filepath) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text += text + "\n"
            
            # Get PDF metadata using PyPDF2
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
            pdf_metadata = pdf_reader.metadata if pdf_reader.metadata else {}
            
            # Extract dates from PDF metadata
            creation_date = pdf_metadata.get('/CreationDate', None)
            mod_date = pdf_metadata.get('/ModDate', None)
            
            if creation_date:
                try:
                    creation_date = creation_date.replace('D:', '')[:14]
                    creation_date = datetime.strptime(creation_date, '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
                except:
                    creation_date = None
            
            if mod_date:
                try:
                    mod_date = mod_date.replace('D:', '')[:14]
                    mod_date = datetime.strptime(mod_date, '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
                except:
                    mod_date = None
            
            return {
                'title': pdf_metadata.get('/Title', os.path.basename(url)),
                'text': extracted_text[:5000],  # Limit text to 5000 characters like in sample.py
                'links': [],
                'content_type': 'application/pdf',
                'last_modified': mod_date,
                'updated_time': None,
                'published_date': creation_date,
                'total_pages': len(pdf_reader.pages),
                'saved_filepath': pdf_filepath,
                'filename': os.path.basename(pdf_filepath)  # Add filename like in sample.py
            }
            
        except Exception as error:
            logging.error(f"Error processing PDF from {url}: {str(error)}")
            return {
                'title': 'Error processing PDF',
                'text': f'Error: {str(error)}',
                'links': [],
                'content_type': 'application/pdf',
                'last_modified': None,
                'updated_time': None,
                'published_date': None,
                'total_pages': 0,
                'saved_filepath': None,
                'filename': None
            }

    def _scrape_url(self, content_entry: Dict[str, str]) -> Optional[Dict]:
        """Scrape a single URL with error handling and rate limiting, handling HTML, PDF, and PPT/PPTX."""
        content_name = content_entry['content_name']
        url = content_entry['url']
        logging.info(f"Starting to process URL: {url} for content: {content_name}")

        try:
            is_allowed, robots_status = self._is_allowed_by_robots(url)
            if not is_allowed:
                logging.warning(f"URL blocked by robots.txt: {url} for content '{content_name}': {robots_status}")
                return None

            logging.info(f"Rate limiting: Waiting between 1-3 seconds before accessing {url}")
            time.sleep(random.uniform(1, 3))

            logging.info(f"Making GET request to: {url}")
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            content_type = response.headers.get('content-type', '').lower()

            # 1. HTML
            if url.lower().endswith('.html') or 'text/html' in content_type:
                logging.info(f"Detected HTML content at: {url}")
                html_filepath = self._save_html_file(response.text, content_name)
                logging.info(f"Saved HTML content to: {html_filepath}")
                soup = BeautifulSoup(response.text, 'html.parser')
                page_metadata = self._extract_page_metadata(soup)
                logging.info(f"Extracted metadata from HTML: {page_metadata}")
                scraped_data = {
                    'title': soup.title.string if soup.title else 'No title found',
                    'text': ' '.join([p.get_text().strip() for p in soup.find_all('p')])[:5000],
                    'links': [a.get('href') for a in soup.find_all('a', href=True)],
                    'content_type': 'text/html',
                    'last_modified': page_metadata['last_modified'],
                    'updated_time': page_metadata['updated_time'],
                    'published_date': page_metadata['published_date'],
                    'saved_filepath': html_filepath,
                    'filename': os.path.basename(html_filepath),
                    'type': 'html'
                }
                logging.info(f"Successfully processed HTML from {url}")

            # 2. PDF
            elif url.lower().endswith('.pdf') or 'application/pdf' in content_type:
                logging.info(f"Detected PDF content at: {url}")
                scraped_data = self._handle_pdf(response, url, content_name)
                scraped_data['type'] = 'pdf'
                logging.info(f"Successfully processed PDF from {url}")

            # 3. PPT/PPTX
            elif url.lower().endswith('.ppt') or url.lower().endswith('.pptx'):
                pdf_url = url.rsplit('.', 1)[0] + '.pdf'
                logging.info(f"Detected PPT/PPTX. Trying as PDF: {pdf_url}")
                try:
                    pdf_response = self.session.get(pdf_url, headers=self.headers, timeout=10)
                    pdf_response.raise_for_status()
                    scraped_data = self._handle_pdf(pdf_response, pdf_url, content_name)
                    scraped_data['type'] = 'pdf'
                    logging.info(f"Successfully processed PDF from PPT URL: {pdf_url}")
                except Exception as ppt_pdf_error:
                    logging.error(f"Failed to process PPT as PDF for {url}: {ppt_pdf_error}")
                    return None

            # 4. Fallback: Try as HTML, then as PDF by appending .pdf
            else:
                try:
                    logging.info(f"Unknown extension/content-type for {url}. Trying as HTML.")
                    html_filepath = self._save_html_file(response.text, content_name)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    page_metadata = self._extract_page_metadata(soup)
                    scraped_data = {
                        'title': soup.title.string if soup.title else 'No title found',
                        'text': ' '.join([p.get_text().strip() for p in soup.find_all('p')])[:5000],
                        'links': [a.get('href') for a in soup.find_all('a', href=True)],
                        'content_type': 'text/html',
                        'last_modified': page_metadata['last_modified'],
                        'updated_time': page_metadata['updated_time'],
                        'published_date': page_metadata['published_date'],
                        'saved_filepath': html_filepath,
                        'filename': os.path.basename(html_filepath),
                        'type': 'html'
                    }
                    logging.info(f"Successfully processed fallback HTML from {url}")
                except Exception as html_error:
                    logging.warning(f"Failed to process as HTML for {url}: {html_error}. Trying as PDF by appending .pdf.")
                    pdf_url = url + '.pdf'
                    try:
                        pdf_response = self.session.get(pdf_url, headers=self.headers, timeout=10)
                        pdf_response.raise_for_status()
                        scraped_data = self._handle_pdf(pdf_response, pdf_url, content_name)
                        scraped_data['type'] = 'pdf'
                        logging.info(f"Successfully processed fallback PDF from {pdf_url}")
                    except Exception as fallback_pdf_error:
                        logging.error(f"Failed to process fallback PDF for {pdf_url}: {fallback_pdf_error}")
                        return None

            scraped_data['robots_status'] = robots_status
            scraped_data['final_url'] = url
            logging.info(f"Successfully completed processing {url} for content '{content_name}'")
            return scraped_data

        except requests.exceptions.RequestException as error:
            logging.error(f"Request failed for URL {url} (content: '{content_name}'): {str(error)}")
            return None
        except Exception as error:
            logging.error(f"Unexpected error processing {url} (content: '{content_name}'): {str(error)}")
            return None

    def _handle_local_text(self, file_path: str, content_name: str) -> Dict:
        """Handle local text file content."""
        try:
            logging.info(f"Processing local text file: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as file:
                text_content = file.read()
            
            # Get file modification time
            file_stat = os.stat(file_path)
            file_mod_time = datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            return {
                'title': os.path.basename(file_path),
                'text': text_content,
                'links': [],
                'content_type': 'text/plain',
                'last_modified': file_mod_time,
                'updated_time': None,
                'published_date': None,
                'saved_filepath': file_path,
                'filename': os.path.basename(file_path),
                'original_filepath': file_path
            }
            
        except Exception as error:
            logging.error(f"Error processing local text file {file_path}: {str(error)}")
            return {
                'title': 'Error processing text file',
                'text': f'Error: {str(error)}',
                'links': [],
                'content_type': 'text/plain',
                'last_modified': None,
                'updated_time': None,
                'published_date': None,
                'saved_filepath': None,
                'filename': None,
                'original_filepath': file_path
            }

    def _process_local_file(self, file_entry: Dict[str, str]) -> Optional[Dict]:
        """Process a single local file using existing PDF and HTML processing methods."""
        content_name = file_entry['content_name']
        file_path = file_entry['file_path']
        file_type = file_entry['file_type']
        
        logging.info(f"Processing local file: {file_path} (type: {file_type})")
        
        try:
            if file_type == '.pdf':
                # Use existing PDF processing logic directly
                logging.info(f"Processing local PDF file: {file_path}")
                
                # Read the PDF file content
                with open(file_path, 'rb') as file:
                    pdf_content = file.read()
                
                if not pdf_content:
                    raise ValueError("Empty PDF content")
                
                # Save PDF to output directory
                pdf_filepath = self._save_pdf_file(pdf_content, content_name)
                
                # Extract text using pdfplumber (same as _handle_pdf)
                extracted_text = ""
                with pdfplumber.open(pdf_filepath) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            extracted_text += text + "\n"
                
                # Get PDF metadata using PyPDF2 (same as _handle_pdf)
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
                pdf_metadata = pdf_reader.metadata if pdf_reader.metadata else {}
                
                # Extract dates from PDF metadata (same as _handle_pdf)
                creation_date = pdf_metadata.get('/CreationDate', None)
                mod_date = pdf_metadata.get('/ModDate', None)
                
                if creation_date:
                    try:
                        creation_date = creation_date.replace('D:', '')[:14]
                        creation_date = datetime.strptime(creation_date, '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        creation_date = None
                
                if mod_date:
                    try:
                        mod_date = mod_date.replace('D:', '')[:14]
                        mod_date = datetime.strptime(mod_date, '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        mod_date = None
                
                # Get file modification time as fallback for last_modified if not available
                if not mod_date:
                    file_stat = os.stat(file_path)
                    file_mod_time = datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    mod_date = file_mod_time
                
                scraped_data = {
                    'title': pdf_metadata.get('/Title', os.path.basename(file_path)),
                    'text': extracted_text,
                    'links': [],
                    'content_type': 'application/pdf',
                    'last_modified': mod_date,
                    'updated_time': None,
                    'published_date': creation_date,
                    'total_pages': len(pdf_reader.pages),
                    'saved_filepath': pdf_filepath,
                    'filename': os.path.basename(pdf_filepath),
                    'original_filepath': file_path,
                    'type': 'pdf'
                }
                
            elif file_type in ['.html', '.htm']:
                # Use existing HTML processing logic from _scrape_url
                with open(file_path, 'r', encoding='utf-8') as file:
                    html_content = file.read()
                
                # Save HTML to output directory using existing _save_html_file method
                html_filepath = self._save_html_file(html_content, content_name)
                
                # Use existing HTML processing logic from _scrape_url
                soup = BeautifulSoup(html_content, 'html.parser')
                page_metadata = self._extract_page_metadata(soup)
                
                # Get file modification time as fallback for last_modified
                file_stat = os.stat(file_path)
                file_mod_time = datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                
                scraped_data = {
                    'title': soup.title.string if soup.title else os.path.basename(file_path),
                    'text': ' '.join([p.get_text().strip() for p in soup.find_all('p')])[:5000],
                    'links': [a.get('href') for a in soup.find_all('a', href=True)],
                    'content_type': 'text/html',
                    'last_modified': page_metadata['last_modified'] or file_mod_time,
                    'updated_time': page_metadata['updated_time'],
                    'published_date': page_metadata['published_date'],
                    'saved_filepath': html_filepath,
                    'filename': os.path.basename(html_filepath),
                    'original_filepath': file_path,
                    'type': 'html'
                }
                
            elif file_type == '.txt':
                scraped_data = self._handle_local_text(file_path, content_name)
                scraped_data['type'] = 'text'
            elif file_type in ['.ppt', '.pptx']:
                # For PPT files, we'll try to extract basic info
                logging.info(f"PPT/PPTX files not fully supported yet: {file_path}")
                scraped_data = {
                    'title': os.path.basename(file_path),
                    'text': f'PPT/PPTX file: {os.path.basename(file_path)} - Content extraction not implemented',
                    'links': [],
                    'content_type': 'application/vnd.ms-powerpoint' if file_type == '.ppt' else 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                    'last_modified': datetime.fromtimestamp(os.stat(file_path).st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'updated_time': None,
                    'published_date': None,
                    'saved_filepath': file_path,
                    'filename': os.path.basename(file_path),
                    'original_filepath': file_path,
                    'type': 'ppt'
                }
            elif file_type in ['.doc', '.docx']:
                # For DOC files, we'll try to extract basic info
                logging.info(f"DOC/DOCX files not fully supported yet: {file_path}")
                scraped_data = {
                    'title': os.path.basename(file_path),
                    'text': f'DOC/DOCX file: {os.path.basename(file_path)} - Content extraction not implemented',
                    'links': [],
                    'content_type': 'application/msword' if file_type == '.doc' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'last_modified': datetime.fromtimestamp(os.stat(file_path).st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'updated_time': None,
                    'published_date': None,
                    'saved_filepath': file_path,
                    'filename': os.path.basename(file_path),
                    'original_filepath': file_path,
                    'type': 'doc'
                }
            else:
                logging.warning(f"Unsupported file type: {file_type} for file {file_path}")
                return None
            
            scraped_data['robots_status'] = 'Local file - no robots.txt check needed'
            scraped_data['final_url'] = f'file://{file_path}'
            
            logging.info(f"Successfully processed local file: {file_path}")
            return scraped_data
            
        except Exception as error:
            logging.error(f"Error processing local file {file_path}: {str(error)}")
            return None

    def scrape_all(self) -> List[Dict]:
        """Scrape all URLs and process all local files sequentially."""
        scraped_results = []
        total_urls = len(self.content_data)
        total_files = len(self.local_files_data)
        successful_urls = 0
        failed_urls = 0
        successful_files = 0
        failed_files = 0

        logging.info(f"Starting to scrape {total_urls} URLs and process {total_files} local files")

        # Process URLs from Excel
        if total_urls > 0:
            logging.info(f"Processing {total_urls} URLs from Excel file")
            for content_entry in self.content_data:
                try:
                    scraped_data = self._scrape_url(content_entry)
                    if scraped_data:
                        successful_urls += 1
                        result = {
                            'content_name': content_entry['content_name'],
                            'url': content_entry['url'],
                            'content': scraped_data,
                            'source': 'url'
                        }
                        scraped_results.append(result)
                        logging.info(f"Successfully scraped {content_entry['url']} ({successful_urls}/{total_urls} successful)")
                    else:
                        failed_urls += 1
                        logging.warning(f"Failed to scrape {content_entry['url']} ({failed_urls}/{total_urls} failed)")
                except Exception as e:
                    failed_urls += 1
                    logging.error(f"Error processing {content_entry['url']} for content '{content_entry['content_name']}': {str(e)}")

        # Process local files from folder
        if total_files > 0:
            logging.info(f"Processing {total_files} local files from folder")
            for file_entry in self.local_files_data:
                try:
                    scraped_data = self._process_local_file(file_entry)
                    if scraped_data:
                        successful_files += 1
                        result = {
                            'content_name': file_entry['content_name'],
                            'file_path': file_entry['file_path'],
                            'content': scraped_data,
                            'source': 'local_file'
                        }
                        scraped_results.append(result)
                        logging.info(f"Successfully processed {file_entry['file_path']} ({successful_files}/{total_files} successful)")
                    else:
                        failed_files += 1
                        logging.warning(f"Failed to process {file_entry['file_path']} ({failed_files}/{total_files} failed)")
                except Exception as e:
                    failed_files += 1
                    logging.error(f"Error processing {file_entry['file_path']} for content '{file_entry['content_name']}': {str(e)}")

        # Log summary
        total_processed = total_urls + total_files
        total_successful = successful_urls + successful_files
        total_failed = failed_urls + failed_files
        
        logging.info(f"Processing completed:")
        logging.info(f"URLs - Total: {total_urls}, Successful: {successful_urls}, Failed: {failed_urls}")
        logging.info(f"Local Files - Total: {total_files}, Successful: {successful_files}, Failed: {failed_files}")
        logging.info(f"Overall - Total: {total_processed}, Successful: {total_successful}, Failed: {total_failed}")
        if total_processed > 0:
            logging.info(f"Overall success rate: {(total_successful/total_processed)*100:.2f}%")

        # Save all results to a single JSON file
        self._save_json_results(scraped_results)
        return scraped_results

    def _save_json_results(self, scraped_results: List[Dict]) -> None:
        """Save all scraped results to a single JSON file, replacing the file if it exists."""
        try:
            json_filename = "scraped_results.json"
            json_filepath = os.path.join(self.output_dir, json_filename)

            logging.info(f"Preparing to save {len(scraped_results)} results to JSON file")

            # Convert datetime objects to strings for JSON serialization
            json_data = []
            for result in scraped_results:
                result_copy = result.copy()
                content = result_copy['content']

                # Ensure all date fields are strings
                for date_field in ['last_modified', 'updated_time', 'published_date']:
                    if content.get(date_field) and not isinstance(content[date_field], str):
                        content[date_field] = str(content[date_field])

                json_data.append(result_copy)

            # Overwrite the file if it exists
            with open(json_filepath, 'w', encoding='utf-8') as json_file:
                json.dump(json_data, json_file, indent=2, ensure_ascii=False)

            logging.info(f"Successfully saved results to JSON file: {json_filepath}")

        except Exception as error:
            logging.error(f"Error saving JSON results: {str(error)}")

def main():
    # Example usage
    logging.info("Starting combined scraper (URLs + local files)")
    
    # Initialize scraper with Excel file and optional folder path
    excel_path = 'websites.xlsx'
    folder_path = 'documents'  # Optional: path to folder containing local files
    
    # Check if folder exists
    if folder_path and not os.path.exists(folder_path):
        logging.warning(f"Folder {folder_path} does not exist. Creating it for demonstration.")
        os.makedirs(folder_path, exist_ok=True)
    
    scraper = CombinedScraper(excel_path, folder_path=folder_path)
    results = scraper.scrape_all()
    
    # Count results by source
    url_results = [r for r in results if r.get('source') == 'url']
    file_results = [r for r in results if r.get('source') == 'local_file']
    
    logging.info(f"Processing completed. Successfully processed {len(url_results)} URLs and {len(file_results)} local files.")
    logging.info(f"Total results: {len(results)}")

if __name__ == "__main__":
    main() 