extends "res://src/panels/BasePanel.gd"

@onready var _body_label: Label = get_node("Background/VBox/Body")


func _ready() -> void:
	panel_id = "assessment_universe"
	display_name = "Assessment & Universe"


func on_activated() -> void:
	refresh_data()


func refresh_data() -> void:
	if not is_inside_tree():
		return
	if _body_label == null:
		return
	
	var strategy_id := AppState.strategy_id
	_body_label.text = "Loading assessment & universe for %s..." % strategy_id
	
	var assess := await ApiClient.get_status_assessment(strategy_id)
	var uni := await ApiClient.get_status_universe(strategy_id)
	
	if assess.has("error") and uni.has("error"):
		_body_label.text = "Error loading assessment/universe: %s" % assess.get("error")
		return
	
	var text := "Strategy: %s\n" % strategy_id
	
	if not assess.has("error"):
		var insts: Array = assess.get("instruments", [])
		text += "\nTop assessed instruments (by abs expected return):\n"
		# Sort by |expected_return| desc if possible
		insts.sort_custom(func(a, b):
			return abs(b.get("expected_return", 0.0)) < abs(a.get("expected_return", 0.0))
		)
		var max_rows := min(insts.size(), 10)
		for i in range(max_rows):
			var ins := insts[i]
			var iid := ins.get("instrument_id", "?")
			var er := ins.get("expected_return", 0.0)
			var conf := float(ins.get("confidence", 0.0)) * 100.0
			text += " - %s: ER=%.3f (%.0f%%)\n" % [iid, er, conf]
	
	if not uni.has("error"):
		var cands: Array = uni.get("candidates", [])
		var included := 0
		for c in cands:
			if c.get("in_universe", false):
				included += 1
		text += "\nUniverse size: %d / %d instruments in universe\n" % [
			included,
			cands.size(),
		]
	
	_body_label.text = text
