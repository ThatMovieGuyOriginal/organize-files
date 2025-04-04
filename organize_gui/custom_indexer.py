"""
Simplified indexer module for the organize GUI
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Union


# Stub for FileInfo
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
    def from_path(cls, path: Path) -> 'FileInfo':
        """Create a FileInfo from a Path."""
        stat = path.stat()
        return cls(
            path=str(path),
            is_dir=path.is_dir(),
            size=stat.st_size,
            mtime=stat.st_mtime,
            ctime=stat.st_ctime,
            indexed_at=datetime.now().timestamp(),
        )

# Simple file index implementation
class FileIndex:
    """
    Simplified file index for faster file operations.
    """
    
    def __init__(self):
        """Initialize the file index."""
        self.files = {}
        self.tags = {}
        self.last_update = datetime.now().timestamp()
        
    def add_file(self, file_info: FileInfo) -> None:
        """Add or update a file in the index."""
        self.files[file_info.path] = file_info
        self.last_update = datetime.now().timestamp()
    
    def add_tag(self, path: str, key: str, value: str) -> None:
        """Add a tag to a file."""
        if path not in self.tags:
            self.tags[path] = {}
        self.tags[path][key] = value
        
    def get_file(self, path: Path) -> Optional[FileInfo]:
        """Get file information from the index."""
        path_str = str(path)
        return self.files.get(path_str)
    
    def get_tag(self, path: str, key: str) -> Optional[str]:
        """Get a tag value for a file."""
        if path in self.tags and key in self.tags[path]:
            return self.tags[path][key]
        return None
    
    def get_files_by_extension(self, extension: str) -> List[FileInfo]:
        """Get files with a specific extension."""
        return [
            file_info for file_info in self.files.values()
            if not file_info.is_dir and Path(file_info.path).suffix.lower() == f".{extension.lower()}"
        ]
    
    def get_files_by_tag(self, key: str, value: Optional[str] = None) -> List[FileInfo]:
        """Get files with a specific tag."""
        result = []
        for path, tags in self.tags.items():
            if key in tags and (value is None or tags[key] == value):
                if path in self.files:
                    result.append(self.files[path])
        return result
    
    def remove_file(self, path: Path) -> None:
        """Remove a file from the index."""
        path_str = str(path)
        if path_str in self.files:
            del self.files[path_str]
        if path_str in self.tags:
            del self.tags[path_str]
            
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
            print(f"Error indexing {directory}: {e}")
            
        return count
    
    def get_statistics(self) -> Dict[str, Union[int, str]]:
        """
        Get statistics about the index.
        
        Returns:
            Dictionary with statistics
        """
        file_count = sum(1 for f in self.files.values() if not f.is_dir)
        dir_count = sum(1 for f in self.files.values() if f.is_dir)
        total_size = sum(f.size for f in self.files.values() if not f.is_dir)
        
        return {
            'file_count': file_count,
            'directory_count': dir_count,
            'total_size': total_size,
            'tag_count': sum(len(tags) for tags in self.tags.values()),
            'last_update': datetime.fromtimestamp(self.last_update).isoformat(),
            'database_size': 0,  # Not applicable for in-memory version
        }

# Global index instancepip install organize-tool==3.3.0 PyQt6==6.4.0 PyYAML
file_index = FileIndex()