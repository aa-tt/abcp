"""
API Client with Caching
Demonstrates: Requests, decorators (caching), JSON, file I/O, exception handling,
context managers, datetime operations
"""

import requests
import json
import hashlib
from typing import Dict, Any, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta
from contextlib import contextmanager
from pathlib import Path
import time
import pickle
from abc import ABC, abstractmethod


# Cache Backend Abstract Class
class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, expires_at: datetime):
        """Set value in cache with expiration."""
        pass
    
    @abstractmethod
    def delete(self, key: str):
        """Delete value from cache."""
        pass
    
    @abstractmethod
    def clear(self):
        """Clear all cache."""
        pass


class MemoryCache(CacheBackend):
    """In-memory cache backend."""
    
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from memory cache."""
        if key in self.cache:
            entry = self.cache[key]
            if datetime.now() < entry['expires_at']:
                return entry['value']
            else:
                # Expired, remove from cache
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any, expires_at: datetime):
        """Set value in memory cache."""
        self.cache[key] = {
            'value': value,
            'expires_at': expires_at,
            'created_at': datetime.now()
        }
    
    def delete(self, key: str):
        """Delete from memory cache."""
        if key in self.cache:
            del self.cache[key]
    
    def clear(self):
        """Clear memory cache."""
        self.cache.clear()
    
    def __len__(self):
        return len(self.cache)


class FileCache(CacheBackend):
    """File-based cache backend using JSON."""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for key."""
        return self.cache_dir / f"{key}.json"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from file cache."""
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                entry = json.load(f)
            
            expires_at = datetime.fromisoformat(entry['expires_at'])
            
            if datetime.now() < expires_at:
                return entry['value']
            else:
                # Expired, delete file
                cache_path.unlink()
                return None
        
        except Exception as e:
            print(f"Error reading cache: {e}")
            return None
    
    def set(self, key: str, value: Any, expires_at: datetime):
        """Set value in file cache."""
        cache_path = self._get_cache_path(key)
        
        entry = {
            'value': value,
            'expires_at': expires_at.isoformat(),
            'created_at': datetime.now().isoformat()
        }
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(entry, f, indent=2)
        except Exception as e:
            print(f"Error writing cache: {e}")
    
    def delete(self, key: str):
        """Delete from file cache."""
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
    
    def clear(self):
        """Clear file cache."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()


# Caching Decorator
def cache_response(ttl: int = 300, backend: Optional[CacheBackend] = None):
    """
    Decorator to cache API responses.
    
    Args:
        ttl: Time to live in seconds (default: 300 = 5 minutes)
        backend: Cache backend to use (default: MemoryCache)
    """
    if backend is None:
        backend = MemoryCache()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key_parts = [func.__name__]
            cache_key_parts.extend(str(arg) for arg in args[1:])  # Skip self
            cache_key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            
            cache_key_string = "_".join(cache_key_parts)
            cache_key = hashlib.md5(cache_key_string.encode()).hexdigest()
            
            # Try to get from cache
            cached_value = backend.get(cache_key)
            if cached_value is not None:
                print(f"  💾 Cache HIT for {func.__name__}")
                return cached_value
            
            print(f"  🌐 Cache MISS for {func.__name__}")
            
            # Call the function
            result = func(*args, **kwargs)
            
            # Store in cache with expiration
            expires_at = datetime.now() + timedelta(seconds=ttl)
            backend.set(cache_key, result, expires_at)
            
            return result
        
        # Add cache control methods
        wrapper.cache_backend = backend
        wrapper.clear_cache = backend.clear
        
        return wrapper
    
    return decorator


