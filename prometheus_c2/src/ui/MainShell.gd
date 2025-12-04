extends Control
## Main shell for Prometheus C2 UI.
##
## Implements the Bloomberg-style layout:
## - Top bar with logo, mode, KPIs, clock.
## - Left navigation (workspaces + panels).
## - Center area (tab bar + active panel).
## - Right strip (alerts + console).

const PANEL_CONFIG := {
	"overview": {
		"title": "Overview",
		"scene": "res://src/panels/OverviewPanel.tscn",
	},
	"regime_stab": {
		"title": "Regime & STAB",
		"scene": "res://src/panels/RegimeStabPanel.tscn",
	},
	"fragility": {
		"title": "Soft Targets & Fragility",
		"scene": "res://src/panels/FragilityPanel.tscn",
	},
	"assessment_universe": {
		"title": "Assessment & Universe",
		"scene": "res://src/panels/AssessmentUniversePanel.tscn",
	},
	"portfolio_risk": {
		"title": "Portfolio & Risk",
		"scene": "res://src/panels/PortfolioRiskPanel.tscn",
	},
	"execution": {
		"title": "Execution",
		"scene": "res://src/panels/ExecutionPanel.tscn",
	},
	"meta_experiments": {
		"title": "Meta & Experiments",
		"scene": "res://src/panels/MetaExperimentsPanel.tscn",
	},
	"live_system": {
		"title": "Live System",
		"scene": "res://src/panels/LiveSystemPanel.tscn",
	},
	"ant_hill": {
		"title": "ANT_HILL",
		"scene": "res://src/panels/AntHillPanel.tscn",
	},
	"geo": {
		"title": "World Map / Globe",
		"scene": "res://src/panels/GeoPanel.tscn",
	},
	"terminal": {
		"title": "Terminal",
		"scene": "res://src/panels/TerminalPanel.tscn",
	},
	"kronos_chat": {
		"title": "Kronos Chat",
		"scene": "res://src/panels/KronosChatPanel.tscn",
	},
}

@onready var workspaces_list: VBoxContainer = %WorkspacesList
@onready var panels_list: VBoxContainer = %PanelsList
@onready var panel_host: PanelContainer = %PanelHost
@onready var tab_label: Label = %TabLabel
@onready var mode_label: Label = %ModeLabel
@onready var kpi_label: Label = %KpiLabel
@onready var clock_label: Label = %ClockLabel
@onready var alerts_container: VBoxContainer = %AlertsContainer
@onready var console_text: TextEdit = %ConsoleText

var current_panel: Control = null

var _kpi_next_refresh_time: float = 0.0
const KPI_REFRESH_INTERVAL := 10.0
var _kpi_refresh_in_progress: bool = false


func _ready() -> void:
	_apply_theme()
	# Subscribe to central logger so all logs surface in the console panel.
	C2Logger.log_message.connect(_on_log_message)
	_build_workspace_nav()
	_build_panel_nav()
	_update_header()
	_open_panel("overview")
	_refresh_overview_kpis()


func _process(_delta: float) -> void:
	# Lightweight clock update; can be refined later.
	if clock_label:
		clock_label.text = Time.get_datetime_string_from_system()
	_maybe_refresh_overview_kpis()


func _apply_theme() -> void:
	var theme_res: Theme = load("res://src/themes/TerminalTheme.tres")
	if theme_res:
		# Apply the project-wide terminal theme. Per-control overrides should be
		# done in the scene editor using this theme's color tokens.
		get_tree().root.theme = theme_res


func _build_workspace_nav() -> void:
	if not workspaces_list:
		return
	
	for child in workspaces_list.get_children():
		child.queue_free()
	
	for workspace_name in WorkspaceManager.get_workspace_names():
		var ws_dict: Dictionary = WorkspaceManager.workspaces.get(workspace_name, {})
		var display_name: String = ws_dict.get("display_name", workspace_name)
		var button := Button.new()
		button.text = display_name
		button.toggle_mode = true
		button.pressed.connect(_on_workspace_button_pressed.bind(workspace_name, button))
		workspaces_list.add_child(button)
		# Mark the default workspace as active.
		if workspace_name == AppState.active_workspace:
			button.button_pressed = true


