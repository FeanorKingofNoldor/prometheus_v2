#include "panels/live_system_panel.hpp"
#include "api_client.hpp"
#include "utils/logger.hpp"
#include "utils/colors.hpp"
#include <format>
#include <ncurses.h>

namespace prometheus::tui {

LiveSystemPanel::LiveSystemPanel() : BasePanel("live_system", "Live System") {
    LOG_INFO("LiveSystemPanel", "Initialized");
}

void LiveSystemPanel::refresh(ApiClient& api_client) {
    LOG_INFO("LiveSystemPanel", "Refreshing data...");
    
    // Try to fetch real data from overview
    auto overview_response = api_client.get_status_overview();
    
    bool has_real_data = false;
    
    if (overview_response.has_value()) {
        parse_system_data(overview_response.value());
        has_real_data = true;
    }
    
    if (!has_real_data) {
        // Use mock data for offline mode
        LOG_WARN("LiveSystemPanel", "Using mock system data");
        system_status_ = "HEALTHY";
        
        metrics_ = {
            {"CPU Usage", 42.5, "%", "OK"},
            {"Memory", 68.2, "%", "OK"},
            {"Disk I/O", 15.3, "MB/s", "OK"},
            {"Network", 128.7, "Mbps", "OK"},
            {"Active Orders", 47, "", "OK"},
            {"Connections", 8, "", "OK"},
            {"Latency", 12.4, "ms", "OK"},
            {"Throughput", 1250, "msgs/s", "OK"}
        };
        
        recent_logs_ = {
            {"2024-12-08 15:42:13", "INFO", "OrderManager", "Order filled: AAPL 100 @ 185.50"},
            {"2024-12-08 15:42:10", "INFO", "RiskEngine", "Position check passed"},
            {"2024-12-08 15:41:58", "WARN", "DataFeed", "Minor latency spike: 45ms"},
            {"2024-12-08 15:41:45", "INFO", "Strategy", "Signal generated: BUY MSFT"},
            {"2024-12-08 15:41:32", "INFO", "Portfolio", "Rebalance triggered"},
            {"2024-12-08 15:41:20", "INFO", "Market", "Market open detected"},
            {"2024-12-08 15:41:15", "INFO", "System", "Health check passed"},
            {"2024-12-08 15:41:00", "INFO", "OrderManager", "Order submitted: TSLA 50"}
        };
    }
}

void LiveSystemPanel::render(WINDOW* window) {
    int height = getmaxy(window);
    int width = getmaxx(window);
    int y = 0;
    
    // Title
    wattron(window, COLOR_PAIR(COLOR_CYAN)); wattron(window, A_BOLD);
    mvwprintw(window, y++, 2, "═════════ LIVE SYSTEM HEALTH MONITOR ═════════");
    wattroff(window, A_BOLD); wattroff(window, COLOR_PAIR(COLOR_CYAN));
    y++;
    
    // System status in center with more prominence
    int center_x = width / 2 - 10;
    wattron(window, A_BOLD);
    mvwprintw(window, y, center_x, "Overall Status: ");
    wattroff(window, A_BOLD);
    
    int status_color = system_status_ == "HEALTHY" ? COLOR_GREEN :
                       system_status_ == "DEGRADED" ? COLOR_YELLOW : COLOR_RED;
    wattron(window, COLOR_PAIR(status_color) | A_BOLD);
    wprintw(window, "%s", system_status_.c_str());
    wattroff(window, COLOR_PAIR(status_color) | A_BOLD);
    y += 2;
    
    // Metrics section with three columns for better space usage
    wattron(window, COLOR_PAIR(COLOR_CYAN)); wattron(window, A_BOLD);
    mvwprintw(window, y++, 2, "System Metrics:");
    wattroff(window, A_BOLD); wattroff(window, COLOR_PAIR(COLOR_CYAN));
    y++;
    
    // Display metrics in three columns
    int col1_x = 3;
    int col2_x = width / 3;
    int col3_x = (width * 2) / 3;
    int metrics_per_col = (metrics_.size() + 2) / 3;  // Distribute across 3 columns
    int y_col1 = y;
    int y_col2 = y;
    int y_col3 = y;
    
    for (size_t i = 0; i < metrics_.size(); ++i) {
        const auto& metric = metrics_[i];
        int x_pos;
        int* y_pos;
        
        if (i < metrics_per_col) {
            x_pos = col1_x;
            y_pos = &y_col1;
        } else if (i < metrics_per_col * 2) {
            x_pos = col2_x;
            y_pos = &y_col2;
        } else {
            x_pos = col3_x;
            y_pos = &y_col3;
        }
        
        // Metric name
        mvwprintw(window, *y_pos, x_pos, "%-18s", metric.name.c_str());
        
        // Value with color on next line
        int color = COLOR_GREEN;
        if (metric.status == "WARNING") color = COLOR_YELLOW;
        else if (metric.status == "ERROR") color = COLOR_RED;
        
        wattron(window, COLOR_PAIR(color) | A_BOLD);
        if (metric.unit.empty()) {
            mvwprintw(window, *y_pos + 1, x_pos + 2, "%.0f", metric.value);
        } else {
            mvwprintw(window, *y_pos + 1, x_pos + 2, "%.1f %s", metric.value, metric.unit.c_str());
        }
        wattroff(window, COLOR_PAIR(color) | A_BOLD);
        
        *y_pos += 3;  // Extra spacing between metrics
    }
    
    y = std::max({y_col1, y_col2, y_col3}) + 1;
    
    // Logs section
    if (y + 4 < height) {
        wattron(window, COLOR_PAIR(COLOR_CYAN)); wattron(window, A_BOLD);
        mvwprintw(window, y++, 2, "Recent System Logs:");
        wattroff(window, A_BOLD); wattroff(window, COLOR_PAIR(COLOR_CYAN));
        y++;
        
        wattron(window, A_BOLD);
        mvwprintw(window, y++, 2, "%-19s %-5s %-15s %s", 
                  "Timestamp", "Level", "Component", "Message");
        wattroff(window, A_BOLD);
        mvwhline(window, y++, 2, ACS_HLINE, width - 4);
        
        // Display logs with scrolling
        int logs_shown = 0;
        int max_logs = height - y - 1;
        
        for (size_t i = scroll_offset_; i < recent_logs_.size() && logs_shown < max_logs; ++i) {
            const auto& log = recent_logs_[i];
            
            // Timestamp
            mvwprintw(window, y, 2, "%-19s", log.timestamp.c_str());
            
            // Level with color
            int level_color = COLOR_WHITE;
            if (log.level == "ERROR" || log.level == "CRITICAL") level_color = COLOR_RED;
            else if (log.level == "WARN" || log.level == "WARNING") level_color = COLOR_YELLOW;
            else if (log.level == "INFO") level_color = COLOR_GREEN;
            
            wattron(window, COLOR_PAIR(level_color) | A_BOLD);
            mvwprintw(window, y, 22, "%-5s", log.level.c_str());
            wattroff(window, COLOR_PAIR(level_color) | A_BOLD);
            
            // Component
            mvwprintw(window, y, 28, "%-15s", log.component.c_str());
            
            // Message (truncate if too long)
            int msg_width = width - 46;
            std::string msg = log.message;
            if ((int)msg.length() > msg_width) {
                msg = msg.substr(0, msg_width - 3) + "...";
            }
            mvwprintw(window, y, 44, "%s", msg.c_str());
            
            y++;
            logs_shown++;
        }
    }
}

bool LiveSystemPanel::handle_input(int ch) {
    switch (ch) {
        case KEY_UP:
            if (scroll_offset_ > 0) {
                scroll_offset_--;
                LOG_INFO("LiveSystemPanel", "Scrolled up");
            }
            return true;
        case KEY_DOWN:
            if (scroll_offset_ + 10 < (int)recent_logs_.size()) {
                scroll_offset_++;
                LOG_INFO("LiveSystemPanel", "Scrolled down");
            }
            return true;
        default:
            break;
    }
    return false;
}

void LiveSystemPanel::parse_system_data(const nlohmann::json& data) {
    try {
        metrics_.clear();
        
        if (data.contains("status")) {
            system_status_ = data["status"].get<std::string>();
        }
        
        if (data.contains("metrics") && data["metrics"].is_array()) {
            for (const auto& m : data["metrics"]) {
                SystemMetric metric;
                metric.name = m.value("name", "");
                metric.value = m.value("value", 0.0);
                metric.unit = m.value("unit", "");
                metric.status = m.value("status", "OK");
                metrics_.push_back(metric);
            }
        }
        
        LOG_INFO("LiveSystemPanel", "Parsed system data successfully");
    } catch (const std::exception& e) {
        LOG_ERROR("LiveSystemPanel", std::string("Failed to parse system data: ") + e.what());
    }
}

} // namespace prometheus::tui
