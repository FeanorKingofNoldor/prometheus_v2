#include "utils/logger.hpp"
#include <algorithm>
#include <iomanip>
#include <sstream>

namespace prometheus::tui {

std::string LogEntry::format_timestamp() const {
    auto time_t = std::chrono::system_clock::to_time_t(timestamp);
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        timestamp.time_since_epoch()) % 1000;
    
    std::stringstream ss;
    ss << std::put_time(std::localtime(&time_t), "%H:%M:%S");
    ss << '.' << std::setfill('0') << std::setw(3) << ms.count();
    return ss.str();
}

std::string LogEntry::level_str() const {
    switch (level) {
        case LogLevel::DEBUG:    return "DEBUG";
        case LogLevel::INFO:     return "INFO";
        case LogLevel::WARN:     return "WARN";
        case LogLevel::ERROR:    return "ERROR";
        case LogLevel::CRITICAL: return "CRITICAL";
    }
    return "UNKNOWN";
}

Logger& Logger::instance() {
    static Logger instance;
    return instance;
}

void Logger::debug(const std::string& source, const std::string& message) {
    log(LogLevel::DEBUG, source, message);
}

void Logger::info(const std::string& source, const std::string& message) {
    log(LogLevel::INFO, source, message);
}

void Logger::warn(const std::string& source, const std::string& message) {
    log(LogLevel::WARN, source, message);
}

void Logger::error(const std::string& source, const std::string& message) {
    log(LogLevel::ERROR, source, message);
}

void Logger::critical(const std::string& source, const std::string& message) {
    log(LogLevel::CRITICAL, source, message);
}

void Logger::log(LogLevel level, const std::string& source, const std::string& message) {
    if (level < min_level_) {
        return;
    }
    
    std::lock_guard<std::mutex> lock(mutex_);
    
    LogEntry entry{
        .timestamp = std::chrono::system_clock::now(),
        .level = level,
        .source = source,
        .message = message
    };
    
    entries_.push_back(std::move(entry));
    
    // Trim if exceeding max
    if (entries_.size() > max_entries_) {
        entries_.erase(entries_.begin(), 
                      entries_.begin() + (entries_.size() - max_entries_));
    }
}

std::vector<LogEntry> Logger::get_recent_logs(size_t count) const {
    std::lock_guard<std::mutex> lock(mutex_);
    
    if (entries_.size() <= count) {
        return entries_;
    }
    
    return std::vector<LogEntry>(
        entries_.end() - count,
        entries_.end()
    );
}

void Logger::clear() {
    std::lock_guard<std::mutex> lock(mutex_);
    entries_.clear();
}

void Logger::set_min_level(LogLevel level) {
    std::lock_guard<std::mutex> lock(mutex_);
    min_level_ = level;
}

void Logger::set_max_entries(size_t max) {
    std::lock_guard<std::mutex> lock(mutex_);
    max_entries_ = max;
}

} // namespace prometheus::tui
