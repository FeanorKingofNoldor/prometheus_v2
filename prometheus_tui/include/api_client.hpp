#pragma once

#include "utils/http_client.hpp"
#include <memory>
#include <optional>

namespace prometheus::tui {

class ApiClient {
public:
    explicit ApiClient(const std::string& base_url = "http://localhost:8000");
    
    // ==================================================================
    // Monitoring/Status APIs
    // ==================================================================
    
    // Get global system overview
    std::optional<json> get_status_overview();
    
    // Get per-market pipeline status
    std::optional<json> get_status_pipeline(const std::string& market_id);
    
    // Get regime status for a region
    std::optional<json> get_status_regime(const std::string& region = "US", 
                                         const std::string& as_of_date = "");
    
    // Get stability status for a region
    std::optional<json> get_status_stability(const std::string& region = "US",
                                            const std::string& as_of_date = "");
    
    // Get fragility entities table
    std::optional<json> get_status_fragility(const std::string& region = "GLOBAL",
                                            const std::string& entity_type = "ANY");
    
    // Get fragility detail for specific entity
    std::optional<json> get_status_fragility_detail(const std::string& entity_id);
    
    // Get assessment output for a strategy
    std::optional<json> get_status_assessment(const std::string& strategy_id);
    
    // Get universe membership for a strategy
    std::optional<json> get_status_universe(const std::string& strategy_id);
    
    // Get portfolio positions and P&L
    std::optional<json> get_status_portfolio(const std::string& portfolio_id);
    
    // Get portfolio risk metrics
    std::optional<json> get_status_portfolio_risk(const std::string& portfolio_id);
    
    // Get recent execution activity
    std::optional<json> get_status_execution(const std::string& portfolio_id,
                                            const std::string& mode = "",
                                            int limit_orders = 50,
                                            int limit_fills = 50);
    
    // Get recent risk actions
    std::optional<json> get_status_risk_actions(const std::string& strategy_id,
                                               int limit = 50);
    
    // ==================================================================
    // Visualization APIs
    // ==================================================================
    
    // Get list of available ANT_HILL scenes
    std::optional<json> get_scenes();
    
    // Get scene graph for a specific view
    std::optional<json> get_scene(const std::string& view_id);
    
    // Get list of execution traces
    std::optional<json> get_traces(const std::string& market_id = "",
                                  const std::string& mode = "");
    
    // Get execution trace events
    std::optional<json> get_trace(const std::string& trace_id);
    
    // Get embedding space vectors
    std::optional<json> get_embedding_space(const std::string& space_id);
    
    // ==================================================================
    // Control APIs
    // ==================================================================
    
    // Submit backtest job
    std::optional<json> run_backtest(const json& params);
    
    // Submit synthetic dataset creation job
    std::optional<json> create_synthetic_dataset(const json& params);
    
    // Schedule DAG execution
    std::optional<json> schedule_dag(const json& params);
    
    // Apply configuration change
    std::optional<json> apply_config_change(const json& params);
    
    // Get job status
    std::optional<json> get_job_status(const std::string& job_id);
    
    // ==================================================================
    // Kronos Chat API
    // ==================================================================
    
    // Chat with Kronos meta-orchestrator
    std::optional<json> kronos_chat(const std::string& question,
                                   const json& context = json::object());
    
    // ==================================================================
    // Geo APIs
    // ==================================================================
    
    // Get country-level status for world map
    std::optional<json> get_countries();
    
    // Get detailed country information
    std::optional<json> get_country_detail(const std::string& country_code);
    
    // ==================================================================
    // Meta APIs
    // ==================================================================
    
    // Get engine configurations
    std::optional<json> get_configs();
    
    // Get performance metrics
    std::optional<json> get_performance_metrics();
    
    // Test connection
    bool test_connection();
    
private:
    std::unique_ptr<HttpClient> http_client_;
    
    // Helper to handle response and log errors
    std::optional<json> handle_response(const HttpResponse& response, 
                                       const std::string& endpoint);
};

} // namespace prometheus::tui
