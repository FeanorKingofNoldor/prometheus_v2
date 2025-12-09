# Prometheus TUI - 27" Monitor Layout Design

## Display Specifications

**Target Resolution**: 2560x1440 (typical 27" QHD) or 1920x1080 (Full HD)
**Terminal Size**: ~200 cols × 60 rows (with reasonable font size)
**Minimum Fallback**: 80×24 (for SSH from smaller terminals)

## Enhanced Bloomberg-Style Layout

### Full Screen Layout (200×60)

```
┌─ PROMETHEUS C2 ───────────────────────────────────────────────── MODE: LIVE ─ 2025-12-08 13:56:53 UTC ─────────────────────────────────────────────────┐
│ ┌─ KPI Bar ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ P&L Today: +1,234.56 (↑2.3%) │ P&L MTD: +5,432.10 │ P&L YTD: +12,345.67 │ MaxDD: -0.042 │ STAB: 0.872 │ LEV: 1.45 │ NetExp: 0.125 │ GrossExp: 1.234 │ │
│ └────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│ ┌─Workspaces────┐ ┌─ Main Panel Area ────────────────────────────────────────────────────────────────────────────┐ ┌─Alerts & Status─────────┐ │
│ │• Overview      │ │                                                                                              │ │[CRITICAL] None           │ │
│ │  Trading       │ │  ╔═══════════════════════════════════════════════════════════════════════════════════════╗  │ │[ERROR] None              │ │
│ │  Research      │ │  ║ OVERVIEW - System Health & Performance                                            ║  │ │[WARN] High volatility  │ │
│ │  Monitoring    │ │  ╚═══════════════════════════════════════════════════════════════════════════════════════╝  │ │       detected in US_EQ  │ │
│ │  Global View   │ │                                                                                              │ │[INFO] Backtest complete │ │
│ └────────────────┘ │  Performance Metrics                    Risk Metrics                                         │ │       job_abc123         │ │
│ ┌─Panels─────────┐ │  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐                 │ ├──────────────────────────┤ │
│ │→Overview       │ │  │ Metric          Value    Change │   │ Metric          Value    Status │                 │ │System Status             │ │
│ │ Regime & STAB  │ │  ├─────────────────────────────────┤   ├─────────────────────────────────┤                 │ │ Pipelines: 3/3 Running   │ │
│ │ Fragility      │ │  │ P&L Today     1234.56   +2.3%  │   │ VaR (95%)      -123.45    OK   │                 │ │ Last Update: 2s ago      │ │
│ │ Assessment     │ │  │ Sharpe Ratio    2.34    +0.15  │   │ CVaR (95%)     -156.78    OK   │                 │ │ Backend: Connected ✓     │ │
│ │ Portfolio      │ │  │ Return/DD       28.5    +1.2   │   │ Net Exposure     0.125    OK   │                 │ │ Memory: 234MB / 2GB      │ │
│ │ Execution      │ │  │ Win Rate       67.3%    +2.1%  │   │ Gross Exp        1.234  WARN   │                 │ └──────────────────────────┘ │
│ │ Meta/Exp       │ │  │ Max DD        -0.042    -0.01  │   │ Leverage         1.450    OK   │                 │ ┌─Live Console─────────────┐ │
│ │ Live System    │ │  └─────────────────────────────────┘   │ Stress Test      PASS     ✓   │                 │ │[13:56:52] INFO: Panel    │ │
│ │ ANT_HILL       │ │                                         └─────────────────────────────────┘                 │ │  activated: Overview     │ │
│ │ Geo            │ │  Market Regimes                                                                             │ │[13:56:45] INFO: API call │ │
│ │ Terminal       │ │  ┌────────────────────────────────────────────────────────────────────────────────────┐    │ │  success: /api/status/   │ │
│ │ Kronos Chat    │ │  │ Region  Regime       Confidence  Duration  Volatility  Momentum  Next Review      │    │ │  overview                │ │
│ └────────────────┘ │  ├────────────────────────────────────────────────────────────────────────────────────┤    │ │[13:56:40] WARN: High vol │ │
│ ┌─Quick Actions──┐ │  │ US      GROWTH         85%       12d       HIGH        STRONG    2025-12-09 09:00 │    │ │  detected                │ │
│ │[R] Refresh     │ │  │ EU      DEFENSIVE      72%       18d       MEDIUM      WEAK      2025-12-09 09:00 │    │ │[13:56:32] INFO: Backtest │ │
│ │[B] Backtest    │ │  │ ASIA    TRANSITION     45%        3d       HIGH        NEUTRAL   2025-12-08 21:00 │    │ │  submitted: job_abc123   │ │
│ │[C] Config      │ │  │ GLOBAL  RISK-OFF       91%        7d       VERY HIGH   NEGATIVE  2025-12-08 18:00 │    │ │> _                       │ │
│ │[J] Jobs        │ │  └────────────────────────────────────────────────────────────────────────────────────┘    │ └──────────────────────────┘ │
│ │[H] Help        │ │                                                                                             │ ┌─Active Jobs──────────────┐ │
│ └────────────────┘ │  Top Positions (by Exposure)                                                                │ │1. backtest_abc123        │ │
│                    │  ┌────────────────────────────────────────────────────────────────────────────────────┐    │ │   Status: RUNNING (45%)  │ │
│ ┌─Network Status─┐ │  │ Ticker   Position    Value      %Port  Beta   Sector        P&L Today  Alerts    │    │ │   Started: 13:45         │ │
│ │Latency: 12ms   │ │  ├────────────────────────────────────────────────────────────────────────────────────┤    │ │2. synthetic_xyz789       │ │
│ │Throughput: OK  │ │  │ AAPL     +1500    +225,000    12.5%  1.2    Technology    +2,340      -         │    │ │   Status: PENDING        │ │
│ │Last Sync: 1s   │ │  │ MSFT     +800     +280,000    15.6%  1.1    Technology    +1,120      -         │    │ │   Queued: 13:50          │ │
│ └────────────────┘ │  │ GOOGL    -500     -65,000      3.6%  1.0    Technology      -890      -         │    │ └──────────────────────────┘ │
│                    │  │ JPM      +2000    +340,000    18.9%  1.4    Financials    +4,560      ⚠        │    │                            │
│                    │  │ XOM      +1200    +125,000     6.9%  0.8    Energy        -1,234      -         │    │                            │
│                    │  └────────────────────────────────────────────────────────────────────────────────────┘    │                            │
│                    │                                                                                             │                            │
│                    └─────────────────────────────────────────────────────────────────────────────────────────────┘                            │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
[Tab] Next Panel │ [Shift+Tab] Prev Panel │ [W] Workspaces │ [1-9] Panel Shortcuts │ [R] Refresh │ [/] Search │ [Q] Quit │ [F1] Help │ [Esc] Back
```

## Layout Zones & Dimensions

### Top Bar (Row 0-2): KPI Dashboard
- **Height**: 3 rows
- **Purpose**: Dense KPI display, system mode, timestamp
- **Content**: 
  - Mode indicator, date/time (always visible)
  - 8-10 key metrics in compact format
  - Color-coded indicators (green/red for P&L, yellow for warnings)

### Left Sidebar (Rows 3-58): Navigation & Status
- **Width**: 20 columns
- **Sections**:
  1. Workspaces (5 items) - 6 rows
  2. Panels (11 items) - 13 rows
  3. Quick Actions (5 items) - 8 rows
  4. Network Status - 5 rows
  5. Extra space for custom widgets

### Main Panel Area (Rows 3-58, Center): Primary Content
- **Width**: ~135 columns (flexible)
- **Height**: 55 rows
- **Purpose**: Active panel content
- **Features**:
  - Large tables with many columns
  - Multiple sub-sections per panel
  - Rich formatting with borders
  - Scrollable content areas
  - Mini-charts using ASCII/Unicode characters

### Right Sidebar (Rows 3-58): Live Updates
- **Width**: 28 columns
- **Sections**:
  1. Alerts by severity (8-10 rows)
  2. System status widget (5 rows)
  3. Live console log (15-20 rows, scrollable)
  4. Active jobs tracker (10-12 rows)
  5. Quick stats or mini-panels

### Bottom Status Bar (Row 59)
- **Height**: 1 row
- **Purpose**: Hotkey hints, context-sensitive help
- **Content**: Changes based on active panel

## Enhanced Features for Large Display

### 1. Multi-Column Tables
```
┌────────────────────────────────────────────────────────────────────────────┐
│ Asset    Side  Qty    Entry      Current    P&L      %Chg   Beta  Vol  IV │
├────────────────────────────────────────────────────────────────────────────┤
│ AAPL     LONG  1500   148.23     150.45    +3,330   +1.5%  1.2   M    32% │
│ MSFT     LONG   800   375.80     377.20    +1,120   +0.4%  1.1   L    28% │
```

### 2. In-Panel Mini-Visualizations
```
P&L Trend (Last 30 Days):
    ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄

Volume Profile:
High   ████████████████████  12.5M
Med    ████████████          8.2M
Low    ██████                4.1M
```

### 3. Side-by-Side Panels (Split View)
When screen is large enough, show 2 panels simultaneously:
```
┌─ Portfolio ──────────────────┐ ┌─ Risk Metrics ───────────────┐
│ Positions table...           │ │ VaR/CVaR charts...           │
│                              │ │                              │
└──────────────────────────────┘ └──────────────────────────────┘
```

### 4. Rich Data Tables with Sorting
- Column headers clickable/highlightable
- Sort indicators (↑↓)
- Color coding for positive/negative values
- Sparklines in cells
- Expandable rows for details

### 5. Dashboard Widgets
Small info boxes that can be scattered around:
```
┌─Market Hours─┐  ┌─Connection─┐  ┌─Memory─────┐
│ 🟢 OPEN      │  │ ✓ API      │  │ 234 / 2048 │
│ Closes: 16:00│  │ ✓ DB       │  │ [████░░░░] │
└──────────────┘  └────────────┘  └────────────┘
```

## Adaptive Layout Strategy

The UI will detect terminal size and adapt:

### Large (≥180 cols): Full Featured
- Show all sections
- Wide tables with many columns
- Side-by-side panels option
- Rich formatting

### Medium (120-179 cols): Standard
- Hide some widgets
- Narrower tables (fewer columns)
- Single panel at a time
- Simplified formatting

### Small (80-119 cols): Compact
- Minimal navigation
- Essential columns only
- Single focused panel
- Basic formatting

### Minimum (80 cols): Fallback
- Text-only mode
- Scrollable content
- Essential info only

## Panel-Specific Enhancements for 27"

### Overview Panel
- 3-4 sections visible simultaneously
- Performance metrics + Risk metrics + Regimes + Positions
- No scrolling needed for summary view

### Portfolio Panel
- 20-30 positions visible at once
- 12-15 columns of data per position
- Real-time P&L updates with color flashing
- Mini chart for each position (inline sparklines)

### Regime Panel
- Multiple markets side-by-side
- Historical regime transitions timeline
- Probability distributions as ASCII histograms
- Factor exposures as bar charts

### Terminal Panel
- Split: Command input (bottom) + Output (top scrolling area)
- Command history sidebar
- Syntax highlighting for commands
- Auto-completion hints

### ANT_HILL Panel
- ASCII art scene representation using Unicode box-drawing
- Multiple views simultaneously (hierarchy + metrics + trace)
- Large node/edge tables

## Color Scheme for Large Display

```cpp
// High-contrast Bloomberg theme optimized for 27" displays
COLOR_PAIR_BG_PRIMARY      = Black
COLOR_PAIR_TEXT_PRIMARY    = Bright White / Cyan
COLOR_PAIR_TEXT_SECONDARY  = Gray / Dim White
COLOR_PAIR_ACCENT_GREEN    = Bright Green     // Positive, Success
COLOR_PAIR_ACCENT_RED      = Bright Red       // Negative, Error
COLOR_PAIR_ACCENT_YELLOW   = Bright Yellow    // Warning
COLOR_PAIR_ACCENT_BLUE     = Bright Blue      // Info, Headers
COLOR_PAIR_ACCENT_MAGENTA  = Bright Magenta   // Highlight, Selection
COLOR_PAIR_BORDER          = Cyan             // Window borders
COLOR_PAIR_HEADER          = Black on Cyan    // Panel headers
COLOR_PAIR_STATUS_OK       = Green on Black   // Status indicators
COLOR_PAIR_STATUS_WARN     = Yellow on Black
COLOR_PAIR_STATUS_ERROR    = Red on Black
```

## Implementation Notes

1. **Dynamic Sizing**: Detect terminal size on startup and resize
2. **Responsive Layout**: Adjust content based on available space
3. **Minimum Viable**: Always degrade gracefully to 80×24
4. **Unicode Support**: Use box-drawing characters (─│┌┐└┘├┤┬┴┼)
5. **Bold/Dim**: Use text attributes for hierarchy
6. **Scroll Indicators**: Show ↑↓ when content overflows
7. **Focus Management**: Clear visual indication of active area
8. **Efficient Rendering**: Only redraw changed regions

## Testing Matrix

- [ ] 200×60 (target 27" QHD)
- [ ] 160×50 (27" with larger font)
- [ ] 120×40 (standard medium)
- [ ] 80×24 (minimum SSH fallback)
- [ ] Resize handling (live terminal resize)
- [ ] Different terminal emulators (alacritty, kitty, urxvt, xterm)
