__doc__ = """
organize - The file management automation tool.

Usage:
  organize run    [options] [<config> | --stdin]
  organize sim    [options] [<config> | --stdin]
  organize watch  [options] [<config> | --stdin]
  organize new    [<config>]
  organize edit   [<config>]
  organize check  [<config> | --stdin]
  organize debug  [<config> | --stdin]
  organize show   [--path|--reveal] [<config>]
  organize list
  organize docs
  organize --version
  organize --help
  organize index  [options] <directory>...
  organize stats

Commands:
  run        Organize your files.
  sim        Simulate organizing your files.
  watch      Watch directories and organize files in real-time.
  new        Creates a default config.
  edit       Edit the config file with $EDITOR
  check      Check config file validity
  debug      Shows the raw config parsing steps.
  show       Print the config to stdout.
               Use --reveal to reveal the file in your file manager
               Use --path to show the path to the file
  list       Lists config files found in the default locations.
  docs       Open the documentation.
  index      Index directories for faster processing.
  stats      Show statistics about the file index.

Options:
  <config>                        A config name or path to a config file.
                                  Some commands also support piping in a config file
                                  via the `--stdin` flag.
  -W --working-dir <dir>          The working directory
  -F --format (default|errorsonly|JSONL)
                                  The output format [Default: default]
  -T --tags <tags>                Tags to run (eg. "initial,release")
  -S --skip-tags <tags>           Tags to skip
  -I --interval <seconds>         Interval in seconds for watch command [Default: 2]
  -h --help                       Show this help page.
  -P --parallel                   Enable parallel execution
  -W --max-workers <workers>      Maximum number of worker threads for parallel execution
"""
import os
import sys
import time
from functools import partial
from pathlib import Path
from typing import Annotated, Dict, Literal, Optional, Set, Union

from docopt import docopt
from pydantic import (BaseModel, ConfigDict, Field, ValidationError,
                      model_validator)
from pydantic.functional_validators import BeforeValidator
from rich.console import Console
from rich.pretty import pprint
from rich.syntax import Syntax
from rich.table import Table
from yaml.scanner import ScannerError

from organize import Config, ConfigError
from organize.find_config import (DOCS_RTD, ConfigNotFound,
                                  create_example_config, find_config,
                                  list_configs)
from organize.logger import enable_logfile
from organize.output import JSONL, Default, Output
from organize.utils import escape
from organize.watcher import watcher

from .__version__ import __version__

Tags = Set[str]
OutputFormat = Annotated[
    Literal["default", "jsonl", "errorsonly"], BeforeValidator(lambda v: v.lower())
]

console = Console()


class ConfigWithPath(BaseModel):
    """
    Allows reading the config from a path, finding it by name or supplying it directly
    via stdin.
    """

    config: str
    config_path: Optional[Path]

    @classmethod
    def from_stdin(cls) -> "ConfigWithPath":
        return cls(config=sys.stdin.read(), config_path=None)

    @classmethod
    def by_name_or_path(cls, name_or_path: Optional[str]) -> "ConfigWithPath":
        config_path = find_config(name_or_path=name_or_path)
        return cls(
            config=config_path.read_text(encoding="utf-8"),
            config_path=config_path,
        )

    def path(self):
        if self.config_path is not None:
            return str(self.config_path)
        return "[config given by string / stdin]"


def _open_uri(uri: str) -> None:
    import webbrowser

    webbrowser.open(uri)


def _output_for_format(format: OutputFormat) -> Output:
    if format == "default":
        return Default()
    elif format == "errorsonly":
        return Default(errors_only=True)
    elif format == "jsonl":
        return JSONL()
    raise ValueError(f"{format} is not a valid output format.")


def execute(
    config: ConfigWithPath,
    working_dir: Optional[Path],
    format: OutputFormat,
    tags: Tags,
    skip_tags: Tags,
    simulate: bool,
    parallel: bool = False,
    max_workers: Optional[int] = None,
) -> None:
    cfg = Config.from_string(
        config=config.config,
        config_path=config.config_path,
    )
    
    if parallel:
        cfg.execute_parallel(
            simulate=simulate,
            output=_output_for_format(format),
            tags=tags,
            skip_tags=skip_tags,
            working_dir=working_dir or Path("."),
            max_workers=max_workers,
        )
    else:
        cfg.execute(
            simulate=simulate,
            output=_output_for_format(format),
            tags=tags,
            skip_tags=skip_tags,
            working_dir=working_dir or Path("."),
        )


