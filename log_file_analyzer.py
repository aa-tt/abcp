"""
Log File Analyzer
Demonstrates: File reading, regex patterns, collections (Counter, defaultdict),
datetime parsing, generators, list comprehensions, statistics
"""

import re
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import Dict, List, Generator, Optional, Tuple
import statistics
import json
from pathlib import Path


class LogEntry:
    """Represents a single log entry."""
    
    # Common log patterns
    PATTERNS = {
        'apache': re.compile(
            r'(?P<ip>[\d.]+) - - \[(?P<timestamp>[^\]]+)\] '
            r'"(?P<method>\w+) (?P<path>[^\s]+) HTTP/[\d.]+" '
            r'(?P<status>\d+) (?P<size>\d+)'
        ),
        'nginx': re.compile(
            r'(?P<ip>[\d.]+) - - \[(?P<timestamp>[^\]]+)\] '
            r'"(?P<method>\w+) (?P<path>[^\s]+) HTTP/[\d.]+" '
            r'(?P<status>\d+) (?P<size>\d+) "(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"'
        ),
        'syslog': re.compile(
            r'(?P<timestamp>\w+\s+\d+\s+\d+:\d+:\d+) (?P<host>\S+) '
            r'(?P<process>\S+?)(\[(?P<pid>\d+)\])?: (?P<message>.+)'
        ),
        'python': re.compile(
            r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - '
            r'(?P<level>\w+) - (?P<logger>\S+) - (?P<message>.+)'
        ),
        'generic': re.compile(
            r'(?P<timestamp>\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[\d.,]*)\s*'
            r'(?:\[(?P<level>\w+)\])?\s*(?P<message>.+)'
        )
    }
    
    def __init__(self, raw_line: str, log_format: str = 'generic'):
        self.raw_line = raw_line.strip()
        self.log_format = log_format
        self.data: Dict = {}
        self.timestamp: Optional[datetime] = None
        self.parse()
    
    def parse(self):
        """Parse log line using regex patterns."""
        pattern = self.PATTERNS.get(self.log_format)
        if not pattern:
            return
        
        match = pattern.search(self.raw_line)
        if match:
            self.data = match.groupdict()
            self.parse_timestamp()
    
    def parse_timestamp(self):
        """Parse timestamp from log entry using datetime parsing."""
        if 'timestamp' not in self.data:
            return
        
        timestamp_str = self.data['timestamp']
        
        # Try various timestamp formats
        formats = [
            '%d/%b/%Y:%H:%M:%S %z',  # Apache/Nginx: 10/Oct/2000:13:55:36 -0700
            '%Y-%m-%d %H:%M:%S,%f',  # Python logging: 2024-01-26 10:30:45,123
            '%Y-%m-%dT%H:%M:%S',     # ISO format: 2024-01-26T10:30:45
            '%Y-%m-%d %H:%M:%S',     # Simple: 2024-01-26 10:30:45
            '%b %d %H:%M:%S',        # Syslog: Jan 26 10:30:45
        ]
        
        for fmt in formats:
            try:
                self.timestamp = datetime.strptime(timestamp_str, fmt)
                # For syslog format, add current year
                if fmt == '%b %d %H:%M:%S':
                    self.timestamp = self.timestamp.replace(year=datetime.now().year)
                return
            except ValueError:
                continue
    
    def get_level(self) -> str:
        """Get log level."""
        return self.data.get('level', 'INFO').upper()
    
    def get_status_code(self) -> Optional[int]:
        """Get HTTP status code if present."""
        status = self.data.get('status')
        return int(status) if status else None
    
    def __str__(self):
        return self.raw_line
    
    def __repr__(self):
        return f"LogEntry(format={self.log_format}, timestamp={self.timestamp})"


