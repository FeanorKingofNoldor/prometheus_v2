extends "res://src/panels/BasePanel.gd"

@onready var _body_label: Label = get_node("Background/VBox/Body")


func _ready() -> void:
	panel_id = "geo"
	display_name = "World Map / Globe"


func on_activated() -> void:
	refresh_data()


func refresh_data() -> void:
	if not is_inside_tree():
		return
	if _body_label == null:
		return
	
	_body_label.text = "Loading geo overview..."
	
	var countries: Array = await ApiClient.get_countries()
	if countries.is_empty():
		_body_label.text = "No geo data available."
		return
	
	# Sort by absolute exposure descending.
	countries.sort_custom(func(a, b):
		return abs(b.get("exposure", 0.0)) < abs(a.get("exposure", 0.0))
	)
	
	var text := "Countries by exposure (top 10):\n"
	var top_n := min(countries.size(), 10)
	for i in range(top_n):
		var c := countries[i]
		var code := c.get("country_code", "??")
		var name := c.get("country_name", code)
		var stab := c.get("stability_index", 0.0)
		var risk := c.get("fragility_risk", "?")
		var exp := c.get("exposure", 0.0) * 100.0
		text += " - %s (%s): STAB=%.3f, risk=%s, exposure=%.1f%%, positions=%d\n" % [
			name,
			code,
			stab,
			risk,
			exp,
			c.get("num_positions", 0),
		]
	
	# Pick the top-exposure country and load details.
	var top_country := countries[0]
	var top_code := top_country.get("country_code", "US")
	var detail := await ApiClient.get_country_detail(top_code)
	if not detail.has("error"):
		text += "\nFocus country: %s (%s)\n" % [
			detail.get("country_name", top_code),
			top_code,
		]
		text += " STAB=%.3f, risk=%s, regime=%s\n" % [
			detail.get("stability_index", 0.0),
			detail.get("fragility_risk", "?"),
			detail.get("regime", "?"),
		]
		var exposures: Dictionary = detail.get("exposures", {})
		if exposures:
			text += " Exposures by asset class:\n"
			for k in exposures.keys():
				text += "  - %s: %.1f%%\n" % [k, exposures[k] * 100.0]
	
	_body_label.text = text
