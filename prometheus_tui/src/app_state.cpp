#include "app_state.hpp"
#include "utils/logger.hpp"

namespace prometheus::tui {

AppState::AppState() {
    LOG_INFO("AppState", "Initialized");
}

AppState& AppState::instance() {
    static AppState instance;
    return instance;
}

std::string AppState::market_id() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return market_id_;
}

std::string AppState::strategy_id() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return strategy_id_;
}

std::string AppState::portfolio_id() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return portfolio_id_;
}

Mode AppState::mode() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return mode_;
}

std::string AppState::as_of_date() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return as_of_date_;
}

std::string AppState::active_workspace() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return active_workspace_;
}

std::string AppState::active_panel() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return active_panel_;
}

void AppState::set_market_id(const std::string& id) {
    std::lock_guard<std::mutex> lock(mutex_);
    market_id_ = id;
    LOG_INFO("AppState", "Market ID changed to: " + id);
}

void AppState::set_strategy_id(const std::string& id) {
    std::lock_guard<std::mutex> lock(mutex_);
    strategy_id_ = id;
    LOG_INFO("AppState", "Strategy ID changed to: " + id);
}

void AppState::set_portfolio_id(const std::string& id) {
    std::lock_guard<std::mutex> lock(mutex_);
    portfolio_id_ = id;
    LOG_INFO("AppState", "Portfolio ID changed to: " + id);
}

void AppState::set_mode(Mode mode) {
    std::lock_guard<std::mutex> lock(mutex_);
    mode_ = mode;
    LOG_INFO("AppState", "Mode changed to: " + mode_to_string(mode));
}

void AppState::set_as_of_date(const std::string& date) {
    std::lock_guard<std::mutex> lock(mutex_);
    as_of_date_ = date;
    LOG_INFO("AppState", "As-of date changed to: " + (date.empty() ? "latest" : date));
}

void AppState::set_active_workspace(const std::string& workspace) {
    std::lock_guard<std::mutex> lock(mutex_);
    active_workspace_ = workspace;
}

void AppState::set_active_panel(const std::string& panel) {
    std::lock_guard<std::mutex> lock(mutex_);
    active_panel_ = panel;
}

AppState::Context AppState::get_context() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return Context{
        .market_id = market_id_,
        .strategy_id = strategy_id_,
        .portfolio_id = portfolio_id_,
        .mode = mode_,
        .as_of_date = as_of_date_
    };
}

std::string AppState::mode_to_string(Mode mode) {
    switch (mode) {
        case Mode::LIVE: return "LIVE";
        case Mode::PAPER: return "PAPER";
        case Mode::BACKTEST: return "BACKTEST";
    }
    return "UNKNOWN";
}

Mode AppState::string_to_mode(const std::string& str) {
    if (str == "LIVE") return Mode::LIVE;
    if (str == "PAPER") return Mode::PAPER;
    if (str == "BACKTEST") return Mode::BACKTEST;
    return Mode::PAPER;  // Default
}

} // namespace prometheus::tui
