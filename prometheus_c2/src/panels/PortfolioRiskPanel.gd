extends "res://src/panels/BasePanel.gd"

@onready var _body_label: Label = get_node("Background/VBox/Body")
@onready var _max_lev_input: LineEdit = %MaxLevInput
@onready var _stage_risk_btn: Button = %StageRiskConfigButton


func _ready() -> void:
	panel_id = "portfolio_risk"
	display_name = "Portfolio & Risk"
	
	if _stage_risk_btn:
		_stage_risk_btn.pressed.connect(_on_stage_risk_pressed)


func on_activated() -> void:
	refresh_data()


func refresh_data() -> void:
	if not is_inside_tree():
		return
	if _body_label == null:
		return
	
	var portfolio_id := AppState.portfolio_id
	_body_label.text = "Loading portfolio & risk for %s..." % portfolio_id
	
	var port := await ApiClient.get_status_portfolio(portfolio_id)
	var risk := await ApiClient.get_status_portfolio_risk(portfolio_id)
	var exec_status := await ApiClient.get_status_execution(portfolio_id, AppState.mode, 25, 25)
	var risk_actions := await ApiClient.get_status_risk_actions(AppState.strategy_id, 20)
	
	if port.has("error") and risk.has("error") and exec_status.has("error"):
		_body_label.text = "Error loading portfolio/risk/execution: %s" % port.get("error")
		return
	
	var text := "Portfolio: %s\\n" % portfolio_id
	
	if not port.has("error"):
		text += "\nTop positions by weight:\n"
		var positions: Array = port.get("positions", [])
		positions.sort_custom(func(a, b):
			return abs(b.get("weight", 0.0)) < abs(a.get("weight", 0.0))
		)
		var max_rows := min(positions.size(), 10)
		for i in range(max_rows):
			var p := positions[i]
			var iid := p.get("instrument_id", "?")
			var w := p.get("weight", 0.0) * 100.0
			var mv := p.get("market_value", 0.0)
			text += " - %s: %.2f%% (MV=%.0f)\n" % [iid, w, mv]
		
		var pnl := port.get("pnl", {})
		if pnl:
			text += "\nP&L: today=%.2f, MTD=%.2f, YTD=%.2f\n" % [
				pnl.get("today", 0.0),
				pnl.get("mtd", 0.0),
				pnl.get("ytd", 0.0),
			]
	
	if not risk.has("error"):
		text += "\\nRisk summary:\\n"
		text += "Volatility:        %.3f\\n" % risk.get("volatility", 0.0)
		text += "VaR 95%%:          %.3f\\n" % risk.get("var_95", 0.0)
		text += "Expected Shortfall: %.3f\\n" % risk.get("expected_shortfall", 0.0)
		text += "Max Drawdown:      %.3f\\n" % risk.get("max_drawdown", 0.0)
		var scenarios: Array = risk.get("scenarios", [])
		if scenarios.size() > 0:
			text += "\\nScenario P&L:\\n"
			for s in scenarios:
				text += " - %s: %.0f\\n" % [s.get("scenario", "?"), s.get("pnl", 0.0)]
	
	if not exec_status.has("error"):
		var mode_str := String(exec_status.get("mode", AppState.mode))
		text += "\\nExecution (mode=%s):\\n" % mode_str
		var orders: Array = exec_status.get("orders", [])
		if orders.size() > 0:
			text += "Recent orders (max 25):\\n"
			for o in orders:
				var ts_o := String(o.get("timestamp", ""))
				var side_o := String(o.get("side", "?"))
				var iid_o := String(o.get("instrument_id", "?"))
				var qty_o := float(o.get("quantity", 0.0))
				var status_o := String(o.get("status", "?"))
				text += " - [%s] %s %.0f %s (%s)\\n" % [ts_o, side_o, qty_o, iid_o, status_o]
		var fills: Array = exec_status.get("fills", [])
		if fills.size() > 0:
			text += "\\nRecent fills (max 25):\\n"
			for f in fills:
				var ts_f := String(f.get("timestamp", ""))
				var side_f := String(f.get("side", "?"))
				var iid_f := String(f.get("instrument_id", "?"))
				var qty_f := float(f.get("quantity", 0.0))
				var price_f := float(f.get("price", 0.0))
				text += " - [%s] %s %.0f %s @ %.2f\\n" % [ts_f, side_f, qty_f, iid_f, price_f]
		var pos: Array = exec_status.get("positions", [])
		if pos.size() > 0:
			text += "\\nLatest positions snapshot (from execution):\\n"
			for p2 in pos:
				var iid_p := String(p2.get("instrument_id", "?"))
				var qty_p := float(p2.get("quantity", 0.0))
				var mv_p := float(p2.get("market_value", 0.0))
				text += " - %s: qty=%.0f MV=%.0f\\n" % [iid_p, qty_p, mv_p]
	
	if not risk_actions.has("error"):
		var acts: Array = risk_actions.get("actions", [])
		if acts.size() > 0:
			text += "\\nRecent risk actions (strategy=%s):\\n" % AppState.strategy_id
			for a in acts:
				var ts_a := String(a.get("created_at", ""))
				var iid_a := String(a.get("instrument_id", ""))
				var atype := String(a.get("action_type", ""))
				var ow := a.get("original_weight", null)
				var aw := a.get("adjusted_weight", null)
				var reason_a := String(a.get("reason", ""))
				var ow_str := ow == null and "" or "%.4f" % float(ow)
				var aw_str := aw == null and "" or "%.4f" % float(aw)
				text += " - [%s] %s %s -> %s (%s) %s\\n" % [
					ts_a,
					iid_a,
					ow_str,
					aw_str,
					atype,
					reason_a,
				]
	
	_body_label.text = text


func _on_stage_risk_pressed() -> void:
	var raw := _max_lev_input and _max_lev_input.text.strip_edges() or ""
	if raw == "":
		_append("Enter a max_leverage value (e.g. 2.0)")
		return
	var value: Variant = raw
	if raw.is_valid_float():
		value = float(raw)
	
	var reason := "Staged via PortfolioRiskPanel"
	_append("Staging risk config max_leverage=%s" % str(value))
	var result := await CommandBus.apply_config_change("risk", "max_leverage", value, reason, true)
	if result.has("job_id"):
		_append("Risk config job staged: %s" % result["job_id"])
	else:
		_append("Risk config staging failed: %s" % str(result))


func _append(line: String) -> void:
	if not _body_label:
		return
	_body_label.text += "\n" + line
