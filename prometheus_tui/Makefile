# Prometheus TUI Makefile
# C++20 Terminal UI for Prometheus v2 Monitoring

CXX := g++
CXXFLAGS := -std=c++20 -Wall -Wextra -O2 -g
INCLUDES := -Iinclude -Iexternal -Iexternal/asio/asio/include
LDFLAGS := -lncurses -lcurl -lfmt -lpthread

# Define ASIO standalone (no Boost dependency)
DEFINES := -DASIO_STANDALONE -DASIO_NO_DEPRECATED

# Directories
SRC_DIR := src
OBJ_DIR := build/obj
BIN_DIR := build

# Target executable
TARGET := $(BIN_DIR)/prometheus_tui

# Source files
SRCS := $(wildcard $(SRC_DIR)/*.cpp) \
        $(wildcard $(SRC_DIR)/panels/*.cpp) \
        $(wildcard $(SRC_DIR)/utils/*.cpp)

# Object files
OBJS := $(SRCS:$(SRC_DIR)/%.cpp=$(OBJ_DIR)/%.o)

# Create necessary directories
$(shell mkdir -p $(OBJ_DIR)/panels $(OBJ_DIR)/utils $(BIN_DIR))

# Default target
all: $(TARGET)

# Link executable
$(TARGET): $(OBJS)
	@echo "Linking $@..."
	$(CXX) $(OBJS) -o $@ $(LDFLAGS)
	@echo "Build complete: $@"

# Compile source files
$(OBJ_DIR)/%.o: $(SRC_DIR)/%.cpp
	@mkdir -p $(dir $@)
	@echo "Compiling $<..."
	$(CXX) $(CXXFLAGS) $(DEFINES) $(INCLUDES) -c $< -o $@

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(OBJ_DIR) $(TARGET)
	@echo "Clean complete"

# Clean everything including dependencies
distclean: clean
	@echo "Cleaning external dependencies..."
	rm -rf external
	@echo "Full clean complete"

# Run the application
run: $(TARGET)
	@echo "Running Prometheus TUI..."
	$(TARGET)

# Install dependencies (requires sudo/root)
deps:
	@echo "Installing system dependencies..."
	@echo "Note: This requires sudo privileges"
	sudo pacman -S --needed cmake nlohmann-json boost
	@echo "Dependencies installed"

# Download header-only dependencies (no sudo required)
deps-local:
	@echo "Downloading header-only dependencies..."
	mkdir -p external
	curl -L https://github.com/nlohmann/json/releases/download/v3.11.3/json.hpp \
		-o external/json.hpp
	git clone --depth 1 https://github.com/chriskohlhoff/asio.git external/asio
	@echo "Local dependencies ready"

# Debug build
debug: CXXFLAGS += -DDEBUG -O0
debug: clean $(TARGET)

# Release build
release: CXXFLAGS := -std=c++20 -Wall -Wextra -O3 -DNDEBUG
release: clean $(TARGET)

# Check dependencies
check-deps:
	@echo "Checking dependencies..."
	@which $(CXX) > /dev/null || (echo "ERROR: g++ not found" && exit 1)
	@echo "  ✓ C++ compiler: $(shell $(CXX) --version | head -n1)"
	@pkg-config --exists ncurses && echo "  ✓ ncurses" || echo "  ✗ ncurses MISSING"
	@pkg-config --exists libcurl && echo "  ✓ libcurl" || echo "  ✗ libcurl MISSING"
	@pkg-config --exists fmt && echo "  ✓ fmt" || echo "  ✗ fmt MISSING"
	@test -f external/json.hpp && echo "  ✓ nlohmann/json" || echo "  ✗ nlohmann/json MISSING (run: make deps-local)"
	@test -d external/asio && echo "  ✓ asio" || echo "  ✗ asio MISSING (run: make deps-local)"

# Help
help:
	@echo "Prometheus TUI Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all          - Build the application (default)"
	@echo "  clean        - Remove build artifacts"
	@echo "  distclean    - Remove build artifacts and dependencies"
	@echo "  run          - Build and run the application"
	@echo "  debug        - Build with debug symbols"
	@echo "  release      - Build optimized release version"
	@echo "  deps-local   - Download header-only dependencies (no sudo)"
	@echo "  check-deps   - Verify all dependencies are available"
	@echo "  help         - Show this help message"

.PHONY: all clean distclean run deps deps-local debug release check-deps help
