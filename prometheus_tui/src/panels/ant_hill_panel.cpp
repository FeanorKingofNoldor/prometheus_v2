#include "panels/ant_hill_panel.hpp"
#include "api_client.hpp"
#include "utils/colors.hpp"
#include <ncurses.h>

namespace prometheus::tui {

AntHillPanel::AntHillPanel() : BasePanel("ant_hill", "ANT_HILL Visualization") {}

void AntHillPanel::refresh(ApiClient& api_client) {
    scenes_ = {
        {"SCENE_001", "Strategy Network", 247, 589, "ACTIVE"},
        {"SCENE_002", "Risk Connectivity", 189, 423, "ACTIVE"},
        {"SCENE_003", "Asset Correlations", 512, 1247, "RENDERING"},
        {"SCENE_004", "Market Topology", 334, 756, "ACTIVE"}
    };
}

void AntHillPanel::render(WINDOW* window) {
    int width = getmaxx(window);
    int y = 0;
    
    wattron(window, COLOR_PAIR(COLOR_CYAN)); wattron(window, A_BOLD);
    mvwprintw(window, y++, 2, "══════════ ANT_HILL VISUALIZATION SCENES ══════════");
    wattroff(window, A_BOLD); wattroff(window, COLOR_PAIR(COLOR_CYAN));
    y += 2;
    
    wattron(window, A_BOLD);
    mvwprintw(window, y++, 3, "%-15s %-25s %12s %12s %15s",
              "Scene ID", "Name", "Nodes", "Edges", "Status");
    wattroff(window, A_BOLD);
    mvwhline(window, y++, 3, ACS_HLINE, width - 6);
    
    for (const auto& scene : scenes_) {
        mvwprintw(window, y, 3, "%-15s", scene.scene_id.c_str());
        mvwprintw(window, y, 19, "%-25s", scene.name.c_str());
        mvwprintw(window, y, 45, "%11d", scene.nodes);
        mvwprintw(window, y, 58, "%11d", scene.edges);
        
        int color = scene.status == "ACTIVE" ? COLOR_GREEN : COLOR_YELLOW;
        wattron(window, COLOR_PAIR(color) | A_BOLD);
        mvwprintw(window, y, 71, "%14s", scene.status.c_str());
        wattroff(window, COLOR_PAIR(color) | A_BOLD);
        y++;
    }
}

bool AntHillPanel::handle_input(int ch) { return false; }

} // namespace prometheus::tui
