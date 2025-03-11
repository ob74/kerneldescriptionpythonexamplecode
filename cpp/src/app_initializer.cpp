#include "app_initializer.hpp"

namespace app {

AppInitializer::AppInitializer(const std::string& binary_file) {
    std::ifstream file(binary_file, std::ios::binary);
    if (!file) {
        throw std::runtime_error("Failed to open binary file: " + binary_file);
    }

    // Read entire file into binary_sequence
    binary_sequence_ = std::vector<uint8_t>(
        std::istreambuf_iterator<char>(file),
        std::istreambuf_iterator<char>()
    );

    // Parse the binary sequence to extract VRD information
    parse_binary_sequence();
}

void AppInitializer::load_vrd_data(const std::string& vrd_name, const std::vector<uint8_t>& data) {
    auto it = vrd_map_.find(vrd_name);
    if (it == vrd_map_.end()) {
        throw std::runtime_error("VRD not found: " + vrd_name);
    }

    if (data.size() != it->second.size) {
        throw std::runtime_error(
            "VRD data size mismatch for " + vrd_name + 
            ". Expected: " + std::to_string(it->second.size) + 
            ", Got: " + std::to_string(data.size())
        );
    }

    it->second.data = data;
    it->second.is_loaded = true;
}

std::vector<uint8_t> AppInitializer::generate_init_sequence() const {
    // Verify all VRDs are loaded
    for (const auto& vrd_pair : vrd_map_) {
        if (!vrd_pair.second.is_loaded) {
            throw std::runtime_error("VRD data not loaded: " + vrd_pair.first);
        }
    }

    std::vector<uint8_t> init_sequence;
    size_t pos = 0;

    while (pos < binary_sequence_.size()) {
        CommandType cmd_type = static_cast<CommandType>(binary_sequence_[pos++]);
        uint32_t length = read_uint32(pos);
        pos += 4;

        switch (cmd_type) {
            case CommandType::APB_WRITE:
                // Copy APB write command as is
                init_sequence.push_back(static_cast<uint8_t>(cmd_type));
                append_uint32(init_sequence, length);
                copy_bytes(init_sequence, pos, length);
                break;

            case CommandType::VRD_INFO: {
                // Skip the VRD info command - we'll generate DMA writes instead
                size_t name_length = length - 8;  // 8 bytes for size and dst_addr
                std::string vrd_name(
                    reinterpret_cast<const char*>(&binary_sequence_[pos]),
                    name_length
                );
                
                // Get VRD info
                const auto& vrd = vrd_map_.at(vrd_name);
                
                // Generate DMA write command for VRD data
                init_sequence.push_back(static_cast<uint8_t>(CommandType::DMA_WRITE));
                append_uint32(init_sequence, vrd.data.size() + 8);  // data size + addr + length
                append_uint32(init_sequence, vrd.dst_addr);
                append_uint32(init_sequence, vrd.data.size());
                init_sequence.insert(
                    init_sequence.end(),
                    vrd.data.begin(),
                    vrd.data.end()
                );
                break;
            }

            case CommandType::DMA_WRITE:
                // Copy DMA write command as is
                init_sequence.push_back(static_cast<uint8_t>(cmd_type));
                append_uint32(init_sequence, length);
                copy_bytes(init_sequence, pos, length);
                break;

            default:
                throw std::runtime_error("Unknown command type: " + std::to_string(static_cast<int>(cmd_type)));
        }

        pos += length;
    }

    return init_sequence;
}

void AppInitializer::parse_binary_sequence() {
    size_t pos = 0;

    while (pos < binary_sequence_.size()) {
        CommandType cmd_type = static_cast<CommandType>(binary_sequence_[pos++]);
        uint32_t length = read_uint32(pos);
        pos += 4;

        if (cmd_type == CommandType::VRD_INFO) {
            size_t name_length = length - 8;  // 8 bytes for size and dst_addr
            std::string name(
                reinterpret_cast<const char*>(&binary_sequence_[pos]),
                name_length
            );
            pos += name_length;

            uint32_t size = read_uint32(pos);
            pos += 4;
            uint32_t dst_addr = read_uint32(pos);
            pos += 4;

            VrdInfo vrd_info{
                name,
                size,
                dst_addr,
                std::vector<uint8_t>(),  // Empty data vector
                false                     // Not loaded yet
            };
            vrd_map_[name] = vrd_info;
        } else {
            pos += length;
        }
    }
}

uint32_t AppInitializer::read_uint32(size_t pos) const {
    return static_cast<uint32_t>(binary_sequence_[pos]) |
           (static_cast<uint32_t>(binary_sequence_[pos + 1]) << 8) |
           (static_cast<uint32_t>(binary_sequence_[pos + 2]) << 16) |
           (static_cast<uint32_t>(binary_sequence_[pos + 3]) << 24);
}

void AppInitializer::append_uint32(std::vector<uint8_t>& vec, uint32_t value) {
    vec.push_back(static_cast<uint8_t>(value));
    vec.push_back(static_cast<uint8_t>(value >> 8));
    vec.push_back(static_cast<uint8_t>(value >> 16));
    vec.push_back(static_cast<uint8_t>(value >> 24));
}

void AppInitializer::copy_bytes(std::vector<uint8_t>& dest, size_t src_pos, size_t length) const {
    dest.insert(
        dest.end(),
        binary_sequence_.begin() + src_pos,
        binary_sequence_.begin() + src_pos + length
    );
}

} // namespace app 