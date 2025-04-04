"""
File system watcher module that monitors directories and triggers
organize rules when files change.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from .logger import logger

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    logger.warning(
        "Watchdog package not installed. File watching functionality is disabled. "
        "Install with 'pip install watchdog'."
    )


class OrganizeEventHandler(FileSystemEventHandler):
    """
    Handles file system events and triggers the appropriate callbacks.
    """
    def __init__(
        self, 
        callback: Callable[[Path, str], None],
        ignore_paths: Set[Path] = None,
        ignore_patterns: List[str] = None,
    ):
        self.callback = callback
        self.ignore_paths = ignore_paths or set()
        self.ignore_patterns = ignore_patterns or []
        
    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        
        path = Path(event.src_path).resolve()
        
        # Skip ignored paths
        if path in self.ignore_paths:
            return
        
        # Skip ignored patterns
        for pattern in self.ignore_patterns:
            if path.match(pattern):
                return
                
        event_type = event.event_type
        self.callback(path, event_type)


class DirectoryWatcher:
    """
    Watches directories for changes and triggers rules accordingly.
    """
    def __init__(self):
        self.observers: Dict[str, Tuple[Observer, Set[Path]]] = {}
        self._running = False
        self._lock = threading.Lock()
        
    def watch(
        self, 
        paths: List[Path], 
        callback: Callable[[Path, str], None],
        recursive: bool = True,
        ignore_paths: Set[Path] = None,
        ignore_patterns: List[str] = None,
    ) -> None:
        """
        Watch the given paths for changes and trigger the callback.
        
        Args:
            paths: Paths to watch
            callback: Function to call when a file changes
            recursive: Whether to watch subdirectories
            ignore_paths: Set of paths to ignore
            ignore_patterns: List of glob patterns to ignore
        """
        if not HAS_WATCHDOG:
            logger.error("Watchdog package not installed. Cannot watch directories.")
            return
            
        with self._lock:
            observer_key = id(callback)
            
            # Create a new observer for this callback if it doesn't exist
            if observer_key not in self.observers:
                observer = Observer()
                self.observers[observer_key] = (observer, set())
                
                if self._running:
                    observer.start()
            else:
                observer, existing_paths = self.observers[observer_key]
            
            # Add new paths to watch
            for path in paths:
                if path not in existing_paths:
                    handler = OrganizeEventHandler(
                        callback=callback,
                        ignore_paths=ignore_paths,
                        ignore_patterns=ignore_patterns
                    )
                    
                    path_str = str(path)
                    observer.schedule(handler, path_str, recursive=recursive)
                    self.observers[observer_key][1].add(path)
    
    def start(self) -> None:
        """Start all observers."""
        with self._lock:
            self._running = True
            for observer, _ in self.observers.values():
                if not observer.is_alive():
                    observer.start()
    
    def stop(self) -> None:
        """Stop all observers."""
        with self._lock:
            self._running = False
            for observer, _ in self.observers.values():
                if observer.is_alive():
                    observer.stop()
    
    def join(self, timeout: Optional[float] = None) -> None:
        """Join all observer threads."""
        for observer, _ in self.observers.values():
            observer.join(timeout=timeout)


# Global watcher instance
watcher = DirectoryWatcher()