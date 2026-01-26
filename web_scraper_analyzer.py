"""
Web Scraper with Data Analysis
Demonstrates: HTTP requests, HTML parsing (BeautifulSoup), regex, data structures,
file writing, exception handling, list/dict comprehensions

pip install beautifulsoup4 requests
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import csv
from datetime import datetime
from typing import List, Dict, Optional
from collections import Counter, defaultdict
from urllib.parse import urljoin, urlparse
import time


class WebScraper:
    """Web scraper with parsing and analysis capabilities."""
    
    def __init__(self, base_url: str, delay: float = 1.0):
        self.base_url = base_url
        self.delay = delay  # Polite scraping delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.scraped_data = []
        self.errors = []
    
    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a web page with error handling."""
        try:
            time.sleep(self.delay)  # Polite delay
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                raise ValueError(f"Invalid content type: {content_type}")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            return soup
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching {url}: {str(e)}"
            self.errors.append(error_msg)
            print(f"✗ {error_msg}")
            return None
        except Exception as e:
            error_msg = f"Unexpected error with {url}: {str(e)}"
            self.errors.append(error_msg)
            print(f"✗ {error_msg}")
            return None
    
    def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract all links from a page using list comprehension."""
        if not soup:
            return []
        
        # Extract all anchor tags and convert to absolute URLs
        links = [
            urljoin(base_url, a.get('href', ''))
            for a in soup.find_all('a', href=True)
            if a.get('href')
        ]
        
        # Filter out invalid URLs using list comprehension
        valid_links = [
            link for link in links
            if urlparse(link).scheme in ('http', 'https')
        ]
        
        return list(set(valid_links))  # Remove duplicates
    
    def extract_emails(self, text: str) -> List[str]:
        """Extract email addresses using regex."""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        return list(set(emails))
    
    def extract_phone_numbers(self, text: str) -> List[str]:
        """Extract phone numbers using regex patterns."""
        # Pattern for various phone formats
        patterns = [
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # 123-456-7890
            r'\(\d{3}\)\s*\d{3}[-.]?\d{4}',     # (123) 456-7890
            r'\+\d{1,3}\s*\d{3}[-.]?\d{3}[-.]?\d{4}'  # +1 123-456-7890
        ]
        
        phones = []
        for pattern in patterns:
            phones.extend(re.findall(pattern, text))
        
        return list(set(phones))
    
    def extract_metadata(self, soup: BeautifulSoup) -> Dict:
        """Extract page metadata using dict comprehension."""
        if not soup:
            return {}
        
        # Extract meta tags
        meta_tags = {
            meta.get('name', meta.get('property', 'unknown')): meta.get('content', '')
            for meta in soup.find_all('meta')
            if meta.get('content')
        }
        
        # Extract common elements
        metadata = {
            'title': soup.title.string if soup.title else 'N/A',
            'meta_tags': meta_tags,
            'headings': {
                f'h{i}': [h.get_text(strip=True) for h in soup.find_all(f'h{i}')]
                for i in range(1, 7)
            },
            'images_count': len(soup.find_all('img')),
            'links_count': len(soup.find_all('a')),
            'scripts_count': len(soup.find_all('script')),
        }
        
        return metadata
    
    def analyze_text_content(self, soup: BeautifulSoup) -> Dict:
        """Analyze text content of the page."""
        if not soup:
            return {}
        
        # Remove script and style elements
        for script in soup(['script', 'style', 'nav', 'footer', 'header']):
            script.decompose()
        
        text = soup.get_text(separator=' ', strip=True)
        
        # Clean text using regex
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        
        # Word analysis
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        word_freq = Counter(words)
        
        # Extract statistics
        analysis = {
            'total_words': len(words),
            'unique_words': len(set(words)),
            'total_chars': len(text),
            'top_10_words': word_freq.most_common(10),
            'avg_word_length': sum(len(w) for w in words) / len(words) if words else 0,
            'emails': self.extract_emails(text),
            'phone_numbers': self.extract_phone_numbers(text),
        }
        
        return analysis
    
    def scrape_page(self, url: str) -> Optional[Dict]:
        """Scrape and analyze a single page."""
        print(f"\n📄 Scraping: {url}")
        
        soup = self.fetch_page(url)
        if not soup:
            return None
        
        metadata = self.extract_metadata(soup)
        text_analysis = self.analyze_text_content(soup)
        links = self.extract_links(soup, url)
        
        page_data = {
            'url': url,
            'scraped_at': datetime.now().isoformat(),
            'metadata': metadata,
            'text_analysis': text_analysis,
            'links': links,
            'external_links': [l for l in links if urlparse(l).netloc != urlparse(url).netloc],
            'internal_links': [l for l in links if urlparse(l).netloc == urlparse(url).netloc],
        }
        
        self.scraped_data.append(page_data)
        print(f"✓ Successfully scraped {url}")
        print(f"  - Found {len(links)} links ({len(page_data['internal_links'])} internal)")
        print(f"  - Analyzed {text_analysis['total_words']} words")
        
        return page_data
    
    def scrape_multiple(self, urls: List[str]) -> List[Dict]:
        """Scrape multiple URLs."""
        print(f"\n🌐 Starting scraping of {len(urls)} URLs...")
        results = []
        
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}]", end=" ")
            result = self.scrape_page(url)
            if result:
                results.append(result)
        
        return results


class DataAnalyzer:
    """Analyze scraped data and generate insights."""
    
    def __init__(self, scraped_data: List[Dict]):
        self.data = scraped_data
    
    def generate_summary(self) -> Dict:
        """Generate comprehensive summary of scraped data."""
        if not self.data:
            return {'error': 'No data to analyze'}
        
        # Aggregate statistics using comprehensions
        total_links = sum(len(page['links']) for page in self.data)
        total_words = sum(page['text_analysis']['total_words'] for page in self.data)
        
        # Collect all emails across pages
        all_emails = [
            email
            for page in self.data
            for email in page['text_analysis']['emails']
        ]
        
        # Collect all phone numbers
        all_phones = [
            phone
            for page in self.data
            for phone in page['text_analysis']['phone_numbers']
        ]
        
        # Domain analysis
        domains = defaultdict(int)
        for page in self.data:
            for link in page['links']:
                domain = urlparse(link).netloc
                if domain:
                    domains[domain] += 1
        
        # Aggregate word frequencies
        all_words = []
        for page in self.data:
            words = page['text_analysis']['top_10_words']
            all_words.extend(words)
        
        # Combine word counts
        word_counter = Counter()
        for word, count in all_words:
            word_counter[word] += count
        
        summary = {
            'total_pages_scraped': len(self.data),
            'total_links_found': total_links,
            'total_words_analyzed': total_words,
            'unique_emails': list(set(all_emails)),
            'unique_phones': list(set(all_phones)),
            'top_20_words': word_counter.most_common(20),
            'top_domains': dict(Counter(domains).most_common(10)),
            'pages_by_word_count': sorted(
                [
                    {'url': p['url'], 'word_count': p['text_analysis']['total_words']}
                    for p in self.data
                ],
                key=lambda x: x['word_count'],
                reverse=True
            ),
            'avg_words_per_page': total_words / len(self.data) if self.data else 0,
            'avg_links_per_page': total_links / len(self.data) if self.data else 0,
        }
        
        return summary
    
    def filter_pages(self, min_words: int = 100) -> List[Dict]:
        """Filter pages by word count using list comprehension."""
        return [
            page for page in self.data
            if page['text_analysis']['total_words'] >= min_words
        ]
    
    def search_keyword(self, keyword: str) -> List[Dict]:
        """Search for pages containing specific keyword."""
        keyword_lower = keyword.lower()
        results = []
        
        for page in self.data:
            # Search in title
            title = page['metadata'].get('title', '').lower()
            # Search in top words
            words = [word for word, _ in page['text_analysis']['top_10_words']]
            
            if keyword_lower in title or keyword_lower in words:
                results.append({
                    'url': page['url'],
                    'title': page['metadata'].get('title'),
                    'relevance': words.count(keyword_lower) if keyword_lower in words else 0
                })
        
        return sorted(results, key=lambda x: x['relevance'], reverse=True)


class DataExporter:
    """Export scraped data to various formats."""
    
    @staticmethod
    def export_to_json(data: Dict, filename: str):
        """Export data to JSON file."""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\n✓ Data exported to {filename}")
        except Exception as e:
            print(f"\n✗ Error exporting to JSON: {e}")
    
    @staticmethod
    def export_to_csv(data: List[Dict], filename: str):
        """Export summary data to CSV file."""
        try:
            if not data:
                print("\n✗ No data to export")
                return
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                # Flatten data for CSV
                rows = []
                for page in data:
                    rows.append({
                        'url': page['url'],
                        'title': page['metadata'].get('title', 'N/A'),
                        'scraped_at': page['scraped_at'],
                        'total_words': page['text_analysis']['total_words'],
                        'unique_words': page['text_analysis']['unique_words'],
                        'total_links': len(page['links']),
                        'internal_links': len(page['internal_links']),
                        'external_links': len(page['external_links']),
                        'images_count': page['metadata'].get('images_count', 0),
                    })
                
                if rows:
                    fieldnames = rows[0].keys()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                    print(f"\n✓ Data exported to {filename}")
        except Exception as e:
            print(f"\n✗ Error exporting to CSV: {e}")
    
    @staticmethod
    def generate_report(summary: Dict, filename: str):
        """Generate a text report."""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("="*60 + "\n")
                f.write("WEB SCRAPING ANALYSIS REPORT\n")
                f.write("="*60 + "\n\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                f.write(f"Total Pages Scraped: {summary['total_pages_scraped']}\n")
                f.write(f"Total Links Found: {summary['total_links_found']}\n")
                f.write(f"Total Words Analyzed: {summary['total_words_analyzed']}\n")
                f.write(f"Average Words per Page: {summary['avg_words_per_page']:.2f}\n")
                f.write(f"Average Links per Page: {summary['avg_links_per_page']:.2f}\n\n")
                
                f.write("Top 20 Most Common Words:\n")
                f.write("-" * 40 + "\n")
                for word, count in summary['top_20_words']:
                    f.write(f"{word:20} : {count:5}\n")
                
                f.write("\n" + "="*60 + "\n")
                f.write(f"Unique Emails Found: {len(summary['unique_emails'])}\n")
                if summary['unique_emails']:
                    for email in summary['unique_emails'][:10]:
                        f.write(f"  - {email}\n")
                
                f.write("\n" + "="*60 + "\n")
                f.write(f"Unique Phone Numbers: {len(summary['unique_phones'])}\n")
                if summary['unique_phones']:
                    for phone in summary['unique_phones'][:10]:
                        f.write(f"  - {phone}\n")
                
                f.write("\n" + "="*60 + "\n")
                f.write("Top Domains:\n")
                for domain, count in summary['top_domains'].items():
                    f.write(f"{domain:30} : {count:5}\n")
            
            print(f"\n✓ Report generated: {filename}")
        except Exception as e:
            print(f"\n✗ Error generating report: {e}")


def main():
    """Main application."""
    print("="*60)
    print("WEB SCRAPER WITH DATA ANALYSIS")
    print("="*60)
    
    # Get URLs to scrape
    print("\nEnter URLs to scrape (one per line, empty line to finish):")
    urls = []
    while True:
        url = input("> ").strip()
        if not url:
            break
        # Validate URL format
        if not re.match(r'https?://', url):
            print("  Invalid URL (must start with http:// or https://)")
            continue
        urls.append(url)
    
    if not urls:
        print("\nNo URLs provided. Using example URLs...")
        urls = [
            'https://example.com',
            'https://httpbin.org/html',
        ]
    
    # Initialize scraper
    delay = 1.0
    try:
        delay_input = input("\nDelay between requests in seconds (default 1.0): ").strip()
        if delay_input:
            delay = float(delay_input)
    except ValueError:
        print("Invalid delay, using default 1.0 seconds")
    
    scraper = WebScraper(base_url=urls[0], delay=delay)
    
    # Scrape pages
    scraped_data = scraper.scrape_multiple(urls)
    
    if not scraped_data:
        print("\n✗ No data was scraped successfully.")
        return
    
    # Analyze data
    print("\n" + "="*60)
    print("ANALYZING DATA...")
    print("="*60)
    
    analyzer = DataAnalyzer(scraped_data)
    summary = analyzer.generate_summary()
    
    # Display summary
    print(f"\n📊 Analysis Summary:")
    print(f"  - Pages scraped: {summary['total_pages_scraped']}")
    print(f"  - Total links: {summary['total_links_found']}")
    print(f"  - Total words: {summary['total_words_analyzed']}")
    print(f"  - Unique emails: {len(summary['unique_emails'])}")
    print(f"  - Unique phones: {len(summary['unique_phones'])}")
    print(f"\n  Top 10 words:")
    for word, count in summary['top_20_words'][:10]:
        print(f"    {word:15} : {count}")
    
    # Export data
    print("\n" + "="*60)
    print("EXPORTING DATA...")
    print("="*60)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    exporter = DataExporter()
    exporter.export_to_json(
        {'summary': summary, 'pages': scraped_data},
        f'scrape_data_{timestamp}.json'
    )
    exporter.export_to_csv(scraped_data, f'scrape_summary_{timestamp}.csv')
    exporter.generate_report(summary, f'scrape_report_{timestamp}.txt')
    
    # Interactive search
    print("\n" + "="*60)
    print("SEARCH")
    print("="*60)
    keyword = input("\nSearch for keyword (or press Enter to skip): ").strip()
    if keyword:
        results = analyzer.search_keyword(keyword)
        if results:
            print(f"\nFound '{keyword}' in {len(results)} pages:")
            for result in results[:5]:
                print(f"  - {result['url']}")
                print(f"    Title: {result['title']}")
                print(f"    Relevance: {result['relevance']}")
        else:
            print(f"\nNo pages found containing '{keyword}'")
    
    print("\n✓ Scraping and analysis complete!")


if __name__ == "__main__":
    main()


"""
Key Features:

* HTTP Requests: Session management with proper headers and timeouts
* HTML Parsing: BeautifulSoup for extracting content, links, metadata
* Regex Patterns: Extract emails, phone numbers, clean text
* Data Analysis: Word frequency, domain statistics, content metrics
* Multiple Exports: JSON, CSV, and formatted text reports
* Error Handling: Comprehensive try-except blocks throughout
* List/Dict Comprehensions: Used extensively for data processing

Demonstrates:

* requests library for HTTP operations
* BeautifulSoup for HTML parsing
* Multiple regex patterns for data extraction
* Counter and defaultdict from collections
* File writing in multiple formats
* Exception handling for network errors
* Data aggregation and analysis
* Polite scraping with delays
"""