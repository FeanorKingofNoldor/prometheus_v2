#include "workspace_manager.hpp"
#include "utils/logger.hpp"

namespace prometheus::tui {

const std::map<std::string, Workspace>& WorkspaceManager::default_workspaces() {
    static const std::map<std::string, Workspace> defaults = {
        {"overview", {
            .id = "overview",
            .display_name = "Overview",
            .panel_ids = {"overview", "regime_stab", "live_system"}
        }},
        {"trading", {
            .id = "trading",
            .display_name = "Trading",
            .panel_ids = {"portfolio_risk", "execution", "fragility", "terminal"}
        }},
        {"research", {
            .id = "research",
            .display_name = "Research",
            .panel_ids = {"assessment_universe", "meta_experiments", "ant_hill"}
        }},
        {"monitoring", {
            .id = "monitoring",
            .display_name = "Monitoring",
            .panel_ids = {"live_system", "regime_stab", "portfolio_risk", "execution", "geo"}
        }},
        {"global", {
            .id = "global",
            .display_name = "Global View",
            .panel_ids = {"geo", "regime_stab", "fragility"}
        }}
    };
    return defaults;
}

WorkspaceManager::WorkspaceManager() {
    workspaces_ = default_workspaces();
    LOG_INFO("WorkspaceManager", "Initialized with " + 
             std::to_string(workspaces_.size()) + " workspaces");
}

WorkspaceManager& WorkspaceManager::instance() {
    static WorkspaceManager instance;
    return instance;
}

const Workspace* WorkspaceManager::get_workspace(const std::string& id) const {
    auto it = workspaces_.find(id);
    if (it != workspaces_.end()) {
        return &it->second;
    }
    return nullptr;
}

std::vector<std::string> WorkspaceManager::get_workspace_ids() const {
    std::vector<std::string> ids;
    ids.reserve(workspaces_.size());
    for (const auto& [id, _] : workspaces_) {
        ids.push_back(id);
    }
    return ids;
}

std::vector<std::string> WorkspaceManager::get_workspace_names() const {
    std::vector<std::string> names;
    names.reserve(workspaces_.size());
    for (const auto& [_, workspace] : workspaces_) {
        names.push_back(workspace.display_name);
    }
    return names;
}

std::vector<std::string> WorkspaceManager::get_panels(const std::string& workspace_id) const {
    auto workspace = get_workspace(workspace_id);
    if (workspace) {
        return workspace->panel_ids;
    }
    return {};
}

} // namespace prometheus::tui