def watch_handler(
    path: Path, 
    event_type: str,
    config: Config,
    format: OutputFormat,
    tags: Tags,
    skip_tags: Tags,
) -> None:
    """Handle file system events and run organize rules"""
    console.print(f"Event: {event_type} - {path}")
    try:
        config.execute_for_path(
            path=path,
            simulate=False,
            output=_output_for_format(format),
            tags=tags,
            skip_tags=skip_tags,
        )
    except Exception as e:
        console.print(f"[red]Error processing {path}:[/] {e}")


def watch(
    config: ConfigWithPath,
    working_dir: Optional[Path],
    format: OutputFormat,
    tags: Tags,
    skip_tags: Tags,
    interval: float,
) -> None:
    """Watch directories and organize files in real-time"""
    from organize.watcher import watcher

    # Load config
    cfg = Config.from_string(
        config=config.config,
        config_path=config.config_path,
    )
    
    # Get all unique paths from rules
    watch_paths: Set[Path] = set()
    for rule in cfg.rules:
        if rule.enabled and should_execute(
            rule_tags=rule.tags,
            tags=tags,
            skip_tags=skip_tags,
        ):
            for location in rule.locations:
                for loc_path in location.path:
                    expanded_path = Path(render(loc_path))
                    watch_paths.add(expanded_path)
    
    if not watch_paths:
        console.print("[yellow]No directories to watch![/] Check your configuration.")
        return
    
    # Set up callback
    handler = partial(
        watch_handler,
        config=cfg,
        format=format,
        tags=tags,
        skip_tags=skip_tags,
    )
    
    # Start watching
    console.print(f"[green]Watching {len(watch_paths)} directories:[/]")
    for path in watch_paths:
        console.print(f"  - {path}")
    
    try:
        watcher.watch(
            paths=list(watch_paths),
            callback=handler,
            recursive=True,
        )
        watcher.start()
        
        console.print(
            "\n[green]Watching for changes...[/] Press Ctrl+C to stop."
        )
        
        while True:
            time.sleep(interval)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping watcher...[/]")
    finally:
        watcher.stop()
        watcher.join()


def new(config: Optional[str]) -> None:
    try:
        new_path = create_example_config(name_or_path=config)
        console.print(
            f'Config "{escape(new_path.name)}" created at "{escape(new_path.absolute())}"'
        )
    except FileExistsError as e:
        console.print(
            f"{e}\n"
            r'Use "organize new \[name]" to create a config in the default location.'
        )
        sys.exit(1)


def edit(config: Optional[str]) -> None:
    config_path = find_config(config)
    editor = os.getenv("EDITOR")
    if editor:
        os.system(f'{editor} "{config_path}"')
    else:
        _open_uri(config_path.as_uri())


def check(config: ConfigWithPath) -> None:
    Config.from_string(config=config.config, config_path=config.config_path)
    console.print(f'No problems found in "{escape(config.path())}".')


def debug(config: ConfigWithPath) -> None:
    conf = Config.from_string(config=config.config, config_path=config.config_path)
    pprint(conf, expand_all=True, indent_guides=False)


def show(config: Optional[str], path: bool, reveal: bool) -> None:
    config_path = find_config(name_or_path=config)
    if path:
        print(config_path)
    elif reveal:
        _open_uri(config_path.parent.as_uri())
    else:
        syntax = Syntax(config_path.read_text(encoding="utf-8"), "yaml")
        console.print(syntax)


def list_() -> None:
    table = Table()
    table.add_column("Config")
    table.add_column("Path", no_wrap=True, style="dim")
    for path in list_configs():
        table.add_row(path.stem, str(path))
    console.print(table)


def docs() -> None:
    uri = DOCS_RTD
    print(f'Opening "{escape(uri)}"')
    _open_uri(uri=uri)


def should_execute(rule_tags: Tags, tags: Tags, skip_tags: Tags) -> bool:
    """Imported from config.py to fix circular imports"""
    if not rule_tags:
        rule_tags = set()
    if not tags:
        tags = set()
    if not skip_tags:
        skip_tags = set()

    if "always" in rule_tags and "always" not in skip_tags:
        return True
    if "never" in rule_tags and "never" not in tags:
        return False
    if not tags and not skip_tags:
        return True
    if not rule_tags and tags:
        return False
    should_run = any(tag in tags for tag in rule_tags) or not tags or not rule_tags
    should_skip = any(tag in skip_tags for tag in rule_tags)
    return should_run and not should_skip


def render(template: str) -> str:
    """Simplified render function to avoid circular imports"""
    from organize.template import render
    return render(template)


class CliArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # commands
    run: bool
    sim: bool
    watch: bool
    new: bool
    edit: bool
    check: bool
    debug: bool
    show: bool
    list: bool
    docs: bool

    # run / sim / watch options
    config: Optional[str] = Field(..., alias="<config>")
    working_dir: Optional[Path] = Field(..., alias="--working-dir")
    format: OutputFormat = Field("default", alias="--format")
    tags: Optional[str] = Field(..., alias="--tags")
    skip_tags: Optional[str] = Field(..., alias="--skip-tags")
    stdin: bool = Field(..., alias="--stdin")
    interval: float = Field(2.0, alias="--interval")
    parallel: bool = Field(False, alias="--parallel")
    max_workers: Optional[int] = Field(None, alias="--max-workers")
    index: bool = Field(False)
    stats: bool = Field(False)
    directory: List[str] = Field(default_factory=list, alias="<directory>")

    # show options
    path: bool = Field(False, alias="--path")
    reveal: bool = Field(False, alias="--reveal")

    # docopt options
    version: bool = Field(..., alias="--version")
    help: bool = Field(..., alias="--help")

    @model_validator(mode="after")
    def either_stdin_or_config(self):
        if self.stdin and self.config is not None:
            raise ValueError("Either set a config file or --stdin.")
        return self


def _split_tags(val: Optional[str]) -> Tags:
    if val is None:
        return set()
    return set(val.split(","))


def cli(argv: Union[list[str], str, None] = None) -> None:
    enable_logfile()
    assert __doc__ is not None
    parsed_args = docopt(
        __doc__,
        argv=argv,
        default_help=True,
        version=f"organize v{__version__}",
    )
    try:
        args = CliArgs.model_validate(parsed_args)

        def _config_with_path():
            if args.stdin:
                return ConfigWithPath.from_stdin()
            else:
                return ConfigWithPath.by_name_or_path(args.config)

        if args.run or args.sim or args.watch:
            tags = _split_tags(args.tags)
            skip_tags = _split_tags(args.skip_tags)
            
            if args.run:
                execute(
                    config=_config_with_path(),
                    working_dir=args.working_dir,
                    format=args.format,
                    tags=tags,
                    skip_tags=skip_tags,
                    simulate=False,
                )
            elif args.sim:
                execute(
                    config=_config_with_path(),
                    working_dir=args.working_dir,
                    format=args.format,
                    tags=tags,
                    skip_tags=skip_tags,
                    simulate=True,
                )
            elif args.watch:
                watch(
                    config=_config_with_path(),
                    working_dir=args.working_dir,
                    format=args.format,
                    tags=tags,
                    skip_tags=skip_tags,
                    interval=args.interval,
                )
        elif args.new:
            new(config=args.config)
        elif args.edit:
            edit(config=args.config)
        elif args.check:
            check(config=_config_with_path())
        elif args.debug:
            debug(config=_config_with_path())
        elif args.show:
            show(config=args.config, path=args.path, reveal=args.reveal)
        elif args.list:
            list_()
        elif args.docs:
            docs()
        elif args.index:
            index_directories(args.directory)
        elif args.stats:
            show_index_stats()
    except (ConfigError, ConfigNotFound) as e:
        console.print(f"[red]Error: Config problem[/]\n{escape(e)}")
        sys.exit(1)
    except ValidationError as e:
        console.print(f"[red]Error: Invalid CLI arguments[/]\n{escape(e)}")
        sys.exit(2)
    except ScannerError as e:
        console.print(f"[red]Error: YAML syntax error[/]\n{escape(e)}")
        sys.exit(3)

def index_directories(directories: List[str], recursive: bool = True) -> None:
    """Index the given directories."""
    from organize.indexer import file_index
    
    total = 0
    for directory in directories:
        path = Path(directory).expanduser().resolve()
        if not path.exists():
            console.print(f"[red]Directory not found:[/] {path}")
            continue
            
        if not path.is_dir():
            console.print(f"[red]Not a directory:[/] {path}")
            continue
            
        console.print(f"Indexing [blue]{path}[/]...")
        count = file_index.index_directory(path, recursive=recursive)
        console.print(f"Indexed [green]{count}[/] files and directories.")
        total += count
        
    console.print(f"Total: [green]{total}[/] files and directories indexed.")


def show_index_stats() -> None:
    """Show statistics about the file index."""
    from organize.indexer import file_index
    
    stats = file_index.get_statistics()
    
    table = Table(title="File Index Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Files", f"{stats['file_count']:,}")
    table.add_row("Directories", f"{stats['directory_count']:,}")
    table.add_row("Total Size", f"{stats['total_size']:,} bytes")
    table.add_row("Tags", f"{stats['tag_count']:,}")
    table.add_row("Last Update", stats['last_update'])
    table.add_row("Database Size", f"{stats['database_size']:,} bytes")
    
    console.print(table)


if __name__ == "__main__":
    cli()