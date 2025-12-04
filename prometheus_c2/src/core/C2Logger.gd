extends Node
## C2Logger – central logging utility for Prometheus C2.
##
## Usage from anywhere:
##   C2Logger.info("SceneGraph", "Loaded 8 nodes")
##   C2Logger.warn("ApiClient", "HTTP 500 for /api/status/overview")
##
## This prints to the Godot console and emits a signal so MainShell can
## surface logs in the UI console panel.

signal log_message(level: String, source: String, message: String)


func _ready() -> void:
	print("C2Logger initialized")


func info(source: String, message: String) -> void:
	_emit("INFO", source, message)


func warn(source: String, message: String) -> void:
	_emit("WARN", source, message)


func error(source: String, message: String) -> void:
	_emit("ERROR", source, message)


func _emit(level: String, source: String, message: String) -> void:
	var line := "[%s] [%s] %s" % [level, source, message]
	print(line)
	log_message.emit(level, source, message)
