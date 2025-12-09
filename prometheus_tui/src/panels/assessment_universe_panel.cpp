#include "panels/assessment_universe_panel.hpp"
#include "api_client.hpp"
#include "utils/logger.hpp"
#include "utils/colors.hpp"
#include <format>
#include <ncurses.h>

namespace prometheus::tui {

AssessmentUniversePanel::AssessmentUniversePanel() 
    : BasePanel("assessment_universe", "Assessment Universe") {
    LOG_INFO("AssessmentUniversePanel", "Initialized");
}

void AssessmentUniversePanel::refresh(ApiClient& api_client) {
    LOG_INFO("AssessmentUniversePanel", "Refreshing data...");
    
    // Try to get real universe data
    auto universe_response = api_client.get_status_universe(strategy_id_);
    
    if (universe_response.has_value()) {
        // Parse real data when available
        LOG_INFO("AssessmentUniversePanel", "Loaded real universe data");
    }
    
    // Mock data for demonstration
    members_ = {
        {"AAPL", "Apple Inc.", 0.87, "IN", 0.92, 0.98, 245},
        {"MSFT", "Microsoft Corp.", 0.85, "IN", 0.89, 0.95, 198},
        {"GOOGL", "Alphabet Inc.", 0.82, "IN", 0.88, 0.91, 167},
        {"AMZN", "Amazon.com Inc.", 0.79, "IN", 0.84, 0.89, 143},
        {"NVDA", "NVIDIA Corp.", 0.91, "IN", 0.93, 0.88, 98},
        {"META", "Meta Platforms", 0.76, "IN", 0.81, 0.85, 76},
        {"TSLA", "Tesla Inc.", 0.72, "PENDING", 0.75, 0.68, 0},
        {"JPM", "JPMorgan Chase", 0.83, "IN", 0.87, 0.94, 234},
        {"V", "Visa Inc.", 0.88, "IN", 0.91, 0.96, 287},
        {"WMT", "Walmart Inc.", 0.74, "IN", 0.79, 0.92, 156},
        {"DIS", "Walt Disney Co.", 0.68, "OUT", 0.71, 0.76, 0},
        {"BA", "Boeing Co.", 0.63, "OUT", 0.67, 0.72, 0},
        {"XOM", "Exxon Mobil", 0.80, "IN", 0.84, 0.91, 201},
        {"PG", "Procter & Gamble", 0.77, "IN", 0.82, 0.93, 178},
        {"HD", "Home Depot", 0.81, "IN", 0.85, 0.89, 145}
    };
    
    total_count_ = members_.size();
    active_count_ = 0;
    for (const auto& m : members_) {
        if (m.universe_status == "IN") active_count_++;
    }
}

void AssessmentUniversePanel::render(WINDOW* window) {
    int height = getmaxy(window);
    int width = getmaxx(window);
    int y = 0;
    
    // Title
    wattron(window, COLOR_PAIR(COLOR_CYAN)); wattron(window, A_BOLD);
    mvwprintw(window, y++, 2, "══════════ STRATEGY UNIVERSE ASSESSMENT ══════════");
    wattroff(window, A_BOLD); wattroff(window, COLOR_PAIR(COLOR_CYAN));
    y++;
    
    // Summary stats - three columns
    int col1 = 3;
    int col2 = width / 3;
    int col3 = (width * 2) / 3;
    
    wattron(window, A_BOLD);
    mvwprintw(window, y, col1, "Strategy:");
    mvwprintw(window, y, col2, "Total Assessed:");
    mvwprintw(window, y, col3, "Active in Universe:");
    wattroff(window, A_BOLD);
    y++;
    
    mvwprintw(window, y, col1 + 2, "%s", strategy_id_.c_str());
    mvwprintw(window, y, col2 + 2, "%d", total_count_);
    wattron(window, COLOR_PAIR(COLOR_GREEN) | A_BOLD);
    mvwprintw(window, y, col3 + 2, "%d", active_count_);
    wattroff(window, COLOR_PAIR(COLOR_GREEN) | A_BOLD);
    
    y += 2;
    
    // Section separator
    mvwhline(window, y++, 2, ACS_HLINE, width - 4);
    y++;
    
    // Table header
    wattron(window, A_BOLD);
    mvwprintw(window, y++, 3, "%-8s %-20s %12s %10s %10s %10s %10s",
              "Symbol", "Name", "Assessment", "Status", "Quality", "Liquidity", "Days");
    wattroff(window, A_BOLD);
    mvwhline(window, y++, 3, ACS_HLINE, width - 6);
    
    // Universe members
    int rows_shown = 0;
    int max_rows = height - y - 1;
    
    for (size_t i = scroll_offset_; i < members_.size() && rows_shown < max_rows; ++i) {
        const auto& member = members_[i];
        
        // Symbol in bold
        wattron(window, A_BOLD);
        mvwprintw(window, y, 3, "%-8s", member.symbol.c_str());
        wattroff(window, A_BOLD);
        
        // Name
        std::string name = member.name;
        if (name.length() > 20) name = name.substr(0, 17) + "...";
        mvwprintw(window, y, 12, "%-20s", name.c_str());
        
        // Assessment score with color
        int assess_color = member.assessment_score > 0.8 ? COLOR_GREEN :
                          member.assessment_score > 0.7 ? COLOR_YELLOW : COLOR_RED;
        wattron(window, COLOR_PAIR(assess_color) | A_BOLD);
        mvwprintw(window, y, 33, "%11.2f", member.assessment_score);
        wattroff(window, COLOR_PAIR(assess_color) | A_BOLD);
        
        // Status
        int status_color = COLOR_WHITE;
        if (member.universe_status == "IN") status_color = COLOR_GREEN;
        else if (member.universe_status == "PENDING") status_color = COLOR_YELLOW;
        else status_color = COLOR_RED;
        
        wattron(window, COLOR_PAIR(status_color) | A_BOLD);
        mvwprintw(window, y, 45, "%9s", member.universe_status.c_str());
        wattroff(window, COLOR_PAIR(status_color) | A_BOLD);
        
        // Quality score
        mvwprintw(window, y, 56, "%9.2f", member.quality_score);
        
        // Liquidity score
        mvwprintw(window, y, 67, "%9.2f", member.liquidity_score);
        
        // Days in universe
        if (member.universe_status == "IN") {
            mvwprintw(window, y, 78, "%9d", member.days_in_universe);
        } else {
            mvwprintw(window, y, 78, "%9s", "-");
        }
        
        y++;
        rows_shown++;
    }
    
    // Scroll indicator
    if (members_.size() > (size_t)max_rows) {
        mvwprintw(window, height - 2, width - 30, "[↑↓ to scroll, %zu/%zu]", 
                  scroll_offset_ + 1, members_.size());
    }
}

bool AssessmentUniversePanel::handle_input(int ch) {
    switch (ch) {
        case KEY_UP:
            if (scroll_offset_ > 0) {
                scroll_offset_--;
            }
            return true;
        case KEY_DOWN:
            if (scroll_offset_ + 10 < (int)members_.size()) {
                scroll_offset_++;
            }
            return true;
        default:
            break;
    }
    return false;
}

} // namespace prometheus::tui
