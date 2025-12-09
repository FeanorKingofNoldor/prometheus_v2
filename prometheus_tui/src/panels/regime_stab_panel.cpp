#include "panels/regime_stab_panel.hpp"
#include "api_client.hpp"
#include "utils/logger.hpp"
#include "utils/colors.hpp"
#include <format>
#include <ncurses.h>

namespace prometheus::tui {

RegimeStabPanel::RegimeStabPanel() : BasePanel("regime_stab", "Regime Stability") {
    LOG_INFO("RegimeStabPanel", "Initialized");
}

void RegimeStabPanel::refresh(ApiClient& api_client) {
    LOG_INFO("RegimeStabPanel", "Refreshing data...");
    
    // Try to fetch real data from regime status API
    auto response = api_client.get_status_regime();
    
    if (response.has_value()) {
        parse_regime_data(response.value());
    } else {
        // Use mock data for offline mode
        LOG_WARN("RegimeStabPanel", "Using mock regime data");
        current_regime_ = "RISK_ON";
        overall_fragility_ = 0.42;
        
        regimes_ = {
            {"RISK_ON", 0.82, 0.35, "STABLE", 47},
            {"NEUTRAL", 0.65, 0.58, "TRANSITIONAL", 12},
            {"RISK_OFF", 0.71, 0.48, "STABLE", 23},
            {"CRISIS", 0.45, 0.89, "VOLATILE", 3}
        };
        
        transitions_ = {
            {"RISK_ON", "NEUTRAL", 0.15},
            {"RISK_ON", "RISK_OFF", 0.08},
            {"NEUTRAL", "RISK_ON", 0.25},
            {"NEUTRAL", "RISK_OFF", 0.18},
            {"RISK_OFF", "NEUTRAL", 0.22},
            {"CRISIS", "RISK_OFF", 0.42}
        };
    }
}

void RegimeStabPanel::render(WINDOW* window) {
    int height = getmaxy(window);
    int width = getmaxx(window);
    int y = 0;
    
    // Title with full width
    wattron(window, COLOR_PAIR(COLOR_CYAN)); wattron(window, A_BOLD);
    mvwprintw(window, y++, 2, "═══════════════ REGIME STABILITY & TRANSITION MATRIX ═══════════════");
    wattroff(window, A_BOLD); wattroff(window, COLOR_PAIR(COLOR_CYAN));
    y++;
    
    // Current regime status - wider layout
    int col1 = 3;
    int col2 = width / 3;
    int col3 = (width * 2) / 3;
    
    // Column 1: Current Regime
    wattron(window, A_BOLD);
    mvwprintw(window, y, col1, "Current Regime:");
    wattroff(window, A_BOLD);
    wattron(window, COLOR_PAIR(COLOR_GREEN) | A_BOLD);
    mvwprintw(window, y + 1, col1 + 2, "%s", current_regime_.c_str());
    wattroff(window, COLOR_PAIR(COLOR_GREEN) | A_BOLD);
    
    // Column 2: Overall Fragility
    wattron(window, A_BOLD);
    mvwprintw(window, y, col2, "System Fragility:");
    wattroff(window, A_BOLD);
    int frag_color = overall_fragility_ < 0.5 ? COLOR_GREEN : 
                     overall_fragility_ < 0.75 ? COLOR_YELLOW : COLOR_RED;
    wattron(window, COLOR_PAIR(frag_color) | A_BOLD);
    mvwprintw(window, y + 1, col2 + 2, "%.3f (%s)", overall_fragility_,
              overall_fragility_ < 0.5 ? "LOW" : 
              overall_fragility_ < 0.75 ? "MODERATE" : "HIGH");
    wattroff(window, COLOR_PAIR(frag_color) | A_BOLD);
    
    // Column 3: Time in Regime
    wattron(window, A_BOLD);
    mvwprintw(window, y, col3, "Time in Regime:");
    wattroff(window, A_BOLD);
    mvwprintw(window, y + 1, col3 + 2, "47 days");
    
    y += 3;
    
    // Regime stability section header
    wattron(window, COLOR_PAIR(COLOR_CYAN)); wattron(window, A_BOLD);
    mvwprintw(window, y++, 2, "All Regime States:");
    wattroff(window, A_BOLD); wattroff(window, COLOR_PAIR(COLOR_CYAN));
    y++;
    
    // Regime table header with better spacing
    wattron(window, A_BOLD);
    mvwprintw(window, y++, 3, "%-20s %15s %15s %20s %15s %12s", 
              "Regime", "Stability", "Fragility", "Status", "Persistence", "Days");
    wattroff(window, A_BOLD);
    mvwhline(window, y++, 3, ACS_HLINE, width - 6);
    
    // Regime data with enhanced visualization
    for (const auto& regime : regimes_) {
        // Regime name - highlight if current with indicator
        std::string regime_display = regime.regime_name;
        if (regime.regime_name == current_regime_) {
            regime_display = "▶ " + regime_display; // Add arrow indicator
            wattron(window, COLOR_PAIR(COLOR_GREEN) | A_BOLD);
            mvwprintw(window, y, 3, "%-20s", regime_display.c_str());
            wattroff(window, COLOR_PAIR(COLOR_GREEN) | A_BOLD);
        } else {
            mvwprintw(window, y, 3, "  %-18s", regime.regime_name.c_str());
        }
        
        // Stability with percentage
        int stab_color = regime.stability > 0.7 ? COLOR_GREEN :
                         regime.stability > 0.5 ? COLOR_YELLOW : COLOR_RED;
        wattron(window, COLOR_PAIR(stab_color));
        mvwprintw(window, y, 24, "%14.1f%%", regime.stability * 100);
        wattroff(window, COLOR_PAIR(stab_color));
        
        // Fragility with bar visualization
        int frag_color_local = regime.fragility < 0.5 ? COLOR_GREEN :
                               regime.fragility < 0.75 ? COLOR_YELLOW : COLOR_RED;
        wattron(window, COLOR_PAIR(frag_color_local));
        mvwprintw(window, y, 40, "%14.1f%%", regime.fragility * 100);
        wattroff(window, COLOR_PAIR(frag_color_local));
        
        // Status with color
        int status_color = COLOR_WHITE;
        if (regime.status == "STABLE") status_color = COLOR_GREEN;
        else if (regime.status == "TRANSITIONAL") status_color = COLOR_YELLOW;
        else if (regime.status == "VOLATILE") status_color = COLOR_RED;
        
        wattron(window, COLOR_PAIR(status_color));
        mvwprintw(window, y, 56, "%19s", regime.status.c_str());
        wattroff(window, COLOR_PAIR(status_color));
        
        // Persistence metric (mock)
        double persistence = regime.stability * (1.0 - regime.fragility);
        mvwprintw(window, y, 77, "%14.2f", persistence);
        
        // Days in regime
        mvwprintw(window, y, 93, "%10d", regime.days_in_regime);
        
        y++;
    }
    
    y += 2;
    
    // Transition probabilities (if room)
    if (y + 2 + (int)transitions_.size() < height - 1) {
        wattron(window, COLOR_PAIR(COLOR_CYAN)); wattron(window, A_BOLD);
        mvwprintw(window, y++, 2, "Key Regime Transitions:");
        wattroff(window, A_BOLD); wattroff(window, COLOR_PAIR(COLOR_CYAN));
        y++;
        
        wattron(window, A_BOLD);
        mvwprintw(window, y++, 2, "%-15s -> %-15s %12s", 
                  "From", "To", "Probability");
        wattroff(window, A_BOLD);
        mvwhline(window, y++, 2, ACS_HLINE, 50);
        
        for (const auto& trans : transitions_) {
            mvwprintw(window, y, 2, "%-15s -> %-15s", 
                      trans.from_regime.c_str(), trans.to_regime.c_str());
            
            // Color code probability
            int prob_color = trans.probability > 0.3 ? COLOR_RED :
                            trans.probability > 0.15 ? COLOR_YELLOW : COLOR_GREEN;
            wattron(window, COLOR_PAIR(prob_color));
            mvwprintw(window, y, 36, "%11.2f%%", trans.probability * 100);
            wattroff(window, COLOR_PAIR(prob_color));
            
            y++;
            if (y >= height - 1) break;
        }
    }
}

bool RegimeStabPanel::handle_input(int ch) {
    // Panel-specific input handling
    switch (ch) {
        case KEY_UP:
        case KEY_DOWN:
            // Could implement scrolling if needed
            LOG_INFO("RegimeStabPanel", "Navigation key pressed");
            return true;
        default:
            break;
    }
    return false;
}

void RegimeStabPanel::parse_regime_data(const nlohmann::json& data) {
    try {
        regimes_.clear();
        transitions_.clear();
        
        if (data.contains("current_regime")) {
            current_regime_ = data["current_regime"].get<std::string>();
        }
        
        if (data.contains("overall_fragility")) {
            overall_fragility_ = data["overall_fragility"].get<double>();
        }
        
        if (data.contains("regimes") && data["regimes"].is_array()) {
            for (const auto& r : data["regimes"]) {
                RegimeData regime;
                regime.regime_name = r.value("name", "UNKNOWN");
                regime.stability = r.value("stability", 0.0);
                regime.fragility = r.value("fragility", 0.0);
                regime.status = r.value("status", "UNKNOWN");
                regime.days_in_regime = r.value("days", 0);
                regimes_.push_back(regime);
            }
        }
        
        if (data.contains("transitions") && data["transitions"].is_array()) {
            for (const auto& t : data["transitions"]) {
                RegimeTransition trans;
                trans.from_regime = t.value("from", "");
                trans.to_regime = t.value("to", "");
                trans.probability = t.value("probability", 0.0);
                transitions_.push_back(trans);
            }
        }
        
        LOG_INFO("RegimeStabPanel", "Parsed regime data successfully");
    } catch (const std::exception& e) {
        LOG_ERROR("RegimeStabPanel", std::string("Failed to parse regime data: ") + e.what());
    }
}

} // namespace prometheus::tui
