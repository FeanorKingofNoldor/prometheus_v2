#include "panels/base_panel.hpp"
#include "utils/logger.hpp"
#include "utils/colors.hpp"

namespace prometheus::tui {

BasePanel::BasePanel(const std::string& id, const std::string& display_name)
    : panel_id_(id), display_name_(display_name) {
}

void BasePanel::on_activated() {
    LOG_INFO("Panel", "Activated: " + panel_id_);
    mark_dirty();
}

void BasePanel::on_deactivated() {
    LOG_INFO("Panel", "Deactivated: " + panel_id_);
}

bool BasePanel::handle_input(int ch) {
    // Default input handling - scrolling
    switch (ch) {
        case KEY_UP:
            if (scroll_offset_ > 0) {
                scroll_offset_--;
                return true;
            }
            break;
        case KEY_DOWN:
            if (scroll_offset_ < max_scroll_) {
                scroll_offset_++;
                return true;
            }
            break;
        case KEY_PPAGE: // Page up
            scroll_offset_ = std::max(0, scroll_offset_ - 10);
            return true;
        case KEY_NPAGE: // Page down
            scroll_offset_ = std::min(max_scroll_, scroll_offset_ + 10);
            return true;
        case KEY_HOME:
            scroll_offset_ = 0;
            return true;
        case KEY_END:
            scroll_offset_ = max_scroll_;
            return true;
    }
    return false;
}

void BasePanel::draw_header(WINDOW* window, const std::string& title) {
    int width = getmaxx(window);
    
    wattron(window, COLOR_PAIR(colors::HEADER_ACTIVE));
    mvwhline(window, 0, 0, ' ', width);
    mvwprintw(window, 0, 2, " %s ", title.c_str());
    wattroff(window, COLOR_PAIR(colors::HEADER_ACTIVE));
}

void BasePanel::draw_border(WINDOW* window) {
    wattron(window, COLOR_PAIR(colors::BORDER));
    box(window, 0, 0);
    wattroff(window, COLOR_PAIR(colors::BORDER));
}

} // namespace prometheus::tui
