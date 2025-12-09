#include "application.hpp"
#include "app_state.hpp"
#include "workspace_manager.hpp"
#include "panels/overview_panel.hpp"
#include "panels/regime_stab_panel.hpp"
#include "panels/live_system_panel.hpp"
#include "panels/portfolio_risk_panel.hpp"
#include "panels/execution_panel.hpp"
#include "panels/assessment_universe_panel.hpp"
#include "panels/meta_experiments_panel.hpp"
#include "panels/ant_hill_panel.hpp"
#include "utils/logger.hpp"
#include <chrono>
#include <thread>
#include <format>

using namespace std::chrono_literals;

namespace prometheus::tui {

Application::Application() {
}

Application::~Application() {
    shutdown();
}

void Application::init() {
    LOG_INFO("Application", "Initializing Prometheus TUI...");
    
    // Initialize singletons
    auto& app_state = AppState::instance();
    auto& ws_manager = WorkspaceManager::instance();
    
    // Initialize API client
    api_client_ = std::make_unique<ApiClient>("http://localhost:8000");
    
    // Test backend connection
    backend_available_ = api_client_->test_connection();
    if (backend_available_) {
        LOG_INFO("Application", "Backend connection successful!");
    } else {
        LOG_WARN("Application", "Backend not available - using mock data");
    }
    
    // Initialize UI
    ui_manager_ = std::make_unique<UIManager>();
    ui_manager_->init();
    
    // Set input timeout
    timeout(50);
    
    // Load initial workspace panels
    current_panel_list_ = ws_manager.get_panels(app_state.active_workspace());
    current_panel_index_ = 0;
    
    // Create and activate first panel
    if (!current_panel_list_.empty()) {
        switch_to_panel(current_panel_list_[0]);
    }
    
    last_refresh_ = std::chrono::steady_clock::now();
    
    LOG_INFO("Application", "Initialization complete");
}

void Application::run() {
    running_ = true;
    LOG_INFO("Application", "Entering main loop");
    
    while (running_) {
        // Render
        ui_manager_->render_top_bar(*api_client_);
        ui_manager_->render_all();
        
        // Handle input
        int ch = ui_manager_->get_input();
        if (ch != ERR) {
            if (!handle_input(ch)) {
                break; // User quit
            }
        }
        
        // Auto-refresh
        handle_auto_refresh();
        
        // Sleep to reduce CPU
        std::this_thread::sleep_for(50ms);
    }
    
    LOG_INFO("Application", "Main loop exited");
}

void Application::shutdown() {
    if (ui_manager_) {
        ui_manager_->shutdown();
        ui_manager_.reset();
    }
    LOG_INFO("Application", "Shutdown complete");
}

std::unique_ptr<BasePanel> Application::create_panel(const std::string& panel_id) {
    // Panel factory - create panels based on ID
    if (panel_id == "overview") {
        return std::make_unique<OverviewPanel>();
    } else if (panel_id == "regime_stab") {
        return std::make_unique<RegimeStabPanel>();
    } else if (panel_id == "live_system") {
        return std::make_unique<LiveSystemPanel>();
    } else if (panel_id == "portfolio_risk") {
        return std::make_unique<PortfolioRiskPanel>();
    } else if (panel_id == "execution") {
        return std::make_unique<ExecutionPanel>();
    } else if (panel_id == "assessment_universe") {
        return std::make_unique<AssessmentUniversePanel>();
    } else if (panel_id == "meta_experiments") {
        return std::make_unique<MetaExperimentsPanel>();
    } else if (panel_id == "ant_hill") {
        return std::make_unique<AntHillPanel>();
    }
    
    // For unimplemented panels, return overview as fallback
    LOG_WARN("Application", "Panel '" + panel_id + "' not implemented yet, using Overview");
    return std::make_unique<OverviewPanel>();
}

void Application::switch_to_panel(const std::string& panel_id) {
    LOG_INFO("Application", "Switching to panel: " + panel_id);
    
    // Create panel
    auto panel = create_panel(panel_id);
    
    // Refresh with data
    if (panel && backend_available_) {
        panel->refresh(*api_client_);
    } else if (panel) {
        // Will use mock data
        panel->refresh(*api_client_);
    }
    
    // Activate panel
    if (panel) {
        ui_manager_->set_active_panel(std::move(panel));
        AppState::instance().set_active_panel(panel_id);
    }
}

void Application::cycle_next_panel() {
    if (current_panel_list_.empty()) return;
    
    current_panel_index_ = (current_panel_index_ + 1) % current_panel_list_.size();
    switch_to_panel(current_panel_list_[current_panel_index_]);
    
    LOG_INFO("Application", std::format("Cycled to panel {}/{}", 
             current_panel_index_ + 1, current_panel_list_.size()));
}

void Application::cycle_prev_panel() {
    if (current_panel_list_.empty()) return;
    
    if (current_panel_index_ == 0) {
        current_panel_index_ = current_panel_list_.size() - 1;
    } else {
        current_panel_index_--;
    }
    switch_to_panel(current_panel_list_[current_panel_index_]);
    
    LOG_INFO("Application", std::format("Cycled to panel {}/{}", 
             current_panel_index_ + 1, current_panel_list_.size()));
}

void Application::switch_workspace(const std::string& workspace_id) {
    LOG_INFO("Application", "Switching to workspace: " + workspace_id);
    
    auto& ws_manager = WorkspaceManager::instance();
    auto* workspace = ws_manager.get_workspace(workspace_id);
    
    if (!workspace) {
        LOG_ERROR("Application", "Workspace not found: " + workspace_id);
        return;
    }
    
    // Update state
    AppState::instance().set_active_workspace(workspace_id);
    
    // Load new panel list
    current_panel_list_ = workspace->panel_ids;
    current_panel_index_ = 0;
    
    // Switch to first panel in workspace
    if (!current_panel_list_.empty()) {
        switch_to_panel(current_panel_list_[0]);
    }
}

void Application::cycle_next_workspace() {
    auto& ws_manager = WorkspaceManager::instance();
    auto ids = ws_manager.get_workspace_ids();
    
    if (ids.empty()) return;
    
    // Find current workspace
    auto current = AppState::instance().active_workspace();
    auto it = std::find(ids.begin(), ids.end(), current);
    
    if (it == ids.end()) {
        // Not found, go to first
        switch_workspace(ids[0]);
    } else {
        // Go to next (wrap around)
        ++it;
        if (it == ids.end()) {
            it = ids.begin();
        }
        switch_workspace(*it);
    }
}

bool Application::handle_input(int ch) {
    LOG_INFO("input", std::format("Key: {} ('{}')", ch, (char)ch));
    
    switch (ch) {
        case 'q':
        case 'Q':
            LOG_INFO("Application", "User quit");
            return false; // Exit
            
        case 'r':
        case 'R':
            // Manual refresh
            if (ui_manager_->get_active_panel()) {
                ui_manager_->get_active_panel()->refresh(*api_client_);
                LOG_INFO("Application", "Manual refresh triggered");
            }
            break;
            
        case '\t':  // Tab
            cycle_next_panel();
            break;
            
        case 'w':
        case 'W':
            cycle_next_workspace();
            break;
            
        case KEY_RESIZE:
            ui_manager_->update_layout();
            LOG_INFO("Application", "Terminal resized");
            break;
            
        default:
            // Pass to active panel
            if (ui_manager_->get_active_panel()) {
                ui_manager_->get_active_panel()->handle_input(ch);
            }
            break;
    }
    
    return true; // Continue running
}

void Application::handle_auto_refresh() {
    const auto refresh_interval = 10s;
    auto now = std::chrono::steady_clock::now();
    
    if (now - last_refresh_ >= refresh_interval) {
        if (ui_manager_->get_active_panel()) {
            ui_manager_->get_active_panel()->refresh(*api_client_);
            LOG_INFO("Application", "Auto-refresh triggered");
        }
        last_refresh_ = now;
    }
}

} // namespace prometheus::tui
