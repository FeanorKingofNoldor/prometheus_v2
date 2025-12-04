extends Node
## HTTP and WebSocket client for Prometheus C2 backend APIs.
##
## Provides async methods for all monitoring, visualization, control, and meta endpoints.
## Configure API_BASE_URL to point to your backend server.

## Base URL for API server
const API_BASE_URL: String = "http://localhost:8000"


func _ready() -> void:
	print("ApiClient initialized")
	print("  Backend: ", API_BASE_URL)


# ============================================================================
# Monitoring/Status APIs
# ============================================================================

## Get global system overview
func get_status_overview() -> Dictionary:
	return await _get_json("/api/status/overview")


## Get per-market pipeline status
func get_status_pipeline(market_id: String) -> Dictionary:
	return await _get_json("/api/status/pipeline?market_id=" + market_id)


## Get regime status for a region
func get_status_regime(region: String = "US", as_of_date: String = "") -> Dictionary:
	var url := "/api/status/regime?region=" + region
	if as_of_date != "":
		url += "&as_of_date=" + as_of_date
	return await _get_json(url)


## Get stability status for a region
func get_status_stability(region: String = "US", as_of_date: String = "") -> Dictionary:
	var url := "/api/status/stability?region=" + region
	if as_of_date != "":
		url += "&as_of_date=" + as_of_date
	return await _get_json(url)


## Get fragility entities table
func get_status_fragility(region: String = "GLOBAL", entity_type: String = "ANY") -> Dictionary:
	return await _get_json("/api/status/fragility?region=" + region + "&entity_type=" + entity_type)


## Get fragility detail for specific entity
func get_status_fragility_detail(entity_id: String) -> Dictionary:
	return await _get_json("/api/status/fragility/" + entity_id)


## Get assessment output for a strategy
func get_status_assessment(strategy_id: String) -> Dictionary:
	return await _get_json("/api/status/assessment?strategy_id=" + strategy_id)


## Get universe membership for a strategy
func get_status_universe(strategy_id: String) -> Dictionary:
	return await _get_json("/api/status/universe?strategy_id=" + strategy_id)


## Get portfolio positions and P&L
func get_status_portfolio(portfolio_id: String) -> Dictionary:
	return await _get_json("/api/status/portfolio?portfolio_id=" + portfolio_id)


## Get portfolio risk metrics
func get_status_portfolio_risk(portfolio_id: String) -> Dictionary:
	return await _get_json("/api/status/portfolio_risk?portfolio_id=" + portfolio_id)


## Get recent execution activity (orders/fills/positions) for a portfolio
func get_status_execution(portfolio_id: String, mode: String = "", limit_orders: int = 50, limit_fills: int = 50) -> Dictionary:
	var url := "/api/status/execution?portfolio_id=" + portfolio_id
	if mode != "":
		url += "&mode=" + mode
	url += "&limit_orders=" + str(limit_orders)
	url += "&limit_fills=" + str(limit_fills)
	return await _get_json(url)


## Get recent risk_actions rows for a strategy
func get_status_risk_actions(strategy_id: String, limit: int = 50) -> Dictionary:
	var url := "/api/status/risk_actions?strategy_id=" + strategy_id + "&limit=" + str(limit)
	return await _get_json(url)


# ============================================================================
# Visualization APIs
# ============================================================================

## Get list of available ANT_HILL scenes
func get_scenes() -> Array:
	var result: Variant = await _get_json("/api/scenes")
	if result.has("error"):
		return []
	return result if result is Array else []


## Get scene graph for a specific view
func get_scene(view_id: String) -> Dictionary:
	return await _get_json("/api/scene/" + view_id)


## Get list of execution traces
func get_traces(market_id: String = "", mode: String = "") -> Array:
	var url := "/api/traces?"
	if market_id != "":
		url += "market_id=" + market_id
	if mode != "":
		url += "&mode=" + mode
	var result: Variant = await _get_json(url)
	if result.has("error"):
		return []
	return result if result is Array else []


