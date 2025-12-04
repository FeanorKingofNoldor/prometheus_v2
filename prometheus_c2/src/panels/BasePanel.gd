extends Control
## Base class for all Prometheus C2 panels.
##
## Panels should inherit from this script and override lifecycle methods
## as needed. MainShell uses these hooks when switching panels.

@export var panel_id: String = ""
@export var display_name: String = ""


func on_activated() -> void:
	"""Called when the panel becomes visible/active."""
	pass


func on_deactivated() -> void:
	"""Called when the panel is hidden or replaced."""
	pass


func refresh_data() -> void:
	"""Called by the shell to refresh panel data from APIs.
	Implementations should call ApiClient and update their UI.
	"""
	pass
