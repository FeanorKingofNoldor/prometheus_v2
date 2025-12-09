# Prometheus TUI - Setup Guide

## System Requirements

- **OS**: Linux (tested on Arch Linux)
- **C++ Compiler**: GCC 13+ or Clang 16+ with C++20 support
- **CMake**: 3.20 or higher
- **Terminal**: Any ANSI-compatible terminal (xterm, urxvt, kitty, alacritty, etc.)

## Dependencies

### Already Installed ✓
- GCC 15.2.1 (excellent C++20 support)
- ncurses 6.5-4
- curl 8.17.0-2
- fmt 12.1.0-1

### Need to Install

Run the following command to install missing dependencies:

```bash
sudo pacman -S --needed cmake nlohmann-json boost
```

**Packages to install:**
- `cmake` - Build system (need 3.20+)
- `nlohmann-json` - Header-only JSON library for Modern C++
- `boost` - For Asio async I/O (or we can use standalone asio)

### Alternative: Header-Only Libraries

If you prefer not to use system packages, you can use header-only versions:

```bash
cd prometheus_tui
mkdir -p external

# nlohmann/json
curl -L https://github.com/nlohmann/json/releases/download/v3.11.3/json.hpp \
  -o external/json.hpp

# asio standalone (no Boost dependency)
git clone --depth 1 https://github.com/chriskohlhoff/asio.git external/asio
```

## Building from Source

```bash
cd prometheus_tui
mkdir build
cd build
cmake ..
make -j$(nproc)
```

## Backend API Setup

The TUI requires the Prometheus monitoring backend to be running:

```bash
# From prometheus_v2 root
cd prometheus/monitoring
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Verify the API is accessible:
```bash
curl http://localhost:8000/api/status/overview
```

## Running the TUI

```bash
cd build
./prometheus_tui
```

### Configuration

Edit `config.json` to customize:
- API base URL (default: http://localhost:8000)
- Refresh intervals
- Color scheme
- Default workspace

## Keyboard Shortcuts

- **Tab**: Cycle through panels
- **W**: Switch workspace
- **R**: Refresh current panel
- **Q**: Quit
- **H** or **F1**: Help
- **Arrow keys**: Navigate within panels
- **Home/End**: Jump to top/bottom
- **PgUp/PgDn**: Page up/down

## Troubleshooting

### "Backend connection failed"
- Ensure backend is running on port 8000
- Check firewall settings
- Verify URL in configuration

### Terminal display issues
- Ensure terminal supports 256 colors: `echo $TERM`
- Try setting: `export TERM=xterm-256color`
- Minimum terminal size: 80x24

### Build errors
- Verify C++20 support: `g++ -std=c++20 -dM -E -x c++ /dev/null | grep __cplusplus`
- Should output: `#define __cplusplus 202002L` or higher

### Link errors
- Check pkg-config: `pkg-config --libs ncurses libcurl`
- Verify all dependencies installed

## Development

### Project Structure
```
prometheus_tui/
├── CMakeLists.txt          # Build configuration
├── README.md               # User documentation
├── SETUP.md                # This file
├── config.json             # Runtime configuration
├── include/                # Header files
│   ├── application.hpp
│   ├── api_client.hpp
│   ├── app_state.hpp
│   ├── ui_manager.hpp
│   ├── workspace_manager.hpp
│   ├── panels/
│   └── utils/
└── src/                    # Implementation files
    ├── main.cpp
    ├── application.cpp
    └── ...
```

### Adding New Panels

1. Create header in `include/panels/your_panel.hpp`
2. Inherit from `BasePanel`
3. Implement required methods: `on_activated`, `refresh`, `render`, `handle_input`
4. Add to `WorkspaceManager` workspace definitions
5. Register in `Application::init_panels()`

### Code Style

- Follow C++ Core Guidelines
- Use modern C++20 features (concepts, ranges, coroutines where appropriate)
- RAII for resource management
- Smart pointers over raw pointers
- `const` correctness
- Meaningful variable names

### Testing

```bash
# Build with tests
cmake -DBUILD_TESTS=ON ..
make
ctest
```

## License

Part of the Prometheus v2 project.
