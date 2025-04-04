# organize_gui/rule_editor.py
from typing import Dict, List, Optional, Set

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog,
                             QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QPushButton, QRadioButton, QSpinBox, QTabWidget,
                             QTextEdit, QVBoxLayout)

from organize.action import Action
from organize.filter import Filter
from organize.location import Location
from organize.registry import ACTIONS, FILTERS
from organize.rule import Rule


class RuleEditorDialog(QDialog):
    """Dialog for creating and editing rules"""
    
    def __init__(self, parent=None, rule: Optional[Rule] = None):
        super().__init__(parent)
        self.rule = rule
        self.setup_ui()
        
        # If editing existing rule, populate fields
        if rule:
            self.populate_from_rule(rule)
        
    def setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("Edit Rule")
        self.setMinimumSize(700, 500)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Form for basic properties
        form_layout = QFormLayout()
        
        # Rule name
        self.name_edit = QLineEdit()
        form_layout.addRow("Rule Name:", self.name_edit)
        
        # Rule enabled
        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setChecked(True)
        form_layout.addRow("", self.enabled_check)
        
        # Rule targets
        targets_layout = QHBoxLayout()
        self.target_files_radio = QRadioButton("Files")
        self.target_dirs_radio = QRadioButton("Directories")
        self.target_files_radio.setChecked(True)
        
        targets_layout.addWidget(self.target_files_radio)
        targets_layout.addWidget(self.target_dirs_radio)
        targets_layout.addStretch()
        
        form_layout.addRow("Targets:", targets_layout)
        
        # Rule tags
        self.tags_edit = QLineEdit()
        form_layout.addRow("Tags (comma separated):", self.tags_edit)
        
        layout.addLayout(form_layout)
        
        # Tabs for locations, filters, actions
        tabs = QTabWidget()
        
        # Locations tab
        locations_tab = self.create_locations_tab()
        tabs.addTab(locations_tab, "Locations")
        
        # Filters tab
        filters_tab = self.create_filters_tab()
        tabs.addTab(filters_tab, "Filters")
        
        # Actions tab
        actions_tab = self.create_actions_tab()
        tabs.addTab(actions_tab, "Actions")
        
        layout.addWidget(tabs)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
    def create_locations_tab(self):
        """Create the locations tab"""
        tab = QGroupBox("Locations")
        layout = QVBoxLayout(tab)
        
        # Locations list
        self.locations_list = QListWidget()
        layout.addWidget(self.locations_list)
        
        # Add location controls
        add_layout = QHBoxLayout()
        
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("Enter location path...")
        add_layout.addWidget(self.location_edit)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_location)
        add_layout.addWidget(browse_btn)
        
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_location)
        add_layout.addWidget(add_btn)
        
        layout.addLayout(add_layout)
        
        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        
        self.subfolders_check = QCheckBox("Include subfolders")
        options_layout.addWidget(self.subfolders_check)
        
        # Min depth
        min_depth_layout = QHBoxLayout()
        min_depth_layout.addWidget(QLabel("Minimum depth:"))
        self.min_depth_spin = QSpinBox()
        self.min_depth_spin.setRange(0, 100)
        min_depth_layout.addWidget(self.min_depth_spin)
        min_depth_layout.addStretch()
        options_layout.addLayout(min_depth_layout)
        
        # Max depth
        max_depth_layout = QHBoxLayout()
        max_depth_layout.addWidget(QLabel("Maximum depth:"))
        self.max_depth_spin = QSpinBox()
        self.max_depth_spin.setRange(0, 100)
        self.max_depth_spin.setSpecialValueText("No limit")
        max_depth_layout.addWidget(self.max_depth_spin)
        max_depth_layout.addStretch()
        options_layout.addLayout(max_depth_layout)
        
        layout.addWidget(options_group)
        
        return tab
        
    def create_filters_tab(self):
        """Create the filters tab"""
        tab = QGroupBox("Filters")
        layout = QVBoxLayout(tab)
        
        # Filter mode
        mode_group = QGroupBox("Filter Mode")
        mode_layout = QHBoxLayout(mode_group)
        
        self.filter_mode_all = QRadioButton("All")
        self.filter_mode_any = QRadioButton("Any")
        self.filter_mode_none = QRadioButton("None")
        
        self.filter_mode_all.setChecked(True)
        
        mode_layout.addWidget(self.filter_mode_all)
        mode_layout.addWidget(self.filter_mode_any)
        mode_layout.addWidget(self.filter_mode_none)
        mode_layout.addStretch()
        
        layout.addWidget(mode_group)
        
        # Filters list
        self.filters_list = QListWidget()
        layout.addWidget(self.filters_list)
        
        # Add filter controls
        add_layout = QHBoxLayout()
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(sorted(FILTERS.keys()))
        add_layout.addWidget(self.filter_combo)
        
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_filter)
        add_layout.addWidget(add_btn)
        
        layout.addLayout(add_layout)
        
        return tab
        
    def create_actions_tab(self):
        """Create the actions tab"""
        tab = QGroupBox("Actions")
        layout = QVBoxLayout(tab)
        
        # Actions list
        self.actions_list = QListWidget()
        layout.addWidget(self.actions_list)
        
        # Add action controls
        add_layout = QHBoxLayout()
        
        self.action_combo = QComboBox()
        self.action_combo.addItems(sorted(ACTIONS.keys()))
        add_layout.addWidget(self.action_combo)
        
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_action)
        add_layout.addWidget(add_btn)
        
        layout.addLayout(add_layout)
        
        return tab
        
    def browse_location(self):
        """Browse for a location"""
        directory = QFileDialog.getExistingDirectory(self, "Select Location")
        if directory:
            self.location_edit.setText(directory)
            
    def add_location(self):
        """Add a location to the list"""
        location = self.location_edit.text().strip()
        if not location:
            return
            
        self.locations_list.addItem(location)
        self.location_edit.clear()
        
    def add_filter(self):
        """Add a filter to the list"""
        filter_name = self.filter_combo.currentText()
        if not filter_name:
            return
            
        # Create a simple representation for now
        self.filters_list.addItem(f"{filter_name}")
        
    def add_action(self):
        """Add an action to the list"""
        action_name = self.action_combo.currentText()
        if not action_name:
            return
            
        # Create a simple representation for now
        self.actions_list.addItem(f"{action_name}")
        
    def populate_from_rule(self, rule: Rule):
        """Populate fields from existing rule"""
        # Basic properties
        self.name_edit.setText(rule.name or "")
        self.enabled_check.setChecked(rule.enabled)
        
        if rule.targets == "dirs":
            self.target_dirs_radio.setChecked(True)
        else:
            self.target_files_radio.setChecked(True)
            
        self.tags_edit.setText(",".join(rule.tags))
        
        # Locations
        for location in rule.locations:
            for path in location.path:
                self.locations_list.addItem(path)
                
        self.subfolders_check.setChecked(rule.subfolders)
        
        # If any location has min_depth or max_depth set, use those values
        if rule.locations:
            self.min_depth_spin.setValue(rule.locations[0].min_depth)
            if rule.locations[0].max_depth != "inherit" and rule.locations[0].max_depth is not None:
                self.max_depth_spin.setValue(rule.locations[0].max_depth)
        
        # Filter mode
        if rule.filter_mode == "any":
            self.filter_mode_any.setChecked(True)
        elif rule.filter_mode == "none":
            self.filter_mode_none.setChecked(True)
        else:
            self.filter_mode_all.setChecked(True)
            
        # Filters (simplified for now)
        for filter in rule.filters:
            filter_name = filter.filter_config.name
            self.filters_list.addItem(f"{filter_name}")
            
        # Actions (simplified for now)
        for action in rule.actions:
            action_name = action.action_config.name
            self.actions_list.addItem(f"{action_name}")
        
    def get_rule(self) -> Rule:
        """Create a Rule from the dialog fields"""
        from organize.rule import action_from_dict, filter_from_dict

        # Basic properties
        name = self.name_edit.text().strip()
        enabled = self.enabled_check.isChecked()
        targets = "dirs" if self.target_dirs_radio.isChecked() else "files"
        
        tags = set()
        if self.tags_edit.text().strip():
            tags = set(self.tags_edit.text().strip().split(","))
            
        # Locations
        locations = []
        for i in range(self.locations_list.count()):
            path = self.locations_list.item(i).text()
            location = Location(
                path=path,
                min_depth=self.min_depth_spin.value(),
                max_depth=self.max_depth_spin.value() if self.max_depth_spin.value() > 0 else None,
            )
            locations.append(location)
            
        # Filter mode
        if self.filter_mode_any.isChecked():
            filter_mode = "any"
        elif self.filter_mode_none.isChecked():
            filter_mode = "none"
        else:
            filter_mode = "all"
            
        # Filters (simplified for now)
        filters = []
        for i in range(self.filters_list.count()):
            filter_text = self.filters_list.item(i).text()
            filter_name = filter_text.split()[0]
            filter = filter_from_dict({filter_name: None})
            filters.append(filter)
            
        # Actions (simplified for now)
        actions = []
        for i in range(self.actions_list.count()):
            action_text = self.actions_list.item(i).text()
            action_name = action_text.split()[0]
            action = action_from_dict({action_name: None})
            actions.append(action)
            
        # Create the rule
        return Rule(
            name=name,
            enabled=enabled,
            targets=targets,
            locations=locations,
            subfolders=self.subfolders_check.isChecked(),
            tags=tags,
            filters=filters,
            filter_mode=filter_mode,
            actions=actions,
        )