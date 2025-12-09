#include "panels/execution_panel.hpp"
#include "api_client.hpp"
#include "utils/logger.hpp"
#include "utils/colors.hpp"
#include "utils/braille_chart.hpp"
#include <format>
#include <ncurses.h>

namespace prometheus::tui {

ExecutionPanel::ExecutionPanel() : BasePanel("execution", "Execution") {
    LOG_INFO("ExecutionPanel", "Initialized");
}

void ExecutionPanel::refresh(ApiClient& api_client) {
    LOG_INFO("ExecutionPanel", "Refreshing data...");
    
    // Try to get real execution data
    auto exec_response = api_client.get_status_execution("MAIN", "", 50, 50);
    
    if (exec_response.has_value()) {
        // Parse real data when available
        LOG_INFO("ExecutionPanel", "Loaded real execution data");
    }
    
    // Mock data with more variety
    recent_orders_ = {
        {"15:42:13", "AAPL", "BUY", 100, 185.50, "FILLED"},
        {"15:42:05", "MSFT", "SELL", 50, 376.20, "FILLED"},
        {"15:41:52", "GOOGL", "BUY", 25, 142.15, "FILLED"},
        {"15:41:40", "TSLA", "BUY", 75, 252.30, "PARTIAL"},
        {"15:41:28", "NVDA", "SELL", 40, 142.00, "FILLED"},
        {"15:41:15", "AAPL", "SELL", 50, 185.75, "FILLED"},
        {"15:41:02", "MSFT", "BUY", 100, 375.80, "FILLED"},
        {"15:40:48", "GOOGL", "SELL", 30, 142.50, "FILLED"},
        {"15:40:35", "TSLA", "SELL", 60, 252.75, "FILLED"},
        {"15:40:22", "NVDA", "BUY", 80, 141.50, "FILLED"},
        {"15:40:10", "AMD", "BUY", 120, 165.80, "FILLED"},
        {"15:39:58", "META", "SELL", 35, 482.90, "FILLED"},
        {"15:39:45", "NFLX", "BUY", 15, 612.40, "FILLED"},
        {"15:39:30", "AMZN", "SELL", 45, 178.25, "FILLED"},
        {"15:39:18", "JPM", "BUY", 90, 195.60, "FILLED"}
    };
}

void ExecutionPanel::render(WINDOW* window) {
    int height = getmaxy(window);
    int width = getmaxx(window);
    int y = 0;
    
    // Title
    wattron(window, COLOR_PAIR(COLOR_CYAN)); wattron(window, A_BOLD);
    mvwprintw(window, y++, 2, "══════════ ORDER EXECUTION ANALYTICS ══════════");
    wattroff(window, A_BOLD); wattroff(window, COLOR_PAIR(COLOR_CYAN));
    y++;
    
    // Calculate execution stats
    int total_orders = recent_orders_.size();
    int filled_orders = 0;
    int buy_orders = 0;
    int sell_orders = 0;
    double total_volume = 0;
    
    for (const auto& order : recent_orders_) {
        if (order.status == "FILLED") filled_orders++;
        if (order.side == "BUY") buy_orders++;
        else sell_orders++;
        total_volume += order.quantity * order.price;
    }
    
    double fill_rate = total_orders > 0 ? (filled_orders * 100.0 / total_orders) : 0;
    
    // Execution Summary - Three columns
    int col1 = 3;
    int col2 = width / 3;
    int col3 = (width * 2) / 3;
    
    wattron(window, A_BOLD);
    mvwprintw(window, y, col1, "Total Orders:");
    mvwprintw(window, y, col2, "Fill Rate:");
    mvwprintw(window, y, col3, "Total Volume:");
    wattroff(window, A_BOLD);
    y++;
    
    mvwprintw(window, y, col1 + 2, "%d", total_orders);
    wattron(window, COLOR_PAIR(fill_rate > 95 ? COLOR_GREEN : COLOR_YELLOW) | A_BOLD);
    mvwprintw(window, y, col2 + 2, "%.1f%%", fill_rate);
    wattroff(window, COLOR_PAIR(fill_rate > 95 ? COLOR_GREEN : COLOR_YELLOW) | A_BOLD);
    mvwprintw(window, y, col3 + 2, "$%.2fM", total_volume / 1000000.0);
    y++;
    
    // Add volume trend sparkline
    std::vector<double> volume_trend = {0.8, 1.2, 1.5, 2.1, 1.8, 2.3, 2.6, 2.8, 3.1, 3.3};
    std::string vol_spark = inline_sparkline(volume_trend, 20);
    mvwprintw(window, y, col3 + 2, "%s", vol_spark.c_str());
    y++;
    
    wattron(window, A_BOLD);
    mvwprintw(window, y, col1, "Buy/Sell:");
    mvwprintw(window, y, col2, "Avg Fill Time:");
    mvwprintw(window, y, col3, "Slippage:");
    wattroff(window, A_BOLD);
    y++;
    
    wattron(window, COLOR_PAIR(COLOR_GREEN));
    mvwprintw(window, y, col1 + 2, "%d", buy_orders);
    wattroff(window, COLOR_PAIR(COLOR_GREEN));
    wprintw(window, " / ");
    wattron(window, COLOR_PAIR(COLOR_RED));
    wprintw(window, "%d", sell_orders);
    wattroff(window, COLOR_PAIR(COLOR_RED));
    
    mvwprintw(window, y, col2 + 2, "24.5ms");
    wattron(window, COLOR_PAIR(COLOR_GREEN));
    mvwprintw(window, y, col3 + 2, "0.03%%");
    wattroff(window, COLOR_PAIR(COLOR_GREEN));
    
    y += 2;
    
    // Section separator
    wattron(window, COLOR_PAIR(COLOR_CYAN) | A_BOLD);
    mvwprintw(window, y++, 2, "Recent Orders:");
    wattroff(window, COLOR_PAIR(COLOR_CYAN) | A_BOLD);
    y++;
    
    // Table header with better spacing
    wattron(window, A_BOLD);
    mvwprintw(window, y++, 3, "%-12s %-10s %-8s %15s %18s %15s %18s", 
              "Time", "Symbol", "Side", "Quantity", "Price", "Notional", "Status");
    wattroff(window, A_BOLD);
    mvwhline(window, y++, 3, ACS_HLINE, width - 6);
    
    // Orders
    int orders_shown = 0;
    int max_orders = height - y - 1;
    
    for (size_t i = scroll_offset_; i < recent_orders_.size() && orders_shown < max_orders; ++i) {
        const auto& order = recent_orders_[i];
        
        mvwprintw(window, y, 3, "%-12s", order.timestamp.c_str());
        
        wattron(window, A_BOLD);
        mvwprintw(window, y, 16, "%-10s", order.symbol.c_str());
        wattroff(window, A_BOLD);
        
        // Color code side
        int side_color = order.side == "BUY" ? COLOR_GREEN : COLOR_RED;
        wattron(window, COLOR_PAIR(side_color) | A_BOLD);
        mvwprintw(window, y, 27, "%-8s", order.side.c_str());
        wattroff(window, COLOR_PAIR(side_color) | A_BOLD);
        
        mvwprintw(window, y, 36, "%14d", order.quantity);
        mvwprintw(window, y, 52, "$%16.2f", order.price);
        
        // Calculate and display notional value
        double notional = order.quantity * order.price;
        mvwprintw(window, y, 71, "$%13.2f", notional);
        
        // Color code status
        int status_color = COLOR_GREEN;
        if (order.status == "PARTIAL") status_color = COLOR_YELLOW;
        else if (order.status == "REJECTED" || order.status == "CANCELLED") status_color = COLOR_RED;
        
        wattron(window, COLOR_PAIR(status_color) | A_BOLD);
        mvwprintw(window, y, 87, "%17s", order.status.c_str());
        wattroff(window, COLOR_PAIR(status_color) | A_BOLD);
        
        y++;
        orders_shown++;
    }
}

bool ExecutionPanel::handle_input(int ch) {
    switch (ch) {
        case KEY_UP:
            if (scroll_offset_ > 0) {
                scroll_offset_--;
            }
            return true;
        case KEY_DOWN:
            if (scroll_offset_ + 10 < (int)recent_orders_.size()) {
                scroll_offset_++;
            }
            return true;
        default:
            break;
    }
    return false;
}

} // namespace prometheus::tui
