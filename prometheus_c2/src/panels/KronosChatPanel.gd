extends "res://src/panels/BasePanel.gd"

@onready var _transcript: TextEdit = %Transcript
@onready var _input: LineEdit = %InputLine


func _ready() -> void:
	panel_id = "kronos_chat"
	display_name = "Kronos Chat"
	if _input:
		_input.text_submitted.connect(_on_question_submitted)


func on_activated() -> void:
	if _transcript and _transcript.text == "":
		_transcript.text = _intro_text()


func _on_question_submitted(text: String) -> void:
	if _input:
		_input.text = ""
	text = text.strip_edges()
	if text == "":
		return
	
	_append_user(text)
	await _send_to_kronos(text)


func _send_to_kronos(question: String) -> void:
	_append_system("Thinking...")
	var ctx := AppState.get_context()
	var result := await ApiClient.kronos_chat(question, ctx)
	if result.has("error"):
		_append_system("Error: %s" % result.get("error"))
		return
	
	var answer := String(result.get("answer", "(no answer)"))
	_append_kronos(answer)
	
	var proposals := result.get("proposals", [])
	if proposals is Array and proposals.size() > 0:
		_append_system("Proposals:")
		for p in proposals:
			var ptype := p.get("type", "?")
			var summary := p.get("summary", "")
			_append_system(" - [%s] %s" % [ptype, summary])


func _append_user(text: String) -> void:
	if not _transcript:
		return
	_transcript.text += "\n[you] " + text
	_transcript.scroll_vertical = _transcript.get_line_count()


func _append_kronos(text: String) -> void:
	if not _transcript:
		return
	_transcript.text += "\n[kronos] " + text
	_transcript.scroll_vertical = _transcript.get_line_count()


func _append_system(text: String) -> void:
	if not _transcript:
		return
	_transcript.text += "\n[sys] " + text
	_transcript.scroll_vertical = _transcript.get_line_count()


func _intro_text() -> String:
	var t := "Kronos Chat\n"
	t += "Ask questions about performance, regimes, configs, and portfolios.\n"
	t += "Examples:\n"
	t += "  Why did we de-risk US banks last week?\n"
	t += "  Which configs underperform in crisis regimes?\n"
	t += "  Propose safer Assessment configs for MAIN.\n"
	return t
