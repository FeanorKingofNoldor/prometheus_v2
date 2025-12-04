extends "res://src/panels/BasePanel.gd"

@onready var _body_label: Label = get_node("Background/VBox/Body")


func _ready() -> void:
	panel_id = "regime_stab"
	display_name = "Regime & STAB"


func on_activated() -> void:
	refresh_data()


func refresh_data() -> void:
	if not is_inside_tree():
		return
	if _body_label == null:
		return
	
	var region := "US"  # Default region for now; later bind to AppState.
	_body_label.text = "Loading regime & stability for %s..." % region
	
	var regime := await ApiClient.get_status_regime(region)
	var stab := await ApiClient.get_status_stability(region)
	
	if regime.has("error") and stab.has("error"):
		_body_label.text = "Error loading regime/stability: %s" % regime.get("error")
		return
	
	var text := "Region: %s\n" % region
	if not regime.has("error"):
		text += "Current regime: %s (%.0f%%)\n" % [
			regime.get("current_regime", "?"),
			float(regime.get("confidence", 0.0)) * 100.0,
		]
		text += "\nRegime history (last few points):\n"
		for point in regime.get("history", [])[-5:]:
			var d := point.get("date", "?")
			var label := point.get("regime", "?")
			var conf := float(point.get("confidence", 0.0)) * 100.0
			text += " - %s: %s (%.0f%%)\n" % [d, label, conf]
	
	if not stab.has("error"):
		text += "\nStability index: %.3f\n" % stab.get("current_index", 0.0)
		text += "Components: liq=%.3f, vol=%.3f, contagion=%.3f\n" % [
			stab.get("liquidity_component", 0.0),
			stab.get("volatility_component", 0.0),
			stab.get("contagion_component", 0.0),
		]
		text += "\nStability history (last few points):\n"
		for point in stab.get("history", [])[-5:]:
			var d2 := point.get("date", "?")
			var idx := point.get("index", 0.0)
			text += " - %s: %.3f\n" % [d2, idx]
	
	_body_label.text = text
