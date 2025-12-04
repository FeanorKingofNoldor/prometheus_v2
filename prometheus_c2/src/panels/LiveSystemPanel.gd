extends "res://src/panels/BasePanel.gd"

@onready var _body_label: Label = get_node("Background/VBox/Body")


func _ready() -> void:
	panel_id = "live_system"
	display_name = "Live System"


func on_activated() -> void:
	refresh_data()


func refresh_data() -> void:
	if not is_inside_tree():
		return
	if _body_label == null:
		return
	
	var market_id := AppState.market_id
	_body_label.text = "Loading pipeline status for %s..." % market_id

	var pipeline := await ApiClient.get_status_pipeline(market_id)
	if pipeline.has("error"):
		_body_label.text = "Error loading pipeline: %s" % pipeline.get("error")
		return
	
	var text := "Market: %s\n" % pipeline.get("market_id", market_id)
	text += "State:  %s\n" % pipeline.get("market_state", "?")
	text += "\nJobs:\n"
	for job in pipeline.get("jobs", []):
		var name := job.get("job_name", "?")
		var status := job.get("last_run_status", "?")
		var last_time := job.get("last_run_time", "-")
		var latency := job.get("latency_ms", null)
		var slo := job.get("slo_ms", null)
		var latency_str := latency == null ? "-" : str(latency) + " ms"
		var slo_str := slo == null ? "-" : str(slo) + " ms"
		text += " - %s: %s (last=%s, lat=%s / SLO=%s)\n" % [
			name,
			status,
			last_time,
			latency_str,
			slo_str,
		]
	
	_body_label.text = text
