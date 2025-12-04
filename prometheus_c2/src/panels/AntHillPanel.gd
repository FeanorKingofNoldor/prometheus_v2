extends "res://src/panels/BasePanel.gd"

@onready var _body_label: Label = get_node("Background/VBox/Body")


func _ready() -> void:
	panel_id = "ant_hill"
	display_name = "ANT_HILL"


func on_activated() -> void:
	refresh_data()


func refresh_data() -> void:
	if not is_inside_tree():
		return
	if _body_label == null:
		return
	
	_body_label.text = "Loading ANT_HILL scenes..."
	C2Logger.info("AntHillPanel", "Refreshing ANT_HILL text summary and traces")
	
	var scenes: Array = await ApiClient.get_scenes()
	if scenes.is_empty():
		C2Logger.warn("AntHillPanel", "No scenes returned from /api/scenes")
		_body_label.text = "No scenes available from backend."
		return
	
	var text := "Available scenes:\n"
	for s in scenes:
		var scene_info: Dictionary = s
		var view_id: String = String(scene_info.get("view_id", "?"))
		var name: String = String(scene_info.get("display_name", view_id))
		var layout: String = String(scene_info.get("layout_type", "standard"))
		text += " - %s (%s) layout=%s\n" % [view_id, name, layout]
	
	# Try to load the root/system view for a quick summary.
	var root_scene: Dictionary = await ApiClient.get_scene("root")
	if not root_scene.has("error"):
		var nodes: Dictionary = root_scene.get("nodes", {})
		var conns: Array = root_scene.get("connections", [])
		C2Logger.info("AntHillPanel", "Root scene: %d nodes, %d connections" % [nodes.size(), conns.size()])
		text += "\nRoot scene summary:\n"
		text += " Nodes: %d\n" % nodes.size()
		text += " Connections: %d\n" % conns.size()
		# List a few key nodes
		var listed: int = 0
		for key in nodes.keys():
			var node: Dictionary = nodes[key]
			var label: String = String(node.get("label", key))
			var ntype: String = String(node.get("type", "?"))
			text += "  - %s (%s)\n" % [label, ntype]
			listed += 1
			if listed >= 8:
				break
	else:
		C2Logger.warn("AntHillPanel", "Backend error for root scene: %s" % root_scene.get("error"))
	
	# Show a preview of available traces.
	var traces: Array = await ApiClient.get_traces()
	if not traces.is_empty():
		C2Logger.info("AntHillPanel", "Received %d traces" % traces.size())
		text += "\nTraces:\n"
		for t in traces:
			var trace: Dictionary = t
			text += " - %s [%s, %s] %s → %s\n" % [
				trace.get("trace_id", "?"),
				trace.get("market_id", "?"),
				trace.get("mode", "?"),
				trace.get("start_time", "?"),
				trace.get("end_time", "?"),
			]
	else:
		text += "\nTraces: none\n"
	
	_body_label.text = text
