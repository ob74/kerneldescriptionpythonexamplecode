#include <iostream>
#include <fstream>
#include <iomanip>
#include "../src/app_initializer.hpp"

// Helper function to create a sample binary sequence file
void create_sample_binary_sequence(const std::string& filename) {
    std::ofstream file(filename, std::ios::binary);
    
    // Sample APB write command
    file.put(static_cast<char>(app::CommandType::APB_WRITE));  // Type
    file.put(0x08); file.put(0x00); file.put(0x00); file.put(0x00);  // Length = 8
    // APB address 0x1000
    file.put(0x00); file.put(0x10); file.put(0x00); file.put(0x00);
    // APB data 0x12345678
    file.put(0x78); file.put(0x56); file.put(0x34); file.put(0x12);

    // Sample VRD info command
    const std::string vrd_name = "test_vrd";
    file.put(static_cast<char>(app::CommandType::VRD_INFO));  // Type
    // Length = name length + 8 bytes for size and address
    uint32_t vrd_length = vrd_name.length() + 8;
    file.put(static_cast<char>(vrd_length));
    file.put(0x00); file.put(0x00); file.put(0x00);
    // VRD name
    file.write(vrd_name.c_str(), vrd_name.length());
    // VRD size = 16 bytes
    file.put(0x10); file.put(0x00); file.put(0x00); file.put(0x00);
    // VRD destination address = 0x2000
    file.put(0x00); file.put(0x20); file.put(0x00); file.put(0x00);

    // Sample DMA write command
    file.put(static_cast<char>(app::CommandType::DMA_WRITE));  // Type
    file.put(0x0C); file.put(0x00); file.put(0x00); file.put(0x00);  // Length = 12
    // Destination address = 0x3000
    file.put(0x00); file.put(0x30); file.put(0x00); file.put(0x00);
    // Data length = 4
    file.put(0x04); file.put(0x00); file.put(0x00); file.put(0x00);
    // Data
    file.put(0xAA); file.put(0xBB); file.put(0xCC); file.put(0xDD);
}

// Helper function to print a binary sequence
void print_sequence(const std::vector<uint8_t>& sequence) {
    std::cout << "Sequence length: " << sequence.size() << " bytes\n";
    for (size_t i = 0; i < sequence.size(); ++i) {
        std::cout << std::hex << std::setw(2) << std::setfill('0') 
                  << static_cast<int>(sequence[i]) << " ";
        if ((i + 1) % 16 == 0) std::cout << "\n";
    }
    std::cout << std::dec << std::endl;
}

int main() {
    try {
        // Create a sample binary sequence file
        const std::string filename = "sample_sequence.bin";
        create_sample_binary_sequence(filename);
        
        // Initialize the app initializer
        app::AppInitializer initializer(filename);
        
        // Create sample VRD data (16 bytes as specified in the sequence)
        std::vector<uint8_t> vrd_data;
        for (int i = 0; i < 16; ++i) {
            vrd_data.push_back(static_cast<uint8_t>(i));
        }
        
        // Load the VRD data
        initializer.load_vrd_data("test_vrd", vrd_data);
        
        // Generate and print the initialization sequence
        std::cout << "Generating initialization sequence...\n";
        auto init_sequence = initializer.generate_init_sequence();
        
        std::cout << "Final initialization sequence:\n";
        print_sequence(init_sequence);
        
        // Expected sequence should contain:
        // 1. Original APB write command
        // 2. DMA write command for the VRD data
        // 3. Original DMA write command
        
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
} 