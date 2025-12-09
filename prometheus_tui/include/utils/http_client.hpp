#pragma once

#include <string>
#include <optional>
#include <map>
#include <json.hpp>

namespace prometheus::tui {

using json = nlohmann::json;

struct HttpResponse {
    long status_code;
    std::string body;
    bool success;
    std::string error_message;
    
    // Parse as JSON
    std::optional<json> as_json() const;
};

class HttpClient {
public:
    HttpClient(const std::string& base_url);
    ~HttpClient();
    
    // HTTP methods
    HttpResponse get(const std::string& path, 
                    const std::map<std::string, std::string>& headers = {});
    
    HttpResponse post(const std::string& path, 
                     const std::string& body,
                     const std::map<std::string, std::string>& headers = {});
    
    HttpResponse post_json(const std::string& path,
                          const json& data,
                          const std::map<std::string, std::string>& headers = {});
    
    // Configuration
    void set_timeout(long timeout_seconds);
    void set_connect_timeout(long timeout_seconds);
    
    // Helper to build full URL
    std::string full_url(const std::string& path) const;
    
private:
    std::string base_url_;
    long timeout_ = 30L;
    long connect_timeout_ = 10L;
    
    HttpResponse perform_request(const std::string& url,
                                 const std::string& method,
                                 const std::string& body,
                                 const std::map<std::string, std::string>& headers);
};

} // namespace prometheus::tui
