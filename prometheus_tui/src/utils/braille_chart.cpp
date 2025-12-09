#include "utils/braille_chart.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <codecvt>
#include <locale>

namespace prometheus::tui {

wchar_t BrailleChart::make_braille(int dots) {
    return BRAILLE_BASE + dots;
}

std::vector<double> BrailleChart::normalize(const std::vector<double>& data,
                                           double min_val, double max_val) {
    if (data.empty()) return {};
    
    // Auto-detect range if not provided
    if (min_val == max_val) {
        min_val = *std::min_element(data.begin(), data.end());
        max_val = *std::max_element(data.begin(), data.end());
    }
    
    // Handle flat line
    if (min_val == max_val) {
        return std::vector<double>(data.size(), 0.5);
    }
    
    std::vector<double> result;
    result.reserve(data.size());
    double range = max_val - min_val;
    
    for (double val : data) {
        result.push_back((val - min_val) / range);
    }
    
    return result;
}

std::string BrailleChart::sparkline(const std::vector<double>& data, 
                                   size_t width, 
                                   size_t height) {
    if (data.empty() || width == 0 || height == 0) return "";
    
    // Normalize data to [0, 1]
    auto normalized = normalize(data, 0, 0);
    
    // Calculate pixels dimensions
    size_t pixel_width = width * 2;   // 2 pixels per character horizontally
    size_t pixel_height = height * 4;  // 4 pixels per character vertically
    
    // Resample data to fit width
    std::vector<double> resampled;
    if (data.size() <= pixel_width) {
        resampled = normalized;
    } else {
        // Downsample
        for (size_t i = 0; i < pixel_width; ++i) {
            size_t idx = (i * data.size()) / pixel_width;
            resampled.push_back(normalized[idx]);
        }
    }
    
    // Create grid of dots
    std::vector<std::vector<bool>> grid(height, std::vector<bool>(width * 2, false));
    
    // Plot line
    for (size_t x = 0; x < resampled.size() && x < pixel_width; ++x) {
        int y = static_cast<int>((1.0 - resampled[x]) * (pixel_height - 1));
        if (y >= 0 && y < static_cast<int>(pixel_height)) {
            size_t row = y / 4;
            if (row < height) {
                grid[row][x] = true;
            }
        }
    }
    
    // Convert grid to braille characters
    std::wstring_convert<std::codecvt_utf8<wchar_t>> converter;
    std::string result;
    
    for (size_t row = 0; row < height; ++row) {
        for (size_t col = 0; col < width; ++col) {
            int dots = 0;
            
            // Left column of braille char (2 pixels wide, 4 pixels tall)
            size_t x1 = col * 2;
            size_t x2 = col * 2 + 1;
            
            for (int dy = 0; dy < 4; ++dy) {
                size_t y = row * 4 + dy;
                if (y < grid.size()) {
                    if (x1 < grid[row].size() && grid[row][x1]) {
                        dots |= BRAILLE_DOTS[dy];
                    }
                    if (x2 < grid[row].size() && grid[row][x2]) {
                        dots |= BRAILLE_DOTS[dy + 4];
                    }
                }
            }
            
            wchar_t wch = make_braille(dots);
            result += converter.to_bytes(wch);
        }
        if (row < height - 1) result += "\n";
    }
    
    return result;
}

std::string inline_sparkline(const std::vector<double>& data, size_t width) {
    if (data.empty() || width == 0) return "";
    
    // Normalize
    double min_val = *std::min_element(data.begin(), data.end());
    double max_val = *std::max_element(data.begin(), data.end());
    
    if (min_val == max_val) {
        // Middle bar character
        std::string result;
        for (size_t i = 0; i < width; ++i) {
            result += "▄";
        }
        return result;
    }
    
    // Resample to width
    std::vector<double> resampled;
    for (size_t i = 0; i < width; ++i) {
        size_t idx = (i * data.size()) / width;
        double val = (data[idx] - min_val) / (max_val - min_val);
        resampled.push_back(val);
    }
    
    // Use block characters for simple sparkline
    // ▁▂▃▄▅▆▇█
    const char* blocks[] = {
        " ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"
    };
    
    std::string result;
    for (double val : resampled) {
        int idx = static_cast<int>(val * 8);
        if (idx < 0) idx = 0;
        if (idx > 8) idx = 8;
        result += blocks[idx];
    }
    
    return result;
}

std::string trend_indicator(const std::vector<double>& data, 
                           size_t width,
                           size_t height) {
    // For single-line indicators, use simple block characters
    if (height == 1) {
        return inline_sparkline(data, width);
    }
    
    // For multi-line, use braille
    return BrailleChart::sparkline(data, width, height);
}

std::vector<std::string> BrailleChart::bars(const std::vector<double>& values,
                                           size_t max_height) {
    std::vector<std::string> result;
    if (values.empty() || max_height == 0) return result;
    
    // Normalize values
    double max_val = *std::max_element(values.begin(), values.end());
    if (max_val == 0) max_val = 1.0;
    
    // Vertical bar characters
    const char* bars_chars[] = {" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"};
    
    for (double val : values) {
        double normalized = val / max_val;
        int bar_height = static_cast<int>(normalized * 8);
        if (bar_height < 0) bar_height = 0;
        if (bar_height > 8) bar_height = 8;
        result.push_back(bars_chars[bar_height]);
    }
    
    return result;
}

std::string BrailleChart::histogram(const std::vector<double>& data,
                                   size_t bins,
                                   size_t width,
                                   size_t height) {
    if (data.empty() || bins == 0) return "";
    
    // Create bins
    double min_val = *std::min_element(data.begin(), data.end());
    double max_val = *std::max_element(data.begin(), data.end());
    double bin_width = (max_val - min_val) / bins;
    
    std::vector<int> bin_counts(bins, 0);
    for (double val : data) {
        int bin = static_cast<int>((val - min_val) / bin_width);
        if (bin >= static_cast<int>(bins)) bin = bins - 1;
        if (bin < 0) bin = 0;
        bin_counts[bin]++;
    }
    
    // Convert to bar chart
    std::vector<double> normalized_bins;
    int max_count = *std::max_element(bin_counts.begin(), bin_counts.end());
    for (int count : bin_counts) {
        normalized_bins.push_back(static_cast<double>(count) / max_count);
    }
    
    return inline_sparkline(normalized_bins, width);
}

} // namespace prometheus::tui
