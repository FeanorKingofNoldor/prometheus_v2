extends "res://src/panels/BasePanel.gd"

@onready var _body_label: Label = get_node("Background/VBox/Body")


func _ready() -> void:
	panel_id = "fragility"
	display_name = "Soft Targets & Fragility"


func on_activated() -> void:
	refresh_data()


func refresh_data() -> void:
	if not is_inside_tree():
		return
	if _body_label == null:
		return
	
	var region := "GLOBAL"
	var entity_type := "ANY"
	_body_label.text = "Loading fragility table for %s/%s..." % [region, entity_type]
	
	var frag := await ApiClient.get_status_fragility(region, entity_type)
	if frag.has("error"):
		_body_label.text = "Error loading fragility: %s" % frag.get("error")
		return
	
	var text := "Soft targets / fragility (%s, %s)\n" % [region, entity_type]
	text += "\nTop entities:\n"
	var entities: Array = frag.get("entities", [])
	var count := min(entities.size(), 15)
	for i in range(count):
		var e := entities[i]
		var eid := e.get("entity_id", "?")
		var etype := e.get("entity_type", "?")
		var score := e.get("soft_target_score", 0.0)
		var alpha := e.get("fragility_alpha", 0.0)
		var cls := e.get("fragility_class", "?")
		text += " - %s (%s): score=%.3f alpha=%.3f class=%s\n" % [
			eid,
			etype,
			score,
			alpha,
			cls,
		]
	
	if entities.size() == 0:
		text += "(no entities)\n"
	elif entities.size() > count:
		text += "... (%d more)\n" % (entities.size() - count)
	
	_body_label.text = text
