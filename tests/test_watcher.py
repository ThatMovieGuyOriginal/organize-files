import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from organize.watcher import DirectoryWatcher, OrganizeEventHandler


@pytest.fixture
def mock_watchdog():
    with patch("organize.watcher.HAS_WATCHDOG", True):
        with patch("organize.watcher.Observer") as MockObserver:
            with patch("organize.watcher.FileSystemEventHandler"):
                mock_observer_instance = MockObserver.return_value
                yield mock_observer_instance


def test_directory_watcher_init():
    watcher = DirectoryWatcher()
    assert watcher.observers == {}
    assert not watcher._running


def test_directory_watcher_watch(mock_watchdog):
    callback = MagicMock()
    watcher = DirectoryWatcher()
    
    # Watch a directory
    watcher.watch([Path("/test")], callback)
    
    # Check if the observer was created and scheduled
    mock_watchdog.schedule.assert_called_once()
    assert len(watcher.observers) == 1


def test_directory_watcher_start_stop(mock_watchdog):
    watcher = DirectoryWatcher()
    callback = MagicMock()
    
    # Watch a directory
    watcher.watch([Path("/test")], callback)
    
    # Start watching
    watcher.start()
    mock_watchdog.start.assert_called_once()
    assert watcher._running
    
    # Stop watching
    watcher.stop()
    mock_watchdog.stop.assert_called_once()
    assert not watcher._running


def test_event_handler_ignores_directories():
    callback = MagicMock()
    handler = OrganizeEventHandler(callback)
    
    # Create a mock event for a directory
    event = MagicMock()
    event.is_directory = True
    event.src_path = "/test/dir"
    
    # Handle the event
    handler.on_any_event(event)
    
    # Callback should not be called for directories
    callback.assert_not_called()


def test_event_handler_ignores_paths():
    callback = MagicMock()
    ignore_paths = {Path("/test/ignore.txt").resolve()}
    handler = OrganizeEventHandler(callback, ignore_paths=ignore_paths)
    
    # Create a mock event for an ignored file
    event = MagicMock()
    event.is_directory = False
    event.src_path = "/test/ignore.txt"
    event.event_type = "created"
    
    # Patch Path.resolve to return a known value
    with patch.object(Path, "resolve", return_value=Path("/test/ignore.txt").resolve()):
        # Handle the event
        handler.on_any_event(event)
        
        # Callback should not be called for ignored paths
        callback.assert_not_called()


def test_event_handler_calls_callback():
    callback = MagicMock()
    handler = OrganizeEventHandler(callback)
    
    # Create a mock event
    event = MagicMock()
    event.is_directory = False
    event.src_path = "/test/file.txt"
    event.event_type = "created"
    
    # Handle the event
    handler.on_any_event(event)
    
    # Callback should be called with the path and event type
    callback.assert_called_once_with(Path("/test/file.txt").resolve(), "created")