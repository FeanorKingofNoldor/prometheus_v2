#include "application.hpp"
#include "utils/logger.hpp"

using namespace prometheus::tui;

int main() {
    LOG_INFO("main", "Prometheus TUI starting...");
    
    try {
        Application app;
        app.init();
        app.run();
        app.shutdown();
    } catch (const std::exception& e) {
        LOG_CRITICAL("main", std::string("Fatal error: ") + e.what());
        return 1;
    }
    
    LOG_INFO("main", "Prometheus TUI shutting down...");
    return 0;
}
