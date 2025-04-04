# organize_gui/main.py
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QDir, QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                             QFileSystemModel, QGroupBox, QHBoxLayout,
                             QHeaderView, QLabel, QLineEdit, QMainWindow,
                             QMenu, QMessageBox, QProgressBar, QPushButton,
                             QSpinBox, QSystemTrayIcon, QTableWidget,
                             QTableWidgetItem, QTabWidget, QTreeView,
                             QVBoxLayout, QWidget)

# Import organize modules
from organize import Config, Rule
from organize.indexer import file_index
from organize.output import SavingOutput
from organize.resource import Resource
from organize.watcher import watcher

from .config_manager import ConfigManager
from .rule_editor import RuleEditorDialog
from .settings import Settings
from .utils import format_size, format_time, get_resource_path
# Local imports
from .worker import IndexWorker, OrganizeWorker, WatchWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize settings and config
        self.settings = Settings()
        self.config_manager = ConfigManager(self.settings)
        
        # Setup UI
        self.setup_ui()
        self.setup_tray()
        
        # Load saved configuration
        self.load_saved_config()
        
        # Connect signals
        self.connect_signals()
        
        # Start timer for stats refresh
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.refresh_stats)
        self.stats_timer.start(10000)  # Refresh every 10 seconds
        
    def setup_ui(self):
        self.setWindowTitle("Organize Tool")
        self.setMinimumSize(900, 600)
        
        # Set icon
        self.setWindowIcon(QIcon(get_resource_path("icons/app_icon.png")))
        
        # Create main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Create tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Create tab contents
        self.create_dashboard_tab()
        self.create_files_tab()
        self.create_rules_tab()
        self.create_watch_tab()
        self.create_settings_tab()
        
        # Status bar with current config
        self.statusBar().showMessage("Ready")
        
    def create_dashboard_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Header
        header = QLabel("Dashboard")
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(header)
        
        # Stats overview
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_table = QTableWidget(0, 2)
        self.stats_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.stats_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.stats_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.stats_table.verticalHeader().setVisible(False)
        stats_layout.addWidget(self.stats_table)
        
        layout.addWidget(stats_group)
        
        # Quick actions
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout(actions_group)
        
        run_btn = QPushButton("Run Organize")
        run_btn.clicked.connect(self.run_organize)
        actions_layout.addWidget(run_btn)
        
        simulate_btn = QPushButton("Simulate")
        simulate_btn.clicked.connect(self.simulate_organize)
        actions_layout.addWidget(simulate_btn)
        
        watch_btn = QPushButton("Start Watching")
        watch_btn.clicked.connect(self.toggle_watch)
        self.watch_btn = watch_btn
        actions_layout.addWidget(watch_btn)
        
        index_btn = QPushButton("Index Files")
        index_btn.clicked.connect(self.start_indexing)
        actions_layout.addWidget(index_btn)
        
        layout.addWidget(actions_group)
        
        # Recent activity
        activity_group = QGroupBox("Recent Activity")
        activity_layout = QVBoxLayout(activity_group)
        
        self.activity_table = QTableWidget(0, 3)
        self.activity_table.setHorizontalHeaderLabels(["Time", "Action", "Path"])
        self.activity_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.activity_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.activity_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.activity_table.verticalHeader().setVisible(False)
        activity_layout.addWidget(self.activity_table)
        
        layout.addWidget(activity_group)
        
        self.tabs.addTab(tab, "Dashboard")
        
    def create_files_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Header with folder selection
        header_layout = QHBoxLayout()
        
        browse_label = QLabel("Browse:")
        header_layout.addWidget(browse_label)
        
        self.path_combo = QComboBox()
        self.path_combo.setEditable(True)
        self.path_combo.addItems([str(Path.home())])
        self.path_combo.currentTextChanged.connect(self.update_file_view)
        header_layout.addWidget(self.path_combo, 1)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_directory)
        header_layout.addWidget(browse_btn)
        
        layout.addLayout(header_layout)
        
        # File tree view
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(str(Path.home()))
        
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setRootIndex(self.file_model.index(str(Path.home())))
        self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.file_context_menu)
        
        # Configure columns
        self.file_tree.setColumnWidth(0, 300)
        
        layout.addWidget(self.file_tree)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        organize_selected_btn = QPushButton("Organize Selected")
        organize_selected_btn.clicked.connect(self.organize_selected)
        btn_layout.addWidget(organize_selected_btn)
        
        index_selected_btn = QPushButton("Index Selected")
        index_selected_btn.clicked.connect(self.index_selected)
        btn_layout.addWidget(index_selected_btn)
        
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        self.tabs.addTab(tab, "Files")
        
    def create_rules_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Header with config selection
        header_layout = QHBoxLayout()
        
        config_label = QLabel("Configuration:")
        header_layout.addWidget(config_label)
        
        self.config_combo = QComboBox()
        self.config_combo.currentIndexChanged.connect(self.load_config)
        header_layout.addWidget(self.config_combo, 1)
        
        new_config_btn = QPushButton("New")
        new_config_btn.clicked.connect(self.create_new_config)
        header_layout.addWidget(new_config_btn)
        
        open_config_btn = QPushButton("Open...")
        open_config_btn.clicked.connect(self.open_config)
        header_layout.addWidget(open_config_btn)
        
        save_config_btn = QPushButton("Save")
        save_config_btn.clicked.connect(self.save_config)
        header_layout.addWidget(save_config_btn)
        
        layout.addLayout(header_layout)
        
        # Rules table
        self.rules_table = QTableWidget(0, 4)
        self.rules_table.setHorizontalHeaderLabels(["Enabled", "Name", "Locations", "Actions"])
        self.rules_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.rules_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.rules_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.rules_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.rules_table.verticalHeader().setVisible(False)
        self.rules_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.rules_table.customContextMenuRequested.connect(self.rule_context_menu)
        layout.addWidget(self.rules_table)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        add_rule_btn = QPushButton("Add Rule")
        add_rule_btn.clicked.connect(self.add_rule)
        btn_layout.addWidget(add_rule_btn)
        
        edit_rule_btn = QPushButton("Edit Rule")
        edit_rule_btn.clicked.connect(self.edit_selected_rule)
        btn_layout.addWidget(edit_rule_btn)
        
        delete_rule_btn = QPushButton("Delete Rule")
        delete_rule_btn.clicked.connect(self.delete_selected_rule)
        btn_layout.addWidget(delete_rule_btn)
        
        btn_layout.addStretch()
        
        run_selected_btn = QPushButton("Run Selected Rules")
        run_selected_btn.clicked.connect(self.run_selected_rules)
        btn_layout.addWidget(run_selected_btn)
        
        layout.addLayout(btn_layout)
        
        self.tabs.addTab(tab, "Rules")
        
    def create_watch_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Watch configuration
        watch_group = QGroupBox("Watch Configuration")
        watch_layout = QVBoxLayout(watch_group)
        
        # Enable watching checkbox
        self.watch_enabled_check = QCheckBox("Enable file watching")
        self.watch_enabled_check.toggled.connect(self.toggle_watch)
        watch_layout.addWidget(self.watch_enabled_check)
        
        # Interval setting
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Check interval (seconds):")
        interval_layout.addWidget(interval_label)
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(2)
        interval_layout.addWidget(self.interval_spin)
        
        interval_layout.addStretch()
        watch_layout.addLayout(interval_layout)
        
        # Tags to include/exclude
        tags_layout = QHBoxLayout()
        
        tags_label = QLabel("Tags to run:")
        tags_layout.addWidget(tags_label)
        
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Tag1,Tag2,...")
        tags_layout.addWidget(self.tags_edit)
        
        skip_tags_label = QLabel("Tags to skip:")
        tags_layout.addWidget(skip_tags_label)
        
        self.skip_tags_edit = QLineEdit()
        self.skip_tags_edit.setPlaceholderText("Tag1,Tag2,...")
        tags_layout.addWidget(self.skip_tags_edit)
        
        watch_layout.addLayout(tags_layout)
        
        # Watched directories list
        self.watched_dirs_table = QTableWidget(0, 2)
        self.watched_dirs_table.setHorizontalHeaderLabels(["Directory", "Actions"])
        self.watched_dirs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.watched_dirs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.watched_dirs_table.verticalHeader().setVisible(False)
        watch_layout.addWidget(self.watched_dirs_table)
        
        # Add watch directory
        add_watch_layout = QHBoxLayout()
        
        self.add_watch_edit = QLineEdit()
        self.add_watch_edit.setPlaceholderText("Directory path...")
        add_watch_layout.addWidget(self.add_watch_edit)
        
        add_watch_browse_btn = QPushButton("Browse...")
        add_watch_browse_btn.clicked.connect(self.browse_watch_directory)
        add_watch_layout.addWidget(add_watch_browse_btn)
        
        add_watch_btn = QPushButton("Add")
        add_watch_btn.clicked.connect(self.add_watch_directory)
        add_watch_layout.addWidget(add_watch_btn)
        
        watch_layout.addLayout(add_watch_layout)
        
        layout.addWidget(watch_group)
        
        # Activity log
        log_group = QGroupBox("Watch Activity")
        log_layout = QVBoxLayout(log_group)
        
        self.watch_log_table = QTableWidget(0, 3)
        self.watch_log_table.setHorizontalHeaderLabels(["Time", "Event", "Path"])
        self.watch_log_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.watch_log_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.watch_log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.watch_log_table.verticalHeader().setVisible(False)
        log_layout.addWidget(self.watch_log_table)
        
        layout.addWidget(log_group)
        
        self.tabs.addTab(tab, "Watch")
        
    def create_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Application settings
        app_group = QGroupBox("Application Settings")
        app_layout = QVBoxLayout(app_group)
        
        # Start minimized
        self.start_minimized_check = QCheckBox("Start minimized to system tray")
        self.start_minimized_check.setChecked(self.settings.get("start_minimized", False))
        app_layout.addWidget(self.start_minimized_check)
        
        # Minimize to tray
        self.minimize_to_tray_check = QCheckBox("Minimize to system tray when closed")
        self.minimize_to_tray_check.setChecked(self.settings.get("minimize_to_tray", True))
        app_layout.addWidget(self.minimize_to_tray_check)
        
        # Show notifications
        self.show_notifications_check = QCheckBox("Show notifications")
        self.show_notifications_check.setChecked(self.settings.get("show_notifications", True))
        app_layout.addWidget(self.show_notifications_check)
        
        # Parallel processing
        parallel_layout = QHBoxLayout()
        
        self.parallel_check = QCheckBox("Enable parallel processing")
        self.parallel_check.setChecked(self.settings.get("parallel_processing", True))
        parallel_layout.addWidget(self.parallel_check)
        
        workers_label = QLabel("Max workers:")
        parallel_layout.addWidget(workers_label)
        
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 32)
        self.workers_spin.setValue(self.settings.get("max_workers", 4))
        parallel_layout.addWidget(self.workers_spin)
        
        parallel_layout.addStretch()
        app_layout.addLayout(parallel_layout)
        
        # Default config
        default_config_layout = QHBoxLayout()
        
        default_config_label = QLabel("Default configuration:")
        default_config_layout.addWidget(default_config_label)
        
        self.default_config_edit = QLineEdit()
        self.default_config_edit.setText(self.settings.get("default_config", ""))
        default_config_layout.addWidget(self.default_config_edit)
        
        default_config_browse_btn = QPushButton("Browse...")
        default_config_browse_btn.clicked.connect(self.browse_default_config)
        default_config_layout.addWidget(default_config_browse_btn)
        
        app_layout.addLayout(default_config_layout)
        
        layout.addWidget(app_group)
        
        # File indexing settings
        index_group = QGroupBox("File Indexing")
        index_layout = QVBoxLayout(index_group)
        
        # Enable indexing
        self.indexing_enabled_check = QCheckBox("Enable file indexing")
        self.indexing_enabled_check.setChecked(self.settings.get("indexing_enabled", True))
        index_layout.addWidget(self.indexing_enabled_check)
        
        # Index on startup
        self.index_on_startup_check = QCheckBox("Index directories on startup")
        self.index_on_startup_check.setChecked(self.settings.get("index_on_startup", False))
        index_layout.addWidget(self.index_on_startup_check)
        
        # Index directories
        index_dirs_label = QLabel("Index directories:")
        index_layout.addWidget(index_dirs_label)
        
        self.index_dirs_table = QTableWidget(0, 2)
        self.index_dirs_table.setHorizontalHeaderLabels(["Directory", "Actions"])
        self.index_dirs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.index_dirs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.index_dirs_table.verticalHeader().setVisible(False)
        index_layout.addWidget(self.index_dirs_table)
        
        # Add index directory
        add_index_layout = QHBoxLayout()
        
        self.add_index_edit = QLineEdit()
        self.add_index_edit.setPlaceholderText("Directory path...")
        add_index_layout.addWidget(self.add_index_edit)
        
        add_index_browse_btn = QPushButton("Browse...")
        add_index_browse_btn.clicked.connect(self.browse_index_directory)
        add_index_layout.addWidget(add_index_browse_btn)
        
        add_index_btn = QPushButton("Add")
        add_index_btn.clicked.connect(self.add_index_directory)
        add_index_layout.addWidget(add_index_btn)
        
        index_layout.addLayout(add_index_layout)
        
        layout.addWidget(index_group)
        
        # Save and reset buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_settings_btn = QPushButton("Save Settings")
        save_settings_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(save_settings_btn)
        
        reset_settings_btn = QPushButton("Reset to Defaults")
        reset_settings_btn.clicked.connect(self.reset_settings)
        btn_layout.addWidget(reset_settings_btn)
        
        layout.addLayout(btn_layout)
        
        self.tabs.addTab(tab, "Settings")

    def setup_tray(self):
        """Setup system tray icon and menu"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(get_resource_path("icons/app_icon.png")))
        
        # Create tray menu
        tray_menu = QMenu()
        
        # Run organize action
        run_action = QAction("Run Organize", self)
        run_action.triggered.connect(self.run_organize)
        tray_menu.addAction(run_action)
        
        # Simulate action
        simulate_action = QAction("Simulate", self)
        simulate_action.triggered.connect(self.simulate_organize)
        tray_menu.addAction(simulate_action)
        
        # Watch toggle action
        self.watch_action = QAction("Start Watching", self)
        self.watch_action.triggered.connect(self.toggle_watch)
        tray_menu.addAction(self.watch_action)
        
        tray_menu.addSeparator()
        
        # Show/hide window action
        self.show_hide_action = QAction("Hide Window", self)
        self.show_hide_action.triggered.connect(self.toggle_window)
        tray_menu.addAction(self.show_hide_action)
        
        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.exit_app)
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()
        
    def connect_signals(self):
        """Connect all signals"""
        # Connect close event
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    
    def load_saved_config(self):
        """Load the saved configuration"""
        # Load configs
        configs = self.config_manager.list_configs()
        self.config_combo.clear()
        self.config_combo.addItems(configs)
        
        # Set default config if available
        default_config = self.settings.get("default_config", "")
        if default_config and default_config in configs:
            self.config_combo.setCurrentText(default_config)
        
        # Load index directories
        self.update_index_dirs_table()
        
        # Load watch directories
        self.update_watch_dirs_table()
        
        # Refresh stats
        self.refresh_stats()
        
    # File tab methods
    def browse_directory(self):
        """Open directory browser dialog"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory", self.path_combo.currentText()
        )
        if directory:
            self.path_combo.addItem(directory)
            self.path_combo.setCurrentText(directory)
            
    def update_file_view(self, path):
        """Update file tree view with new path"""
        if path and os.path.isdir(path):
            self.file_tree.setRootIndex(self.file_model.index(path))
            
    def file_context_menu(self, position):
        """Show context menu for file tree"""
        index = self.file_tree.indexAt(position)
        if not index.isValid():
            return
            
        path = self.file_model.filePath(index)
        
        menu = QMenu()
        
        organize_action = QAction("Organize", self)
        organize_action.triggered.connect(lambda: self.organize_path(path))
        menu.addAction(organize_action)
        
        simulate_action = QAction("Simulate", self)
        simulate_action.triggered.connect(lambda: self.simulate_path(path))
        menu.addAction(simulate_action)
        
        menu.addSeparator()
        
        index_action = QAction("Add to Index", self)
        index_action.triggered.connect(lambda: self.index_path(path))
        menu.addAction(index_action)
        
        watch_action = QAction("Add to Watch List", self)
        watch_action.triggered.connect(lambda: self.add_to_watch_list(path))
        menu.addAction(watch_action)
        
        menu.exec(self.file_tree.viewport().mapToGlobal(position))
            
    def organize_selected(self):
        """Organize selected files/folders"""
        indexes = self.file_tree.selectedIndexes()
        if not indexes:
            return
            
        # Get unique paths (only first column)
        paths = set()
        for index in indexes:
            if index.column() == 0:
                path = self.file_model.filePath(index)
                paths.add(path)
                
        for path in paths:
            self.organize_path(path)
            
    def index_selected(self):
        """Index selected files/folders"""
        indexes = self.file_tree.selectedIndexes()
        if not indexes:
            return
            
        # Get unique paths (only first column)
        paths = set()
        for index in indexes:
            if index.column() == 0:
                path = self.file_model.filePath(index)
                if os.path.isdir(path):
                    paths.add(path)
                
        self.index_paths(list(paths))
            
    def organize_path(self, path):
        """Organize a specific path"""
        if not self.config_manager.current_config:
            QMessageBox.warning(self, "No Configuration", "Please select a configuration first.")
            return
            
        self.run_organize(paths=[path])
        
    def simulate_path(self, path):
        """Simulate organize for a specific path"""
        if not self.config_manager.current_config:
            QMessageBox.warning(self, "No Configuration", "Please select a configuration first.")
            return
            
        self.simulate_organize(paths=[path])
        
    def index_path(self, path):
        """Add a path to the index"""
        if not os.path.isdir(path):
            QMessageBox.warning(self, "Not a Directory", "Can only index directories.")
            return
            
        self.index_paths([path])
        
    def add_to_watch_list(self, path):
        """Add a path to the watch list"""
        if not os.path.isdir(path):
            QMessageBox.warning(self, "Not a Directory", "Can only watch directories.")
            return
            
        # Add to settings
        watch_dirs = self.settings.get("watch_directories", [])
        if path not in watch_dirs:
            watch_dirs.append(path)
            self.settings.set("watch_directories", watch_dirs)
            self.update_watch_dirs_table()
            
            # Update watcher if running
            if self.watch_enabled_check.isChecked():
                self.start_watching()
                
    # Rules tab methods
    def load_config(self, index):
        """Load selected configuration"""
        if index < 0:
            return
            
        config_name = self.config_combo.currentText()
        self.config_manager.load_config(config_name)
        
        # Update rules table
        self.update_rules_table()
        
    def create_new_config(self):
        """Create a new configuration"""
        name, ok = QMessageBox.getText(self, "New Configuration", "Enter configuration name:")
        if ok and name:
            self.config_manager.create_new_config(name)
            self.config_combo.addItem(name)
            self.config_combo.setCurrentText(name)
            
    def open_config(self):
        """Open a configuration file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Configuration", "", "YAML Files (*.yml *.yaml);;All Files (*.*)"
        )
        if file_path:
            self.config_manager.load_config_from_path(file_path)
            
            # Update UI
            self.config_combo.addItem(os.path.basename(file_path))
            self.config_combo.setCurrentText(os.path.basename(file_path))
            
    def save_config(self):
        """Save current configuration"""
        if not self.config_manager.current_config:
            QMessageBox.warning(self, "No Configuration", "No configuration to save.")
            return
            
        self.config_manager.save_current_config()
        
    def update_rules_table(self):
        """Update the rules table with current configuration"""
        self.rules_table.setRowCount(0)
        
        if not self.config_manager.current_config:
            return
            
        for i, rule in enumerate(self.config_manager.current_config.rules):
            self.rules_table.insertRow(i)
            
            # Enabled checkbox
            enabled_checkbox = QCheckBox()
            enabled_checkbox.setChecked(rule.enabled)
            enabled_checkbox.stateChanged.connect(lambda state, row=i: self.toggle_rule_enabled(row, state))
            self.rules_table.setCellWidget(i, 0, enabled_checkbox)
            
            # Rule name
            name_item = QTableWidgetItem(rule.name or f"Rule #{i+1}")
            self.rules_table.setItem(i, 1, name_item)
            
            # Locations
            locations = []
            for location in rule.locations:
                for path in location.path:
                    locations.append(path)
            locations_item = QTableWidgetItem(", ".join(locations) if locations else "Standalone")
            self.rules_table.setItem(i, 2, locations_item)
            
            # Actions
            actions = [action.action_config.name for action in rule.actions]
            actions_item = QTableWidgetItem(", ".join(actions))
            self.rules_table.setItem(i, 3, actions_item)
            
    def toggle_rule_enabled(self, row, state):
        """Toggle a rule's enabled state"""
        if self.config_manager.current_config:
            self.config_manager.current_config.rules[row].enabled = (state == Qt.CheckState.Checked.value)
            
    def rule_context_menu(self, position):
        """Show context menu for rules table"""
        index = self.rules_table.indexAt(position)
        if not index.isValid():
            return
            
        row = index.row()
        
        menu = QMenu()
        
        edit_action = QAction("Edit Rule", self)
        edit_action.triggered.connect(lambda: self.edit_rule(row))
        menu.addAction(edit_action)
        
        delete_action = QAction("Delete Rule", self)
        delete_action.triggered.connect(lambda: self.delete_rule(row))
        menu.addAction(delete_action)
        
        menu.addSeparator()
        
        run_action = QAction("Run This Rule", self)
        run_action.triggered.connect(lambda: self.run_rule(row))
        menu.addAction(run_action)
        
        menu.exec(self.rules_table.viewport().mapToGlobal(position))
        
    def add_rule(self):
        """Add a new rule"""
        if not self.config_manager.current_config:
            QMessageBox.warning(self, "No Configuration", "Please select a configuration first.")
            return
            
        dialog = RuleEditorDialog(self)
        if dialog.exec():
            rule = dialog.get_rule()
            self.config_manager.add_rule(rule)
            self.update_rules_table()
            
    def edit_selected_rule(self):
        """Edit selected rule"""
        rows = self.rules_table.selectionModel().selectedRows()
        if not rows:
            return
            
        self.edit_rule(rows[0].row())
        
    def edit_rule(self, row):
        """Edit rule at specific row"""
        if not self.config_manager.current_config:
            return
            
        rule = self.config_manager.current_config.rules[row]
        dialog = RuleEditorDialog(self, rule)
        if dialog.exec():
            updated_rule = dialog.get_rule()
            self.config_manager.update_rule(row, updated_rule)
            self.update_rules_table()
            
    def delete_selected_rule(self):
        """Delete selected rule"""
        rows = self.rules_table.selectionModel().selectedRows()
        if not rows:
            return
            
        self.delete_rule(rows[0].row())
        
    def delete_rule(self, row):
        """Delete rule at specific row"""
        if not self.config_manager.current_config:
            return
            
        confirm = QMessageBox.question(
            self, "Confirm Delete", 
            "Are you sure you want to delete this rule?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            self.config_manager.delete_rule(row)
            self.update_rules_table()
            
    def run_selected_rules(self):
        """Run selected rules"""
        rows = self.rules_table.selectionModel().selectedRows()
        if not rows:
            return
            
        rule_indexes = [row.row() for row in rows]
        self.run_rules(rule_indexes)
        
    def run_rule(self, row):
        """Run a specific rule"""
        self.run_rules([row])
        
    def run_rules(self, rule_indexes):
        """Run specific rules"""
        if not self.config_manager.current_config:
            return
            
        # Create list of rules to run
        rules = [self.config_manager.current_config.rules[i] for i in rule_indexes]
        
        # Use worker to run rules
        worker = OrganizeWorker(
            config=self.config_manager.current_config,
            simulate=False,
            rules=rules
        )
        worker.finished.connect(self.handle_organize_finished)
        worker.start()
        
        self.statusBar().showMessage("Running rules...")
        
    # Watch tab methods
    def toggle_watch(self):
        """Toggle file watching"""
        if self.watch_enabled_check.isChecked():
            self.start_watching()
            self.watch_btn.setText("Stop Watching")
            self.watch_action.setText("Stop Watching")
        else:
            self.stop_watching()
            self.watch_btn.setText("Start Watching")
            self.watch_action.setText("Start Watching")
            
    def start_watching(self):
        """Start watching directories"""
        # Get directories to watch
        watch_dirs = self.settings.get("watch_directories", [])
        if not watch_dirs:
            QMessageBox.warning(self, "No Watch Directories", "Please add directories to watch.")
            self.watch_enabled_check.setChecked(False)
            return
            
        # Get tags
        tags = self.tags_edit.text().strip().split(",") if self.tags_edit.text().strip() else []
        skip_tags = self.skip_tags_edit.text().strip().split(",") if self.skip_tags_edit.text().strip() else []
        
        # Start worker
        self.watch_worker = WatchWorker(
            config=self.config_manager.current_config,
            directories=watch_dirs,
            interval=self.interval_spin.value(),
            tags=tags,
            skip_tags=skip_tags
        )
        self.watch_worker.event_detected.connect(self.handle_watch_event)
        self.watch_worker.start()
        
        # Update UI
        self.statusBar().showMessage("Watching directories...")
        
    def stop_watching(self):
        """Stop watching directories"""
        if hasattr(self, "watch_worker") and self.watch_worker.isRunning():
            self.watch_worker.stop()
            self.watch_worker.wait()
            
        self.statusBar().showMessage("Watch stopped")
        
    def handle_watch_event(self, time_str, event_type, path):
        """Handle file system watch event"""
        # Add to watch log
        row = self.watch_log_table.rowCount()
        self.watch_log_table.insertRow(row)
        
        self.watch_log_table.setItem(row, 0, QTableWidgetItem(time_str))
        self.watch_log_table.setItem(row, 1, QTableWidgetItem(event_type))
        self.watch_log_table.setItem(row, 2, QTableWidgetItem(path))
        
        # Scroll to bottom
        self.watch_log_table.scrollToBottom()
        
        # Add to activity log
        self.add_activity(time_str, f"Watch: {event_type}", path)
        
        # Show notification
        if self.settings.get("show_notifications", True):
            self.tray_icon.showMessage(
                "File Change Detected",
                f"{event_type}: {path}",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            
    def browse_watch_directory(self):
        """Browse for a directory to watch"""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory to Watch")
        if directory:
            self.add_watch_edit.setText(directory)
            
    def add_watch_directory(self):
        """Add a directory to the watch list"""
        path = self.add_watch_edit.text().strip()
        if not path or not os.path.isdir(path):
            QMessageBox.warning(self, "Invalid Directory", "Please enter a valid directory path.")
            return
            
        # Add to settings
        watch_dirs = self.settings.get("watch_directories", [])
        if path not in watch_dirs:
            watch_dirs.append(path)
            self.settings.set("watch_directories", watch_dirs)
            self.update_watch_dirs_table()
            
            # Update watcher if running
            if self.watch_enabled_check.isChecked():
                self.stop_watching()
                self.start_watching()
                
        # Clear input
        self.add_watch_edit.clear()
        
    def update_watch_dirs_table(self):
        """Update the watch directories table"""
        self.watched_dirs_table.setRowCount(0)
        
        watch_dirs = self.settings.get("watch_directories", [])
        for i, directory in enumerate(watch_dirs):
            self.watched_dirs_table.insertRow(i)
            self.watched_dirs_table.setItem(i, 0, QTableWidgetItem(directory))
            
            # Create remove button
            remove_btn = QPushButton("Remove")
            remove_btn.clicked.connect(lambda _, dir=directory: self.remove_watch_dir(dir))
            self.watched_dirs_table.setCellWidget(i, 1, remove_btn)
            
    def remove_watch_dir(self, directory):
        """Remove a directory from the watch list"""
        watch_dirs = self.settings.get("watch_directories", [])
        if directory in watch_dirs:
            watch_dirs.remove(directory)
            self.settings.set("watch_directories", watch_dirs)
            self.update_watch_dirs_table()
            
            # Update watcher if running
            if self.watch_enabled_check.isChecked():
                self.stop_watching()
                if watch_dirs:  # Only restart if there are still directories to watch
                    self.start_watching()
        
    # Settings tab methods
    def browse_default_config(self):
        """Browse for default configuration file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Default Configuration", "", "YAML Files (*.yml *.yaml);;All Files (*.*)"
        )
        if file_path:
            self.default_config_edit.setText(file_path)
            
    def browse_index_directory(self):
        """Browse for a directory to index"""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory to Index")
        if directory:
            self.add_index_edit.setText(directory)
            
    def add_index_directory(self):
        """Add a directory to the index list"""
        path = self.add_index_edit.text().strip()
        if not path or not os.path.isdir(path):
            QMessageBox.warning(self, "Invalid Directory", "Please enter a valid directory path.")
            return
            
        # Add to settings
        index_dirs = self.settings.get("index_directories", [])
        if path not in index_dirs:
            index_dirs.append(path)
            self.settings.set("index_directories", index_dirs)
            self.update_index_dirs_table()
                
        # Clear input
        self.add_index_edit.clear()
        
    def update_index_dirs_table(self):
        """Update the index directories table"""
        self.index_dirs_table.setRowCount(0)
        
        index_dirs = self.settings.get("index_directories", [])
        for i, directory in enumerate(index_dirs):
            self.index_dirs_table.insertRow(i)
            self.index_dirs_table.setItem(i, 0, QTableWidgetItem(directory))
            
            # Create remove button
            remove_btn = QPushButton("Remove")
            remove_btn.clicked.connect(lambda _, dir=directory: self.remove_index_dir(dir))
            self.index_dirs_table.setCellWidget(i, 1, remove_btn)
            
    def remove_index_dir(self, directory):
        """Remove a directory from the index list"""
        index_dirs = self.settings.get("index_directories", [])
        if directory in index_dirs:
            index_dirs.remove(directory)
            self.settings.set("index_directories", index_dirs)
            self.update_index_dirs_table()
        
    def save_settings(self):
        """Save all settings"""
        self.settings.set("start_minimized", self.start_minimized_check.isChecked())
        self.settings.set("minimize_to_tray", self.minimize_to_tray_check.isChecked())
        self.settings.set("show_notifications", self.show_notifications_check.isChecked())
        self.settings.set("parallel_processing", self.parallel_check.isChecked())
        self.settings.set("max_workers", self.workers_spin.value())
        self.settings.set("default_config", self.default_config_edit.text())
        self.settings.set("indexing_enabled", self.indexing_enabled_check.isChecked())
        self.settings.set("index_on_startup", self.index_on_startup_check.isChecked())
        
        self.settings.save()
        self.statusBar().showMessage("Settings saved")
        
    def reset_settings(self):
        """Reset settings to defaults"""
        confirm = QMessageBox.question(
            self, "Confirm Reset", 
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            self.settings.reset()
            
            # Reload UI
            self.start_minimized_check.setChecked(self.settings.get("start_minimized", False))
            self.minimize_to_tray_check.setChecked(self.settings.get("minimize_to_tray", True))
            self.show_notifications_check.setChecked(self.settings.get("show_notifications", True))
            self.parallel_check.setChecked(self.settings.get("parallel_processing", True))
            self.workers_spin.setValue(self.settings.get("max_workers", 4))
            self.default_config_edit.setText(self.settings.get("default_config", ""))
            self.indexing_enabled_check.setChecked(self.settings.get("indexing_enabled", True))
            self.index_on_startup_check.setChecked(self.settings.get("index_on_startup", False))
            
            self.update_index_dirs_table()
            self.update_watch_dirs_table()
            
            self.statusBar().showMessage("Settings reset to defaults")
        
    # Common methods
    def run_organize(self, paths=None):
        """Run organize with current configuration"""
        if not self.config_manager.current_config:
            QMessageBox.warning(self, "No Configuration", "Please select a configuration first.")
            return
            
        # Create worker
        worker = OrganizeWorker(
            config=self.config_manager.current_config,
            simulate=False,
            parallel=self.settings.get("parallel_processing", True),
            max_workers=self.settings.get("max_workers", 4),
            paths=paths
        )
        worker.finished.connect(self.handle_organize_finished)
        worker.start()
        
        self.statusBar().showMessage("Running organize...")
        
    def simulate_organize(self, paths=None):
        """Simulate organize with current configuration"""
        if not self.config_manager.current_config:
            QMessageBox.warning(self, "No Configuration", "Please select a configuration first.")
            return
            
        # Create worker
        worker = OrganizeWorker(
            config=self.config_manager.current_config,
            simulate=True,
            parallel=self.settings.get("parallel_processing", True),
            max_workers=self.settings.get("max_workers", 4),
            paths=paths
        )
        worker.finished.connect(self.handle_organize_finished)
        worker.start()
        
        self.statusBar().showMessage("Simulating organize...")
        
    def handle_organize_finished(self, success, error):
        """Handle organize worker finished"""
        self.statusBar().showMessage(f"Done. Success: {success}, Errors: {error}")
        
        # Show notification
        if self.settings.get("show_notifications", True):
            self.tray_icon.showMessage(
                "Organize Complete",
                f"Successfully processed {success} files with {error} errors.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            
        # Refresh stats
        self.refresh_stats()
        
    def start_indexing(self):
        """Start indexing files"""
        if not self.settings.get("indexing_enabled", True):
            QMessageBox.warning(self, "Indexing Disabled", "File indexing is disabled in settings.")
            return
            
        directories = self.settings.get("index_directories", [])
        if not directories:
            # Ask user to select directories
            directory = QFileDialog.getExistingDirectory(self, "Select Directory to Index")
            if directory:
                directories = [directory]
            else:
                return
                
        self.index_paths(directories)
        
    def index_paths(self, paths):
        """Index specified paths"""
        if not paths:
            return
            
        # Create worker
        worker = IndexWorker(paths=paths)
        worker.progress_update.connect(self.handle_index_progress)
        worker.finished.connect(self.handle_index_finished)
        worker.start()
        
        self.statusBar().showMessage("Indexing files...")
        
    def handle_index_progress(self, path, count):
        """Handle indexing progress update"""
        self.statusBar().showMessage(f"Indexing {path}: {count} files/folders...")
        
    def handle_index_finished(self, total_count):
        """Handle indexing finished"""
        self.statusBar().showMessage(f"Indexing complete. {total_count} files/folders indexed.")
        
        # Show notification
        if self.settings.get("show_notifications", True):
            self.tray_icon.showMessage(
                "Indexing Complete",
                f"{total_count} files/folders indexed.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            
        # Refresh stats
        self.refresh_stats()
        
    def refresh_stats(self):
        """Refresh statistics table"""
        self.stats_table.setRowCount(0)
        
        try:
            # Get index stats
            if self.settings.get("indexing_enabled", True):
                index_stats = file_index.get_statistics()
                
                # Add to table
                self.add_stat("Files Indexed", f"{index_stats['file_count']:,}")
                self.add_stat("Directories Indexed", f"{index_stats['directory_count']:,}")
                self.add_stat("Total Size", format_size(index_stats['total_size']))
                self.add_stat("Index Last Updated", index_stats['last_update'])
                self.add_stat("Index Database Size", format_size(index_stats['database_size']))
            
            # Get rule stats
            if self.config_manager.current_config:
                self.add_stat("Current Config", self.config_combo.currentText())
                self.add_stat("Rules", str(len(self.config_manager.current_config.rules)))
                
                # Count enabled rules
                enabled_rules = sum(1 for rule in self.config_manager.current_config.rules if rule.enabled)
                self.add_stat("Enabled Rules", str(enabled_rules))
                
            # Get watch stats
            watch_dirs = self.settings.get("watch_directories", [])
            self.add_stat("Watched Directories", str(len(watch_dirs)))
            self.add_stat("Watching", "Yes" if self.watch_enabled_check.isChecked() else "No")
            
        except Exception as e:
            self.statusBar().showMessage(f"Error refreshing stats: {str(e)}")
            
    def add_stat(self, name, value):
        """Add a statistic to the stats table"""
        row = self.stats_table.rowCount()
        self.stats_table.insertRow(row)
        
        self.stats_table.setItem(row, 0, QTableWidgetItem(name))
        self.stats_table.setItem(row, 1, QTableWidgetItem(value))
        
    def add_activity(self, time_str, action, path):
        """Add an activity to the activity log"""
        row = self.activity_table.rowCount()
        self.activity_table.insertRow(row)
        
        self.activity_table.setItem(row, 0, QTableWidgetItem(time_str))
        self.activity_table.setItem(row, 1, QTableWidgetItem(action))
        self.activity_table.setItem(row, 2, QTableWidgetItem(path))
        
        # Limit rows
        if self.activity_table.rowCount() > 100:
            self.activity_table.removeRow(0)
            
        # Scroll to bottom
        self.activity_table.scrollToBottom()
        
    # Window/tray methods
    def toggle_window(self):
        """Toggle window visibility"""
        if self.isVisible():
            self.hide()
            self.show_hide_action.setText("Show Window")
        else:
            self.show()
            self.show_hide_action.setText("Hide Window")
            
    def tray_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_window()
            
    def closeEvent(self, event):
        """Handle window close event"""
        if self.settings.get("minimize_to_tray", True) and not self.exiting:
            event.ignore()
            self.hide()
            self.show_hide_action.setText("Show Window")
            
            if self.settings.get("show_notifications", True):
                self.tray_icon.showMessage(
                    "Organize Tool",
                    "Application minimized to tray. Click the tray icon to restore.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000
                )
        else:
            # Save settings
            self.settings.save()
            
            # Stop watchers
            self.stop_watching()
            
            event.accept()
            
    def exit_app(self):
        """Exit the application"""
        self.exiting = True
        self.close()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Organize Tool")
    app.setApplicationVersion("3.5.0")
    
    # Set style
    app.setStyle("Fusion")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()