# Rate Limiting Decorator
def rate_limit(calls: int = 10, period: int = 60):
    """
    Decorator to rate limit API calls.
    
    Args:
        calls: Number of calls allowed
        period: Time period in seconds
    """
    call_times = []
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            
            # Remove old calls outside the time window
            while call_times and call_times[0] < now - period:
                call_times.pop(0)
            
            # Check if rate limit exceeded
            if len(call_times) >= calls:
                wait_time = period - (now - call_times[0])
                print(f"  ⏱️  Rate limit reached. Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
                call_times.pop(0)
            
            # Record this call
            call_times.append(now)
            
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Retry Decorator
def retry(max_attempts: int = 3, delay: int = 1, backoff: int = 2):
    """
    Decorator to retry failed requests.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    
                    print(f"  ⚠️  Attempt {attempt} failed: {e}")
                    print(f"  ⏳ Retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
        return wrapper
    
    return decorator


class APIClient:
    """Generic API client with caching and error handling."""
    
    def __init__(self, base_url: str, cache_backend: Optional[CacheBackend] = None,
                 default_ttl: int = 300, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.cache_backend = cache_backend or MemoryCache()
        self.default_ttl = default_ttl
        self.timeout = timeout
        self.session = requests.Session()
        self.request_log: list = []
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'Python API Client/1.0',
            'Accept': 'application/json'
        })
    
    def set_auth(self, token: str = None, username: str = None, password: str = None):
        """Set authentication credentials."""
        if token:
            self.session.headers['Authorization'] = f'Bearer {token}'
        elif username and password:
            self.session.auth = (username, password)
    
    def _log_request(self, method: str, url: str, response_time: float, 
                     status_code: int, cached: bool = False):
        """Log API request."""
        self.request_log.append({
            'timestamp': datetime.now().isoformat(),
            'method': method,
            'url': url,
            'response_time': response_time,
            'status_code': status_code,
            'cached': cached
        })
    
    @retry(max_attempts=3, delay=1, backoff=2)
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request with retry logic."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        start_time = time.time()
        response = self.session.request(
            method,
            url,
            timeout=self.timeout,
            **kwargs
        )
        response_time = time.time() - start_time
        
        response.raise_for_status()
        self._log_request(method, url, response_time, response.status_code)
        
        return response
    
    @cache_response(ttl=300)
    def get(self, endpoint: str, params: Optional[Dict] = None, ttl: Optional[int] = None) -> Dict:
        """
        GET request with caching.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            ttl: Cache time-to-live (overrides default)
        """
        response = self._make_request('GET', endpoint, params=params)
        return response.json()
    
    def post(self, endpoint: str, data: Optional[Dict] = None, 
             json_data: Optional[Dict] = None) -> Dict:
        """POST request (not cached)."""
        response = self._make_request('POST', endpoint, data=data, json=json_data)
        return response.json()
    
    def put(self, endpoint: str, data: Optional[Dict] = None,
            json_data: Optional[Dict] = None) -> Dict:
        """PUT request (not cached)."""
        response = self._make_request('PUT', endpoint, data=data, json=json_data)
        return response.json()
    
    def delete(self, endpoint: str) -> Dict:
        """DELETE request (not cached)."""
        response = self._make_request('DELETE', endpoint)
        return response.json() if response.content else {}
    
    def clear_cache(self):
        """Clear all cached responses."""
        self.cache_backend.clear()
        print("✓ Cache cleared")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        if isinstance(self.cache_backend, MemoryCache):
            return {
                'backend': 'memory',
                'entries': len(self.cache_backend)
            }
        elif isinstance(self.cache_backend, FileCache):
            cache_files = list(self.cache_backend.cache_dir.glob("*.json"))
            return {
                'backend': 'file',
                'entries': len(cache_files),
                'cache_dir': str(self.cache_backend.cache_dir)
            }
        return {'backend': 'unknown'}
    
    def get_request_stats(self) -> Dict:
        """Get request statistics."""
        if not self.request_log:
            return {'total_requests': 0}
        
        total = len(self.request_log)
        cached = sum(1 for r in self.request_log if r.get('cached', False))
        avg_response_time = sum(r['response_time'] for r in self.request_log) / total
        
        status_codes = {}
        for req in self.request_log:
            code = req['status_code']
            status_codes[code] = status_codes.get(code, 0) + 1
        
        return {
            'total_requests': total,
            'cached_requests': cached,
            'cache_hit_rate': (cached / total * 100) if total > 0 else 0,
            'avg_response_time': avg_response_time,
            'status_codes': status_codes
        }
    
    def save_request_log(self, filepath: str = "api_request_log.json"):
        """Save request log to file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.request_log, f, indent=2)
        print(f"✓ Request log saved to {filepath}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.session.close()


@contextmanager
def api_session(base_url: str, **kwargs):
    """Context manager for API client."""
    client = APIClient(base_url, **kwargs)
    try:
        yield client
    finally:
        client.session.close()


# Example API Clients
class JSONPlaceholderClient(APIClient):
    """Client for JSONPlaceholder API (testing API)."""
    
    def __init__(self, cache_backend: Optional[CacheBackend] = None):
        super().__init__(
            base_url="https://jsonplaceholder.typicode.com",
            cache_backend=cache_backend
        )
    
    @cache_response(ttl=600)  # Cache for 10 minutes
    def get_posts(self, user_id: Optional[int] = None) -> list:
        """Get all posts or posts by user."""
        params = {'userId': user_id} if user_id else None
        return self.get('posts', params=params)
    
    @cache_response(ttl=600)
    def get_post(self, post_id: int) -> dict:
        """Get a specific post."""
        return self.get(f'posts/{post_id}')
    
    @cache_response(ttl=600)
    def get_users(self) -> list:
        """Get all users."""
        return self.get('users')
    
    @cache_response(ttl=600)
    def get_user(self, user_id: int) -> dict:
        """Get a specific user."""
        return self.get(f'users/{user_id}')
    
    def create_post(self, title: str, body: str, user_id: int) -> dict:
        """Create a new post."""
        return self.post('posts', json_data={
            'title': title,
            'body': body,
            'userId': user_id
        })


class GitHubClient(APIClient):
    """Client for GitHub API."""
    
    def __init__(self, token: Optional[str] = None, 
                 cache_backend: Optional[CacheBackend] = None):
        super().__init__(
            base_url="https://api.github.com",
            cache_backend=cache_backend
        )
        if token:
            self.set_auth(token=token)
    
    @cache_response(ttl=300)
    @rate_limit(calls=10, period=60)  # GitHub rate limit
    def get_user(self, username: str) -> dict:
        """Get GitHub user information."""
        return self.get(f'users/{username}')
    
    @cache_response(ttl=300)
    @rate_limit(calls=10, period=60)
    def get_repos(self, username: str) -> list:
        """Get user repositories."""
        return self.get(f'users/{username}/repos')
    
    @cache_response(ttl=600)
    @rate_limit(calls=10, period=60)
    def search_repositories(self, query: str, sort: str = 'stars') -> dict:
        """Search repositories."""
        return self.get('search/repositories', params={
            'q': query,
            'sort': sort
        })


def demo_jsonplaceholder():
    """Demo with JSONPlaceholder API."""
    print("="*70)
    print("JSONPlaceholder API Demo")
    print("="*70)
    
    # Create client with file cache
    cache = FileCache(cache_dir=".api_cache")
    client = JSONPlaceholderClient(cache_backend=cache)
    
    print("\n--- First Request (should be cached) ---")
    posts = client.get_posts()
    print(f"Retrieved {len(posts)} posts")
    print(f"First post: {posts[0]['title']}")
    
    print("\n--- Second Request (should use cache) ---")
    posts = client.get_posts()
    print(f"Retrieved {len(posts)} posts")
    
    print("\n--- Get Specific Post ---")
    post = client.get_post(1)
    print(f"Post #{post['id']}: {post['title']}")
    
    print("\n--- Get Users ---")
    users = client.get_users()
    print(f"Retrieved {len(users)} users")
    
    print("\n--- Get Posts by User ---")
    user_posts = client.get_posts(user_id=1)
    print(f"User 1 has {len(user_posts)} posts")
    
    print("\n--- Create New Post ---")
    new_post = client.create_post(
        title="Test Post",
        body="This is a test post",
        user_id=1
    )
    print(f"Created post: {new_post}")
    
    print("\n--- Cache Statistics ---")
    cache_stats = client.get_cache_stats()
    print(f"Cache backend: {cache_stats['backend']}")
    print(f"Cache entries: {cache_stats['entries']}")
    
    print("\n--- Request Statistics ---")
    stats = client.get_request_stats()
    print(f"Total requests: {stats['total_requests']}")
    print(f"Cached requests: {stats['cached_requests']}")
    print(f"Cache hit rate: {stats['cache_hit_rate']:.1f}%")
    print(f"Avg response time: {stats['avg_response_time']:.3f}s")
    
    # Save log
    client.save_request_log()


def demo_github():
    """Demo with GitHub API."""
    print("="*70)
    print("GitHub API Demo")
    print("="*70)
    
    with api_session("https://api.github.com") as client:
        print("\n--- Get Python Repository Info ---")
        try:
            repo_response = client.get('repos/python/cpython')
            print(f"Repository: {repo_response['full_name']}")
            print(f"Stars: {repo_response['stargazers_count']}")
            print(f"Forks: {repo_response['forks_count']}")
            print(f"Description: {repo_response['description']}")
        except Exception as e:
            print(f"Error: {e}")
        
        print("\n--- Request Statistics ---")
        stats = client.get_request_stats()
        print(f"Total requests: {stats['total_requests']}")


def interactive_mode():
    """Interactive API client."""
    print("="*70)
    print("INTERACTIVE API CLIENT")
    print("="*70)
    
    print("\nSelect API:")
    print("1. JSONPlaceholder (testing API)")
    print("2. Custom API")
    
    choice = input("\nChoice (1 or 2): ").strip()
    
    if choice == '1':
        client = JSONPlaceholderClient(cache_backend=FileCache())
        base_url = "https://jsonplaceholder.typicode.com"
    else:
        base_url = input("Enter API base URL: ").strip()
        client = APIClient(base_url, cache_backend=FileCache())
    
    print(f"\nConnected to: {base_url}")
    print("\nCommands:")
    print("  get <endpoint> [params]  - GET request")
    print("  post <endpoint> <json>   - POST request")
    print("  cache                    - Show cache stats")
    print("  clear                    - Clear cache")
    print("  stats                    - Show request stats")
    print("  log                      - Save request log")
    print("  quit                     - Exit")
    
    while True:
        try:
            cmd = input("\napi> ").strip()
            
            if not cmd:
                continue
            
            parts = cmd.split(maxsplit=1)
            command = parts[0].lower()
            
            if command == 'get':
                if len(parts) < 2:
                    print("Usage: get <endpoint>")
                    continue
                
                endpoint = parts[1]
                result = client.get(endpoint)
                print(json.dumps(result, indent=2))
            
            elif command == 'post':
                if len(parts) < 2:
                    print("Usage: post <endpoint> <json_data>")
                    continue
                
                args = parts[1].split(maxsplit=1)
                endpoint = args[0]
                json_data = json.loads(args[1]) if len(args) > 1 else {}
                
                result = client.post(endpoint, json_data=json_data)
                print(json.dumps(result, indent=2))
            
            elif command == 'cache':
                stats = client.get_cache_stats()
                print(f"Cache Stats: {json.dumps(stats, indent=2)}")
            
            elif command == 'clear':
                client.clear_cache()
            
            elif command == 'stats':
                stats = client.get_request_stats()
                print(f"Request Stats: {json.dumps(stats, indent=2)}")
            
            elif command == 'log':
                client.save_request_log()
            
            elif command == 'quit':
                break
            
            else:
                print(f"Unknown command: {command}")
        
        except KeyboardInterrupt:
            print("\nUse 'quit' to exit")
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n✓ Session closed")


def main():
    """Main application."""
    print("\n1. JSONPlaceholder Demo")
    print("2. GitHub Demo")
    print("3. Interactive Mode")
    
    choice = input("\nChoice (1-3): ").strip()
    
    if choice == '1':
        demo_jsonplaceholder()
    elif choice == '2':
        demo_github()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()


"""
Key Features:

* Caching Decorator: @cache_response with configurable TTL
* Multiple Cache Backends: Memory and file-based caching
* Requests: Full HTTP client with session management
* JSON: Parsing and storing API responses
* File I/O: Persistent cache storage
* Exception Handling: Retry logic and comprehensive error handling
* Context Managers: @contextmanager for session management
* Datetime Operations: Cache expiration and request logging

Demonstrates:

* Custom decorators for caching (@cache_response)
* Rate limiting decorator (@rate_limit)
* Retry decorator with exponential backoff (@retry)
* Abstract base classes for cache backends
* Context managers for resource management
* MD5 hashing for cache keys
* JSON serialization/deserialization
* File-based persistent caching
* Request logging and statistics

Features:

* Automatic response caching with TTL
* Memory and file cache backends
* Rate limiting for API calls
* Automatic retry with exponential backoff
* Request logging and statistics
* Cache hit/miss tracking
* Context manager support
* Built-in clients for JSONPlaceholder and GitHub APIs
"""