func _build_panel_nav() -> void:
	if not panels_list:
		return
	
	for child in panels_list.get_children():
		child.queue_free()
	
	for panel_id in PANEL_CONFIG.keys():
		var cfg: Dictionary = PANEL_CONFIG[panel_id]
		
		# Create container for button + detach button
		var hbox := HBoxContainer.new()
		
		var button := Button.new()
		button.text = cfg.get("title", panel_id)
		button.toggle_mode = true
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.pressed.connect(_on_panel_button_pressed.bind(panel_id, button))
		hbox.add_child(button)
		if panel_id == AppState.active_panel:
			button.button_pressed = true
		
		# Add detach button
		var detach_btn := Button.new()
		detach_btn.text = "↗"
		detach_btn.tooltip_text = "Open in new window"
		detach_btn.custom_minimum_size = Vector2(30, 0)
		detach_btn.pressed.connect(_on_detach_panel.bind(panel_id))
		hbox.add_child(detach_btn)
		
		panels_list.add_child(hbox)


func _on_workspace_button_pressed(workspace_name: String, button: Button) -> void:
	# Untoggle other workspace buttons
	for child in workspaces_list.get_children():
		if child is Button and child != button:
			child.button_pressed = false
	
	AppState.set_active_workspace(workspace_name)
	# Optionally open the first panel in this workspace.
	var panels: Array = WorkspaceManager.get_workspace_panels(workspace_name)
	if panels.size() > 0:
		var first_panel_id: String = panels[0]
		if PANEL_CONFIG.has(first_panel_id):
			_open_panel(first_panel_id)


func _on_panel_button_pressed(panel_id: String, button: Button) -> void:
	# Untoggle other panel buttons
	for child in panels_list.get_children():
		if child is Button and child != button:
			child.button_pressed = false
	
	_open_panel(panel_id)


func _open_panel(panel_id: String) -> void:
	if not PANEL_CONFIG.has(panel_id):
		push_warning("Unknown panel id: " + panel_id)
		return
	
	var cfg: Dictionary = PANEL_CONFIG[panel_id]
	var scene_path: String = cfg.get("scene", "")
	if scene_path == "":
		push_warning("Panel has no scene path: " + panel_id)
		return
	
	if is_instance_valid(current_panel):
		if current_panel.has_method("on_deactivated"):
			current_panel.on_deactivated()
		current_panel.queue_free()
		current_panel = null
	
	var scene: PackedScene = load(scene_path)
	if scene == null:
		push_error("Failed to load panel scene: " + scene_path)
		return
	
	var instance := scene.instantiate()
	if not (instance is Control):
		push_error("Panel scene root must be a Control: " + scene_path)
		instance.queue_free()
		return
	
	current_panel = instance
	panel_host.add_child(current_panel)
	
	if current_panel.has_method("on_activated"):
		current_panel.on_activated()
	
	AppState.set_active_panel(panel_id)
	_update_tab_label(panel_id)
	C2Logger.info("MainShell", "Switched to panel: %s" % PANEL_CONFIG[panel_id].get("title", panel_id))


func _update_tab_label(panel_id: String) -> void:
	if not tab_label:
		return
	var cfg: Dictionary = PANEL_CONFIG.get(panel_id, {})
	var title: String = cfg.get("title", panel_id)
	tab_label.text = title


func _update_header() -> void:
	if mode_label:
		var mode_name: String = String(AppState.Mode.keys()[AppState.mode])
		mode_label.text = "MODE: %s" % mode_name


func _maybe_refresh_overview_kpis() -> void:
	if _kpi_refresh_in_progress:
		return
	var now := Time.get_unix_time_from_system()
	if now < _kpi_next_refresh_time:
		return
	_kpi_next_refresh_time = now + KPI_REFRESH_INTERVAL
	_refresh_overview_kpis()


