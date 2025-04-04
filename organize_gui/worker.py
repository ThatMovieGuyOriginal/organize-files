# organize_gui/worker.py
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

from PyQt6.QtCore import QThread, pyqtSignal

from organize import Config
from organize.indexer import file_index
from organize.output import SavingOutput
from organize.resource import Resource
from organize.rule import Rule
from organize.watcher import watcher


class OrganizeWorker(QThread):
    """Worker thread for running organize operations"""
    finished = pyqtSignal(int, int)  # success, errors
    
    def __init__(
        self, 
        config: Config, 
        simulate: bool = False,
        parallel: bool = False,
        max_workers: Optional[int] = None,
        paths: Optional[List[str]] = None,
        rules: Optional[List[Rule]] = None,
    ):
        super().__init__()
        self.config = config
        self.simulate = simulate
        self.parallel = parallel
        self.max_workers = max_workers
        self.paths = paths
        self.rules = rules
    
    def run(self):
        """Run organize operation"""
        output = SavingOutput()
        
        # If specific paths are provided, process them directly
        if self.paths:
            success = 0
            errors = 0
            
            for path in self.paths:
                self.config.execute_for_path(
                    path=Path(path),
                    simulate=self.simulate,
                    output=output,
                )
                
                # Get results
                if output.msg_report:
                    success += output.msg_report.success_count
                    errors += output.msg_report.error_count
        
        # If specific rules are provided, run only those rules
        elif self.rules:
            # Create a new config with only the specified rules
            new_config = Config(rules=self.rules)
            
            if self.parallel:
                new_config.execute_parallel(
                    simulate=self.simulate,
                    output=output,
                    max_workers=self.max_workers,
                )
            else:
                new_config.execute(
                    simulate=self.simulate,
                    output=output,
                )
                
            # Get results
            if output.msg_report:
                success = output.msg_report.success_count
                errors = output.msg_report.error_count
            else:
                success = 0
                errors = 0
        
        # Otherwise, run all rules
        else:
            if self.parallel:
                self.config.execute_parallel(
                    simulate=self.simulate,
                    output=output,
                    max_workers=self.max_workers,
                )
            else:
                self.config.execute(
                    simulate=self.simulate,
                    output=output,
                )
                
            # Get results
            if output.msg_report:
                success = output.msg_report.success_count
                errors = output.msg_report.error_count
            else:
                success = 0
                errors = 0
                
        self.finished.emit(success, errors)


class IndexWorker(QThread):
    """Worker thread for indexing files"""
    progress_update = pyqtSignal(str, int)  # path, count
    finished = pyqtSignal(int)  # total count
    
    def __init__(self, paths: List[str]):
        super().__init__()
        self.paths = paths
    
    def run(self):
        """Run indexing operation"""
        total_count = 0
        
        for path in self.paths:
            path_obj = Path(path)
            count = file_index.index_directory(path_obj, recursive=True)
            self.progress_update.emit(str(path_obj), count)
            total_count += count
            
        self.finished.emit(total_count)


class WatchWorker(QThread):
    """Worker thread for watching directories"""
    event_detected = pyqtSignal(str, str, str)  # time, event_type, path
    
    def __init__(
        self, 
        config: Config, 
        directories: List[str],
        interval: int = 2,
        tags: Optional[List[str]] = None,
        skip_tags: Optional[List[str]] = None,
    ):
        super().__init__()
        self.config = config
        self.directories = directories
        self.interval = interval
        self.tags = set(tags) if tags else set()
        self.skip_tags = set(skip_tags) if skip_tags else set()
        self.running = True
    
    def run(self):
        """Run watch operation"""
        # Define watch handler
        def handler(path, event_type):
            # Get current time
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Emit signal
            self.event_detected.emit(now, event_type, str(path))
            
            # Process the file
            self.config.execute_for_path(
                path=path,
                simulate=False,
                output=SavingOutput(),
                tags=self.tags,
                skip_tags=self.skip_tags,
            )
        
        # Start watching
        paths = [Path(dir) for dir in self.directories]
        watcher.watch(
            paths=paths, 
            callback=handler,
            recursive=True
        )
        watcher.start()
        
        # Keep thread running until stopped
        while self.running:
            self.msleep(100)
            
        # Stop watching
        watcher.stop()
        watcher.join()
    
    def stop(self):
        """Stop watching"""
        self.running = False