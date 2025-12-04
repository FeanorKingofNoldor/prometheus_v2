extends "res://src/panels/BasePanel.gd"

@onready var _body_label: Label = get_node("Background/VBox/Body")


func _ready() -> void:
	panel_id = "overview"
	display_name = "Overview"


func on_activated() -> void:
	refresh_data()


func refresh_data() -> void:
	if not is_inside_tree():
		return
	if _body_label == null:
		return
	
	_body_label.text = "Loading system overview..."

	var overview := await ApiClient.get_status_overview()
	if overview.has("error"):
		_body_label.text = "Error loading overview: %s" % overview.get("error")
		return
	
	var pnl_today := float(overview.get("pnl_today", 0.0))
	var pnl_mtd := float(overview.get("pnl_mtd", 0.0))
	var pnl_ytd := float(overview.get("pnl_ytd", 0.0))
	var max_dd := float(overview.get("max_drawdown", 0.0))
	var net_exp := float(overview.get("net_exposure", 0.0))
	var gross_exp := float(overview.get("gross_exposure", 0.0))
	var lev := float(overview.get("leverage", 0.0))
	var glob_stab := float(overview.get("global_stability_index", 0.0))
	
	var text := ""
	text += "P&L Today : %8.2f\n" % pnl_today
	text += "P&L MTD   : %8.2f\n" % pnl_mtd
	text += "P&L YTD   : %8.2f\n" % pnl_ytd
	text += "Max DD    : %8.3f\n" % max_dd
	text += "Net Exp   : %8.3f\n" % net_exp
	text += "Gross Exp : %8.3f\n" % gross_exp
	text += "Leverage  : %8.3f\n" % lev
	text += "Global STAB: %6.3f\n" % glob_stab
	text += "\nRegimes:\n"
	for regime in overview.get("regimes", []):
		var region: String = String(regime.get("region", "?"))
		var label: String = String(regime.get("regime_label", "?"))
		var conf := float(regime.get("confidence", 0.0)) * 100.0
		text += " - %s: %s (%.0f%%)\n" % [region, label, conf]
	
	var alerts: Array = overview.get("alerts", [])
	if alerts.size() > 0:
		text += "\nAlerts:\n"
		for alert in alerts:
			var sev: String = String(alert.get("severity", "INFO"))
			var msg: String = String(alert.get("message", ""))
			text += " - [%s] %s\n" % [sev, msg]
	else:
		text += "\nAlerts: none\n"
	
	# Optionally enrich with US regime & stability snapshots.
	var regime_us := await ApiClient.get_status_regime("US")
	if not regime_us.has("error"):
		text += "\nUS Regime: %s (%.0f%%)\n" % [
			regime_us.get("current_regime", "?"),
			float(regime_us.get("confidence", 0.0)) * 100.0,
		]
	
	var stab_us := await ApiClient.get_status_stability("US")
	if not stab_us.has("error"):
		text += "US STAB idx: %.3f (liq=%.3f, vol=%.3f, contagion=%.3f)\n" % [
			stab_us.get("current_index", 0.0),
			stab_us.get("liquidity_component", 0.0),
			stab_us.get("volatility_component", 0.0),
			stab_us.get("contagion_component", 0.0),
		]
	
	_body_label.text = text
