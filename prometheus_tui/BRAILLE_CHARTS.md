# Braille Charts Feature

## Overview
Added btop++-style braille/sparkline charts to the Prometheus TUI using Unicode braille patterns and block characters. These provide compact, high-resolution visualizations of trends directly in the terminal.

## What Are Braille Charts?

### Braille Patterns
- **Unicode Range**: U+2800 - U+28FF (Braille Patterns block)
- **Resolution**: Each braille character is a 2×4 grid of dots (8 pixels per character)
- **Advantages**: 
  - High resolution in small space
  - Universal terminal support
  - Elegant appearance
  - Low visual noise

### Block Characters  
For simpler single-line sparklines, we use Unicode block elements:
- `▁▂▃▄▅▆▇█` (vertical height indicators)
- Each character represents a different height level

## Implementation

### Core Utilities (`braille_chart.hpp/cpp`)

#### `inline_sparkline(data, width)`
Simple one-line sparkline using block characters (▁▂▃▄▅▆▇█):
```cpp
std::vector<double> pnl_trend = {-100, -50, 200, 500, 800, 1100, 1234.56};
std::string spark = inline_sparkline(pnl_trend, 15);
// Output: "▁▂▃▄▅▆▇█" (shows trend upward)
```

#### `BrailleChart::sparkline(data, width, height)`
Multi-line chart using braille patterns for higher resolution:
```cpp
std::vector<double> data = {/* ... */};
std::string chart = BrailleChart::sparkline(data, 20, 3);
// Output: 20-char wide, 3-char tall chart using braille dots
```

#### `BrailleChart::bars(values, max_height)`
Vertical bar chart for comparing values:
```cpp
std::vector<double> values = {0.3, 0.7, 0.5, 0.9};
auto bars = BrailleChart::bars(values, 8);
// Output: Vector of height-appropriate block characters
```

#### `BrailleChart::histogram(data, bins, width, height)`
Distribution visualization:
```cpp
std::vector<double> data = {/* values */};
std::string hist = BrailleChart::histogram(data, 10, 30, 1);
// Output: 30-char histogram showing distribution in 10 bins
```

## Where They're Used

### 1. OverviewPanel
**P&L Today Trend**
- Location: Below "P&L Today" value (Column 1)
- Shows: Intraday P&L progression
- Data: Last 7 time points
- Width: 15 characters
- Example: `▁▂▃▄▅▆▇` (trending upward throughout day)

### 2. ExecutionPanel  
**Volume Trend**
- Location: Below "Total Volume" (Column 3)
- Shows: Trading volume progression over last 10 periods
- Data: Recent volume measurements
- Width: 20 characters
- Example: `▂▃▄▅▆▇██` (increasing volume)

### 3. PortfolioRiskPanel
**P&L History**
- Location: Below "Total P&L" (Column 2)
- Shows: Cumulative P&L growth over 11 periods
- Data: Historical P&L snapshots
- Width: 18 characters
- Example: `▁▂▃▄▅▆▇█` (steady growth)

## Technical Details

### How Braille Patterns Work

Braille characters have 8 dot positions numbered:
```
1 4
2 5
3 6
7 8
```

Each dot can be on (1) or off (0), giving 2^8 = 256 possible patterns.

In code:
```cpp
static constexpr int BRAILLE_DOTS[8] = {
    0x01, 0x02, 0x04, 0x08,  // Left column: dots 1,2,3,7
    0x10, 0x20, 0x40, 0x80   // Right column: dots 4,5,6,8
};

wchar_t make_braille(int dots) {
    return 0x2800 + dots;  // Base braille + dot pattern
}
```

### Data Normalization

All charts normalize input data to [0, 1] range:
```cpp
normalized_value = (value - min) / (max - min)
```

This ensures:
- Consistent scaling
- Full use of available height
- Proper visual comparison

### Resampling

When data points exceed available width, we downsample:
```cpp
for (size_t i = 0; i < target_width; ++i) {
    size_t idx = (i * data.size()) / target_width;
    resampled.push_back(data[idx]);
}
```

This maintains the overall trend shape while fitting the space.

## Visual Examples

