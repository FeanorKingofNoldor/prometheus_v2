#pragma once

#include "base_panel.hpp"
#include <json.hpp>
#include <vector>
#include <string>

namespace prometheus::tui {

class RegimeStabPanel : public BasePanel {
public:
    RegimeStabPanel();
    ~RegimeStabPanel() override = default;
    
    void refresh(ApiClient& api_client) override;
    void render(WINDOW* window) override;
    bool handle_input(int ch) override;
    
private:
    struct RegimeData {
        std::string regime_name;
        double stability;
        double fragility;
        std::string status;
        int days_in_regime;
    };
    
    struct RegimeTransition {
        std::string from_regime;
        std::string to_regime;
        double probability;
    };
    
    std::vector<RegimeData> regimes_;
    std::vector<RegimeTransition> transitions_;
    std::string current_regime_;
    double overall_fragility_ = 0.0;
    
    void parse_regime_data(const nlohmann::json& data);
};

} // namespace prometheus::tui
