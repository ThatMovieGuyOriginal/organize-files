import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from organize.indexer import FileIndex, FileInfo


@pytest.fixture
def temp_db_path(tmp_path):
    """Return a temporary path for the database file."""
    return tmp_path / "test_index.db"


@pytest.fixture
def file_index(temp_db_path):
    """Return a FileIndex instance with a temporary database path."""
    return FileIndex(index_path=temp_db_path)


def test_file_info_from_path(tmp_path):
    """Test creating FileInfo from a Path."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    file_info = FileInfo.from_path(test_file)
    
    assert file_info.path == str(test_file)
    assert not file_info.is_dir
    assert file_info.size > 0
    assert file_info.mtime > 0
    assert file_info.ctime > 0
    assert file_info.indexed_at > 0


def test_file_index_add_get_file(file_index, tmp_path):
    """Test adding and retrieving a file from the index."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    file_info = FileInfo.from_path(test_file)
    file_index.add_file(file_info)
    
    # Retrieve the file from the index
    retrieved = file_index.get_file(test_file)
    
    assert retrieved is not None
    assert retrieved.path == file_info.path
    assert retrieved.size == file_info.size
    assert retrieved.is_dir == file_info.is_dir


def test_file_index_add_tags(file_index, tmp_path):
    """Test adding and retrieving tags."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    # Add the file to the index
    file_info = FileInfo.from_path(test_file)
    file_index.add_file(file_info)
    
    # Add tags
    file_index.add_tag(str(test_file), "category", "document")
    file_index.add_tag(str(test_file), "priority", "high")
    
    # Retrieve tags
    category = file_index.get_tag(str(test_file), "category")
    priority = file_index.get_tag(str(test_file), "priority")
    
    assert category == "document"
    assert priority == "high"


def test_file_index_get_files_by_extension(file_index, tmp_path):
    """Test retrieving files by extension."""
    # Create test files
    (tmp_path / "test1.txt").write_text("test content 1")
    (tmp_path / "test2.txt").write_text("test content 2")
    (tmp_path / "test.pdf").write_text("pdf content")
    
    # Add files to the index
    for file_path in tmp_path.iterdir():
        file_index.add_file(FileInfo.from_path(file_path))
    
    # Retrieve txt files
    txt_files = file_index.get_files_by_extension("txt")
    
    assert len(txt_files) == 2
    assert all(file.path.endswith(".txt") for file in txt_files)


def test_file_index_remove_file(file_index, tmp_path):
    """Test removing a file from the index."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    # Add the file to the index
    file_info = FileInfo.from_path(test_file)
    file_index.add_file(file_info)
    
    # Remove the file
    file_index.remove_file(test_file)
    
    # Try to retrieve the file
    retrieved = file_index.get_file(test_file)
    
    assert retrieved is None


def test_file_index_clean_index(file_index, tmp_path):
    """Test cleaning the index of old entries."""
    # Create test files
    test_file1 = tmp_path / "test1.txt"
    test_file1.write_text("test content 1")
    test_file2 = tmp_path / "test2.txt"
    test_file2.write_text("test content 2")
    
    # Add files to the index with different timestamps
    now = time.time()
    file_index.add_file(FileInfo(
        path=str(test_file1),
        is_dir=False,
        size=len("test content 1"),
        mtime=now,
        ctime=now,
        indexed_at=now - 100  # Old entry
    ))
    file_index.add_file(FileInfo(
        path=str(test_file2),
        is_dir=False,
        size=len("test content 2"),
        mtime=now,
        ctime=now,
        indexed_at=now  # Recent entry
    ))
    
    # Clean the index
    removed = file_index.clean_index(max_age=50)
    
    assert removed == 1
    assert file_index.get_file(test_file1) is None
    assert file_index.get_file(test_file2) is not None


def test_file_index_index_directory(file_index, tmp_path):
    """Test indexing a directory."""
    # Create test directory structure
    sub_dir = tmp_path / "subdir"
    sub_dir.mkdir()
    (tmp_path / "file1.txt").write_text("content 1")
    (tmp_path / "file2.pdf").write_text("content 2")
    (sub_dir / "file3.txt").write_text("content 3")
    
    # Index the directory
    count = file_index.index_directory(tmp_path)
    
    # Should have indexed 4 items (root dir, subdir, 2 files in root, 1 file in subdir)
    assert count == 5
    
    # Check statistics
    stats = file_index.get_statistics()
    assert stats["file_count"] == 3
    assert stats["directory_count"] == 2