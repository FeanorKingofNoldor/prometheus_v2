extends "res://src/panels/BasePanel.gd"

@onready var _body_label: Label = get_node("Background/VBox/Body")


func _ready() -> void:
	panel_id = "execution"
	display_name = "Execution"


func on_activated() -> void:
	refresh_data()


func refresh_data() -> void:
	if not is_inside_tree():
		return
	if _body_label == null:
		return
	
	var portfolio_id := AppState.portfolio_id
	var strategy_id := AppState.strategy_id
	var mode_name := String(AppState.Mode.keys()[AppState.mode])
	_body_label.text = "Loading execution status for %s (mode=%s)..." % [portfolio_id, mode_name]
	
	var exec_status := await ApiClient.get_status_execution(portfolio_id, mode_name, 25, 25)
	var risk_actions := await ApiClient.get_status_risk_actions(strategy_id, 20)
	
	if exec_status.has("error") and risk_actions.has("error"):
		_body_label.text = "Error loading execution/risk: %s" % exec_status.get("error")
		return
	
	var text := "Execution status for %s (mode=%s)\n" % [portfolio_id, mode_name]
	text += "".ljust(60, "=") + "\n"
	
	if not exec_status.has("error"):
		var orders: Array = exec_status.get("orders", [])
		var fills: Array = exec_status.get("fills", [])
		var pos: Array = exec_status.get("positions", [])
		var mode_str := String(exec_status.get("mode", mode_name))
		text += "\nOrders (mode=%s, max 25):\n" % mode_str
		if orders.is_empty():
			text += "  (none)\n"
		else:
			for o in orders:
				var ts_o := String(o.get("timestamp", ""))
				var side_o := String(o.get("side", "?"))
				var iid_o := String(o.get("instrument_id", "?"))
				var qty_o := float(o.get("quantity", 0.0))
				var status_o := String(o.get("status", "?"))
				text += "  [%s] %s %.0f %s (%s)\n" % [ts_o, side_o, qty_o, iid_o, status_o]
			
		text += "\nFills (max 25):\n"
		if fills.is_empty():
			text += "  (none)\n"
		else:
			for f in fills:
				var ts_f := String(f.get("timestamp", ""))
				var side_f := String(f.get("side", "?"))
				var iid_f := String(f.get("instrument_id", "?"))
				var qty_f := float(f.get("quantity", 0.0))
				var price_f := float(f.get("price", 0.0))
				text += "  [%s] %s %.0f %s @ %.2f\n" % [ts_f, side_f, qty_f, iid_f, price_f]
			
		text += "\nLatest positions snapshot:\n"
		if pos.is_empty():
			text += "  (none)\n"
		else:
			for p in pos:
				var iid_p := String(p.get("instrument_id", "?"))
				var qty_p := float(p.get("quantity", 0.0))
				var mv_p := float(p.get("market_value", 0.0))
				var upnl_p := float(p.get("unrealized_pnl", 0.0))
				text += "  %s: qty=%.0f MV=%.0f UPNL=%.0f\n" % [iid_p, qty_p, mv_p, upnl_p]
	
	if not risk_actions.has("error"):
		var acts: Array = risk_actions.get("actions", [])
		text += "\nRisk actions (strategy=%s, max 20):\n" % strategy_id
		if acts.is_empty():
			text += "  (none)\n"
		else:
			for a in acts:
				var ts_a := String(a.get("created_at", ""))
				var iid_a := String(a.get("instrument_id", ""))
				var atype := String(a.get("action_type", ""))
				var ow := a.get("original_weight", null)
				var aw := a.get("adjusted_weight", null)
				var reason_a := String(a.get("reason", ""))
				var ow_str := ow == null and "" or "%.4f" % float(ow)
				var aw_str := aw == null and "" or "%.4f" % float(aw)
				# Highlight execution-time rejects vs book-level caps.
				var tag := atype
				if atype == "EXECUTION_REJECT":
					tag = "EXECUTION_REJECT*"
				text += "  [%s] %s %s -> %s (%s) %s\\n" % [
					ts_a,
					iid_a,
					ow_str,
					aw_str,
					tag,
					reason_a,
				]
					ts_a,
					iid_a,
					ow_str,
					aw_str,
					atype,
					reason_a,
				]
	
	_body_label.text = text
