# Kernel Description Python Example Code

This project provides a Python implementation for managing hardware configurations and network settings in a grid-based system. It's designed to handle kernel allocations, network configurations, and APB (Advanced Peripheral Bus) settings for hardware components.

## Overview

The system is built around several key components:

### Grid System
- `Grid`: Manages the physical layout and allocation of kernels in a grid-based system
- `Chip`: A 16x16 grid implementation
- `Haps`: A 4x2 grid implementation

### Network Management
- `GridNOC`: Handles all network-related functionality including:
  - Broadcast network configurations
  - AXI2AHB bridge settings
  - Network switching capabilities

### Hardware Components
- `BroadCastNetwork`: Represents NOC (Network-on-Chip) configurations for specific broadcast networks
- `AXI2AHB`: Manages bridge configurations between AXI and AHB buses
- `KernelSizeComponent`: Handles kernel size configurations
- `IOChannel`: Manages input/output channel configurations
- `VariableResidentData`: Handles data allocation and management

### Command System
- `BirdCommandSequence`: Represents sequences of hardware commands
- `BirdCommand`: Individual commands for hardware configuration
- `NetworkType`: Defines network configurations with broadcast types and destinations

## Network Types

The system supports various network configurations:

### Broadcast Types
- `DIRECT`: Direct access
- `PEG_MSS_BRCST`: PEG to MSS broadcast
- `PEG_PE_BRCST`: PEG to PE broadcast
- `SUPER_PE_ID_BRCST`: Supergroup PE ID broadcast
- `SUPER_PE_BRCST`: Supergroup PE broadcast
- `SUPER_MSS_BRCST`: Supergroup MSS broadcast

### Destination Types
- `VCORE`: Virtual core destination
- `MSS`: Memory subsystem destination
- `APB`: Advanced Peripheral Bus destination

## Usage Example

```python
# Create a grid
grid = Grid(16, 16)

# Create a kernel supergroup
supergroup = KernelSuperGroup(x=0, y=0, size_x=2, size_y=2, kernel_size=KernelSize.SIZE_2X2)

# Add a broadcast network
network = grid.add_broadcast_network(supergroup, NetworkType(BroadcastType.SUPER_PE_BRCST, GridDestinationType.VCORE))

# Get APB settings
settings = grid.get_apb_settings(NetworkType(BroadcastType.SUPER_PE_BRCST, GridDestinationType.VCORE))

# Switch networks
switch_cmd = grid.get_network_switch(NetworkType(BroadcastType.SUPER_MSS_BRCST, GridDestinationType.MSS))
```

## Command Structure

Commands are organized into sequences that can be converted to bytes for hardware communication:

### Command Types
- `SINGLE`: Single 32-bit value command
- `SAFE_SINGLE`: Safe single command with additional checks
- `DMA`: Direct Memory Access command

### Command Format
```
SINGLE: [type(1B)] [total_len(4B)] [dst_addr(4B)] [data(4B)]
DMA: [type(1B)] [total_len(4B)] [dst_addr(4B)] [data_len(4B)] [data(Nx4B)]
```

## Resource Management

The system handles various hardware resources:
- Memory requirements
- DMA channels
- Barrier synchronization
- Network bandwidth

## Error Handling

The system includes validation for:
- Grid boundaries
- Kernel size compatibility
- Network type compatibility
- Resource availability
- Command data types

## Dependencies

- Python 3.x
- Standard library only (no external dependencies)

## Contributing

Feel free to submit issues and enhancement requests!
 