class LogFileReader:
    """Read log files with generator for memory efficiency."""
    
    def __init__(self, filepath: str, log_format: str = 'generic'):
        self.filepath = filepath
        self.log_format = log_format
    
    def read_lines(self) -> Generator[str, None, None]:
        """Generator that yields lines from log file."""
        try:
            with open(self.filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if line:  # Skip empty lines
                        yield line
        except FileNotFoundError:
            print(f"Error: File '{self.filepath}' not found")
        except Exception as e:
            print(f"Error reading file: {e}")
    
    def read_entries(self) -> Generator[LogEntry, None, None]:
        """Generator that yields parsed log entries."""
        for line in self.read_lines():
            entry = LogEntry(line, self.log_format)
            if entry.data:  # Only yield successfully parsed entries
                yield entry
    
    def read_entries_with_filter(self, filter_func) -> Generator[LogEntry, None, None]:
        """Generator that yields filtered log entries."""
        for entry in self.read_entries():
            if filter_func(entry):
                yield entry


class LogAnalyzer:
    """Analyze log files with various statistical methods."""
    
    def __init__(self):
        self.entries: List[LogEntry] = []
        self.errors_by_type = Counter()
        self.requests_by_hour = defaultdict(int)
        self.requests_by_path = Counter()
        self.requests_by_ip = Counter()
        self.status_codes = Counter()
        self.log_levels = Counter()
    
    def add_entry(self, entry: LogEntry):
        """Add a log entry to analysis."""
        self.entries.append(entry)
        
        # Analyze log level
        level = entry.get_level()
        self.log_levels[level] += 1
        
        # Analyze timestamp patterns
        if entry.timestamp:
            hour = entry.timestamp.hour
            self.requests_by_hour[hour] += 1
        
        # Analyze HTTP requests (for web server logs)
        if 'path' in entry.data:
            self.requests_by_path[entry.data['path']] += 1
        
        if 'ip' in entry.data:
            self.requests_by_ip[entry.data['ip']] += 1
        
        if 'status' in entry.data:
            status = entry.get_status_code()
            if status:
                self.status_codes[status] += 1
    
    def analyze_errors(self) -> Dict:
        """Analyze error patterns using regex."""
        error_patterns = {
            'Database Error': re.compile(r'(database|sql|connection)\s+(error|failed|timeout)', re.I),
            'Memory Error': re.compile(r'(memory|out of memory|oom)', re.I),
            'Authentication Error': re.compile(r'(auth|login|permission)\s+(failed|denied|error)', re.I),
            'Network Error': re.compile(r'(network|socket|connection)\s+(error|timeout|refused)', re.I),
            'File Error': re.compile(r'(file|directory)\s+(not found|error|permission denied)', re.I),
        }
        
        error_details = defaultdict(list)
        
        for entry in self.entries:
            message = entry.data.get('message', entry.raw_line)
            
            for error_type, pattern in error_patterns.items():
                if pattern.search(message):
                    error_details[error_type].append({
                        'timestamp': entry.timestamp.isoformat() if entry.timestamp else 'N/A',
                        'message': message[:100]  # First 100 chars
                    })
        
        return dict(error_details)
    
    def find_patterns(self, pattern: str, case_sensitive: bool = False) -> List[LogEntry]:
        """Find entries matching a regex pattern using list comprehension."""
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)
        
        # Using list comprehension with regex matching
        return [
            entry for entry in self.entries
            if regex.search(entry.raw_line)
        ]
    
    def get_time_range(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Get time range of log entries."""
        timestamps = [e.timestamp for e in self.entries if e.timestamp]
        if not timestamps:
            return None, None
        return min(timestamps), max(timestamps)
    
    def get_hourly_stats(self) -> Dict:
        """Get hourly request statistics using defaultdict."""
        if not self.requests_by_hour:
            return {}
        
        return {
            'requests_by_hour': dict(sorted(self.requests_by_hour.items())),
            'peak_hour': max(self.requests_by_hour.items(), key=lambda x: x[1]),
            'quiet_hour': min(self.requests_by_hour.items(), key=lambda x: x[1]),
            'avg_requests_per_hour': statistics.mean(self.requests_by_hour.values()),
        }
    
    def get_status_code_stats(self) -> Dict:
        """Analyze HTTP status codes using Counter."""
        if not self.status_codes:
            return {}
        
        total = sum(self.status_codes.values())
        
        # Group by status code category using dict comprehension
        categories = {
            '2xx (Success)': sum(count for code, count in self.status_codes.items() if 200 <= code < 300),
            '3xx (Redirect)': sum(count for code, count in self.status_codes.items() if 300 <= code < 400),
            '4xx (Client Error)': sum(count for code, count in self.status_codes.items() if 400 <= code < 500),
            '5xx (Server Error)': sum(count for code, count in self.status_codes.items() if 500 <= code < 600),
        }
        
        return {
            'total_requests': total,
            'by_category': categories,
            'top_10_status_codes': dict(self.status_codes.most_common(10)),
            'error_rate': (categories['4xx (Client Error)'] + categories['5xx (Server Error)']) / total * 100 if total > 0 else 0
        }
    
    def get_ip_stats(self) -> Dict:
        """Analyze IP addresses using Counter."""
        if not self.requests_by_ip:
            return {}
        
        return {
            'unique_ips': len(self.requests_by_ip),
            'top_10_ips': dict(self.requests_by_ip.most_common(10)),
            'avg_requests_per_ip': statistics.mean(self.requests_by_ip.values()),
            'median_requests_per_ip': statistics.median(self.requests_by_ip.values()),
        }
    
    def get_log_level_stats(self) -> Dict:
        """Analyze log levels using Counter."""
        if not self.log_levels:
            return {}
        
        total = sum(self.log_levels.values())
        
        return {
            'total_entries': total,
            'by_level': dict(self.log_levels.most_common()),
            'error_percentage': (self.log_levels.get('ERROR', 0) + self.log_levels.get('CRITICAL', 0)) / total * 100 if total > 0 else 0
        }
    
    def generate_summary(self) -> Dict:
        """Generate comprehensive summary using statistics."""
        start_time, end_time = self.get_time_range()
        
        summary = {
            'total_entries': len(self.entries),
            'time_range': {
                'start': start_time.isoformat() if start_time else 'N/A',
                'end': end_time.isoformat() if end_time else 'N/A',
                'duration': str(end_time - start_time) if start_time and end_time else 'N/A'
            },
            'log_levels': self.get_log_level_stats(),
            'hourly_stats': self.get_hourly_stats(),
            'status_codes': self.get_status_code_stats(),
            'ip_stats': self.get_ip_stats(),
            'top_10_paths': dict(self.requests_by_path.most_common(10)) if self.requests_by_path else {},
        }
        
        return summary


class LogReportGenerator:
    """Generate reports from log analysis."""
    
    @staticmethod
    def generate_text_report(analyzer: LogAnalyzer, filename: str):
        """Generate text report."""
        summary = analyzer.generate_summary()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("LOG ANALYSIS REPORT\n")
            f.write("="*70 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Summary
            f.write(f"Total Log Entries: {summary['total_entries']}\n")
            f.write(f"Time Range: {summary['time_range']['start']} to {summary['time_range']['end']}\n")
            f.write(f"Duration: {summary['time_range']['duration']}\n\n")
            
            # Log Levels
            if summary['log_levels']:
                f.write("-"*70 + "\n")
                f.write("LOG LEVELS\n")
                f.write("-"*70 + "\n")
                for level, count in summary['log_levels']['by_level'].items():
                    percentage = count / summary['log_levels']['total_entries'] * 100
                    f.write(f"{level:15} : {count:6} ({percentage:5.1f}%)\n")
                f.write(f"\nError Rate: {summary['log_levels']['error_percentage']:.2f}%\n\n")
            
            # Hourly Stats
            if summary['hourly_stats']:
                f.write("-"*70 + "\n")
                f.write("HOURLY DISTRIBUTION\n")
                f.write("-"*70 + "\n")
                peak_hour, peak_count = summary['hourly_stats']['peak_hour']
                f.write(f"Peak Hour: {peak_hour}:00 with {peak_count} requests\n")
                f.write(f"Average Requests/Hour: {summary['hourly_stats']['avg_requests_per_hour']:.1f}\n\n")
            
            # Status Codes
            if summary['status_codes']:
                f.write("-"*70 + "\n")
                f.write("HTTP STATUS CODES\n")
                f.write("-"*70 + "\n")
                for category, count in summary['status_codes']['by_category'].items():
                    percentage = count / summary['status_codes']['total_requests'] * 100
                    f.write(f"{category:20} : {count:6} ({percentage:5.1f}%)\n")
                f.write(f"\nTotal Error Rate: {summary['status_codes']['error_rate']:.2f}%\n\n")
                
                f.write("Top Status Codes:\n")
                for code, count in summary['status_codes']['top_10_status_codes'].items():
                    f.write(f"  {code}: {count}\n")
                f.write("\n")
            
            # IP Stats
            if summary['ip_stats']:
                f.write("-"*70 + "\n")
                f.write("IP ADDRESS STATISTICS\n")
                f.write("-"*70 + "\n")
                f.write(f"Unique IPs: {summary['ip_stats']['unique_ips']}\n")
                f.write(f"Avg Requests/IP: {summary['ip_stats']['avg_requests_per_ip']:.1f}\n")
                f.write(f"Median Requests/IP: {summary['ip_stats']['median_requests_per_ip']:.1f}\n\n")
                
                f.write("Top 10 IPs:\n")
                for ip, count in summary['ip_stats']['top_10_ips'].items():
                    f.write(f"  {ip:15} : {count} requests\n")
                f.write("\n")
            
            # Top Paths
            if summary['top_10_paths']:
                f.write("-"*70 + "\n")
                f.write("TOP 10 REQUESTED PATHS\n")
                f.write("-"*70 + "\n")
                for path, count in summary['top_10_paths'].items():
                    f.write(f"{count:6} : {path}\n")
        
        print(f"\n✓ Report generated: {filename}")
    
    @staticmethod
    def generate_json_report(analyzer: LogAnalyzer, filename: str):
        """Generate JSON report."""
        summary = analyzer.generate_summary()
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"✓ JSON report generated: {filename}")


def create_sample_log_file(filename: str, log_type: str = 'apache'):
    """Create a sample log file for testing."""
    
    samples = {
        'apache': [
            '192.168.1.100 - - [26/Jan/2026:10:30:45 +0000] "GET /index.html HTTP/1.1" 200 1234',
            '192.168.1.101 - - [26/Jan/2026:10:31:15 +0000] "POST /api/login HTTP/1.1" 401 567',
            '192.168.1.100 - - [26/Jan/2026:10:32:00 +0000] "GET /style.css HTTP/1.1" 200 4567',
            '192.168.1.102 - - [26/Jan/2026:11:15:30 +0000] "GET /api/data HTTP/1.1" 500 89',
            '192.168.1.100 - - [26/Jan/2026:11:20:00 +0000] "GET /about.html HTTP/1.1" 200 2345',
            '192.168.1.103 - - [26/Jan/2026:12:00:00 +0000] "POST /api/submit HTTP/1.1" 201 123',
            '192.168.1.101 - - [26/Jan/2026:13:45:30 +0000] "GET /contact.html HTTP/1.1" 404 456',
            '192.168.1.100 - - [26/Jan/2026:14:30:00 +0000] "GET /index.html HTTP/1.1" 200 1234',
        ],
        'python': [
            '2026-01-26 10:30:45,123 - INFO - app.main - Application started',
            '2026-01-26 10:31:15,456 - WARNING - app.database - Database connection slow',
            '2026-01-26 10:32:00,789 - ERROR - app.auth - Authentication failed for user: admin',
            '2026-01-26 11:15:30,012 - CRITICAL - app.database - Database connection timeout',
            '2026-01-26 11:20:00,345 - INFO - app.main - Processing request',
            '2026-01-26 12:00:00,678 - ERROR - app.network - Network connection refused',
            '2026-01-26 13:45:30,901 - WARNING - app.memory - Memory usage at 85%',
            '2026-01-26 14:30:00,234 - INFO - app.main - Task completed successfully',
        ]
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        for line in samples.get(log_type, samples['apache']):
            f.write(line + '\n')
    
    print(f"✓ Created sample log file: {filename}")


def main():
    """Main application."""
    print("="*70)
    print("LOG FILE ANALYZER")
    print("="*70)
    
    # Get log file
    print("\n1. Analyze existing log file")
    print("2. Create and analyze sample log file")
    choice = input("\nChoice (1 or 2): ").strip()
    
    if choice == '2':
        print("\nSelect log format:")
        print("1. Apache/Nginx (Web Server)")
        print("2. Python Logging")
        fmt_choice = input("Choice: ").strip()
        
        log_format = 'apache' if fmt_choice == '1' else 'python'
        filename = f'sample_{log_format}.log'
        
        create_sample_log_file(filename, log_format)
        filepath = filename
    else:
        filepath = input("\nEnter log file path: ").strip()
        
        print("\nSelect log format:")
        print("1. Apache")
        print("2. Nginx")
        print("3. Python Logging")
        print("4. Syslog")
        print("5. Generic")
        fmt_choice = input("Choice (default: 5): ").strip() or '5'
        
        format_map = {'1': 'apache', '2': 'nginx', '3': 'python', '4': 'syslog', '5': 'generic'}
        log_format = format_map.get(fmt_choice, 'generic')
    
    if not Path(filepath).exists():
        print(f"\n✗ File not found: {filepath}")
        return
    
    # Read and analyze log file
    print(f"\n📊 Analyzing log file: {filepath}")
    print("Format:", log_format)
    
    reader = LogFileReader(filepath, log_format)
    analyzer = LogAnalyzer()
    
    # Process entries using generator (memory efficient)
    entry_count = 0
    for entry in reader.read_entries():
        analyzer.add_entry(entry)
        entry_count += 1
    
    print(f"\n✓ Processed {entry_count} log entries")
    
    # Generate summary
    print("\n" + "="*70)
    print("ANALYSIS SUMMARY")
    print("="*70)
    
    summary = analyzer.generate_summary()
    
    print(f"\nTotal Entries: {summary['total_entries']}")
    print(f"Time Range: {summary['time_range']['start']} to {summary['time_range']['end']}")
    print(f"Duration: {summary['time_range']['duration']}")
    
    # Log Levels
    if summary['log_levels']:
        print(f"\n--- Log Levels ---")
        for level, count in summary['log_levels']['by_level'].items():
            print(f"  {level}: {count}")
        print(f"Error Rate: {summary['log_levels']['error_percentage']:.2f}%")
    
    # Status Codes
    if summary['status_codes']:
        print(f"\n--- HTTP Status Codes ---")
        print(f"Total Requests: {summary['status_codes']['total_requests']}")
        print(f"Error Rate: {summary['status_codes']['error_rate']:.2f}%")
        print("\nTop Status Codes:")
        for code, count in list(summary['status_codes']['top_10_status_codes'].items())[:5]:
            print(f"  {code}: {count}")
    
    # Search functionality
    print("\n" + "="*70)
    print("SEARCH")
    print("="*70)
    pattern = input("\nSearch for pattern (regex, or Enter to skip): ").strip()
    
    if pattern:
        results = analyzer.find_patterns(pattern)
        print(f"\nFound {len(results)} matching entries:")
        for entry in results[:10]:  # Show first 10
            print(f"  {entry}")
        if len(results) > 10:
            print(f"  ... and {len(results) - 10} more")
    
    # Error analysis
    print("\n" + "="*70)
    print("ERROR ANALYSIS")
    print("="*70)
    
    errors = analyzer.analyze_errors()
    if errors:
        for error_type, occurrences in errors.items():
            print(f"\n{error_type}: {len(occurrences)} occurrences")
            for occ in occurrences[:3]:  # Show first 3
                print(f"  [{occ['timestamp']}] {occ['message']}")
    else:
        print("\nNo specific error patterns detected.")
    
    # Generate reports
    print("\n" + "="*70)
    print("GENERATE REPORTS")
    print("="*70)
    
    if input("\nGenerate text report? (y/n): ").lower() == 'y':
        report_filename = f"log_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        LogReportGenerator.generate_text_report(analyzer, report_filename)
    
    if input("Generate JSON report? (y/n): ").lower() == 'y':
        json_filename = f"log_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        LogReportGenerator.generate_json_report(analyzer, json_filename)
    
    print("\n✓ Analysis complete!")


if __name__ == "__main__":
    main()


"""
Key Features:

* File Reading: Efficient file reading with error handling
* Regex Patterns: Multiple patterns for Apache, Nginx, Python, Syslog formats
* Collections: Counter for frequency counting, defaultdict for aggregation
* Datetime Parsing: Parse multiple timestamp formats
* Generators: Memory-efficient log reading with yield
* List Comprehensions: Filter and transform data efficiently
* Statistics: Mean, median calculations using statistics module

Demonstrates:

* Generators with yield for memory-efficient file reading
* Multiple regex patterns for different log formats
* Counter.most_common() for frequency analysis
* defaultdict for grouping data
* DateTime parsing with multiple format attempts
* List comprehensions for filtering
* Statistical analysis with mean/median
* Error pattern detection with regex
* JSON and text report generation

Features:

* Parse multiple log formats (Apache, Nginx, Python, Syslog)
* Hourly traffic analysis
* HTTP status code statistics
* IP address tracking
* Error pattern detection
* Search with regex
* Generate text and JSON reports
* Sample log file generation for testing"""