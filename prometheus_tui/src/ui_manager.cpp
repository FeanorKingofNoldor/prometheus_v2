#include "ui_manager.hpp"
#include "api_client.hpp"
#include "app_state.hpp"
#include "workspace_manager.hpp"
#include "utils/logger.hpp"
#include "utils/colors.hpp"
#include <ctime>
#include <format>

namespace prometheus::tui {

void LayoutDimensions::calculate(int tw, int th) {
    term_width = tw;
    term_height = th;
    
    // Make left sidebar same width as right sidebar for consistency
    if (term_width > 180) {
        left_width = 35;  // Match right sidebar width
        right_width = 35;
    }
    
    // Main panel area
    main_x = left_width;
    main_y = top_bar_height;
    main_width = term_width - left_width - right_width;
    main_height = term_height - top_bar_height - status_bar_height;
}

UIManager::UIManager() {
}

UIManager::~UIManager() {
    shutdown();
}

void UIManager::init() {
    if (initialized_) return;
    
    // Initialize ncurses
    initscr();
    cbreak();
    noecho();
    keypad(stdscr, TRUE);
    curs_set(0);
    // Note: timeout will be set in main loop
    
    // Initialize colors
    colors::init_color_pairs();
    
    // Calculate layout
    int h, w;
    getmaxyx(stdscr, h, w);
    layout_.calculate(w, h);
    
    // Create windows
    create_windows();
    
    initialized_ = true;
    LOG_INFO("UIManager", std::format("Initialized ({}x{})", w, h));
}

void UIManager::shutdown() {
    if (!initialized_) return;
    
    destroy_windows();
    endwin();
    
    initialized_ = false;
    LOG_INFO("UIManager", "Shut down");
}

void UIManager::create_windows() {
    destroy_windows();
    
    const auto& l = layout_;
    
    // Top bar
    top_bar_win_ = newwin(l.top_bar_height, l.term_width, 0, 0);
    
    // Left navigation
    left_nav_win_ = newwin(l.main_height, l.left_width, l.main_y, 0);
    
    // Main panel
    main_panel_win_ = newwin(l.main_height, l.main_width, l.main_y, l.main_x);
    
    // Right sidebar
    right_sidebar_win_ = newwin(l.main_height, l.right_width, 
                                l.main_y, l.main_x + l.main_width);
    
    // Status bar
    status_bar_win_ = newwin(l.status_bar_height, l.term_width, 
                             l.term_height - l.status_bar_height, 0);
    
    LOG_INFO("UIManager", "Windows created");
}

void UIManager::destroy_windows() {
    if (top_bar_win_) { delwin(top_bar_win_); top_bar_win_ = nullptr; }
    if (left_nav_win_) { delwin(left_nav_win_); left_nav_win_ = nullptr; }
    if (main_panel_win_) { delwin(main_panel_win_); main_panel_win_ = nullptr; }
    if (right_sidebar_win_) { delwin(right_sidebar_win_); right_sidebar_win_ = nullptr; }
    if (status_bar_win_) { delwin(status_bar_win_); status_bar_win_ = nullptr; }
}

void UIManager::update_layout() {
    int h, w;
    getmaxyx(stdscr, h, w);
    
    if (h != layout_.term_height || w != layout_.term_width) {
        layout_.calculate(w, h);
        create_windows();
        LOG_INFO("UIManager", std::format("Layout updated ({}x{})", w, h));
    }
}

void UIManager::render_all() {
    // Don't clear stdscr - let windows handle their own clearing
    
    // Render all windows
    render_left_nav();
    render_main_panel();
    render_right_sidebar();
    render_status_bar();
    
    // Refresh stdscr last to show everything
    doupdate();
}

void UIManager::render_top_bar(ApiClient& api_client) {
    if (!top_bar_win_) return;
    
    werase(top_bar_win_);
    
    auto& state = AppState::instance();
    
    // Background
    wattron(top_bar_win_, COLOR_PAIR(colors::HEADER));
    for (int i = 0; i < layout_.top_bar_height; i++) {
        mvwhline(top_bar_win_, i, 0, ' ', layout_.term_width);
    }
    
    // Title
    wattron(top_bar_win_, A_BOLD);
    mvwprintw(top_bar_win_, 0, 2, "PROMETHEUS C2");
    wattroff(top_bar_win_, A_BOLD);
    
    // Mode
    std::string mode = AppState::mode_to_string(state.mode());
    mvwprintw(top_bar_win_, 0, layout_.term_width - 30, "MODE: %s", mode.c_str());
    
    // Time
    time_t now = time(nullptr);
    char timebuf[64];
    strftime(timebuf, sizeof(timebuf), "%Y-%m-%d %H:%M:%S", localtime(&now));
    mvwprintw(top_bar_win_, 0, layout_.term_width - 22, "%s", timebuf);
    
    wattroff(top_bar_win_, COLOR_PAIR(colors::HEADER));
    
    // KPI bar (row 1)
    mvwprintw(top_bar_win_, 1, 2, "P&L: ---");
    mvwprintw(top_bar_win_, 1, 20, "STAB: ---");
    mvwprintw(top_bar_win_, 1, 35, "LEV: ---");
    
    // Separator
    wattron(top_bar_win_, COLOR_PAIR(colors::BORDER));
    mvwhline(top_bar_win_, 2, 0, ACS_HLINE, layout_.term_width);
    wattroff(top_bar_win_, COLOR_PAIR(colors::BORDER));
    
    wnoutrefresh(top_bar_win_);
}

void UIManager::render_left_nav() {
    if (!left_nav_win_) return;
    
    werase(left_nav_win_);
    
    wattron(left_nav_win_, COLOR_PAIR(colors::BORDER));
    box(left_nav_win_, 0, 0);
    wattroff(left_nav_win_, COLOR_PAIR(colors::BORDER));
    
    render_workspace_list();
    render_panel_list();
    
    wnoutrefresh(left_nav_win_);
}

void UIManager::render_workspace_list() {
    auto& ws_mgr = WorkspaceManager::instance();
    auto& state = AppState::instance();
    
    // Header
    wattron(left_nav_win_, COLOR_PAIR(colors::ACCENT_CYAN) | A_BOLD);
    mvwprintw(left_nav_win_, 1, 2, "Workspaces");
    wattroff(left_nav_win_, COLOR_PAIR(colors::ACCENT_CYAN) | A_BOLD);
    
    auto ids = ws_mgr.get_workspace_ids();
    int row = 2;
    for (const auto& id : ids) {
        auto* ws = ws_mgr.get_workspace(id);
        if (!ws) continue;
        
        bool active = (id == state.active_workspace());
        
        if (active) {
            wattron(left_nav_win_, COLOR_PAIR(colors::NAV_ACTIVE) | A_BOLD);
            mvwprintw(left_nav_win_, row, 2, "• %s", ws->display_name.c_str());
            wattroff(left_nav_win_, COLOR_PAIR(colors::NAV_ACTIVE) | A_BOLD);
        } else {
            mvwprintw(left_nav_win_, row, 2, "  %s", ws->display_name.c_str());
        }
        row++;
    }
}

void UIManager::render_panel_list() {
    auto& state = AppState::instance();
    auto& ws_mgr = WorkspaceManager::instance();
    
    // Get current workspace panels
    auto panel_ids = ws_mgr.get_panels(state.active_workspace());
    
    int start_row = 9;
    
    // Header
    wattron(left_nav_win_, COLOR_PAIR(colors::ACCENT_CYAN) | A_BOLD);
    mvwprintw(left_nav_win_, start_row, 2, "Panels");
    wattroff(left_nav_win_, COLOR_PAIR(colors::ACCENT_CYAN) | A_BOLD);
    
    int row = start_row + 1;
    for (const auto& id : panel_ids) {
        bool active = (id == state.active_panel());
        
        if (active) {
            wattron(left_nav_win_, COLOR_PAIR(colors::NAV_ACTIVE));
            mvwprintw(left_nav_win_, row, 2, "→ %s", id.c_str());
            wattroff(left_nav_win_, COLOR_PAIR(colors::NAV_ACTIVE));
        } else {
            mvwprintw(left_nav_win_, row, 2, "  %s", id.c_str());
        }
        row++;
        
        if (row >= layout_.main_height - 2) break;
    }
}

void UIManager::render_right_sidebar() {
    if (!right_sidebar_win_) return;
    
    werase(right_sidebar_win_);
    
    wattron(right_sidebar_win_, COLOR_PAIR(colors::BORDER));
    box(right_sidebar_win_, 0, 0);
    wattroff(right_sidebar_win_, COLOR_PAIR(colors::BORDER));
    
    render_alerts_section();
    render_console_section();
    
    wnoutrefresh(right_sidebar_win_);
}

void UIManager::render_alerts_section() {
    // Header
    wattron(right_sidebar_win_, COLOR_PAIR(colors::ACCENT_YELLOW) | A_BOLD);
    mvwprintw(right_sidebar_win_, 1, 2, "Alerts");
    wattroff(right_sidebar_win_, COLOR_PAIR(colors::ACCENT_YELLOW) | A_BOLD);
    
    // Content
    wattron(right_sidebar_win_, COLOR_PAIR(colors::STATUS_OK));
    mvwprintw(right_sidebar_win_, 3, 2, "✓ All systems OK");
    wattroff(right_sidebar_win_, COLOR_PAIR(colors::STATUS_OK));
}

void UIManager::render_console_section() {
    int console_start = 8;
    
    // Header
    wattron(right_sidebar_win_, COLOR_PAIR(colors::ACCENT_BLUE) | A_BOLD);
    mvwprintw(right_sidebar_win_, console_start, 2, "Live Console");
    wattroff(right_sidebar_win_, COLOR_PAIR(colors::ACCENT_BLUE) | A_BOLD);
    
    // Recent logs
    auto logs = Logger::instance().get_recent_logs(10);
    int row = console_start + 2;
    
    for (const auto& log : logs) {
        if (row >= layout_.main_height - 2) break;
        
        int color = colors::TEXT_PRIMARY;
        if (log.level == LogLevel::ERROR) {
            color = colors::ACCENT_RED;
        } else if (log.level == LogLevel::WARN) {
            color = colors::ACCENT_YELLOW;
        } else if (log.level == LogLevel::INFO) {
            color = colors::ACCENT_GREEN;
        }
        
        wattron(right_sidebar_win_, COLOR_PAIR(color));
        
        // Truncate message to fit
        std::string msg = log.message;
        int max_len = layout_.right_width - 4;
        if (msg.length() > (size_t)max_len) {
            msg = msg.substr(0, max_len - 3) + "...";
        }
        
        mvwprintw(right_sidebar_win_, row, 2, "%s", msg.c_str());
        wattroff(right_sidebar_win_, COLOR_PAIR(color));
        
        row++;
    }
}

void UIManager::render_status_bar() {
    if (!status_bar_win_) return;
    
    werase(status_bar_win_);
    
    wattron(status_bar_win_, COLOR_PAIR(colors::HEADER));
    mvwhline(status_bar_win_, 0, 0, ' ', layout_.term_width);
    
    // Hotkeys
    mvwprintw(status_bar_win_, 0, 2, 
              "[Tab] Next Panel | [W] Workspaces | [R] Refresh | [Q] Quit | [H] Help");
    
    wattroff(status_bar_win_, COLOR_PAIR(colors::HEADER));
    wnoutrefresh(status_bar_win_);
}

void UIManager::render_main_panel() {
    if (!main_panel_win_) return;
    
    if (active_panel_) {
        active_panel_->render(main_panel_win_);
        wnoutrefresh(main_panel_win_);
    } else {
        werase(main_panel_win_);
        wattron(main_panel_win_, COLOR_PAIR(colors::BORDER));
        box(main_panel_win_, 0, 0);
        wattroff(main_panel_win_, COLOR_PAIR(colors::BORDER));
        
        mvwprintw(main_panel_win_, 2, 2, "No active panel");
        wnoutrefresh(main_panel_win_);
    }
}

void UIManager::set_active_panel(std::unique_ptr<BasePanel> panel) {
    if (active_panel_) {
        active_panel_->on_deactivated();
    }
    
    active_panel_ = std::move(panel);
    
    if (active_panel_) {
        active_panel_->on_activated();
        AppState::instance().set_active_panel(active_panel_->panel_id());
    }
}

int UIManager::get_input() {
    return getch();
}

} // namespace prometheus::tui
