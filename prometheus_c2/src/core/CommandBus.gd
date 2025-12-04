extends Node
## High-level command bus for control operations.
##
## Wraps ApiClient control endpoints and manages job tracking.
## All mutating operations go through this bus for consistent logging and state management.

## Signal emitted when a job is submitted
signal job_submitted(job_id: String, job_type: String)

## Signal emitted when a job status changes
signal job_status_changed(job_id: String, status: String)

## Cache of active jobs
var active_jobs: Dictionary = {}


func _ready() -> void:
	print("CommandBus initialized")


## Submit a backtest job
func run_backtest(
	strategy_id: String,
	start_date: String,
	end_date: String,
	market_ids: Array = [],
	config_overrides: Dictionary = {}
) -> Dictionary:
	var params := {
		"strategy_id": strategy_id,
		"start_date": start_date,
		"end_date": end_date,
		"market_ids": market_ids,
		"config_overrides": config_overrides
	}
	
	var result := await ApiClient.run_backtest(params)
	
	if result.has("job_id"):
		var job_id: String = result["job_id"]
		active_jobs[job_id] = {
			"type": "BACKTEST",
			"status": "PENDING",
			"params": params
		}
		job_submitted.emit(job_id, "BACKTEST")
		print("Backtest job submitted: ", job_id)
	
	return result


## Create synthetic dataset
func create_synthetic_dataset(
	dataset_name: String,
	scenario_type: String,
	num_samples: int = 1000,
	parameters: Dictionary = {}
) -> Dictionary:
	var params := {
		"dataset_name": dataset_name,
		"scenario_type": scenario_type,
		"num_samples": num_samples,
		"parameters": parameters
	}
	
	var result := await ApiClient.create_synthetic_dataset(params)
	
	if result.has("job_id"):
		var job_id: String = result["job_id"]
		active_jobs[job_id] = {
			"type": "SYNTHETIC_DATASET",
			"status": "PENDING",
			"params": params
		}
		job_submitted.emit(job_id, "SYNTHETIC_DATASET")
		print("Synthetic dataset job submitted: ", job_id)
	
	return result


## Schedule DAG execution for a market
func schedule_dag(
	market_id: String,
	dag_name: String,
	force: bool = false,
	parameters: Dictionary = {}
) -> Dictionary:
	var params := {
		"market_id": market_id,
		"dag_name": dag_name,
		"force": force,
		"parameters": parameters
	}
	
	var result := await ApiClient.schedule_dag(params)
	
	if result.has("job_id"):
		var job_id: String = result["job_id"]
		active_jobs[job_id] = {
			"type": "DAG_EXECUTION",
			"status": "PENDING",
			"params": params
		}
		job_submitted.emit(job_id, "DAG_EXECUTION")
		print("DAG job submitted: ", job_id)
	
	return result


## Apply configuration change
func apply_config_change(
	engine_name: String,
	config_key: String,
	config_value,
	reason: String,
	requires_approval: bool = true
) -> Dictionary:
	var params := {
		"engine_name": engine_name,
		"config_key": config_key,
		"config_value": config_value,
		"reason": reason,
		"requires_approval": requires_approval
	}
	
	var result := await ApiClient.apply_config_change(params)
	
	if result.has("job_id"):
		var job_id: String = result["job_id"]
		active_jobs[job_id] = {
			"type": "CONFIG_CHANGE",
			"status": "STAGED" if requires_approval else "PENDING",
			"params": params
		}
		job_submitted.emit(job_id, "CONFIG_CHANGE")
		print("Config change job submitted: ", job_id)
	
	return result


## Watch job status (polling)
func watch_job(job_id: String) -> Dictionary:
	var status := await ApiClient.get_job_status(job_id)
	
	if status.has("status") and active_jobs.has(job_id):
		var old_status: String = active_jobs[job_id]["status"]
		var new_status: String = status["status"]
		
		if old_status != new_status:
			active_jobs[job_id]["status"] = new_status
			job_status_changed.emit(job_id, new_status)
			print("Job %s status changed: %s -> %s" % [job_id, old_status, new_status])
	
	return status


## Get all active jobs
func get_active_jobs() -> Array:
	var jobs: Array = []
	for job_id in active_jobs.keys():
		jobs.append({
			"job_id": job_id,
			"type": active_jobs[job_id]["type"],
			"status": active_jobs[job_id]["status"]
		})
	return jobs


## Clear completed jobs from cache
func clear_completed_jobs() -> void:
	var to_remove: Array = []
	for job_id in active_jobs.keys():
		var status: String = active_jobs[job_id]["status"]
		if status in ["COMPLETED", "FAILED", "CANCELLED"]:
			to_remove.append(job_id)
	
	for job_id in to_remove:
		active_jobs.erase(job_id)
	
	if to_remove.size() > 0:
		print("Cleared %d completed jobs" % to_remove.size())
