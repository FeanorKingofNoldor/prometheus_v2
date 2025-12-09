#include "api_client.hpp"
#include "utils/logger.hpp"
#include <format>

namespace prometheus::tui {

ApiClient::ApiClient(const std::string& base_url) 
    : http_client_(std::make_unique<HttpClient>(base_url)) {
    LOG_INFO("ApiClient", "Initialized with base URL: " + base_url);
}

// ==================================================================
// Monitoring/Status APIs
// ==================================================================

std::optional<json> ApiClient::get_status_overview() {
    auto response = http_client_->get("/api/status/overview");
    return handle_response(response, "get_status_overview");
}

std::optional<json> ApiClient::get_status_pipeline(const std::string& market_id) {
    auto response = http_client_->get("/api/status/pipeline?market_id=" + market_id);
    return handle_response(response, "get_status_pipeline");
}

std::optional<json> ApiClient::get_status_regime(const std::string& region,
                                                 const std::string& as_of_date) {
    std::string url = "/api/status/regime?region=" + region;
    if (!as_of_date.empty()) {
        url += "&as_of_date=" + as_of_date;
    }
    auto response = http_client_->get(url);
    return handle_response(response, "get_status_regime");
}

std::optional<json> ApiClient::get_status_stability(const std::string& region,
                                                   const std::string& as_of_date) {
    std::string url = "/api/status/stability?region=" + region;
    if (!as_of_date.empty()) {
        url += "&as_of_date=" + as_of_date;
    }
    auto response = http_client_->get(url);
    return handle_response(response, "get_status_stability");
}

std::optional<json> ApiClient::get_status_fragility(const std::string& region,
                                                   const std::string& entity_type) {
    std::string url = std::format("/api/status/fragility?region={}&entity_type={}", 
                                  region, entity_type);
    auto response = http_client_->get(url);
    return handle_response(response, "get_status_fragility");
}

std::optional<json> ApiClient::get_status_fragility_detail(const std::string& entity_id) {
    auto response = http_client_->get("/api/status/fragility/" + entity_id);
    return handle_response(response, "get_status_fragility_detail");
}

std::optional<json> ApiClient::get_status_assessment(const std::string& strategy_id) {
    auto response = http_client_->get("/api/status/assessment?strategy_id=" + strategy_id);
    return handle_response(response, "get_status_assessment");
}

std::optional<json> ApiClient::get_status_universe(const std::string& strategy_id) {
    auto response = http_client_->get("/api/status/universe?strategy_id=" + strategy_id);
    return handle_response(response, "get_status_universe");
}

std::optional<json> ApiClient::get_status_portfolio(const std::string& portfolio_id) {
    auto response = http_client_->get("/api/status/portfolio?portfolio_id=" + portfolio_id);
    return handle_response(response, "get_status_portfolio");
}

std::optional<json> ApiClient::get_status_portfolio_risk(const std::string& portfolio_id) {
    auto response = http_client_->get("/api/status/portfolio_risk?portfolio_id=" + portfolio_id);
    return handle_response(response, "get_status_portfolio_risk");
}

std::optional<json> ApiClient::get_status_execution(const std::string& portfolio_id,
                                                   const std::string& mode,
                                                   int limit_orders,
                                                   int limit_fills) {
    std::string url = std::format("/api/status/execution?portfolio_id={}&limit_orders={}&limit_fills={}",
                                  portfolio_id, limit_orders, limit_fills);
    if (!mode.empty()) {
        url += "&mode=" + mode;
    }
    auto response = http_client_->get(url);
    return handle_response(response, "get_status_execution");
}

std::optional<json> ApiClient::get_status_risk_actions(const std::string& strategy_id,
                                                      int limit) {
    std::string url = std::format("/api/status/risk_actions?strategy_id={}&limit={}",
                                  strategy_id, limit);
    auto response = http_client_->get(url);
    return handle_response(response, "get_status_risk_actions");
}

// ==================================================================
// Visualization APIs
// ==================================================================

std::optional<json> ApiClient::get_scenes() {
    auto response = http_client_->get("/api/scenes");
    return handle_response(response, "get_scenes");
}

std::optional<json> ApiClient::get_scene(const std::string& view_id) {
    auto response = http_client_->get("/api/scene/" + view_id);
    return handle_response(response, "get_scene");
}

std::optional<json> ApiClient::get_traces(const std::string& market_id,
                                         const std::string& mode) {
    std::string url = "/api/traces?";
    if (!market_id.empty()) {
        url += "market_id=" + market_id;
    }
    if (!mode.empty()) {
        if (!market_id.empty()) url += "&";
        url += "mode=" + mode;
    }
    auto response = http_client_->get(url);
    return handle_response(response, "get_traces");
}

std::optional<json> ApiClient::get_trace(const std::string& trace_id) {
    auto response = http_client_->get("/api/traces/" + trace_id);
    return handle_response(response, "get_trace");
}

std::optional<json> ApiClient::get_embedding_space(const std::string& space_id) {
    auto response = http_client_->get("/api/embedding_space/" + space_id);
    return handle_response(response, "get_embedding_space");
}

// ==================================================================
// Control APIs
// ==================================================================

std::optional<json> ApiClient::run_backtest(const json& params) {
    auto response = http_client_->post_json("/api/control/run_backtest", params);
    return handle_response(response, "run_backtest");
}

std::optional<json> ApiClient::create_synthetic_dataset(const json& params) {
    auto response = http_client_->post_json("/api/control/create_synthetic_dataset", params);
    return handle_response(response, "create_synthetic_dataset");
}

std::optional<json> ApiClient::schedule_dag(const json& params) {
    auto response = http_client_->post_json("/api/control/schedule_dag", params);
    return handle_response(response, "schedule_dag");
}

std::optional<json> ApiClient::apply_config_change(const json& params) {
    auto response = http_client_->post_json("/api/control/apply_config_change", params);
    return handle_response(response, "apply_config_change");
}

std::optional<json> ApiClient::get_job_status(const std::string& job_id) {
    auto response = http_client_->get("/api/control/jobs/" + job_id);
    return handle_response(response, "get_job_status");
}

// ==================================================================
// Kronos Chat API
// ==================================================================

std::optional<json> ApiClient::kronos_chat(const std::string& question,
                                          const json& context) {
    json payload = {
        {"question", question},
        {"context", context}
    };
    auto response = http_client_->post_json("/api/kronos/chat", payload);
    return handle_response(response, "kronos_chat");
}

// ==================================================================
// Geo APIs
// ==================================================================

std::optional<json> ApiClient::get_countries() {
    auto response = http_client_->get("/api/geo/countries");
    return handle_response(response, "get_countries");
}

std::optional<json> ApiClient::get_country_detail(const std::string& country_code) {
    auto response = http_client_->get("/api/geo/country/" + country_code);
    return handle_response(response, "get_country_detail");
}

// ==================================================================
// Meta APIs
// ==================================================================

std::optional<json> ApiClient::get_configs() {
    auto response = http_client_->get("/api/meta/configs");
    return handle_response(response, "get_configs");
}

std::optional<json> ApiClient::get_performance_metrics() {
    auto response = http_client_->get("/api/meta/performance");
    return handle_response(response, "get_performance_metrics");
}

// ==================================================================
// Helper methods
// ==================================================================

bool ApiClient::test_connection() {
    try {
        auto response = http_client_->get("/health");
        return response.success;
    } catch (...) {
        return false;
    }
}

std::optional<json> ApiClient::handle_response(const HttpResponse& response,
                                              const std::string& endpoint) {
    if (!response.success) {
        LOG_ERROR("ApiClient", std::format("{}: {} - {}", 
                  endpoint, response.status_code, response.error_message));
        return std::nullopt;
    }
    
    auto json_response = response.as_json();
    if (!json_response) {
        LOG_ERROR("ApiClient", endpoint + ": Failed to parse JSON response");
        return std::nullopt;
    }
    
    return json_response;
}

} // namespace prometheus::tui
