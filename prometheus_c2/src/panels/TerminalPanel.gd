extends "res://src/panels/BasePanel.gd"

@onready var _output: TextEdit = %Output
@onready var _input: LineEdit = %InputLine


func _ready() -> void:
	panel_id = "terminal"
	display_name = "Terminal"
	
	if _input:
		_input.text_submitted.connect(_on_command_submitted)
	
	# Listen for job events from CommandBus to surface updates.
	CommandBus.job_submitted.connect(_on_job_submitted)
	CommandBus.job_status_changed.connect(_on_job_status_changed)


func on_activated() -> void:
	if _output and _output.text == "":
		_output.text = _help_text()


func _on_command_submitted(text: String) -> void:
	if _input:
		_input.text = ""
	text = text.strip_edges()
	if text == "":
		return
	
	_log("> " + text)
	await _dispatch_command(text)


func _dispatch_command(cmd: String) -> void:
	var parts := cmd.strip_edges().split(" ", false)
	if parts.is_empty():
		return
	
	var verb := parts[0].to_lower()
	match verb:
		"help":
			_log(_help_text())
		"backtest":
			await _cmd_backtest(parts)
		"synthetic":
			await _cmd_synthetic(parts)
		"dag":
			await _cmd_dag(parts)
		"config":
			await _cmd_config(parts)
		"jobs":
			await _cmd_jobs(parts)
		_:
			_log("Unknown command group '%s'. Type 'help' for usage." % verb)


func _cmd_backtest(parts: Array) -> void:
	# Syntax: backtest run [strategy_id] [start_date] [end_date] [market_ids_csv]
	if parts.size() < 2 or parts[1] != "run":
		_log("Usage: backtest run [strategy_id] [start_date] [end_date] [market_ids_csv]")
		return
	
	var strategy_id := parts.size() > 2 and String(parts[2]) or AppState.strategy_id
	var start_date := parts.size() > 3 and String(parts[3]) or "2024-01-01"
	var end_date := parts.size() > 4 and String(parts[4]) or "2024-12-31"
	var market_ids_csv := parts.size() > 5 and String(parts[5]) or AppState.market_id
	var market_ids := market_ids_csv.split(",", false)
	
	_log("Submitting backtest: strategy=%s %s→%s markets=%s" % [
		strategy_id, start_date, end_date, String.join(",", market_ids),
	])
	var result := await CommandBus.run_backtest(strategy_id, start_date, end_date, market_ids)
	if result.has("job_id"):
		_log("Backtest job submitted: %s" % result["job_id"])
	else:
		_log("Backtest submission failed: %s" % str(result))


func _cmd_synthetic(parts: Array) -> void:
	# Syntax: synthetic create [dataset_name] [scenario_type] [num_samples]
	if parts.size() < 2 or parts[1] != "create":
		_log("Usage: synthetic create [dataset_name] [scenario_type] [num_samples]")
		return
	
	var dataset_name := parts.size() > 2 and String(parts[2]) or "synthetic_scenarios"
	var scenario_type := parts.size() > 3 and String(parts[3]) or "generic"
	var num_samples := parts.size() > 4 and int(parts[4]) or 1000
	
	_log("Submitting synthetic dataset job: %s (%s, %d)" % [
		dataset_name, scenario_type, num_samples,
	])
	var result := await CommandBus.create_synthetic_dataset(dataset_name, scenario_type, num_samples)
	if result.has("job_id"):
		_log("Synthetic dataset job submitted: %s" % result["job_id"])
	else:
		_log("Synthetic dataset submission failed: %s" % str(result))


func _cmd_dag(parts: Array) -> void:
	# Syntax: dag run [market_id] [dag_name]
	if parts.size() < 2 or parts[1] != "run":
		_log("Usage: dag run [market_id] [dag_name]")
		return
	
	var market_id := parts.size() > 2 and String(parts[2]) or AppState.market_id
	var dag_name := parts.size() > 3 and String(parts[3]) or "eod_pipeline"
	
	_log("Scheduling DAG: %s for market %s" % [dag_name, market_id])
	var result := await CommandBus.schedule_dag(market_id, dag_name)
	if result.has("job_id"):
		_log("DAG job submitted: %s" % result["job_id"])
	else:
		_log("DAG scheduling failed: %s" % str(result))


func _cmd_config(parts: Array) -> void:
	# Syntax: config apply [engine_name] [config_key] [config_value]
	if parts.size() < 2 or parts[1] != "apply":
		_log("Usage: config apply [engine_name] [config_key] [config_value]")
		return
	
	if parts.size() < 5:
		_log("Usage: config apply [engine_name] [config_key] [config_value]")
		return
	
	var engine_name := String(parts[2])
	var config_key := String(parts[3])
	var raw_value := String(parts[4])
	var value: Variant = raw_value
	# Try simple numeric parsing.
	if raw_value.is_valid_int():
		value = int(raw_value)
	elif raw_value.is_valid_float():
		value = float(raw_value)
	
	var reason := "Applied via TerminalPanel"
	_log("Staging config change: %s.%s=%s" % [engine_name, config_key, str(value)])
	var result := await CommandBus.apply_config_change(engine_name, config_key, value, reason, true)
	if result.has("job_id"):
		_log("Config job staged: %s" % result["job_id"])
	else:
		_log("Config change failed: %s" % str(result))


func _cmd_jobs(parts: Array) -> void:
	# Syntax: jobs list | jobs watch [job_id]
	if parts.size() == 1 or parts[1] == "list":
		var jobs := CommandBus.get_active_jobs()
		if jobs.is_empty():
			_log("No active jobs.")
			return
		_log("Active jobs:")
		for j in jobs:
			_log(" - %s [%s] %s" % [j.get("job_id", "?"), j.get("type", "?"), j.get("status", "?")])
		return
	
	if parts[1] == "watch":
		if parts.size() < 3:
			_log("Usage: jobs watch [job_id]")
			return
		var job_id := String(parts[2])
		_log("Watching job %s..." % job_id)
		var status := await CommandBus.watch_job(job_id)
		_log("Job %s status: %s" % [job_id, status.get("status", "?")])
		return
	
	_log("Usage: jobs list | jobs watch [job_id]")


func _on_job_submitted(job_id: String, job_type: String) -> void:
	_log("[job] submitted %s (%s)" % [job_id, job_type])


func _on_job_status_changed(job_id: String, status: String) -> void:
	_log("[job] %s status -> %s" % [job_id, status])


func _log(message: String) -> void:
	if not _output:
		return
	_output.text += message + "\n"
	_output.scroll_vertical = _output.get_line_count()


func _help_text() -> String:
	var t := ""
	t += "Prometheus C2 Terminal\n"
	t += "Commands:\n"
	t += "  help\n"
	t += "  backtest run [strategy_id] [start_date] [end_date] [market_ids_csv]\n"
	t += "  synthetic create [dataset_name] [scenario_type] [num_samples]\n"
	t += "  dag run [market_id] [dag_name]\n"
	t += "  config apply [engine_name] [config_key] [config_value]\n"
	t += "  jobs list\n"
	t += "  jobs watch [job_id]\n"
	return t
