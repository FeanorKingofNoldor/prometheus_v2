#pragma once

#include "base_panel.hpp"
#include <json.hpp>
#include <vector>
#include <string>

namespace prometheus::tui {

class PortfolioRiskPanel : public BasePanel {
public:
    PortfolioRiskPanel();
    ~PortfolioRiskPanel() override = default;
    
    void refresh(ApiClient& api_client) override;
    void render(WINDOW* window) override;
    bool handle_input(int ch) override;
    
private:
    struct RiskMetric {
        std::string name;
        double value;
        double limit;
        std::string status;
    };
    
    struct Position {
        std::string symbol;
        int quantity;
        double value;
        double pnl;
        double pnl_pct;
    };
    
    std::vector<RiskMetric> risk_metrics_;
    std::vector<Position> positions_;
    double total_portfolio_value_ = 0.0;
    double total_pnl_ = 0.0;
};

} // namespace prometheus::tui
