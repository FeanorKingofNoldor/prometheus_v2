#pragma once

#include "base_panel.hpp"
#include <json.hpp>
#include <vector>
#include <string>

namespace prometheus::tui {

class MetaExperimentsPanel : public BasePanel {
public:
    MetaExperimentsPanel();
    ~MetaExperimentsPanel() override = default;
    
    void refresh(ApiClient& api_client) override;
    void render(WINDOW* window) override;
    bool handle_input(int ch) override;
    
private:
    struct Experiment {
        std::string exp_id;
        std::string name;
        std::string status;  // RUNNING, COMPLETED, FAILED
        double performance_score;
        int iterations;
        std::string hyperparams;
    };
    
    std::vector<Experiment> experiments_;
    int scroll_offset_ = 0;
};

} // namespace prometheus::tui
