#pragma once

#include <string>
#include <vector>
#include <map>

namespace prometheus::tui {

struct Workspace {
    std::string id;
    std::string display_name;
    std::vector<std::string> panel_ids;
};

class WorkspaceManager {
public:
    static WorkspaceManager& instance();
    
    // Get workspace by ID
    const Workspace* get_workspace(const std::string& id) const;
    
    // Get all workspace IDs
    std::vector<std::string> get_workspace_ids() const;
    
    // Get workspace display names
    std::vector<std::string> get_workspace_names() const;
    
    // Get panels for a workspace
    std::vector<std::string> get_panels(const std::string& workspace_id) const;
    
    // Default workspaces
    static const std::map<std::string, Workspace>& default_workspaces();
    
private:
    WorkspaceManager();
    ~WorkspaceManager() = default;
    WorkspaceManager(const WorkspaceManager&) = delete;
    WorkspaceManager& operator=(const WorkspaceManager&) = delete;
    
    std::map<std::string, Workspace> workspaces_;
};

} // namespace prometheus::tui
