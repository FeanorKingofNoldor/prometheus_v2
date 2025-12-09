#pragma once

#include <vector>
#include <string>
#include <cstddef>

namespace prometheus::tui {

/**
 * Braille chart renderer for terminal-based graphs.
 * Uses Unicode braille patterns (U+2800 - U+28FF) for high-resolution charts.
 * Each braille character is a 2x4 grid of dots, providing 8 pixels per character.
 */
class BrailleChart {
public:
    /**
     * Create a sparkline (mini line chart) using braille characters.
     * @param data Vector of data points to plot
     * @param width Width in characters (each char = 2 horizontal pixels)
     * @param height Height in characters (each char = 4 vertical pixels)
     * @return String containing braille characters representing the chart
     */
    static std::string sparkline(const std::vector<double>& data, 
                                 size_t width, 
                                 size_t height);
    
    /**
     * Create a bar chart using braille patterns.
     * @param values Vector of values to display as bars
     * @param max_height Maximum height in characters
     * @return Vector of strings, one per bar
     */
    static std::vector<std::string> bars(const std::vector<double>& values,
                                         size_t max_height);
    
    /**
     * Create a histogram using braille characters.
     * @param data Data points to create histogram from
     * @param bins Number of bins
     * @param width Width in characters
     * @param height Height in characters
     * @return String containing the histogram
     */
    static std::string histogram(const std::vector<double>& data,
                                 size_t bins,
                                 size_t width,
                                 size_t height);

private:
    // Braille dot positions (1-indexed as per Unicode standard)
    // Dots are numbered:
    //   1 4
    //   2 5
    //   3 6
    //   7 8
    static constexpr int BRAILLE_DOTS[8] = {
        0x01, 0x02, 0x04, 0x08,  // Left column: dots 1,2,3,7
        0x10, 0x20, 0x40, 0x80   // Right column: dots 4,5,6,8
    };
    
    static constexpr wchar_t BRAILLE_BASE = 0x2800;
    
    // Helper to create braille character from dot pattern
    static wchar_t make_braille(int dots);
    
    // Helper to normalize data to range [0, 1]
    static std::vector<double> normalize(const std::vector<double>& data,
                                        double min_val, double max_val);
};

/**
 * Simple sparkline for inline display (single line of text).
 */
std::string inline_sparkline(const std::vector<double>& data, size_t width = 20);

/**
 * Create a trend indicator using braille patterns.
 * Shows last N data points as a mini-chart.
 */
std::string trend_indicator(const std::vector<double>& data, 
                           size_t width = 10,
                           size_t height = 1);

} // namespace prometheus::tui
