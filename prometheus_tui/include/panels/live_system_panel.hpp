#pragma once

#include "base_panel.hpp"
#include <json.hpp>
#include <vector>
#include <string>

namespace prometheus::tui {

class LiveSystemPanel : public BasePanel {
public:
    LiveSystemPanel();
    ~LiveSystemPanel() override = default;
    
    void refresh(ApiClient& api_client) override;
    void render(WINDOW* window) override;
    bool handle_input(int ch) override;
    
private:
    struct SystemMetric {
        std::string name;
        double value;
        std::string unit;
        std::string status;  // OK, WARNING, ERROR
    };
    
    struct LogEntry {
        std::string timestamp;
        std::string level;
        std::string component;
        std::string message;
    };
    
    std::vector<SystemMetric> metrics_;
    std::vector<LogEntry> recent_logs_;
    std::string system_status_;
    int scroll_offset_ = 0;
    
    void parse_system_data(const nlohmann::json& data);
};

} // namespace prometheus::tui
