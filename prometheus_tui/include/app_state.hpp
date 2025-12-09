#pragma once

#include <string>
#include <mutex>
#include <functional>
#include <vector>

namespace prometheus::tui {

enum class Mode {
    LIVE,
    PAPER,
    BACKTEST
};

class AppState {
public:
    static AppState& instance();
    
    // Current context
    std::string market_id() const;
    std::string strategy_id() const;
    std::string portfolio_id() const;
    Mode mode() const;
    std::string as_of_date() const;
    
    // Active UI state
    std::string active_workspace() const;
    std::string active_panel() const;
    
    // Setters
    void set_market_id(const std::string& id);
    void set_strategy_id(const std::string& id);
    void set_portfolio_id(const std::string& id);
    void set_mode(Mode mode);
    void set_as_of_date(const std::string& date);
    void set_active_workspace(const std::string& workspace);
    void set_active_panel(const std::string& panel);
    
    // Get full context for API calls
    struct Context {
        std::string market_id;
        std::string strategy_id;
        std::string portfolio_id;
        Mode mode;
        std::string as_of_date;
    };
    
    Context get_context() const;
    
    // Helper to convert mode to string
    static std::string mode_to_string(Mode mode);
    static Mode string_to_mode(const std::string& str);
    
private:
    AppState();
    ~AppState() = default;
    AppState(const AppState&) = delete;
    AppState& operator=(const AppState&) = delete;
    
    mutable std::mutex mutex_;
    
    // Context
    std::string market_id_ = "US_EQ";
    std::string strategy_id_ = "MAIN";
    std::string portfolio_id_ = "MAIN";
    Mode mode_ = Mode::PAPER;
    std::string as_of_date_ = "";  // Empty means "latest"
    
    // UI state
    std::string active_workspace_ = "overview";
    std::string active_panel_ = "overview";
};

} // namespace prometheus::tui
