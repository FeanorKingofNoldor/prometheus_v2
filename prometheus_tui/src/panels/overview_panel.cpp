#include "panels/overview_panel.hpp"
#include "api_client.hpp"
#include "utils/colors.hpp"
#include "utils/logger.hpp"
#include "utils/braille_chart.hpp"
#include <format>

namespace prometheus::tui {

OverviewPanel::OverviewPanel() 
    : BasePanel("overview", "System Overview & Health") {
}

void OverviewPanel::refresh(ApiClient& api_client) {
    LOG_INFO("OverviewPanel", "Refreshing data...");
    
    // Fetch overview data
    overview_data_ = api_client.get_status_overview();
    if (!overview_data_) {
        // Backend not available - use mock data for demo
        LOG_WARN("OverviewPanel", "Backend not available, using mock data");
        
        overview_data_ = json({
            {"pnl_today", 1234.56},
            {"pnl_mtd", 5432.10},
            {"pnl_ytd", 12345.67},
            {"max_drawdown", -0.042},
            {"net_exposure", 0.125},
            {"gross_exposure", 1.234},
            {"leverage", 1.45},
            {"global_stability_index", 0.872},
            {"regimes", json::array({
                {{"region", "US"}, {"regime_label", "GROWTH"}, {"confidence", 0.85}},
                {{"region", "EU"}, {"regime_label", "DEFENSIVE"}, {"confidence", 0.72}},
                {{"region", "ASIA"}, {"regime_label", "TRANSITION"}, {"confidence", 0.45}}
            })},
            {"alerts", json::array({
                {{"severity", "WARN"}, {"message", "High volatility detected in US_EQ"}},
                {{"severity", "INFO"}, {"message", "Backtest completed successfully"}}
            })}
        });
        
        regime_data_ = json({
            {"current_regime", "GROWTH"},
            {"confidence", 0.85}
        });
        
        error_message_.clear();
        mark_clean();
        LOG_INFO("OverviewPanel", "Mock data loaded");
        return;
    }
    
    // Fetch US regime data
    regime_data_ = api_client.get_status_regime("US");
    
    // Fetch US stability data
    stability_data_ = api_client.get_status_stability("US");
    
    error_message_.clear();
    mark_clean();
    LOG_INFO("OverviewPanel", "Data refreshed successfully");
}

void OverviewPanel::render(WINDOW* window) {
    werase(window);
    draw_border(window);
    draw_header(window, display_name_);
    
    int width = getmaxx(window);
    int height = getmaxy(window);
    
    if (!error_message_.empty()) {
        wattron(window, COLOR_PAIR(colors::ACCENT_RED));
        mvwprintw(window, 3, 2, "Error: %s", error_message_.c_str());
        wattroff(window, COLOR_PAIR(colors::ACCENT_RED));
        return;
    }
    
    if (!overview_data_) {
        wattron(window, COLOR_PAIR(colors::TEXT_DIM));
        mvwprintw(window, 3, 2, "Loading data...");
        wattroff(window, COLOR_PAIR(colors::TEXT_DIM));
        return;
    }
    
    // Render sections with separators
    int current_row = 2;
    render_kpis(window, current_row);
    current_row += 10;
    
    if (current_row < height - 2) {
        // Section separator
        mvwhline(window, current_row++, 2, ACS_HLINE, width - 4);
        current_row++;
        
        render_regimes(window, current_row);
        current_row += 8;
    }
    
    if (current_row < height - 2) {
        // Section separator
        mvwhline(window, current_row++, 2, ACS_HLINE, width - 4);
        current_row++;
        
        render_alerts(window, current_row);
    }
}

void OverviewPanel::render_kpis(WINDOW* window, int start_row) {
    const auto& data = *overview_data_;
    int width = getmaxx(window);
    
    // Three-column layout for better space usage
    int col1_x = 3;
    int col2_x = width / 3;
    int col3_x = (width * 2) / 3;
    
    // ============ COLUMN 1: P&L Metrics ============
    wattron(window, COLOR_PAIR(colors::ACCENT_CYAN) | A_BOLD);
    mvwprintw(window, start_row, col1_x, "═══ PERFORMANCE ═══");
    wattroff(window, COLOR_PAIR(colors::ACCENT_CYAN) | A_BOLD);
    
    int row = start_row + 2;
    
    // P&L Today
    double pnl_today = data.value("pnl_today", 0.0);
    int color = pnl_today >= 0 ? colors::KPI_POSITIVE : colors::KPI_NEGATIVE;
    const char* sign = pnl_today >= 0 ? "+" : "";
    
    wattron(window, COLOR_PAIR(colors::TEXT_PRIMARY));
    mvwprintw(window, row, col1_x, "P&L Today");
    wattroff(window, COLOR_PAIR(colors::TEXT_PRIMARY));
    wattron(window, COLOR_PAIR(color) | A_BOLD);
    mvwprintw(window, row + 1, col1_x + 2, "%s$%.2f", sign, pnl_today);
    wattroff(window, COLOR_PAIR(color) | A_BOLD);
    
    // Add mini sparkline trend (mock data for today)
    std::vector<double> pnl_trend = {-100, -50, 200, 500, 800, 1100, 1234.56};
    std::string spark = inline_sparkline(pnl_trend, 15);
    
    // Make sparkline more visible with color
    wattron(window, COLOR_PAIR(colors::KPI_POSITIVE));
    mvwprintw(window, row + 2, col1_x + 2, "[%s]", spark.c_str());
    wattroff(window, COLOR_PAIR(colors::KPI_POSITIVE));
    
    // Also show it as text for debugging
    mvwprintw(window, row + 3, col1_x + 2, "Trend: %zu pts", pnl_trend.size());
    
    // P&L MTD
    double pnl_mtd = data.value("pnl_mtd", 0.0);
    color = pnl_mtd >= 0 ? colors::KPI_POSITIVE : colors::KPI_NEGATIVE;
    mvwprintw(window, row + 3, col1_x, "MTD");
    wattron(window, COLOR_PAIR(color) | A_BOLD);
    mvwprintw(window, row + 4, col1_x + 2, "%+.2f", pnl_mtd);
    wattroff(window, COLOR_PAIR(color) | A_BOLD);
    
    // P&L YTD
    double pnl_ytd = data.value("pnl_ytd", 0.0);
    color = pnl_ytd >= 0 ? colors::KPI_POSITIVE : colors::KPI_NEGATIVE;
    mvwprintw(window, row + 6, col1_x, "YTD");
    wattron(window, COLOR_PAIR(color) | A_BOLD);
    mvwprintw(window, row + 7, col1_x + 2, "%+.2f", pnl_ytd);
    wattroff(window, COLOR_PAIR(color) | A_BOLD);
    
    // ============ COLUMN 2: Risk Metrics ============
    wattron(window, COLOR_PAIR(colors::ACCENT_CYAN) | A_BOLD);
    mvwprintw(window, start_row, col2_x, "═══ RISK METRICS ═══");
    wattroff(window, COLOR_PAIR(colors::ACCENT_CYAN) | A_BOLD);
    
    row = start_row + 2;
    
    // Max Drawdown
    double max_dd = data.value("max_drawdown", 0.0);
    color = max_dd > -0.05 ? colors::STATUS_OK : 
            max_dd > -0.10 ? colors::STATUS_WARN : colors::STATUS_ERROR;
    mvwprintw(window, row, col2_x, "Max Drawdown");
    wattron(window, COLOR_PAIR(color));
    mvwprintw(window, row + 1, col2_x + 2, "%.2f%%", max_dd * 100);
    wattroff(window, COLOR_PAIR(color));
    
    // Net Exposure
    double net_exp = data.value("net_exposure", 0.0);
    mvwprintw(window, row + 3, col2_x, "Net Exposure");
    mvwprintw(window, row + 4, col2_x + 2, "%.2f%%", net_exp * 100);
    
    // Gross Exposure
    double gross_exp = data.value("gross_exposure", 0.0);
    mvwprintw(window, row + 6, col2_x, "Gross Exposure");
    mvwprintw(window, row + 7, col2_x + 2, "%.2f%%", gross_exp * 100);
    
    // ============ COLUMN 3: System Health ============
    wattron(window, COLOR_PAIR(colors::ACCENT_CYAN) | A_BOLD);
    mvwprintw(window, start_row, col3_x, "═══ SYSTEM HEALTH ═══");
    wattroff(window, COLOR_PAIR(colors::ACCENT_CYAN) | A_BOLD);
    
    row = start_row + 2;
    
    // Stability Index
    double stab = data.value("global_stability_index", 0.0);
    color = stab > 0.7 ? colors::STATUS_OK : 
            stab > 0.5 ? colors::STATUS_WARN : colors::STATUS_ERROR;
    mvwprintw(window, row, col3_x, "Stability Index");
    wattron(window, COLOR_PAIR(color) | A_BOLD);
    mvwprintw(window, row + 1, col3_x + 2, "%.3f", stab);
    wattroff(window, COLOR_PAIR(color) | A_BOLD);
    
    // Leverage
    double leverage = data.value("leverage", 0.0);
    color = leverage > 2.0 ? colors::STATUS_WARN : colors::STATUS_OK;
    mvwprintw(window, row + 3, col3_x, "Leverage");
    wattron(window, COLOR_PAIR(color));
    mvwprintw(window, row + 4, col3_x + 2, "%.2fx", leverage);
    wattroff(window, COLOR_PAIR(color));
    
    // Active Strategies (mock)
    mvwprintw(window, row + 6, col3_x, "Active Strategies");
    wattron(window, COLOR_PAIR(colors::STATUS_OK));
    mvwprintw(window, row + 7, col3_x + 2, "3 / 4");
    wattroff(window, COLOR_PAIR(colors::STATUS_OK));
}

void OverviewPanel::render_regimes(WINDOW* window, int start_row) {
    int width = getmaxx(window);
    
    // Section title with separator line
    wattron(window, COLOR_PAIR(colors::ACCENT_CYAN) | A_BOLD);
    mvwprintw(window, start_row, 2, "═══ GLOBAL MARKET REGIMES ═══");
    wattroff(window, COLOR_PAIR(colors::ACCENT_CYAN) | A_BOLD);
    
    start_row += 2;
    
    // Table header with more spacing
    wattron(window, COLOR_PAIR(colors::TEXT_DIM) | A_BOLD);
    mvwprintw(window, start_row, 3, "%-15s %-20s %15s %15s %15s",
              "Region", "Regime", "Confidence", "Stability", "Duration");
    wattroff(window, COLOR_PAIR(colors::TEXT_DIM) | A_BOLD);
    start_row++;
    // Header separator line
    mvwhline(window, start_row++, 3, ACS_HLINE, width - 6);
    
    // Draw regimes from overview with enhanced display
    if (overview_data_->contains("regimes")) {
        const auto& regimes = (*overview_data_)["regimes"];
        for (const auto& regime : regimes) {
            std::string region = regime.value("region", "?");
            std::string label = regime.value("regime_label", "?");
            double conf = regime.value("confidence", 0.0);
            
            // Color code based on regime type
            int regime_color = colors::TEXT_PRIMARY;
            if (label.find("GROWTH") != std::string::npos || 
                label.find("RISK_ON") != std::string::npos) {
                regime_color = colors::STATUS_OK;
            } else if (label.find("DEFENSIVE") != std::string::npos ||
                       label.find("RISK_OFF") != std::string::npos) {
                regime_color = colors::STATUS_WARN;
            } else if (label.find("CRISIS") != std::string::npos) {
                regime_color = colors::STATUS_ERROR;
            }
            
            // Region
            wattron(window, COLOR_PAIR(colors::TEXT_PRIMARY) | A_BOLD);
            mvwprintw(window, start_row, 3, "%-15s", region.c_str());
            wattroff(window, COLOR_PAIR(colors::TEXT_PRIMARY) | A_BOLD);
            
            // Regime label with color
            wattron(window, COLOR_PAIR(regime_color) | A_BOLD);
            mvwprintw(window, start_row, 19, "%-20s", label.c_str());
            wattroff(window, COLOR_PAIR(regime_color) | A_BOLD);
            
            // Confidence with color gradient
            int conf_color = conf > 0.7 ? colors::STATUS_OK :
                            conf > 0.5 ? colors::STATUS_WARN : colors::STATUS_ERROR;
            wattron(window, COLOR_PAIR(conf_color));
            mvwprintw(window, start_row, 40, "%14.1f%%", conf * 100.0);
            wattroff(window, COLOR_PAIR(conf_color));
            
            // Mock stability and duration
            double stability = 0.6 + (conf * 0.3); // Mock calculation
            int days = 15 + (int)(conf * 30); // Mock days
            
            mvwprintw(window, start_row, 56, "%14.2f", stability);
            mvwprintw(window, start_row, 72, "%12dd", days);
            
            start_row++;
        }
    }
    
    // Add US regime detail if available
    if (regime_data_) {
        start_row++;
        std::string current = regime_data_->value("current_regime", "UNKNOWN");
        double conf = regime_data_->value("confidence", 0.0);
        
        wattron(window, COLOR_PAIR(colors::ACCENT_BLUE));
        mvwprintw(window, start_row, 2, "US Detail: %s (%.1f%% confidence)",
                 current.c_str(), conf * 100.0);
        wattroff(window, COLOR_PAIR(colors::ACCENT_BLUE));
    }
}

void OverviewPanel::render_alerts(WINDOW* window, int start_row) {
    if (!overview_data_->contains("alerts")) {
        return;
    }
    
    const auto& alerts = (*overview_data_)["alerts"];
    if (alerts.empty()) {
        wattron(window, COLOR_PAIR(colors::STATUS_OK));
        mvwprintw(window, start_row, 2, "✓ No active alerts");
        wattroff(window, COLOR_PAIR(colors::STATUS_OK));
        return;
    }
    
    // Section title
    wattron(window, COLOR_PAIR(colors::ACCENT_YELLOW) | A_BOLD);
    mvwprintw(window, start_row, 2, "Active Alerts (%zu)", alerts.size());
    wattroff(window, COLOR_PAIR(colors::ACCENT_YELLOW) | A_BOLD);
    
    start_row += 2;
    
    int count = 0;
    for (const auto& alert : alerts) {
        if (count >= 5) break; // Show max 5 alerts
        
        std::string severity = alert.value("severity", "INFO");
        std::string message = alert.value("message", "");
        
        int color = colors::ACCENT_BLUE;
        if (severity == "CRITICAL" || severity == "ERROR") {
            color = colors::ACCENT_RED;
        } else if (severity == "WARN" || severity == "WARNING") {
            color = colors::ACCENT_YELLOW;
        }
        
        wattron(window, COLOR_PAIR(color));
        mvwprintw(window, start_row, 2, "[%s] %s",
                 severity.c_str(), message.c_str());
        wattroff(window, COLOR_PAIR(color));
        
        start_row++;
        count++;
    }
}

} // namespace prometheus::tui