## Get execution trace events
func get_trace(trace_id: String) -> Dictionary:
	return await _get_json("/api/traces/" + trace_id)


## Get embedding space vectors
func get_embedding_space(space_id: String) -> Dictionary:
	return await _get_json("/api/embedding_space/" + space_id)


# ============================================================================
# Control APIs
# ============================================================================

## Submit backtest job
func run_backtest(params: Dictionary) -> Dictionary:
	return await _post_json("/api/control/run_backtest", params)


## Submit synthetic dataset creation job
func create_synthetic_dataset(params: Dictionary) -> Dictionary:
	return await _post_json("/api/control/create_synthetic_dataset", params)


## Schedule DAG execution
func schedule_dag(params: Dictionary) -> Dictionary:
	return await _post_json("/api/control/schedule_dag", params)


## Apply configuration change
func apply_config_change(params: Dictionary) -> Dictionary:
	return await _post_json("/api/control/apply_config_change", params)


## Get job status
func get_job_status(job_id: String) -> Dictionary:
	return await _get_json("/api/control/jobs/" + job_id)


# ============================================================================
# Kronos Chat API
# ============================================================================

## Chat with Kronos meta-orchestrator
func kronos_chat(question: String, context: Dictionary = {}) -> Dictionary:
	var payload := {
		"question": question,
		"context": context
	}
	return await _post_json("/api/kronos/chat", payload)


# ============================================================================
# Geo APIs
# ============================================================================

## Get country-level status for world map
func get_countries() -> Array:
	var result: Variant = await _get_json("/api/geo/countries")
	if result.has("error"):
		return []
	return result if result is Array else []


## Get detailed country information
func get_country_detail(country_code: String) -> Dictionary:
	return await _get_json("/api/geo/country/" + country_code)


# ============================================================================
# Meta APIs
# ============================================================================

## Get engine configurations
func get_configs() -> Array:
	var result: Variant = await _get_json("/api/meta/configs")
	if result.has("error"):
		return []
	return result if result is Array else []


## Get engine performance metrics
func get_performance(engine_name: String, period: String = "30d") -> Dictionary:
	return await _get_json("/api/meta/performance?engine_name=" + engine_name + "&period=" + period)


# ============================================================================
# Intelligence APIs (Meta/Kronos)
# ============================================================================

## Get diagnostic report for strategy
func get_diagnostics(strategy_id: String, min_sample_size: int = 5) -> Dictionary:
	return await _get_json("/api/intelligence/diagnostics/" + strategy_id + "?min_sample_size=" + str(min_sample_size))


## Generate improvement proposals for strategy
func generate_proposals(strategy_id: String, min_confidence: float = 0.3, min_sharpe: float = 0.1) -> Array:
	var url := "/api/intelligence/proposals/generate/" + strategy_id
	url += "?min_confidence=" + str(min_confidence)
	url += "&min_sharpe_improvement=" + str(min_sharpe)
	var result: Variant = await _post_json(url, {})
	if result.has("error"):
		return []
	return result if result is Array else []


## List configuration proposals
func list_proposals(strategy_id: String = "", status: String = "") -> Array:
	var url := "/api/intelligence/proposals?"
	if strategy_id != "":
		url += "strategy_id=" + strategy_id
	if status != "":
		url += "&status=" + status
	var result: Variant = await _get_json(url)
	if result.has("error"):
		return []
	return result if result is Array else []


## Approve a proposal
func approve_proposal(proposal_id: String, user_id: String) -> Dictionary:
	var payload := {"user_id": user_id}
	return await _post_json("/api/intelligence/proposals/" + proposal_id + "/approve", payload)


## Reject a proposal
func reject_proposal(proposal_id: String, user_id: String) -> Dictionary:
	var payload := {"user_id": user_id}
	return await _post_json("/api/intelligence/proposals/" + proposal_id + "/reject", payload)


## Apply an approved proposal
func apply_proposal(proposal_id: String, user_id: String, dry_run: bool = false) -> Dictionary:
	var payload := {"user_id": user_id}
	var url := "/api/intelligence/proposals/" + proposal_id + "/apply"
	if dry_run:
		url += "?dry_run=true"
	return await _post_json(url, payload)


