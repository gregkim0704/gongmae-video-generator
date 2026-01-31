"""
Caching utilities using MD5 hashing
Adapted from quote-video-generator
"""
import hashlib
import shutil
from pathlib import Path
from typing import Optional, Dict, Any


def get_cache_key(*args, **kwargs) -> str:
    """
    Generate a cache key from arguments using MD5 hash.

    Args:
        *args: Positional arguments to include in hash
        **kwargs: Keyword arguments to include in hash

    Returns:
        MD5 hash string
    """
    cache_str = "_".join(str(arg) for arg in args)
    if kwargs:
        cache_str += "_" + "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return hashlib.md5(cache_str.encode()).hexdigest()


def get_cached_file(
    cache_dir: Path,
    cache_key: str,
    extension: str = ""
) -> Optional[Path]:
    """
    Check if a cached file exists.

    Args:
        cache_dir: Directory where cache files are stored
        cache_key: The cache key (MD5 hash)
        extension: File extension (e.g., ".mp3", ".png")

    Returns:
        Path to cached file if exists, None otherwise
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_file = cache_dir / f"{cache_key}{extension}"

    if cached_file.exists():
        return cached_file
    return None


def cache_file(
    source_path: Path,
    cache_dir: Path,
    cache_key: str,
    extension: str = ""
) -> Path:
    """
    Cache a file by copying it to the cache directory.

    Args:
        source_path: Path to the source file
        cache_dir: Directory where cache files are stored
        cache_key: The cache key (MD5 hash)
        extension: File extension (e.g., ".mp3", ".png")

    Returns:
        Path to the cached file
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_file = cache_dir / f"{cache_key}{extension}"

    shutil.copy2(source_path, cached_file)
    return cached_file


def cleanup_cache(cache_dir: Path, keep_latest: int = 100) -> int:
    """
    Clean up old cache files, keeping only the most recent ones.

    Args:
        cache_dir: Directory where cache files are stored
        keep_latest: Number of most recent files to keep

    Returns:
        Number of files deleted
    """
    if not cache_dir.exists():
        return 0

    # Get all files sorted by modification time (newest first)
    files = sorted(
        cache_dir.iterdir(),
        key=lambda p: p.stat().st_mtime if p.is_file() else 0,
        reverse=True
    )

    deleted = 0
    for file_path in files[keep_latest:]:
        if file_path.is_file():
            try:
                file_path.unlink()
                deleted += 1
            except OSError:
                pass

    return deleted
