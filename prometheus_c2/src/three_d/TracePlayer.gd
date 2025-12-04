extends Node3D
## TracePlayer – placeholder for execution trace visualization.
##
## In a future iteration this node will animate packets along edges in the
## SceneGraph using `/api/traces/{trace_id}` or `/api/traces/live`. For now it
## simply fetches trace metadata and logs a short summary for debugging.

@export var trace_id: String = ""


func _ready() -> void:
	if trace_id == "":
		return
	await _load_trace(trace_id)


func _load_trace(id: String) -> void:
	var data := await ApiClient.get_trace(id)
	if data.has("error"):
		push_warning("TracePlayer: backend error: %s" % data.get("error"))
		return
	var events: Array = data.get("events", [])
	push_warning("TracePlayer: loaded %d events for trace %s" % [events.size(), id])
