extends "res://src/panels/BasePanel.gd"
## Meta/Kronos Intelligence Panel
##
## Displays:
## - Strategy diagnostics (performance analysis)
## - Generated proposals (config improvements)
## - Applied changes and outcomes
## - Approval workflow

@onready var _content: Label = get_node("Background/VBox/ScrollContainer/Content")

var _current_strategy: String = ""


func _ready() -> void:
	panel_id = "meta_experiments"
	display_name = "Meta & Experiments"


func on_activated() -> void:
	refresh_data()


func refresh_data() -> void:
	if not is_inside_tree() or _content == null:
		return
	
	_current_strategy = AppState.strategy_id
	_content.text = "Loading intelligence data for %s..." % _current_strategy
	
	# Fetch all intelligence data in parallel
	var diagnostics_task := ApiClient.get_diagnostics(_current_strategy, 5)
	var proposals_task := ApiClient.list_proposals(_current_strategy, "PENDING")
	var changes_task := ApiClient.list_changes(_current_strategy, false)
	
	var diagnostics: Dictionary = await diagnostics_task
	var proposals: Array = await proposals_task
	var changes: Array = await changes_task
	
	if diagnostics.has("error"):
		_content.text = "Error loading diagnostics: %s" % diagnostics["error"]
		return
	
	# Build comprehensive display
	var text := ""
	
	# === DIAGNOSTICS SECTION ===
	text += "═══════════════════════════════════════════════════════════\n"
	text += "  STRATEGY DIAGNOSTICS: %s\n" % _current_strategy
	text += "═══════════════════════════════════════════════════════════\n\n"
	
	text += "📊 OVERALL PERFORMANCE\n"
	text += "  Sharpe Ratio:   %7.3f\n" % diagnostics.get("overall_sharpe", 0.0)
	text += "  Return:         %7.2f%%\n" % (diagnostics.get("overall_return", 0.0) * 100.0)
	text += "  Volatility:     %7.2f%%\n" % (diagnostics.get("overall_volatility", 0.0) * 100.0)
	text += "  Max Drawdown:   %7.2f%%\n" % (diagnostics.get("max_drawdown", 0.0) * 100.0)
	text += "  Sample Size:    %d runs\n" % diagnostics.get("sample_size", 0)
	text += "\n"
	
	var underperforming := diagnostics.get("underperforming_count", 0)
	var high_risk := diagnostics.get("high_risk_count", 0)
	var comparisons := diagnostics.get("config_comparisons_count", 0)
	
	text += "⚠️  RISK ANALYSIS\n"
	if underperforming > 0:
		text += "  Underperforming configs: %d\n" % underperforming
	else:
		text += "  ✅ No underperforming configs\n"
	
	if high_risk > 0:
		text += "  High-risk configs: %d\n" % high_risk
	else:
		text += "  ✅ All configs within risk limits\n"
	
	text += "\n"
	text += "🔬 CONFIG ANALYSIS\n"
	text += "  Config comparisons found: %d\n" % comparisons
	text += "  Analysis timestamp: %s\n" % diagnostics.get("analysis_timestamp", "N/A")
	text += "\n\n"
	
	# === PROPOSALS SECTION ===
	text += "═══════════════════════════════════════════════════════════\n"
	text += "  IMPROVEMENT PROPOSALS (%d PENDING)\n" % proposals.size()
	text += "═══════════════════════════════════════════════════════════\n\n"
	
	if proposals.size() == 0:
		text += "  📭 No pending proposals\n"
		text += "  Run diagnostics to generate new proposals\n\n"
	else:
		for i in range(min(proposals.size(), 5)):
			var prop: Dictionary = proposals[i]
			var conf := float(prop.get("confidence_score", 0.0))
			var sharpe_delta := float(prop.get("expected_sharpe_improvement", 0.0))
			var return_delta := float(prop.get("expected_return_improvement", 0.0))
			
			text += "  %d. [%s] %s\n" % [
				i + 1,
				String(prop.get("proposal_id", "?"))[0:8],
				prop.get("proposal_type", "?")
			]
			text += "     Target: %s\n" % prop.get("target_component", "?")
			text += "     %s → %s\n" % [
				str(prop.get("current_value", "?")),
				str(prop.get("proposed_value", "?"))
			]
			text += "     Impact: Sharpe +%.3f, Return +%.2f%%\n" % [sharpe_delta, return_delta * 100.0]
			text += "     Confidence: %.0f%%\n" % (conf * 100.0)
			text += "     Rationale: %s\n" % prop.get("rationale", "N/A")
			text += "\n"
		
		if proposals.size() > 5:
			text += "  ... and %d more proposals\n\n" % (proposals.size() - 5)
	
	text += "\n"
	
	# === CHANGES SECTION ===
	text += "═══════════════════════════════════════════════════════════\n"
	text += "  APPLIED CHANGES (%d RECENT)\n" % changes.size()
	text += "═══════════════════════════════════════════════════════════\n\n"
	
	if changes.size() == 0:
		text += "  📋 No applied changes yet\n\n"
	else:
		for i in range(min(changes.size(), 5)):
			var change: Dictionary = changes[i]
			var sharpe_before := change.get("sharpe_before")
			var sharpe_after := change.get("sharpe_after")
			var improvement := change.get("sharpe_improvement")
			var reverted := bool(change.get("is_reverted", false))
			
			text += "  %d. [%s] %s\n" % [
				i + 1,
				String(change.get("change_id", "?"))[0:8],
				change.get("change_type", "?")
			]
			text += "     Target: %s\n" % change.get("target_component", "?")
			text += "     Applied: %s\n" % change.get("applied_at", "?")
			
			if sharpe_before != null and sharpe_after != null:
				text += "     Sharpe: %.3f → %.3f (" % [sharpe_before, sharpe_after]
				if improvement != null:
					text += "%+.3f" % improvement
				text += ")\n"
			else:
				text += "     Evaluation: Pending\n"
			
			if reverted:
				text += "     ⚠️ REVERTED\n"
			
			text += "\n"
		
		if changes.size() > 5:
			text += "  ... and %d more changes\n\n" % (changes.size() - 5)
	
	text += "\n"
	text += "═══════════════════════════════════════════════════════════\n"
	text += "  ACTIONS\n"
	text += "═══════════════════════════════════════════════════════════\n"
	text += "  Use Terminal to:\n"
	text += "  • Generate proposals: propose <strategy_id>\n"
	text += "  • Approve proposal:   approve <proposal_id>\n"
	text += "  • Apply proposal:     apply <proposal_id>\n"
	text += "  • Revert change:      revert <change_id> <reason>\n"
	
	_content.text = text
