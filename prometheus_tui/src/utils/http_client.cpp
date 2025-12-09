#include "utils/http_client.hpp"
#include "utils/logger.hpp"
#include <curl/curl.h>
#include <stdexcept>

namespace prometheus::tui {

// Callback for curl to write response data
static size_t write_callback(void* contents, size_t size, size_t nmemb, std::string* userp) {
    size_t total_size = size * nmemb;
    userp->append(static_cast<char*>(contents), total_size);
    return total_size;
}

std::optional<json> HttpResponse::as_json() const {
    if (!success || body.empty()) {
        return std::nullopt;
    }
    
    try {
        return nlohmann::json::parse(body);
    } catch (const nlohmann::json::exception& e) {
        LOG_ERROR("HttpResponse", std::string("JSON parse error: ") + e.what());
        return std::nullopt;
    }
}

HttpClient::HttpClient(const std::string& base_url) 
    : base_url_(base_url) {
    curl_global_init(CURL_GLOBAL_ALL);
    LOG_INFO("HttpClient", "Initialized with base URL: " + base_url);
}

HttpClient::~HttpClient() {
    curl_global_cleanup();
}

HttpResponse HttpClient::get(const std::string& path, 
                             const std::map<std::string, std::string>& headers) {
    return perform_request(full_url(path), "GET", "", headers);
}

HttpResponse HttpClient::post(const std::string& path, 
                              const std::string& body,
                              const std::map<std::string, std::string>& headers) {
    return perform_request(full_url(path), "POST", body, headers);
}

HttpResponse HttpClient::post_json(const std::string& path,
                                   const json& data,
                                   const std::map<std::string, std::string>& headers) {
    auto headers_copy = headers;
    headers_copy["Content-Type"] = "application/json";
    return post(path, data.dump(), headers_copy);
}

void HttpClient::set_timeout(long timeout_seconds) {
    timeout_ = timeout_seconds;
}

void HttpClient::set_connect_timeout(long timeout_seconds) {
    connect_timeout_ = timeout_seconds;
}

std::string HttpClient::full_url(const std::string& path) const {
    if (path.empty() || path[0] != '/') {
        return base_url_ + "/" + path;
    }
    return base_url_ + path;
}

HttpResponse HttpClient::perform_request(const std::string& url,
                                         const std::string& method,
                                         const std::string& body,
                                         const std::map<std::string, std::string>& headers) {
    CURL* curl = curl_easy_init();
    if (!curl) {
        return HttpResponse{
            .status_code = 0,
            .body = "",
            .success = false,
            .error_message = "Failed to initialize CURL"
        };
    }
    
    std::string response_body;
    struct curl_slist* header_list = nullptr;
    
    // Set URL
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    
    // Set method
    if (method == "POST") {
        curl_easy_setopt(curl, CURLOPT_POST, 1L);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body.c_str());
        curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, body.size());
    }
    
    // Set headers
    for (const auto& [key, value] : headers) {
        std::string header = key + ": " + value;
        header_list = curl_slist_append(header_list, header.c_str());
    }
    if (header_list) {
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, header_list);
    }
    
    // Set timeouts
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, timeout_);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, connect_timeout_);
    
    // Set write callback
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response_body);
    
    // Perform request
    CURLcode res = curl_easy_perform(curl);
    
    HttpResponse response;
    
    if (res != CURLE_OK) {
        response.status_code = 0;
        response.body = "";
        response.success = false;
        response.error_message = curl_easy_strerror(res);
        LOG_ERROR("HttpClient", "Request failed: " + std::string(curl_easy_strerror(res)));
    } else {
        long status_code;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status_code);
        
        response.status_code = status_code;
        response.body = response_body;
        response.success = (status_code >= 200 && status_code < 300);
        response.error_message = response.success ? "" : "HTTP " + std::to_string(status_code);
        
        if (!response.success) {
            LOG_WARN("HttpClient", "Request returned status " + std::to_string(status_code));
        }
    }
    
    // Cleanup
    if (header_list) {
        curl_slist_free_all(header_list);
    }
    curl_easy_cleanup(curl);
    
    return response;
}

} // namespace prometheus::tui
