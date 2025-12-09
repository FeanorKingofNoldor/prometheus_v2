#pragma once

#include "panels/base_panel.hpp"
#include <json.hpp>
#include <optional>

namespace prometheus::tui {

using json = nlohmann::json;

class OverviewPanel : public BasePanel {
public:
    OverviewPanel();
    
    void refresh(ApiClient& api_client) override;
    void render(WINDOW* window) override;
    
private:
    std::optional<json> overview_data_;
    std::optional<json> regime_data_;
    std::optional<json> stability_data_;
    std::string error_message_;
    
    void render_kpis(WINDOW* window, int start_row);
    void render_regimes(WINDOW* window, int start_row);
    void render_alerts(WINDOW* window, int start_row);
};

} // namespace prometheus::tui