## Apply multiple approved proposals in batch
func apply_proposals_batch(user_id: String, strategy_id: String = "", max_proposals: int = 10, dry_run: bool = false) -> Array:
	var payload := {"user_id": user_id}
	var url := "/api/intelligence/proposals/apply-batch?"
	if strategy_id != "":
		url += "strategy_id=" + strategy_id + "&"
	url += "max_proposals=" + str(max_proposals)
	if dry_run:
		url += "&dry_run=true"
	var result: Variant = await _post_json(url, payload)
	if result.has("error"):
		return []
	return result if result is Array else []


## List configuration changes
func list_changes(strategy_id: String = "", is_reverted: bool = false) -> Array:
	var url := "/api/intelligence/changes?"
	if strategy_id != "":
		url += "strategy_id=" + strategy_id + "&"
	url += "is_reverted=" + str(is_reverted)
	var result: Variant = await _get_json(url)
	if result.has("error"):
		return []
	return result if result is Array else []


## Revert a configuration change
func revert_change(change_id: String, reason: String, user_id: String, dry_run: bool = false) -> Dictionary:
	var payload := {
		"reason": reason,
		"user_id": user_id
	}
	var url := "/api/intelligence/changes/" + change_id + "/revert"
	if dry_run:
		url += "?dry_run=true"
	return await _post_json(url, payload)


# ============================================================================
# Internal HTTP Helpers
# ============================================================================

## Internal helper for GET requests
## NOTE: return type is Variant because some endpoints legitimately return
## arrays at the top level (e.g. /api/scenes). Callers cast or check types
## as needed.
func _get_json(endpoint: String) -> Variant:
	var url: String = API_BASE_URL + endpoint
	var client: HTTPRequest = HTTPRequest.new()
	add_child(client)
	C2Logger.info("ApiClient", "GET " + url)
	var error: int = client.request(url)
	if error != OK:
		C2Logger.error("ApiClient", "GET failed for %s (code=%d)" % [url, error])
		client.queue_free()
		return {"error": "Request failed"}
	var result: Array = await client.request_completed
	client.queue_free()
	var response_code: int = int(result[1])
	var body: PackedByteArray = result[3]
	if response_code != 200:
		C2Logger.warn("ApiClient", "HTTP %d for %s" % [response_code, url])
		return {"error": "HTTP " + str(response_code)}
	var json := JSON.new()
	var parse_result: int = json.parse(body.get_string_from_utf8())
	if parse_result != OK:
		C2Logger.error("ApiClient", "JSON parse error for %s: %s" % [url, json.get_error_message()])
		return {"error": "Parse error"}
	return json.data


## Internal helper for POST requests
func _post_json(endpoint: String, payload: Dictionary) -> Dictionary:
	var url: String = API_BASE_URL + endpoint
	var headers: Array = ["Content-Type: application/json"]
	var body: String = JSON.stringify(payload)
	var client: HTTPRequest = HTTPRequest.new()
	add_child(client)
	C2Logger.info("ApiClient", "POST " + url)
	var error: int = client.request(url, headers, HTTPClient.METHOD_POST, body)
	if error != OK:
		C2Logger.error("ApiClient", "POST failed for %s (code=%d)" % [url, error])
		client.queue_free()
		return {"error": "Request failed"}
	var result: Array = await client.request_completed
	client.queue_free()
	var response_code: int = int(result[1])
	var response_body: PackedByteArray = result[3]
	if response_code < 200 or response_code >= 300:
		C2Logger.warn("ApiClient", "HTTP %d for %s" % [response_code, url])
		return {"error": "HTTP " + str(response_code)}
	var json := JSON.new()
	var parse_result: int = json.parse(response_body.get_string_from_utf8())
	if parse_result != OK:
		C2Logger.error("ApiClient", "JSON parse error for %s: %s" % [url, json.get_error_message()])
		return {"error": "Parse error"}
	return json.data
