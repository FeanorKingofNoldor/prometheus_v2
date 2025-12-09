#include "panels/portfolio_risk_panel.hpp"
#include "api_client.hpp"
#include "utils/logger.hpp"
#include "utils/colors.hpp"
#include "utils/braille_chart.hpp"
#include <format>
#include <ncurses.h>

namespace prometheus::tui {

PortfolioRiskPanel::PortfolioRiskPanel() : BasePanel("portfolio_risk", "Portfolio Risk") {
    LOG_INFO("PortfolioRiskPanel", "Initialized");
}

void PortfolioRiskPanel::refresh(ApiClient& api_client) {
    LOG_INFO("PortfolioRiskPanel", "Refreshing data...");
    
    // Mock data for now
    risk_metrics_ = {
        {"VaR (95%)", 125000, 250000, "OK"},
        {"CVaR (95%)", 185000, 350000, "OK"},
        {"Max Drawdown", 0.08, 0.15, "OK"},
        {"Sharpe Ratio", 1.85, 1.0, "OK"},
        {"Beta", 0.92, 1.5, "OK"},
        {"Leverage", 1.2, 2.0, "OK"}
    };
    
    positions_ = {
        {"AAPL", 500, 92750, 1250, 1.35},
        {"MSFT", 300, 112800, -450, -0.40},
        {"GOOGL", 200, 28400, 800, 2.90},
        {"TSLA", 150, 37875, 2125, 5.95},
        {"NVDA", 400, 56800, 3200, 5.97}
    };
    
    total_portfolio_value_ = 328625;
    total_pnl_ = 6925;
}

void PortfolioRiskPanel::render(WINDOW* window) {
    int height = getmaxy(window);
    int width = getmaxx(window);
    int y = 0;
    
    // Title
    wattron(window, COLOR_PAIR(COLOR_CYAN)); wattron(window, A_BOLD);
    mvwprintw(window, y++, 2, "════════ PORTFOLIO RISK ANALYSIS & POSITIONS ════════");
    wattroff(window, A_BOLD); wattroff(window, COLOR_PAIR(COLOR_CYAN));
    y++;
    
    // Portfolio summary - wider three-column layout
    int col1 = 3;
    int col2 = width / 3;
    int col3 = (width * 2) / 3;
    
    // Column 1: Portfolio Value
    wattron(window, A_BOLD);
    mvwprintw(window, y, col1, "Portfolio Value");
    wattroff(window, A_BOLD);
    mvwprintw(window, y + 1, col1 + 2, "$%.2f", total_portfolio_value_);
    
    // Column 2: Total P&L
    wattron(window, A_BOLD);
    mvwprintw(window, y, col2, "Total P&L");
    wattroff(window, A_BOLD);
    int pnl_color = total_pnl_ >= 0 ? COLOR_GREEN : COLOR_RED;
    wattron(window, COLOR_PAIR(pnl_color) | A_BOLD);
    mvwprintw(window, y + 1, col2 + 2, "%+.2f (%.2f%%)", 
              total_pnl_, (total_pnl_ / total_portfolio_value_) * 100);
    wattroff(window, COLOR_PAIR(pnl_color) | A_BOLD);
    
    // Column 3: Number of Positions
    wattron(window, A_BOLD);
    mvwprintw(window, y, col3, "Positions");
    wattroff(window, A_BOLD);
    mvwprintw(window, y + 1, col3 + 2, "%zu active", positions_.size());
    
    // Add PnL trend under total
    std::vector<double> pnl_history = {-200, 150, 400, 850, 1200, 1800, 2400, 3100, 4200, 5500, 6925};
    std::string pnl_spark = inline_sparkline(pnl_history, 18);
    mvwprintw(window, y + 2, col2 + 2, "%s", pnl_spark.c_str());
    
    y += 4;
    
    // Risk metrics header
    wattron(window, COLOR_PAIR(COLOR_CYAN)); wattron(window, A_BOLD);
    mvwprintw(window, y++, 2, "Risk Metrics:");
    wattroff(window, A_BOLD); wattroff(window, COLOR_PAIR(COLOR_CYAN));
    y++;
    
    // Risk metrics table with more spacing
    wattron(window, A_BOLD);
    mvwprintw(window, y++, 3, "%-25s %20s %20s %15s %15s", 
              "Metric", "Current", "Limit", "Utilization", "Status");
    wattroff(window, A_BOLD);
    mvwhline(window, y++, 3, ACS_HLINE, width - 6);
    
    for (const auto& metric : risk_metrics_) {
        mvwprintw(window, y, 3, "%-25s", metric.name.c_str());
        
        // Current value
        wattron(window, A_BOLD);
        mvwprintw(window, y, 29, "%19.2f", metric.value);
        wattroff(window, A_BOLD);
        
        // Limit
        mvwprintw(window, y, 50, "%19.2f", metric.limit);
        
        // Utilization percentage
        double utilization = metric.limit > 0 ? (metric.value / metric.limit) * 100 : 0;
        int util_color = utilization < 50 ? COLOR_GREEN :
                        utilization < 80 ? COLOR_YELLOW : COLOR_RED;
        wattron(window, COLOR_PAIR(util_color));
        mvwprintw(window, y, 71, "%14.1f%%", utilization);
        wattroff(window, COLOR_PAIR(util_color));
        
        // Status
        int status_color = metric.status == "OK" ? COLOR_GREEN : COLOR_RED;
        wattron(window, COLOR_PAIR(status_color) | A_BOLD);
        mvwprintw(window, y, 87, "%14s", metric.status.c_str());
        wattroff(window, COLOR_PAIR(status_color) | A_BOLD);
        y++;
    }
    
    y += 2;
    
    // Positions section
    if (y + 3 < height) {
        y += 2;
        wattron(window, COLOR_PAIR(COLOR_CYAN)); wattron(window, A_BOLD);
        mvwprintw(window, y++, 2, "Top Positions:");
        wattroff(window, A_BOLD); wattroff(window, COLOR_PAIR(COLOR_CYAN));
        y++;
        
        // Positions table with wider columns
        wattron(window, A_BOLD);
        mvwprintw(window, y++, 3, "%-12s %15s %20s %18s %15s %15s", 
                  "Symbol", "Quantity", "Market Value", "P&L ($)", "P&L (%)", "Weight");
        wattroff(window, A_BOLD);
        mvwhline(window, y++, 3, ACS_HLINE, width - 6);
        
        for (const auto& pos : positions_) {
            // Symbol in bold
            wattron(window, A_BOLD);
            mvwprintw(window, y, 3, "%-12s", pos.symbol.c_str());
            wattroff(window, A_BOLD);
            
            // Quantity
            mvwprintw(window, y, 16, "%14d", pos.quantity);
            
            // Market Value
            mvwprintw(window, y, 32, "$%18.2f", pos.value);
            
            // P&L with color
            int pnl_color_pos = pos.pnl >= 0 ? COLOR_GREEN : COLOR_RED;
            wattron(window, COLOR_PAIR(pnl_color_pos) | A_BOLD);
            mvwprintw(window, y, 52, "%+17.2f", pos.pnl);
            mvwprintw(window, y, 71, "%+14.2f%%", pos.pnl_pct);
            wattroff(window, COLOR_PAIR(pnl_color_pos) | A_BOLD);
            
            // Portfolio weight
            double weight = (pos.value / total_portfolio_value_) * 100.0;
            mvwprintw(window, y, 87, "%14.2f%%", weight);
            
            y++;
            if (y >= height - 1) break;
        }
    }
}

bool PortfolioRiskPanel::handle_input(int ch) {
    // Handle input
    return false;
}

} // namespace prometheus::tui
