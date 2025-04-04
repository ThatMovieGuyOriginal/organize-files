"""
Module for file and directory indexing to speed up file operations.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from platformdirs import user_cache_dir

from .logger import logger


@dataclass
class FileInfo:
    """Information about a file or directory."""
    path: str
    is_dir: bool
    size: int = 0
    mtime: float = 0
    ctime: float = 0
    indexed_at: float = 0
    
    @classmethod
    def from_path(cls, path: Path) -> FileInfo:
        """Create a FileInfo from a Path."""
        stat = path.stat()
        return cls(
            path=str(path),
            is_dir=path.is_dir(),
            size=stat.st_size,
            mtime=stat.st_mtime,
            ctime=stat.st_ctime,
            indexed_at=time.time(),
        )


class FileIndex:
    """
    SQLite-based file index for faster file operations.
    """
    
    def __init__(self, index_path: Optional[Path] = None):
        """
        Initialize the file index.
        
        Args:
            index_path: Path to the index file, defaults to user cache directory
        """
        if index_path is None:
            cache_dir = Path(user_cache_dir(appname="organize", ensure_exists=True))
            index_path = cache_dir / "file_index.db"
            
        self.index_path = index_path
        self._create_tables()
        
    def _create_tables(self) -> None:
        """Create the required database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create files table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                is_dir INTEGER NOT NULL,
                size INTEGER NOT NULL,
                mtime REAL NOT NULL,
                ctime REAL NOT NULL,
                indexed_at REAL NOT NULL
            )
            ''')
            
            # Create tags table for custom metadata
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                path TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (path, key),
                FOREIGN KEY (path) REFERENCES files(path) ON DELETE CASCADE
            )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_is_dir ON files(is_dir)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_indexed_at ON files(indexed_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tags_key ON tags(key)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tags_key_value ON tags(key, value)')
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with foreign key support enabled."""
        conn = sqlite3.connect(self.index_path)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()
    
    def add_file(self, file_info: FileInfo) -> None:
        """
        Add or update a file in the index.
        
        Args:
            file_info: Information about the file
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO files (path, is_dir, size, mtime, ctime, indexed_at) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (
                    file_info.path,
                    int(file_info.is_dir),
                    file_info.size,
                    file_info.mtime,
                    file_info.ctime,
                    file_info.indexed_at,
                )
            )
            conn.commit()
    
    def add_tag(self, path: str, key: str, value: str) -> None:
        """
        Add or update a tag for a file.
        
        Args:
            path: Path to the file
            key: Tag key
            value: Tag value
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO tags (path, key, value) VALUES (?, ?, ?)',
                (path, key, value)
            )
            conn.commit()
    
    def get_file(self, path: Path) -> Optional[FileInfo]:
        """
        Get file information from the index.
        
        Args:
            path: Path to the file
            
        Returns:
            FileInfo if the file is in the index, None otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT path, is_dir, size, mtime, ctime, indexed_at FROM files WHERE path = ?',
                (str(path),)
            )
            row = cursor.fetchone()
            
            if row:
                return FileInfo(
                    path=row[0],
                    is_dir=bool(row[1]),
                    size=row[2],
                    mtime=row[3],
                    ctime=row[4],
                    indexed_at=row[5],
                )
            return None
    
    def get_tag(self, path: str, key: str) -> Optional[str]:
        """
        Get a tag value for a file.
        
        Args:
            path: Path to the file
            key: Tag key
            
        Returns:
            Tag value if found, None otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT value FROM tags WHERE path = ? AND key = ?',
                (path, key)
            )
            row = cursor.fetchone()
            return row[0] if row else None
    
    def get_files_by_extension(self, extension: str) -> List[FileInfo]:
        """
        Get files with a specific extension.
        
        Args:
            extension: File extension (without dot)
            
        Returns:
            List of FileInfo objects
        """
        pattern = f"%.{extension}"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT path, is_dir, size, mtime, ctime, indexed_at FROM files '
                'WHERE is_dir = 0 AND path LIKE ?',
                (pattern,)
            )
            return [
                FileInfo(
                    path=row[0],
                    is_dir=bool(row[1]),
                    size=row[2],
                    mtime=row[3],
                    ctime=row[4],
                    indexed_at=row[5],
                )
                for row in cursor.fetchall()
            ]
    
    def get_files_by_tag(self, key: str, value: Optional[str] = None) -> List[FileInfo]:
        """
        Get files with a specific tag.
        
        Args:
            key: Tag key
            value: Optional tag value
            
        Returns:
            List of FileInfo objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if value is None:
                cursor.execute(
                    'SELECT f.path, f.is_dir, f.size, f.mtime, f.ctime, f.indexed_at '
                    'FROM files f JOIN tags t ON f.path = t.path '
                    'WHERE t.key = ?',
                    (key,)
                )
            else:
                cursor.execute(
                    'SELECT f.path, f.is_dir, f.size, f.mtime, f.ctime, f.indexed_at '
                    'FROM files f JOIN tags t ON f.path = t.path '
                    'WHERE t.key = ? AND t.value = ?',
                    (key, value)
                )
            return [
                FileInfo(
                    path=row[0],
                    is_dir=bool(row[1]),
                    size=row[2],
                    mtime=row[3],
                    ctime=row[4],
                    indexed_at=row[5],
                )
                for row in cursor.fetchall()
            ]
    
    def remove_file(self, path: Path) -> None:
        """
        Remove a file from the index.
        
        Args:
            path: Path to the file
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM files WHERE path = ?', (str(path),))
            conn.commit()
    
    def clean_index(self, max_age: float = 30 * 24 * 60 * 60) -> int:
        """
        Remove files from the index that haven't been seen recently.
        
        Args:
            max_age: Maximum age in seconds
            
        Returns:
            Number of files removed
        """
        cutoff = time.time() - max_age
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM files WHERE indexed_at < ?', (cutoff,))
            count = cursor.rowcount
            conn.commit()
            return count
    
    def index_directory(self, directory: Path, recursive: bool = True) -> int:
        """
        Index all files in a directory.
        
        Args:
            directory: Directory to index
            recursive: Whether to index subdirectories
            
        Returns:
            Number of files indexed
        """
        count = 0
        try:
            # Index the directory itself
            self.add_file(FileInfo.from_path(directory))
            count += 1
            
            # Index its contents
            for item in directory.iterdir():
                if item.is_dir() and recursive:
                    count += self.index_directory(item, recursive)
                else:
                    self.add_file(FileInfo.from_path(item))
                    count += 1
                    
        except (PermissionError, FileNotFoundError) as e:
            logger.warning(f"Error indexing {directory}: {e}")
            
        return count
    
    def get_statistics(self) -> Dict[str, Union[int, str]]:
        """
        Get statistics about the index.
        
        Returns:
            Dictionary with statistics
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Count files and dirs
            cursor.execute('SELECT COUNT(*) FROM files WHERE is_dir = 0')
            file_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM files WHERE is_dir = 1')
            dir_count = cursor.fetchone()[0]
            
            # Get total size
            cursor.execute('SELECT SUM(size) FROM files WHERE is_dir = 0')
            total_size = cursor.fetchone()[0] or 0
            
            # Get tag count
            cursor.execute('SELECT COUNT(*) FROM tags')
            tag_count = cursor.fetchone()[0]
            
            # Get last update
            cursor.execute('SELECT MAX(indexed_at) FROM files')
            last_update = cursor.fetchone()[0] or 0
            
            # Database size
            cursor.execute('SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()')
            db_size = cursor.fetchone()[0]
            
            return {
                'file_count': file_count,
                'directory_count': dir_count,
                'total_size': total_size,
                'tag_count': tag_count,
                'last_update': datetime.fromtimestamp(last_update).isoformat(),
                'database_size': db_size,
            }


# Global index instance
file_index = FileIndex()