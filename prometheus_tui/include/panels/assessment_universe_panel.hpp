#pragma once

#include "base_panel.hpp"
#include <json.hpp>
#include <vector>
#include <string>

namespace prometheus::tui {

class AssessmentUniversePanel : public BasePanel {
public:
    AssessmentUniversePanel();
    ~AssessmentUniversePanel() override = default;
    
    void refresh(ApiClient& api_client) override;
    void render(WINDOW* window) override;
    bool handle_input(int ch) override;
    
private:
    struct UniverseMember {
        std::string symbol;
        std::string name;
        double assessment_score;
        std::string universe_status;  // IN, OUT, PENDING
        double quality_score;
        double liquidity_score;
        int days_in_universe;
    };
    
    std::vector<UniverseMember> members_;
    std::string strategy_id_ = "MAIN";
    int scroll_offset_ = 0;
    int total_count_ = 0;
    int active_count_ = 0;
};

} // namespace prometheus::tui
