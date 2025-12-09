#pragma once

#include "ui_manager.hpp"
#include "api_client.hpp"
#include "panels/base_panel.hpp"
#include <memory>
#include <map>
#include <string>

namespace prometheus::tui {

class Application {
public:
    Application();
    ~Application();
    
    // Initialize and run
    void init();
    void run();
    void shutdown();
    
    // Panel management
    void switch_to_panel(const std::string& panel_id);
    void cycle_next_panel();
    void cycle_prev_panel();
    
    // Workspace management
    void switch_workspace(const std::string& workspace_id);
    void cycle_next_workspace();
    
private:
    std::unique_ptr<UIManager> ui_manager_;
    std::unique_ptr<ApiClient> api_client_;
    
    bool running_ = false;
    bool backend_available_ = false;
    
    // Current workspace and panel list
    std::vector<std::string> current_panel_list_;
    size_t current_panel_index_ = 0;
    
    // Panel factory
    std::unique_ptr<BasePanel> create_panel(const std::string& panel_id);
    
    // Event handlers
    bool handle_input(int ch);
    void handle_auto_refresh();
    
    // Main loop timing
    std::chrono::steady_clock::time_point last_refresh_;
};

} // namespace prometheus::tui