func _refresh_overview_kpis() -> void:
	if not kpi_label:
		return
	_kpi_refresh_in_progress = true
	var overview := await ApiClient.get_status_overview()
	_kpi_refresh_in_progress = false
	if overview.has("error"):
		kpi_label.text = "P&L TDAY: ERR | STAB: -- | LEV: --"
		return
	var pnl_today := float(overview.get("pnl_today", 0.0))
	var stab := float(overview.get("global_stability_index", 0.0))
	var lev := float(overview.get("leverage", 0.0))
	var sign := "+" if pnl_today >= 0.0 else "-"
	kpi_label.text = "P&L TDAY: %s%.2f | STAB: %.3f | LEV: %.2f" % [
		sign,
		abs(pnl_today),
		stab,
		lev,
	]
	# Color P&L: green for positive, red for negative.
	if pnl_today > 0.0:
		kpi_label.modulate = Color(0.22, 0.77, 0.44)
	elif pnl_today < 0.0:
		kpi_label.modulate = Color(0.93, 0.30, 0.36)
	else:
		kpi_label.modulate = Color(0.90, 0.98, 0.91)
	_update_alerts(overview.get("alerts", []))


func _update_alerts(alerts: Array) -> void:
	if not alerts_container:
		return
	for child in alerts_container.get_children():
		child.queue_free()
	if alerts.is_empty():
		var none_lbl := Label.new()
		none_lbl.text = "No active alerts"
		alerts_container.add_child(none_lbl)
		return
	var max_alerts: int = min(alerts.size(), 6)
	for i in range(max_alerts):
		var a: Dictionary = alerts[i]
		var lbl := Label.new()
		var sev := String(a.get("severity", "INFO"))
		var msg := String(a.get("message", ""))
		lbl.text = "[%s] %s" % [sev, msg]
		match sev:
			"CRITICAL", "ERROR":
				lbl.modulate = Color(0.93, 0.30, 0.36)
			"WARN", "WARNING":
				lbl.modulate = Color(0.96, 0.61, 0.16)
			_:
				lbl.modulate = Color(0.05, 0.68, 0.90)
		alerts_container.add_child(lbl)


func _log_to_console(message: String) -> void:
	if not console_text:
		return
	var timestamp := Time.get_datetime_string_from_system()
	console_text.text += "[%s] %s\n" % [timestamp, message]
	console_text.scroll_vertical = console_text.get_line_count()


func _on_log_message(level: String, source: String, message: String) -> void:
	# Bridge central logger into the on-screen console.
	_log_to_console("[%s] [%s] %s" % [level, source, message])


func _on_detach_panel(panel_id: String) -> void:
	if not PANEL_CONFIG.has(panel_id):
		C2Logger.warn("MainShell", "Cannot detach unknown panel: %s" % panel_id)
		return
	
	var cfg: Dictionary = PANEL_CONFIG[panel_id]
	var scene_path: String = cfg.get("scene", "")
	if scene_path == "":
		C2Logger.warn("MainShell", "Panel has no scene: %s" % panel_id)
		return
	
	# Load panel scene
	var scene: PackedScene = load(scene_path)
	if scene == null:
		C2Logger.error("MainShell", "Failed to load panel scene: %s" % scene_path)
		return
	
	var instance := scene.instantiate()
	if not (instance is Control):
		C2Logger.error("MainShell", "Panel root must be Control: %s" % scene_path)
		instance.queue_free()
		return
	
	# Create new window
	var window := Window.new()
	window.title = cfg.get("title", panel_id)
	window.size = Vector2i(1280, 720)
	window.initial_position = Window.WINDOW_INITIAL_POSITION_CENTER_SCREEN_WITH_MOUSE_FOCUS
	
	# Add panel to window
	window.add_child(instance)
	
	# Activate panel
	if instance.has_method("on_activated"):
		instance.on_activated()
	
	# Add window to scene tree
	get_tree().root.add_child(window)
	
	# Mark as detached in WorkspaceManager
	WorkspaceManager.detach_panel(panel_id)
	
	# Connect close signal to clean up
	window.close_requested.connect(_on_detached_window_closed.bind(panel_id, window, instance))
	
	C2Logger.info("MainShell", "Detached panel '%s' to new window" % cfg.get("title", panel_id))


func _on_detached_window_closed(panel_id: String, window: Window, panel_instance: Control) -> void:
	# Cleanup
	if panel_instance and panel_instance.has_method("on_deactivated"):
		panel_instance.on_deactivated()
	
	WorkspaceManager.reattach_panel(panel_id)
	
	if is_instance_valid(window):
		window.queue_free()
	
	C2Logger.info("MainShell", "Closed detached panel: %s" % panel_id)
