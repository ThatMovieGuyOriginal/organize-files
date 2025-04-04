from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from organize.parallel import process_parallel, process_paths_parallel


def test_process_parallel():
    """Test processing items in parallel."""
    items = [1, 2, 3, 4, 5]
    processor = lambda x: x * 2
    
    results = process_parallel(items, processor)
    
    assert sorted(results) == [2, 4, 6, 8, 10]


def test_process_parallel_with_error():
    """Test processing items in parallel with one failing."""
    items = [1, 2, 0, 4, 5]
    
    def processor(x):
        return 10 // x
    
    with patch("organize.parallel.logger") as mock_logger:
        results = process_parallel(items, processor)
        
        # Should have logged the error
        assert mock_logger.error.called
        assert mock_logger.exception.called
        
        # Should still return successful results
        assert sorted(results) == [2, 2, 5, 10]


def test_process_paths_parallel():
    """Test processing paths in parallel."""
    paths = [Path("/test/file1.txt"), Path("/test/file2.txt")]
    processor = lambda p: p.name
    
    results = process_paths_parallel(paths, processor)
    
    assert sorted(results) == ["file1.txt", "file2.txt"]