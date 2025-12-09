#pragma once
#include "base_panel.hpp"
#include <vector>
#include <string>

namespace prometheus::tui {

class AntHillPanel : public BasePanel {
public:
    AntHillPanel();
    ~AntHillPanel() override = default;
    void refresh(ApiClient& api_client) override;
    void render(WINDOW* window) override;
    bool handle_input(int ch) override;
private:
    struct Scene {
        std::string scene_id;
        std::string name;
        int nodes;
        int edges;
        std::string status;
    };
    std::vector<Scene> scenes_;
};

} // namespace prometheus::tui
