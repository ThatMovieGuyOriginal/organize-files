"""
Module for parallel processing of files and directories.
"""
from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Callable, Iterable, List, Optional, TypeVar

from .logger import logger

T = TypeVar('T')
R = TypeVar('R')


def process_parallel(
    items: Iterable[T],
    processor: Callable[[T], R],
    max_workers: Optional[int] = None,
    timeout: Optional[float] = None,
) -> List[R]:
    """
    Process items in parallel using a ThreadPoolExecutor.
    
    Args:
        items: Items to process
        processor: Function to process each item
        max_workers: Maximum number of worker threads
        timeout: Maximum time to wait for all threads to complete
        
    Returns:
        List of results from processing each item
    """
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all jobs
        future_to_item = {
            executor.submit(processor, item): item for item in items
        }
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_item, timeout=timeout):
            item = future_to_item[future]
            
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing {item}: {e}")
                logger.exception(e)
                
    return results


def process_paths_parallel(
    paths: Iterable[Path], 
    processor: Callable[[Path], R],
    max_workers: Optional[int] = None,
) -> List[R]:
    """
    Process paths in parallel using ThreadPoolExecutor.
    
    Args:
        paths: Paths to process
        processor: Function to process each path
        max_workers: Maximum number of worker threads
        
    Returns:
        List of results from processing each path
    """
    return process_parallel(
        items=paths,
        processor=processor,
        max_workers=max_workers,
    )