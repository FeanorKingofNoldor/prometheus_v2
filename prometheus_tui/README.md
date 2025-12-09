# Prometheus TUI

Terminal-based monitoring UI for Prometheus v2 using C++20 and ncurses.

## Overview

Prometheus TUI is a Bloomberg-style terminal interface for monitoring the Prometheus v2 quantitative trading system. Designed for headless servers and SSH access, it provides real-time system status, market regime monitoring, portfolio tracking, and command execution capabilities.

## Features

- **Bloomberg-style Layout**: Top status bar, left navigation, main panel area, alerts, console
- **11 Monitoring Panels**:
  - Overview: System KPIs and health
  - Regime & STAB: Market regime and stability metrics
  - Fragility: Soft targets and vulnerable entities
  - Assessment & Universe: Strategy signals
  - Portfolio & Risk: Positions and risk metrics
  - Execution: Orders and fills
  - Meta & Experiments: Intelligence layer
  - Live System: Pipeline status
  - ANT_HILL: Visualization data
  - Geo: Geographic exposure
  - Terminal: Command execution
  - Kronos Chat: NL interface

- **Workspace Management**: 5 predefined workspaces (Overview, Trading, Research, Monitoring, Global)
- **Real-time Updates**: Auto-refresh with configurable intervals
- **Keyboard-Driven**: Efficient navigation without mouse
- **SSH-Friendly**: Full functionality over remote connections

## Quick Start

```bash
# Build
make

# Run
make run

# Or directly
./build/prometheus_tui
```

## Prerequisites

- Linux (tested on Arch Linux)
- GCC 15+ with C++20 support
- ncurses, curl, fmt libraries
- Prometheus backend API running on localhost:8000

See [SETUP.md](SETUP.md) for detailed installation instructions.

## Architecture

```
Application
├── UIManager (ncurses rendering)
├── ApiClient (HTTP client)
├── AppState (global state)
├── WorkspaceManager (layout management)
├── CommandBus (control operations)
└── Panels (11 panel implementations)
```

Built with modern C++20 features:
- Smart pointers and RAII
- std::format for string formatting
- Thread-safe design
- Clean separation of concerns

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Tab` | Cycle through panels |
| `W` | Switch workspace |
| `R` | Refresh current panel |
| `Q` | Quit application |
| `H` / `F1` | Show help |
| `Arrow Keys` | Navigate within panels |
| `Home` / `End` | Jump to top/bottom |
| `PgUp` / `PgDn` | Page up/down |

## Development

```bash
# Debug build
make debug

# Release build
make release

# Clean
make clean
```

## Project Structure

```
prometheus_tui/
├── Makefile              # Build configuration
├── README.md             # This file
├── SETUP.md              # Detailed setup guide
├── include/              # Header files
│   ├── application.hpp
│   ├── api_client.hpp
│   ├── app_state.hpp
│   ├── ui_manager.hpp
│   ├── workspace_manager.hpp
│   ├── command_bus.hpp
│   ├── panels/           # Panel interfaces
│   └── utils/            # Utilities
├── src/                  # Implementation files
│   ├── main.cpp
│   ├── *.cpp
│   ├── panels/
│   └── utils/
└── external/             # Third-party dependencies
    ├── json.hpp          # nlohmann/json
    └── asio/             # Standalone ASIO
```

## Configuration

Create `config.json` in the working directory:

```json
{
  "api_base_url": "http://localhost:8000",
  "refresh_interval_seconds": 10,
  "default_workspace": "overview",
  "color_scheme": "bloomberg"
}
```

## Backend API

The TUI connects to the Prometheus monitoring backend. Ensure it's running:

```bash
cd ../prometheus/monitoring
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## License

Part of the Prometheus v2 project.

## Related Projects

- [prometheus_c2](../prometheus_c2/) - Godot-based GUI client
- [prometheus/monitoring](../prometheus/monitoring/) - Backend API server
