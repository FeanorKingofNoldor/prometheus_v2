extends Node
## Workspace and layout manager for Prometheus C2.
##
## Manages workspaces (collections of panels), saved layouts, and panel visibility.
## Persists workspace configurations to disk for session restore.

## Default workspaces configuration
const DEFAULT_WORKSPACES := {
	"overview": {
		"display_name": "Overview",
		"panels": ["overview", "regime_stab", "live_system"]
	},
	"trading": {
		"display_name": "Trading",
		"panels": ["portfolio_risk", "execution", "fragility", "terminal"]
	},
	"research": {
		"display_name": "Research",
		"panels": ["assessment_universe", "meta_experiments", "ant_hill"]
	},
	"monitoring": {
		"display_name": "Monitoring",
		"panels": ["live_system", "regime_stab", "portfolio_risk", "execution", "geo"]
	},
	"global": {
		"display_name": "Global View",
		"panels": ["geo", "regime_stab", "fragility"]
	}
}

## Current workspace configurations
var workspaces: Dictionary = DEFAULT_WORKSPACES.duplicate(true)

## Currently open panels (detached windows)
var detached_panels: Array = []

## Signal emitted when workspace layout changes
signal layout_changed(workspace_name: String, panels: Array)

## Signal emitted when a panel is detached
signal panel_detached(panel_id: String)

## Signal emitted when a panel is reattached
signal panel_reattached(panel_id: String)


func _ready() -> void:
	print("WorkspaceManager initialized")
	# Load saved workspaces if available, but always validate and fall back to
	# DEFAULT_WORKSPACES if something looks wrong. This prevents a corrupt
	# workspaces.json from breaking the UI navigation.
	_load_workspaces()
	if typeof(workspaces) != TYPE_DICTIONARY or workspaces.is_empty():
		print("Invalid or empty workspaces; resetting to defaults")
		workspaces = DEFAULT_WORKSPACES.duplicate(true)


## Get panels for a workspace
func get_workspace_panels(workspace_name: String) -> Array:
	if typeof(workspaces) != TYPE_DICTIONARY:
		workspaces = DEFAULT_WORKSPACES.duplicate(true)
	if workspaces.has(workspace_name):
		var ws: Variant = workspaces[workspace_name]
		if ws is Dictionary and ws.has("panels") and ws["panels"] is Array:
			return ws["panels"]
	return []


## Get all workspace names
func get_workspace_names() -> Array:
	if typeof(workspaces) != TYPE_DICTIONARY or workspaces.is_empty():
		workspaces = DEFAULT_WORKSPACES.duplicate(true)
	return workspaces.keys()


## Add a panel to a workspace
func add_panel_to_workspace(workspace_name: String, panel_id: String) -> void:
	if not workspaces.has(workspace_name):
		push_error("Workspace not found: " + workspace_name)
		return
	
	var panels: Array = workspaces[workspace_name]["panels"]
	if not panels.has(panel_id):
		panels.append(panel_id)
		layout_changed.emit(workspace_name, panels)
		_save_workspaces()
		print("Added panel %s to workspace %s" % [panel_id, workspace_name])


## Remove a panel from a workspace
func remove_panel_from_workspace(workspace_name: String, panel_id: String) -> void:
	if not workspaces.has(workspace_name):
		push_error("Workspace not found: " + workspace_name)
		return
	
	var panels: Array = workspaces[workspace_name]["panels"]
	var idx := panels.find(panel_id)
	if idx != -1:
		panels.remove_at(idx)
		layout_changed.emit(workspace_name, panels)
		_save_workspaces()
		print("Removed panel %s from workspace %s" % [panel_id, workspace_name])


## Create a new workspace
func create_workspace(workspace_name: String, display_name: String, panels: Array = []) -> void:
	if workspaces.has(workspace_name):
		push_warning("Workspace already exists: " + workspace_name)
		return
	
	workspaces[workspace_name] = {
		"display_name": display_name,
		"panels": panels
	}
	_save_workspaces()
	print("Created workspace: ", workspace_name)


## Delete a workspace
func delete_workspace(workspace_name: String) -> void:
	if not workspaces.has(workspace_name):
		push_error("Workspace not found: " + workspace_name)
		return
	
	workspaces.erase(workspace_name)
	_save_workspaces()
	print("Deleted workspace: ", workspace_name)


## Detach a panel into its own window
func detach_panel(panel_id: String) -> void:
	if not detached_panels.has(panel_id):
		detached_panels.append(panel_id)
		panel_detached.emit(panel_id)
		print("Panel detached: ", panel_id)


## Reattach a panel back to main window
func reattach_panel(panel_id: String) -> void:
	var idx := detached_panels.find(panel_id)
	if idx != -1:
		detached_panels.remove_at(idx)
		panel_reattached.emit(panel_id)
		print("Panel reattached: ", panel_id)


## Check if a panel is detached
func is_panel_detached(panel_id: String) -> bool:
	return detached_panels.has(panel_id)


## Reset to default workspaces
func reset_to_defaults() -> void:
	workspaces = DEFAULT_WORKSPACES.duplicate(true)
	detached_panels.clear()
	_save_workspaces()
	print("Workspaces reset to defaults")


## Load workspaces from disk
func _load_workspaces() -> void:
	var save_path := "user://workspaces.json"
	if not FileAccess.file_exists(save_path):
		print("No saved workspaces found, using defaults")
		return
	
	var file := FileAccess.open(save_path, FileAccess.READ)
	if file == null:
		push_error("Failed to open workspaces file")
		return
	
	var json_text := file.get_as_text()
	file.close()
	
	var json := JSON.new()
	var parse_result := json.parse(json_text)
	
	if parse_result != OK:
		push_error("Failed to parse workspaces JSON: " + json.get_error_message())
		return
	
	var data: Variant = json.data
	if typeof(data) != TYPE_DICTIONARY:
		push_error("Workspaces JSON root is not a dictionary; using defaults")
		return
	if data.has("workspaces") and data["workspaces"] is Dictionary:
		workspaces = data["workspaces"]
	if data.has("detached_panels") and data["detached_panels"] is Array:
		detached_panels = data["detached_panels"]
	
	print("Loaded %d workspaces from disk" % workspaces.size())


## Save workspaces to disk
func _save_workspaces() -> void:
	var save_path := "user://workspaces.json"
	var data := {
		"workspaces": workspaces,
		"detached_panels": detached_panels
	}
	
	var file := FileAccess.open(save_path, FileAccess.WRITE)
	if file == null:
		push_error("Failed to save workspaces")
		return
	
	file.store_string(JSON.stringify(data, "\t"))
	file.close()
	print("Saved workspaces to disk")
