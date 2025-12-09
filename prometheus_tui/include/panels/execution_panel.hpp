#pragma once

#include "base_panel.hpp"
#include <json.hpp>
#include <vector>
#include <string>

namespace prometheus::tui {

class ExecutionPanel : public BasePanel {
public:
    ExecutionPanel();
    ~ExecutionPanel() override = default;
    
    void refresh(ApiClient& api_client) override;
    void render(WINDOW* window) override;
    bool handle_input(int ch) override;
    
private:
    struct Order {
        std::string timestamp;
        std::string symbol;
        std::string side;
        int quantity;
        double price;
        std::string status;
    };
    
    std::vector<Order> recent_orders_;
    int scroll_offset_ = 0;
};

} // namespace prometheus::tui