### Sparkline Progression
```
Data:  [1, 2, 3, 4, 5, 6, 7, 8]
Chart: ▁▂▃▄▅▆▇█

Data:  [8, 7, 6, 5, 4, 3, 2, 1]
Chart: █▇▆▅▄▃▂▁

Data:  [3, 5, 2, 8, 4, 6, 1, 7]
Chart: ▃▅▂█▄▆▁▇
```

### Trend Patterns
- **Steady Growth**: `▁▂▃▄▅▆▇█`
- **Steady Decline**: `█▇▆▅▄▃▂▁`
- **Volatile**: `▄█▂▇▁▆▃█`
- **Flat**: `▄▄▄▄▄▄▄▄`
- **Recovery**: `█▅▃▁▂▄▆█`

## Color Integration

Charts work with ncurses color pairs:
```cpp
wattron(window, COLOR_PAIR(COLOR_GREEN));
mvwprintw(window, y, x, "%s", sparkline.c_str());
wattroff(window, COLOR_PAIR(COLOR_GREEN));
```

Color-coded sparklines:
- **Green**: Positive/upward trends
- **Red**: Negative/downward trends  
- **Yellow**: Warning/volatile
- **White**: Neutral/historical

## Performance Characteristics

### Memory
- Minimal: Only stores normalized data vectors
- No persistent buffers
- Generated on-demand during render

### CPU
- **O(n)** where n = number of data points
- Fast normalization and resampling
- No complex calculations
- Suitable for real-time updates

### Rendering
- Pure UTF-8 strings
- Single `mvwprintw()` call per chart
- No special ncurses features required
- Works on any UTF-8 terminal

## Future Enhancements

### Short Term
1. **Filled Area Charts**: Shade area under sparkline
2. **Multiple Series**: Overlay two trends in one chart
3. **Axis Labels**: Min/max values at chart edges
4. **Color Gradients**: Smooth color transitions based on value

### Medium Term  
1. **Live Updates**: Animated chart updates
2. **Zoom/Pan**: Interactive chart navigation
3. **Tooltips**: Hover for exact values
4. **Thresholds**: Horizontal lines for targets/limits

### Long Term
1. **Custom Braille Rendering**: Full 2D braille canvas
2. **Chart Types**: Candlesticks, scatter plots, heatmaps
3. **Real Braille Math**: Proper line drawing algorithms
4. **Export**: Save charts as images or SVG

## Terminal Compatibility

### Tested On
- ✅ Arch Linux / bash
- ✅ Modern terminals with UTF-8 support
- ✅ Warp terminal
- ✅ Alacritty, Kitty, iTerm2

### Requirements
- UTF-8 locale
- Unicode font with braille patterns
- Block characters (▁▂▃▄▅▆▇█) support

### Fallback
If braille/blocks don't display:
- Could fall back to ASCII art (`-`, `=`, `#`)
- Could use simple `*` character plots
- Could display numeric values instead

## Usage Guidelines

### When to Use Sparklines
✅ **Good for:**
- Showing trends at a glance
- Compact space requirements
- Pattern recognition
- Comparing multiple trends side-by-side

❌ **Avoid for:**
- Precise value reading
- Complex multi-variable analysis
- When exact numbers matter more than trends
- Very noisy data (needs smoothing first)

### Data Preparation
1. **Smooth noisy data**: Apply moving average if needed
2. **Consistent intervals**: Use evenly-spaced time points
3. **Reasonable point count**: 10-50 points work best
4. **Handle outliers**: Consider capping extreme values

### Visual Design
- **Position**: Place near related numeric values
- **Width**: 10-25 characters is optimal
- **Context**: Add labels to indicate what's shown
- **Color**: Match sparkline color to value color

## Example Integration

```cpp
// In your panel render method:

// 1. Prepare data
std::vector<double> trend_data = get_historical_values();

// 2. Generate sparkline
std::string spark = inline_sparkline(trend_data, 20);

// 3. Color-code based on trend
int color = trend_data.back() > trend_data.front() 
    ? COLOR_GREEN : COLOR_RED;

// 4. Render
wattron(window, COLOR_PAIR(color));
mvwprintw(window, row, col, "%s", spark.c_str());
wattroff(window, COLOR_PAIR(color));
```

## Conclusion

Braille charts add professional polish and information density to the TUI without cluttering the interface. They follow the btop++ style of elegant, minimalist data visualization that's perfect for terminal environments.

The implementation is lightweight, performant, and easily extensible for future chart types and features.
