from __future__ import annotations

import os
import textwrap
from pathlib import Path
from typing import Iterable, List, Optional, Set, Union

import yaml
from pydantic import ConfigDict, ValidationError
from pydantic.dataclasses import dataclass

from .errors import ConfigError
from .output import Default, Output
from .resource import Resource
from .template import render
from .utils import ReportSummary, normalize_unicode

Tags = Iterable[str]


def default_yaml_cnst(loader, tag_suffix, node):
    # disable yaml constructors for strings starting with exclamation marks
    # https://stackoverflow.com/a/13281292/300783
    return str(node.tag)


yaml.add_multi_constructor("", default_yaml_cnst, Loader=yaml.SafeLoader)


def should_execute(rule_tags: Tags, tags: Tags, skip_tags: Tags) -> bool:
    """
    returns whether the rule with `rule_tags` should be executed,
    given `tags` and `skip_tags`
    """
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


@dataclass(config=ConfigDict(extra="ignore"))
class Config:
    rules: List[Rule]

    _config_path: Optional[Path] = None

    @classmethod
    def from_string(cls, config: str, config_path: Optional[Path] = None) -> Config:
        normalized = normalize_unicode(config)
        dedented = textwrap.dedent(normalized)
        as_dict = yaml.load(dedented, Loader=yaml.SafeLoader)
        try:
            if not as_dict:
                raise ValueError("Config is empty")
            inst = cls(**as_dict)
            inst._config_path = config_path
            return inst
        except ValidationError as e:
            # add a config_path property to the ValidationError
            raise ConfigError(e=e, config_path=config_path) from e

    @classmethod
    def from_path(cls, config_path: Path) -> Config:
        text = config_path.read_text(encoding="utf-8")
        inst = cls.from_string(text, config_path=config_path)
        return inst

    def execute(
        self,
        simulate: bool = True,
        output: Output = Default(),
        tags: Tags = set(),
        skip_tags: Tags = set(),
        working_dir: Union[str, Path] = ".",
    ) -> None:
        working_path = Path(render(str(working_dir)))
        os.chdir(working_path)
        output.start(
            simulate=simulate,
            config_path=self._config_path,
            working_dir=working_path,
        )
        summary = ReportSummary()
        try:
            for rule_nr, rule in enumerate(self.rules):
                if should_execute(
                    rule_tags=rule.tags,
                    tags=tags,
                    skip_tags=skip_tags,
                ):
                    rule_summary = rule.execute(
                        simulate=simulate,
                        output=output,
                        rule_nr=rule_nr,
                    )
                    summary += rule_summary
        finally:
            output.end(summary.success, summary.errors)
    
    def execute_for_path(
        self,
        path: Path,
        simulate: bool = True,
        output: Output = Default(),
        tags: Tags = set(),
        skip_tags: Tags = set(),
    ) -> None:
        """
        Execute rules for a specific path.
        
        Args:
            path: Path to execute rules for
            simulate: Whether to simulate execution
            output: Output handler
            tags: Tags to run
            skip_tags: Tags to skip
        """
        path = path.resolve()
        output.start(
            simulate=simulate,
            config_path=self._config_path,
            working_dir=Path("."),
        )
        summary = ReportSummary()
        
        try:
            # Create a direct resource from the path
            resource = Resource(path=path)
            
            # Find all rules that should process this resource
            for rule_nr, rule in enumerate(self.rules):
                if not rule.enabled:
                    continue
                    
                if not should_execute(
                    rule_tags=rule.tags,
                    tags=tags,
                    skip_tags=skip_tags,
                ):
                    continue
                
                # Skip rules that don't target this resource type
                if rule.targets == "files" and not resource.is_file():
                    continue
                if rule.targets == "dirs" and not resource.is_dir():
                    continue
                
                # Skip rules with locations that don't match this path
                if rule.locations:
                    location_matches = False
                    for location in rule.locations:
                        for loc_path in location.path:
                            expanded_path = Path(render(loc_path))
                            try:
                                relative = path.relative_to(expanded_path)
                                if relative:
                                    resource.basedir = expanded_path
                                    location_matches = True
                                    break
                            except ValueError:
                                pass
                        if location_matches:
                            break
                            
                    if not location_matches:
                        continue
                
                # Execute the rule with this resource
                res_copy = Resource(
                    path=resource.path,
                    basedir=resource.basedir,
                    rule=rule,
                    rule_nr=rule_nr,
                )
                
                try:
                    rule_summary = rule.execute_for_resource(
                        resource=res_copy,
                        simulate=simulate,
                        output=output,
                    )
                    summary += rule_summary
                except Exception as e:
                    output.msg(
                        res=res_copy,
                        msg=str(e),
                        level="error",
                        sender="execute_for_path",
                    )
                    summary.errors += 1
                    
        finally:
            output.end(summary.success, summary.errors)