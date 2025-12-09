#include "panels/meta_experiments_panel.hpp"
#include "api_client.hpp"
#include "utils/logger.hpp"
#include "utils/colors.hpp"
#include <ncurses.h>

namespace prometheus::tui {

MetaExperimentsPanel::MetaExperimentsPanel() 
    : BasePanel("meta_experiments", "Meta Experiments") {
}

void MetaExperimentsPanel::refresh(ApiClient& api_client) {
    experiments_ = {
        {"EXP_001", "LSTM-Attention-v2", "COMPLETED", 0.87, 1000, "lr=0.001,layers=3"},
        {"EXP_002", "Transformer-Base", "RUNNING", 0.82, 743, "lr=0.0005,heads=8"},
        {"EXP_003", "GRU-Ensemble", "COMPLETED", 0.79, 1200, "lr=0.002,units=256"},
        {"EXP_004", "CNN-LSTM-Hybrid", "FAILED", 0.45, 234, "lr=0.01,conv=32"},
        {"EXP_005", "Meta-Learner-v3", "RUNNING", 0.91, 567, "meta_lr=0.0001"}
    };
}

void MetaExperimentsPanel::render(WINDOW* window) {
    int height = getmaxy(window);
    int width = getmaxx(window);
    int y = 0;
    
    wattron(window, COLOR_PAIR(COLOR_CYAN)); wattron(window, A_BOLD);
    mvwprintw(window, y++, 2, "══════════ META-LEARNING EXPERIMENTS ══════════");
    wattroff(window, A_BOLD); wattroff(window, COLOR_PAIR(COLOR_CYAN));
    y += 2;
    
    wattron(window, A_BOLD);
    mvwprintw(window, y++, 3, "%-12s %-20s %12s %12s %12s %-25s",
              "Exp ID", "Name", "Status", "Score", "Iterations", "Hyperparameters");
    wattroff(window, A_BOLD);
    mvwhline(window, y++, 3, ACS_HLINE, width - 6);
    
    for (const auto& exp : experiments_) {
        mvwprintw(window, y, 3, "%-12s", exp.exp_id.c_str());
        mvwprintw(window, y, 16, "%-20s", exp.name.c_str());
        
        int status_color = exp.status == "COMPLETED" ? COLOR_GREEN :
                          exp.status == "RUNNING" ? COLOR_YELLOW : COLOR_RED;
        wattron(window, COLOR_PAIR(status_color) | A_BOLD);
        mvwprintw(window, y, 37, "%11s", exp.status.c_str());
        wattroff(window, COLOR_PAIR(status_color) | A_BOLD);
        
        mvwprintw(window, y, 50, "%11.3f", exp.performance_score);
        mvwprintw(window, y, 63, "%11d", exp.iterations);
        mvwprintw(window, y, 76, "%-25s", exp.hyperparams.c_str());
        y++;
    }
}

bool MetaExperimentsPanel::handle_input(int ch) {
    return false;
}

} // namespace prometheus::tui
