#pragma once

#include <ncurses.h>

namespace prometheus::tui::colors {

// Color pair IDs for ncurses
enum ColorPair {
    DEFAULT = 0,
    
    // Text colors
    TEXT_PRIMARY = 1,
    TEXT_SECONDARY = 2,
    TEXT_DIM = 3,
    
    // Accent colors
    ACCENT_GREEN = 4,      // Positive, Success
    ACCENT_RED = 5,        // Negative, Error
    ACCENT_YELLOW = 6,     // Warning
    ACCENT_BLUE = 7,       // Info, Headers
    ACCENT_CYAN = 8,       // Highlights
    ACCENT_MAGENTA = 9,    // Selection
    
    // UI elements
    BORDER = 10,
    HEADER = 11,
    HEADER_ACTIVE = 12,
    
    // Status indicators
    STATUS_OK = 13,
    STATUS_WARN = 14,
    STATUS_ERROR = 15,
    STATUS_CRITICAL = 16,
    
    // Special
    KPI_POSITIVE = 17,
    KPI_NEGATIVE = 18,
    KPI_NEUTRAL = 19,
    
    // Navigation
    NAV_ACTIVE = 20,
    NAV_INACTIVE = 21,
    
    MAX_PAIRS = 22
};

// Initialize all color pairs
inline void init_color_pairs() {
    // Assume 256-color terminal support
    start_color();
    use_default_colors();
    
    // Text colors
    init_pair(TEXT_PRIMARY, COLOR_WHITE, -1);
    init_pair(TEXT_SECONDARY, 250, -1);  // Light gray
    init_pair(TEXT_DIM, 240, -1);        // Dim gray
    
    // Accent colors (bright versions)
    init_pair(ACCENT_GREEN, COLOR_GREEN, -1);
    init_pair(ACCENT_RED, COLOR_RED, -1);
    init_pair(ACCENT_YELLOW, COLOR_YELLOW, -1);
    init_pair(ACCENT_BLUE, COLOR_BLUE, -1);
    init_pair(ACCENT_CYAN, COLOR_CYAN, -1);
    init_pair(ACCENT_MAGENTA, COLOR_MAGENTA, -1);
    
    // UI elements
    init_pair(BORDER, COLOR_CYAN, -1);
    init_pair(HEADER, COLOR_BLACK, COLOR_CYAN);
    init_pair(HEADER_ACTIVE, COLOR_BLACK, COLOR_GREEN);
    
    // Status indicators
    init_pair(STATUS_OK, COLOR_GREEN, -1);
    init_pair(STATUS_WARN, COLOR_YELLOW, -1);
    init_pair(STATUS_ERROR, COLOR_RED, -1);
    init_pair(STATUS_CRITICAL, COLOR_WHITE, COLOR_RED);
    
    // KPI colors
    init_pair(KPI_POSITIVE, COLOR_GREEN, -1);
    init_pair(KPI_NEGATIVE, COLOR_RED, -1);
    init_pair(KPI_NEUTRAL, COLOR_WHITE, -1);
    
    // Navigation
    init_pair(NAV_ACTIVE, COLOR_BLACK, COLOR_CYAN);
    init_pair(NAV_INACTIVE, COLOR_WHITE, -1);
}

} // namespace prometheus::tui::colors
