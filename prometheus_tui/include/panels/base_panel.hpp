#pragma once

#include <string>
#include <ncurses.h>

namespace prometheus::tui {

class ApiClient;

class BasePanel {
public:
    explicit BasePanel(const std::string& id, const std::string& display_name);
    virtual ~BasePanel() = default;
    
    // Getters
    std::string panel_id() const { return panel_id_; }
    std::string display_name() const { return display_name_; }
    
    // Lifecycle methods
    virtual void on_activated();
    virtual void on_deactivated();
    
    // Core methods (to be implemented by subclasses)
    virtual void refresh(ApiClient& api_client) = 0;
    virtual void render(WINDOW* window) = 0;
    virtual bool handle_input(int ch);
    
    // Helper to check if panel needs refresh
    bool needs_refresh() const { return needs_refresh_; }
    void mark_dirty() { needs_refresh_ = true; }
    void mark_clean() { needs_refresh_ = false; }
    
protected:
    std::string panel_id_;
    std::string display_name_;
    bool needs_refresh_ = true;
    
    // Scroll support
    int scroll_offset_ = 0;
    int max_scroll_ = 0;
    
    // Helper methods for subclasses
    void draw_header(WINDOW* window, const std::string& title);
    void draw_border(WINDOW* window);
};

} // namespace prometheus::tui
