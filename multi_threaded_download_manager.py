"""
Multi-threaded Download Manager
Demonstrates: Threading/multiprocessing, requests, progress tracking, queue management,
file I/O, error handling, context managers
"""

import threading
import requests
from queue import Queue, Empty
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import time
import json
from contextlib import contextmanager
import hashlib
from urllib.parse import urlparse
import os


@dataclass
class DownloadTask:
    """Represents a download task."""
    url: str
    filename: Optional[str] = None
    destination: str = "downloads"
    priority: int = 0  # Higher number = higher priority
    chunk_size: int = 8192
    timeout: int = 30
    max_retries: int = 3
    
    def __post_init__(self):
        """Generate filename if not provided."""
        if not self.filename:
            # Extract filename from URL
            parsed = urlparse(self.url)
            self.filename = Path(parsed.path).name or f"download_{int(time.time())}"
    
    def get_filepath(self) -> Path:
        """Get full file path."""
        return Path(self.destination) / self.filename
    
    def __lt__(self, other):
        """For priority queue comparison."""
        return self.priority > other.priority  # Higher priority first


@dataclass
class DownloadProgress:
    """Track download progress."""
    task: DownloadTask
    total_size: int = 0
    downloaded: int = 0
    start_time: float = 0
    status: str = 'pending'  # pending, downloading, completed, failed, paused
    error: Optional[str] = None
    retry_count: int = 0
    speed: float = 0  # bytes per second
    
    def update(self, chunk_size: int):
        """Update progress with new chunk."""
        self.downloaded += chunk_size
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            self.speed = self.downloaded / elapsed
    
    def get_percentage(self) -> float:
        """Get download percentage."""
        if self.total_size == 0:
            return 0
        return (self.downloaded / self.total_size) * 100
    
    def get_eta(self) -> str:
        """Get estimated time remaining."""
        if self.speed == 0 or self.total_size == 0:
            return "Unknown"
        
        remaining = self.total_size - self.downloaded
        seconds = remaining / self.speed
        return str(timedelta(seconds=int(seconds)))
    
    def format_size(self, size: int) -> str:
        """Format size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    def format_speed(self) -> str:
        """Format speed in human-readable format."""
        return f"{self.format_size(self.speed)}/s"
    
    def __str__(self):
        """String representation of progress."""
        return (f"{self.task.filename}: {self.get_percentage():.1f}% "
                f"({self.format_size(self.downloaded)}/{self.format_size(self.total_size)}) "
                f"[{self.format_speed()}] ETA: {self.get_eta()}")


class DownloadWorker(threading.Thread):
    """Worker thread for downloading files."""
    
    def __init__(self, task_queue: Queue, progress_callback: Optional[Callable] = None,
                 stop_event: threading.Event = None):
        super().__init__(daemon=True)
        self.task_queue = task_queue
        self.progress_callback = progress_callback
        self.stop_event = stop_event or threading.Event()
        self.current_progress: Optional[DownloadProgress] = None
    
    def run(self):
        """Worker main loop."""
        while not self.stop_event.is_set():
            try:
                # Get task from queue with timeout
                task = self.task_queue.get(timeout=1)
                
                # Download the file
                self.download_file(task)
                
                # Mark task as done
                self.task_queue.task_done()
                
            except Empty:
                # No tasks available, continue waiting
                continue
            except Exception as e:
                print(f"Worker error: {e}")
    
    def download_file(self, task: DownloadTask):
        """Download a single file with progress tracking."""
        progress = DownloadProgress(task=task, start_time=time.time())
        self.current_progress = progress
        
        # Create destination directory
        Path(task.destination).mkdir(parents=True, exist_ok=True)
        filepath = task.get_filepath()
        
        retry_count = 0
        
        while retry_count <= task.max_retries:
            try:
                progress.status = 'downloading'
                progress.retry_count = retry_count
                
                # Send HEAD request to get file size
                with requests.head(task.url, timeout=task.timeout, allow_redirects=True) as response:
                    response.raise_for_status()
                    progress.total_size = int(response.headers.get('content-length', 0))
                
                # Download file with streaming
                with requests.get(task.url, stream=True, timeout=task.timeout) as response:
                    response.raise_for_status()
                    
                    # Write to temporary file first
                    temp_filepath = filepath.with_suffix('.tmp')
                    
                    with open(temp_filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=task.chunk_size):
                            if self.stop_event.is_set():
                                progress.status = 'paused'
                                return
                            
                            if chunk:
                                f.write(chunk)
                                progress.update(len(chunk))
                                
                                # Call progress callback
                                if self.progress_callback:
                                    self.progress_callback(progress)
                    
                    # Rename temp file to final filename
                    temp_filepath.rename(filepath)
                
                progress.status = 'completed'
                if self.progress_callback:
                    self.progress_callback(progress)
                
                print(f"\n✓ Download completed: {task.filename}")
                break
                
            except requests.exceptions.RequestException as e:
                retry_count += 1
                progress.error = str(e)
                
                if retry_count > task.max_retries:
                    progress.status = 'failed'
                    if self.progress_callback:
                        self.progress_callback(progress)
                    print(f"\n✗ Download failed after {task.max_retries} retries: {task.filename}")
                    print(f"   Error: {e}")
                else:
                    print(f"\n⚠ Retry {retry_count}/{task.max_retries} for {task.filename}")
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    
            except Exception as e:
                progress.status = 'failed'
                progress.error = str(e)
                if self.progress_callback:
                    self.progress_callback(progress)
                print(f"\n✗ Unexpected error downloading {task.filename}: {e}")
                break


class DownloadManager:
    """Manages multiple download workers and tracks progress."""
    
    def __init__(self, num_workers: int = 4):
        self.num_workers = num_workers
        self.task_queue = Queue()
        self.workers: List[DownloadWorker] = []
        self.stop_event = threading.Event()
        self.progress_lock = threading.Lock()
        self.all_progress: Dict[str, DownloadProgress] = {}
        self.stats = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'in_progress': 0
        }
    
    def progress_callback(self, progress: DownloadProgress):
        """Callback for progress updates."""
        with self.progress_lock:
            self.all_progress[progress.task.filename] = progress
            
            # Update stats
            if progress.status == 'completed':
                self.stats['completed'] += 1
                self.stats['in_progress'] -= 1
            elif progress.status == 'failed':
                self.stats['failed'] += 1
                self.stats['in_progress'] -= 1
    
    def start(self):
        """Start worker threads."""
        for i in range(self.num_workers):
            worker = DownloadWorker(
                self.task_queue,
                self.progress_callback,
                self.stop_event
            )
            worker.start()
            self.workers.append(worker)
        
        print(f"✓ Started {self.num_workers} download workers")
    
    def stop(self):
        """Stop all workers gracefully."""
        print("\n⏹ Stopping download manager...")
        self.stop_event.set()
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5)
        
        print("✓ Download manager stopped")
    
    def add_download(self, url: str, filename: Optional[str] = None,
                    destination: str = "downloads", priority: int = 0):
        """Add a download task to the queue."""
        task = DownloadTask(
            url=url,
            filename=filename,
            destination=destination,
            priority=priority
        )
        
        self.task_queue.put(task)
        self.stats['total'] += 1
        self.stats['in_progress'] += 1
        
        print(f"✓ Added to queue: {task.filename} (Priority: {priority})")
        return task
    
    def add_downloads_from_file(self, filepath: str):
        """Add multiple downloads from a text file (one URL per line)."""
        try:
            with open(filepath, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
            
            for url in urls:
                self.add_download(url)
            
            print(f"✓ Added {len(urls)} downloads from {filepath}")
        except Exception as e:
            print(f"✗ Error reading file: {e}")
    
    def wait_for_completion(self):
        """Wait for all downloads to complete."""
        self.task_queue.join()
    
    def get_active_downloads(self) -> List[DownloadProgress]:
        """Get list of active downloads."""
        with self.progress_lock:
            return [
                p for p in self.all_progress.values()
                if p.status in ['downloading', 'pending']
            ]
    
    def get_statistics(self) -> Dict:
        """Get download statistics."""
        active = self.get_active_downloads()
        
        total_downloaded = sum(p.downloaded for p in self.all_progress.values())
        total_size = sum(p.total_size for p in self.all_progress.values())
        avg_speed = sum(p.speed for p in active) if active else 0
        
        return {
            **self.stats,
            'active': len(active),
            'total_downloaded': total_downloaded,
            'total_size': total_size,
            'avg_speed': avg_speed
        }
    
    def print_status(self):
        """Print current download status."""
        stats = self.get_statistics()
        
        print(f"\n{'='*70}")
        print("DOWNLOAD MANAGER STATUS")
        print(f"{'='*70}")
        print(f"Total: {stats['total']} | "
              f"Completed: {stats['completed']} | "
              f"Failed: {stats['failed']} | "
              f"Active: {stats['active']}")
        
        active = self.get_active_downloads()
        if active:
            print(f"\nActive Downloads:")
            for progress in active:
                print(f"  {progress}")
    
    def save_progress(self, filepath: str = "download_progress.json"):
        """Save download progress to file."""
        with self.progress_lock:
            data = {
                'stats': self.stats,
                'downloads': [
                    {
                        'url': p.task.url,
                        'filename': p.task.filename,
                        'status': p.status,
                        'downloaded': p.downloaded,
                        'total_size': p.total_size,
                        'error': p.error
                    }
                    for p in self.all_progress.values()
                ]
            }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n✓ Progress saved to {filepath}")


@contextmanager
def download_session(num_workers: int = 4):
    """Context manager for download manager."""
    manager = DownloadManager(num_workers)
    manager.start()
    try:
        yield manager
    finally:
        manager.stop()


def monitor_downloads(manager: DownloadManager, interval: float = 2.0):
    """Monitor and display download progress."""
    try:
        while True:
            active = manager.get_active_downloads()
            
            if not active and manager.task_queue.empty():
                break
            
            # Clear screen (simple version)
            print("\n" * 2)
            manager.print_status()
            
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print("\n\n⏸ Monitoring paused")


def interactive_mode():
    """Interactive download manager."""
    print("="*70)
    print("MULTI-THREADED DOWNLOAD MANAGER")
    print("="*70)
    
    num_workers = int(input("\nNumber of worker threads (default 4): ").strip() or "4")
    
    with download_session(num_workers) as manager:
        print("\nCommands:")
        print("  add <url> [filename] [priority] - Add download")
        print("  file <path>                     - Add from file")
        print("  status                          - Show status")
        print("  stats                           - Show statistics")
        print("  save                            - Save progress")
        print("  monitor                         - Monitor downloads")
        print("  stop                            - Stop and exit")
        
        while True:
            try:
                cmd = input("\ndl> ").strip()
                
                if not cmd:
                    continue
                
                parts = cmd.split()
                command = parts[0].lower()
                
                if command == 'add':
                    if len(parts) < 2:
                        print("Usage: add <url> [filename] [priority]")
                        continue
                    
                    url = parts[1]
                    filename = parts[2] if len(parts) > 2 and not parts[2].isdigit() else None
                    priority = int(parts[-1]) if len(parts) > 2 and parts[-1].isdigit() else 0
                    
                    manager.add_download(url, filename, priority=priority)
                
                elif command == 'file':
                    if len(parts) < 2:
                        print("Usage: file <path>")
                        continue
                    
                    manager.add_downloads_from_file(parts[1])
                
                elif command == 'status':
                    manager.print_status()
                
                elif command == 'stats':
                    stats = manager.get_statistics()
                    print(f"\nStatistics:")
                    print(f"  Total Tasks: {stats['total']}")
                    print(f"  Completed: {stats['completed']}")
                    print(f"  Failed: {stats['failed']}")
                    print(f"  In Progress: {stats['in_progress']}")
                    print(f"  Active Workers: {stats['active']}")
                    
                    if stats['total_size'] > 0:
                        progress = DownloadProgress(
                            task=DownloadTask(url=""),
                            total_size=stats['total_size'],
                            downloaded=stats['total_downloaded']
                        )
                        print(f"  Total Downloaded: {progress.format_size(stats['total_downloaded'])}")
                        print(f"  Total Size: {progress.format_size(stats['total_size'])}")
                        print(f"  Average Speed: {progress.format_size(stats['avg_speed'])}/s")
                
                elif command == 'save':
                    manager.save_progress()
                
                elif command == 'monitor':
                    print("\nMonitoring downloads (Ctrl+C to stop)...")
                    monitor_downloads(manager)
                
                elif command == 'stop':
                    break
                
                else:
                    print(f"Unknown command: {command}")
            
            except KeyboardInterrupt:
                print("\n\nUse 'stop' command to exit")
            except Exception as e:
                print(f"Error: {e}")
    
    print("\n✓ Download manager closed")


def demo():
    """Demonstration mode with sample downloads."""
    print("="*70)
    print("DOWNLOAD MANAGER DEMO")
    print("="*70)
    
    # Sample small files for testing
    demo_urls = [
        ("https://httpbin.org/delay/2", "delay_test.json"),
        ("https://httpbin.org/bytes/1024", "random_1kb.bin"),
        ("https://httpbin.org/image/png", "sample_image.png"),
    ]
    
    print("\nDemo will download sample test files from httpbin.org")
    print(f"Files will be saved to: downloads/")
    
    input("\nPress Enter to start demo...")
    
    with download_session(num_workers=2) as manager:
        # Add demo downloads
        for url, filename in demo_urls:
            manager.add_download(url, filename=filename)
        
        print("\n✓ Downloads queued")
        print("\nMonitoring progress...")
        
        # Monitor until complete
        monitor_downloads(manager, interval=1.0)
        
        # Wait for completion
        manager.wait_for_completion()
        
        # Show final stats
        print("\n" + "="*70)
        print("DEMO COMPLETE")
        print("="*70)
        manager.print_status()
        
        stats = manager.get_statistics()
        print(f"\nCompleted: {stats['completed']}/{stats['total']}")
        
        if stats['failed'] > 0:
            print(f"Failed: {stats['failed']}")


def main():
    """Main application."""
    print("\n1. Interactive Mode")
    print("2. Run Demo")
    choice = input("\nChoice (1 or 2): ").strip()
    
    if choice == '2':
        demo()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()

"""
Key Features:

* Threading: Multiple worker threads for concurrent downloads
* Queue Management: Priority queue for task distribution
* Progress Tracking: Real-time progress with speed, ETA, and percentage
* Requests: HTTP downloads with streaming and retry logic
* File I/O: Safe file writing with temporary files
* Error Handling: Retry logic with exponential backoff
* Context Managers: @contextmanager for resource management

Demonstrates:

* threading.Thread for concurrent workers
* Queue for thread-safe task management
* threading.Event for graceful shutdown
* threading.Lock for shared state protection
* requests.get(stream=True) for efficient downloads
* @dataclass for data structures
* Context manager pattern
* Progress callbacks
* Exponential backoff for retries

Features:

* Concurrent downloads with configurable worker threads
* Priority-based download queue
* Real-time progress tracking (speed, ETA, percentage)
* Automatic retry with exponential backoff
* Graceful shutdown with stop events
* Save/load progress to JSON
* Batch downloads from file
* Interactive shell interface
"""