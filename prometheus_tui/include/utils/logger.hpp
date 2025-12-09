#pragma once

#include <string>
#include <vector>
#include <mutex>
#include <chrono>
#include <format>

namespace prometheus::tui {

enum class LogLevel {
    DEBUG,
    INFO,
    WARN,
    ERROR,
    CRITICAL
};

struct LogEntry {
    std::chrono::system_clock::time_point timestamp;
    LogLevel level;
    std::string source;
    std::string message;
    
    std::string format_timestamp() const;
    std::string level_str() const;
};

class Logger {
public:
    static Logger& instance();
    
    // Logging methods
    void debug(const std::string& source, const std::string& message);
    void info(const std::string& source, const std::string& message);
    void warn(const std::string& source, const std::string& message);
    void error(const std::string& source, const std::string& message);
    void critical(const std::string& source, const std::string& message);
    
    // Get recent log entries for console display
    std::vector<LogEntry> get_recent_logs(size_t count = 100) const;
    
    // Clear old logs
    void clear();
    
    // Configuration
    void set_min_level(LogLevel level);
    void set_max_entries(size_t max);
    
private:
    Logger() = default;
    ~Logger() = default;
    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;
    
    void log(LogLevel level, const std::string& source, const std::string& message);
    
    mutable std::mutex mutex_;
    std::vector<LogEntry> entries_;
    LogLevel min_level_ = LogLevel::DEBUG;
    size_t max_entries_ = 1000;
};

// Convenience macros
#define LOG_DEBUG(source, msg) prometheus::tui::Logger::instance().debug(source, msg)
#define LOG_INFO(source, msg) prometheus::tui::Logger::instance().info(source, msg)
#define LOG_WARN(source, msg) prometheus::tui::Logger::instance().warn(source, msg)
#define LOG_ERROR(source, msg) prometheus::tui::Logger::instance().error(source, msg)
#define LOG_CRITICAL(source, msg) prometheus::tui::Logger::instance().critical(source, msg)

} // namespace prometheus::tui
