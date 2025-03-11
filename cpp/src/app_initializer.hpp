#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <memory>
#include <fstream>
#include <stdexcept>
#include <cstdint>

namespace app {

// Command types in the binary sequence
enum class CommandType : uint8_t {
    APB_WRITE = 0x01,  // Single APB register write
    VRD_INFO = 0x02,   // Variable Resident Data information
    PM_BINARY = 0x03,  // Program Memory binary (deprecated)
    DMA_WRITE = 0x04   // DMA write command
};

// Structure to hold VRD information
struct VrdInfo {
    std::string name;      // VRD identifier
    uint32_t size;         // Size in bytes
    uint32_t dst_addr;     // Destination address
    std::vector<uint8_t> data;  // Data to be loaded
    bool is_loaded;        // Track if data has been loaded
};

/**
 * @brief Class for handling application initialization sequences
 * 
 * This class reads a binary sequence file containing initialization commands,
 * allows loading of VRD data, and generates the final initialization sequence.
 */
class AppInitializer {
public:
    /**
     * @brief Construct a new App Initializer object
     * 
     * @param binary_file Path to the binary sequence file
     * @throw std::runtime_error if file cannot be opened
     */
    explicit AppInitializer(const std::string& binary_file);

    /**
     * @brief Load data for a specific VRD
     * 
     * @param vrd_name Name of the VRD to load
     * @param data Binary data for the VRD
     * @throw std::runtime_error if VRD not found or size mismatch
     */
    void load_vrd_data(const std::string& vrd_name, const std::vector<uint8_t>& data);

    /**
     * @brief Generate the final initialization sequence
     * 
     * @return std::vector<uint8_t> The complete initialization sequence
     * @throw std::runtime_error if any VRD is not loaded
     */
    std::vector<uint8_t> generate_init_sequence() const;

    /**
     * @brief Get the number of VRDs in the sequence
     * 
     * @return size_t Number of VRDs
     */
    size_t get_vrd_count() const { return vrd_map_.size(); }

    /**
     * @brief Check if a specific VRD exists
     * 
     * @param vrd_name Name of the VRD to check
     * @return true if VRD exists
     */
    bool has_vrd(const std::string& vrd_name) const {
        return vrd_map_.find(vrd_name) != vrd_map_.end();
    }

    /**
     * @brief Get information about a specific VRD
     * 
     * @param vrd_name Name of the VRD
     * @return const VrdInfo& Reference to VRD information
     * @throw std::runtime_error if VRD not found
     */
    const VrdInfo& get_vrd_info(const std::string& vrd_name) const {
        auto it = vrd_map_.find(vrd_name);
        if (it == vrd_map_.end()) {
            throw std::runtime_error("VRD not found: " + vrd_name);
        }
        return it->second;
    }

private:
    std::vector<uint8_t> binary_sequence_;
    std::unordered_map<std::string, VrdInfo> vrd_map_;

    void parse_binary_sequence();
    uint32_t read_uint32(size_t pos) const;
    static void append_uint32(std::vector<uint8_t>& vec, uint32_t value);
    void copy_bytes(std::vector<uint8_t>& dest, size_t src_pos, size_t length) const;
};

} // namespace app 