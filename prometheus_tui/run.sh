#!/bin/bash
# Prometheus TUI launcher script

# Ensure we're in the right directory
cd "$(dirname "$0")"

# Check if built
if [ ! -f "build/prometheus_tui" ]; then
    echo "Building prometheus_tui..."
    make
fi

# Set terminal to support 256 colors
export TERM=xterm-256color

# Clear screen first
clear

# Run the TUI
./build/prometheus_tui

# Clear screen after exit
clear

echo "Prometheus TUI exited."
