import os
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, Iterator, List, Literal, NamedTuple, Optional, Set

from natsort import os_sorted
from pydantic import Field
from pydantic.dataclasses import dataclass


def pattern_match(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch(name, pat) for pat in patterns)


class ScandirResult(NamedTuple):
    dirs: List[os.DirEntry]
    nondirs: List[os.DirEntry]


def scandir(top: str, collectfiles: bool = True) -> ScandirResult:
    result = ScandirResult(dirs=[], nondirs=[])
    try:
        # build iterator if we have the permissions to this folder
        scandir_it = os.scandir(top)
    except OSError:
        return result

    with scandir_it:
        while True:
            try:
                try:
                    entry = next(scandir_it)
                except StopIteration:
                    break
            except OSError:
                return result

            try:
                is_symlink = entry.is_symlink()
            except OSError:
                # If is_symlink() raises an OSError, consider that the
                # entry is not a symbolic link, same behaviour than
                # os.path.islink().
                is_symlink = False

            # As of now, we skip all symlinks.
            if is_symlink:
                continue

            try:
                is_dir = entry.is_dir()
            except OSError:
                # If is_dir() raises an OSError, consider that the entry is not
                # a directory, same behaviour than os.path.isdir().
                is_dir = False

            if is_dir:
                result.dirs.append(entry)
            elif collectfiles:
                result.nondirs.append(entry)
    return ScandirResult(
        dirs=os_sorted(result.dirs, key=lambda x: x.name),
        nondirs=os_sorted(result.nondirs, key=lambda x: x.name),
    )


class DirActions(NamedTuple):
    to_yield: List[os.DirEntry]
    to_walk: List[os.DirEntry]


@dataclass(frozen=True)
class Walker:
    min_depth: int = 0
    max_depth: Optional[int] = None
    method: Literal["breadth", "depth"] = "breadth"
    filter_dirs: Optional[List[str]] = None
    filter_files: Optional[List[str]] = None
    exclude_dirs: Set[str] = Field(default_factory=set)
    exclude_files: Set[str] = Field(default_factory=set)
    use_index: bool = False

    def _should_yield_file(self, entry: os.DirEntry, lvl: int) -> bool:
        return (
            lvl >= self.min_depth
            and not pattern_match(entry.name, self.exclude_files)
            and (
                self.filter_files is None
                or pattern_match(entry.name, self.filter_files)
            )
        )

    def _dir_actions(self, entries: Iterable[os.DirEntry], lvl: int) -> DirActions:
        result = DirActions(to_yield=[], to_walk=[])
        for entry in entries:
            if not pattern_match(entry.name, self.exclude_dirs) and (
                self.filter_dirs is None or pattern_match(entry.name, self.filter_dirs)
            ):
                if self.max_depth is None or lvl < self.max_depth:
                    result.to_walk.append(entry)
                if lvl >= self.min_depth:
                    result.to_yield.append(entry)
        return result

    def walk(
        self,
        top: str,
        files: bool = True,
        dirs: bool = True,
        lvl: int = 0,
    ) -> Iterator[os.DirEntry]:
        if not files and not dirs:
            return

        # If using the index, check if it's available first
        if self.use_index:
            try:
                from organize.indexer import file_index

                # For directories, we can use the index directly
                if dirs and not files:
                    for file_info in file_index.get_files_by_tag("is_dir", "True"):
                        path = Path(file_info.path)
                        if self._should_yield_indexed_dir(path, top, lvl):
                            yield path
                    return
                    
                # For files, we can use the index too
                if files and not dirs:
                    for file_info in file_index.get_files_by_tag("is_dir", "False"):
                        path = Path(file_info.path)
                        if self._should_yield_indexed_file(path, top, lvl):
                            yield path
                    return
            except (ImportError, AttributeError):
                # Index not available, fall back to regular walking
                pass

        # list all dirs and nondirs of the folder
        result = scandir(top, collectfiles=files)

        if self.method == "breadth":
            # Return entries
            for entry in result.nondirs:
                if files and self._should_yield_file(entry=entry, lvl=lvl):
                    yield entry
            dir_actions = self._dir_actions(result.dirs, lvl=lvl)
            if dirs:
                yield from dir_actions.to_yield
            # Recurse into sub-directories
            for entry in dir_actions.to_walk:
                yield from self.walk(entry.path, files=files, dirs=dirs, lvl=lvl + 1)

        elif self.method == "depth":
            dir_actions = self._dir_actions(result.dirs, lvl=lvl)
            # Recurse into sub-directories
            for entry in dir_actions.to_walk:
                yield from self.walk(entry.path, files=files, dirs=dirs, lvl=lvl + 1)
            # Return entries
            for entry in result.nondirs:
                if files and self._should_yield_file(entry=entry, lvl=lvl):
                    yield entry
            if dirs:
                yield from dir_actions.to_yield
        else:
            raise ValueError(f'Unknown method "{self.method}"')
            
    def _should_yield_indexed_file(self, path: Path, top: str, lvl: int) -> bool:
        """Check if an indexed file should be yielded."""
        # Check if the file is in the correct base directory
        try:
            rel_path = path.relative_to(top)
        except ValueError:
            return False
            
        # Check depth
        depth = len(rel_path.parts) - 1
        if depth < self.min_depth:
            return False
        if self.max_depth is not None and depth > self.max_depth:
            return False
            
        # Check exclusions and filters
        if pattern_match(path.name, self.exclude_files):
            return False
            
        if self.filter_files is not None and not pattern_match(path.name, self.filter_files):
            return False
            
        return True
        
    def _should_yield_indexed_dir(self, path: Path, top: str, lvl: int) -> bool:
        """Check if an indexed directory should be yielded."""
        # Check if the directory is in the correct base directory
        try:
            rel_path = path.relative_to(top)
        except ValueError:
            return False
            
        # Check depth
        depth = len(rel_path.parts) - 1
        if depth < self.min_depth:
            return False
        if self.max_depth is not None and depth > self.max_depth:
            return False
            
        # Check exclusions and filters
        if pattern_match(path.name, self.exclude_dirs):
            return False
            
        if self.filter_dirs is not None and not pattern_match(path.name, self.filter_dirs):
            return False
            
        return True

    def files(self, path: str) -> Iterator[Path]:
        # if path is a single file we emit just the path itself
        if os.path.isfile(path):
            yield Path(path)
            return
        # otherwise we walk the given folder
        for entry in self.walk(path, files=True, dirs=False):
            if isinstance(entry, Path):
                yield entry
            else:
                yield Path(entry.path)

    def dirs(self, path: str) -> Iterator[Path]:
        for entry in self.walk(path, files=False, dirs=True):
            if isinstance(entry, Path):
                yield entry
            else:
                yield Path(entry.path)