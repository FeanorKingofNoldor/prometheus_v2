extends Node
## Global application state for Prometheus C2.
##
## Maintains current context: market, strategy, portfolio, date, mode, and active workspace.
## All panels and systems can access this state via the AppState autoload.

## Current market identifier (e.g., "US_EQ", "EU_EQ")
var market_id: String = "US_EQ"

## Current strategy identifier
var strategy_id: String = "MAIN"

## Current portfolio identifier
var portfolio_id: String = "MAIN"

## As-of date for historical queries (null = current/latest)
var as_of_date: String = ""

## Execution mode: LIVE, PAPER, or BACKTEST
enum Mode { LIVE, PAPER, BACKTEST }
var mode: Mode = Mode.PAPER

## Current active workspace name
var active_workspace: String = "overview"

## Current active panel
var active_panel: String = "overview"

## Signal emitted when market context changes
signal market_changed(new_market_id: String)

## Signal emitted when strategy/portfolio context changes
signal portfolio_changed(new_portfolio_id: String)

## Signal emitted when mode changes
signal mode_changed(new_mode: Mode)

## Signal emitted when active panel changes
signal panel_changed(new_panel: String)

## Signal emitted when workspace changes
signal workspace_changed(new_workspace: String)


func _ready() -> void:
	print("AppState initialized")
	print("  Market: ", market_id)
	print("  Strategy: ", strategy_id)
	print("  Portfolio: ", portfolio_id)
	print("  Mode: ", Mode.keys()[mode])


## Set the current market and emit signal
func set_market(new_market_id: String) -> void:
	if market_id != new_market_id:
		market_id = new_market_id
		market_changed.emit(new_market_id)
		print("Market changed to: ", new_market_id)


## Set the current portfolio and emit signal
func set_portfolio(new_portfolio_id: String) -> void:
	if portfolio_id != new_portfolio_id:
		portfolio_id = new_portfolio_id
		portfolio_changed.emit(new_portfolio_id)
		print("Portfolio changed to: ", new_portfolio_id)


## Set the execution mode and emit signal
func set_mode(new_mode: Mode) -> void:
	if mode != new_mode:
		mode = new_mode
		mode_changed.emit(new_mode)
		print("Mode changed to: ", Mode.keys()[new_mode])


## Set the active panel
func set_active_panel(panel_id: String) -> void:
	if active_panel != panel_id:
		active_panel = panel_id
		panel_changed.emit(panel_id)
		print("Active panel: ", panel_id)


## Set the active workspace
func set_active_workspace(workspace_name: String) -> void:
	if active_workspace != workspace_name:
		active_workspace = workspace_name
		workspace_changed.emit(workspace_name)
		print("Active workspace: ", workspace_name)


## Get current context as a dictionary for API calls
func get_context() -> Dictionary:
	return {
		"market_id": market_id,
		"strategy_id": strategy_id,
		"portfolio_id": portfolio_id,
		"as_of_date": as_of_date if as_of_date != "" else null,
		"mode": Mode.keys()[mode]
	}
