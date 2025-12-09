#pragma once

#include "panels/base_panel.hpp"
#include <ncurses.h>
#include <memory>
#include <map>
#include <string>

namespace prometheus::tui {

class ApiClient;

struct LayoutDimensions {
    // Terminal size
    int term_width;
    int term_height;
    
    // Top bar (KPI dashboard)
    int top_bar_height = 3;
    
    // Left sidebar (navigation)
    int left_width = 20;
    
    // Right sidebar (alerts + console)
    int right_width = 30;
    
    // Status bar at bottom
    int status_bar_height = 1;
    
    // Calculated main panel dimensions
    int main_x;
    int main_y;
    int main_width;
    int main_height;
    
    void calculate(int tw, int th);
};

class UIManager {
public:
    UIManager();
    ~UIManager();
    
    // Initialization
    void init();
    void shutdown();
    
    // Layout management
    void update_layout();
    void render_all();
    
    // Component rendering
    void render_top_bar(ApiClient& api_client);
    void render_left_nav();
    void render_right_sidebar();
    void render_status_bar();
    void render_main_panel();
    
    // Panel management
    void set_active_panel(std::unique_ptr<BasePanel> panel);
    BasePanel* get_active_panel() { return active_panel_.get(); }
    
    // Input routing
    int get_input();
    
    // Terminal info
    const LayoutDimensions& layout() const { return layout_; }
    
private:
    // Windows
    WINDOW* top_bar_win_ = nullptr;
    WINDOW* left_nav_win_ = nullptr;
    WINDOW* main_panel_win_ = nullptr;
    WINDOW* right_sidebar_win_ = nullptr;
    WINDOW* status_bar_win_ = nullptr;
    
    // Layout
    LayoutDimensions layout_;
    
    // Active panel
    std::unique_ptr<BasePanel> active_panel_;
    
    // State
    bool initialized_ = false;
    
    // Helper methods
    void create_windows();
    void destroy_windows();
    void render_workspace_list();
    void render_panel_list();
    void render_alerts_section();
    void render_console_section();
};

} // namespace prometheus::tui
