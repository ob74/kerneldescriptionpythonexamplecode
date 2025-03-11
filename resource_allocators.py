from typing import Dict, List, Optional, Tuple, Any
from hw_resources import ResourceScope, HWResource, MemoryResource, DMAResource, BarrierResource
from hw_components import KernelSizeComponent
from kernel_types import ResourceRequirement, MemoryRequirement, DMARequirement, BarrierRequirement


class ResourceAllocator:
    """Base class for resource allocators"""

    def allocate(self, requirement: ResourceRequirement) -> List[HWResource]:
        """Allocate resources for a requirement"""
        raise NotImplementedError("Subclasses must implement allocate()")

    def reset(self):
        """Reset allocator to initial state"""
        raise NotImplementedError("Subclasses must implement reset()")


class MemoryAllocator(ResourceAllocator):
    def __init__(self, kernel_size: KernelSizeComponent):
        self.kernel_size = kernel_size
        self.x_size, self.y_size = kernel_size.get_dimensions()

        # Create memory maps for MSS and PE levels
        # For simplicity, we'll use a flat allocation strategy
        self.mss_memory = {}  # mss_id -> (start_address, current_offset)
        self.pe_memory = {}  # (pe_x, pe_y) -> (start_address, current_offset)

        # Initialize memory maps
        self._init_memory_maps()

    def _init_memory_maps(self):
        """Initialize memory maps with base addresses"""
        # Set up MSS memory (8 MSS per chip)
        for mss_id in range(8):
            self.mss_memory[mss_id] = (0x10000000 + mss_id * 0x1000000, 0)

        # Set up PE memory
        for pe_x in range(self.x_size):
            for pe_y in range(self.y_size):
                self.pe_memory[(pe_x, pe_y)] = (0x20000000 + (pe_x * self.y_size + pe_y) * 0x1000000, 0)

    def allocate(self, requirement: ResourceRequirement) -> List[HWResource]:
        if not isinstance(requirement, MemoryRequirement):
            return []

        resources = []

        if requirement.scope == ResourceScope.ONE_MSS:
            # Allocate from a specific MSS (pick the first one with enough space)
            for mss_id, (base_addr, offset) in self.mss_memory.items():
                addr = base_addr + offset
                self.mss_memory[mss_id] = (base_addr, offset + requirement.size)
                resources.append(MemoryResource(
                    address=addr,
                    length=requirement.size,
                    scope=ResourceScope.ONE_MSS,
                    mss_id=mss_id
                ))
                break

        elif requirement.scope == ResourceScope.ONE_PE:
            # Allocate from a specific PE (pick the first one with enough space)
            for pe_coords, (base_addr, offset) in self.pe_memory.items():
                addr = base_addr + offset
                pe_x, pe_y = pe_coords
                self.pe_memory[pe_coords] = (base_addr, offset + requirement.size)
                resources.append(MemoryResource(
                    address=addr,
                    length=requirement.size,
                    scope=ResourceScope.ONE_PE,
                    pe_x=pe_x,
                    pe_y=pe_y
                ))
                break

        elif requirement.scope == ResourceScope.PE_GROUP:
            # Allocate from all PEs (distribute evenly)
            size_per_pe = requirement.size // (self.x_size * self.y_size)
            for pe_x in range(self.x_size):
                for pe_y in range(self.y_size):
                    pe_coords = (pe_x, pe_y)
                    base_addr, offset = self.pe_memory[pe_coords]
                    addr = base_addr + offset
                    self.pe_memory[pe_coords] = (base_addr, offset + size_per_pe)
                    resources.append(MemoryResource(
                        address=addr,
                        length=size_per_pe,
                        scope=ResourceScope.ONE_PE,
                        pe_x=pe_x,
                        pe_y=pe_y
                    ))

        return resources

    def reset(self):
        """Reset memory allocator to initial state"""
        self._init_memory_maps()


class DMAAllocator(ResourceAllocator):
    def __init__(self, kernel_size: KernelSizeComponent):
        self.kernel_size = kernel_size
        self.x_size, self.y_size = kernel_size.get_dimensions()

        # Track available DMA channels
        self.mss_dma_channels = {}  # mss_id -> next_available_channel
        self.pe_dma_channels = {}  # (pe_x, pe_y) -> next_available_channel

        # Initialize DMA channels
        self._init_dma_channels()

    def _init_dma_channels(self):
        """Initialize DMA channel tracking"""
        # For MSS level: 8 channels per MSS
        for mss_id in range(8):
            self.mss_dma_channels[mss_id] = 0

        # For PE level: 4 channels per PE
        for pe_x in range(self.x_size):
            for pe_y in range(self.y_size):
                self.pe_dma_channels[(pe_x, pe_y)] = 0

    def allocate(self, requirement: ResourceRequirement) -> List[HWResource]:
        if not isinstance(requirement, DMARequirement):
            return []

        resources = []

        if requirement.scope == ResourceScope.ONE_MSS:
            # Allocate from a specific MSS (pick the first one with available channels)
            for mss_id, next_channel in self.mss_dma_channels.items():
                if next_channel < 8:  # Assuming 8 channels per MSS
                    channel_id = next_channel
                    self.mss_dma_channels[mss_id] = next_channel + 1
                    resources.append(DMAResource(
                        channel_id=channel_id,
                        scope=ResourceScope.ONE_MSS,
                        is_input=requirement.is_input,
                        mss_id=mss_id
                    ))
                    break

        elif requirement.scope == ResourceScope.ONE_PE:
            # Allocate from a specific PE (pick the first one with available channels)
            for pe_coords, next_channel in self.pe_dma_channels.items():
                if next_channel < 4:  # Assuming 4 channels per PE
                    channel_id = next_channel
                    pe_x, pe_y = pe_coords
                    self.pe_dma_channels[pe_coords] = next_channel + 1
                    resources.append(DMAResource(
                        channel_id=channel_id,
                        scope=ResourceScope.ONE_PE,
                        is_input=requirement.is_input,
                        pe_x=pe_x,
                        pe_y=pe_y
                    ))
                    break

        elif requirement.scope == ResourceScope.PE_GROUP:
            # Allocate from the first available channel in each PE
            for pe_x in range(self.x_size):
                for pe_y in range(self.y_size):
                    pe_coords = (pe_x, pe_y)
                    next_channel = self.pe_dma_channels[pe_coords]
                    if next_channel < 4:  # Assuming 4 channels per PE
                        channel_id = next_channel
                        self.pe_dma_channels[pe_coords] = next_channel + 1
                        resources.append(DMAResource(
                            channel_id=channel_id,
                            scope=ResourceScope.ONE_PE,
                            is_input=requirement.is_input,
                            pe_x=pe_x,
                            pe_y=pe_y
                        ))

        return resources

    def reset(self):
        """Reset DMA allocator to initial state"""
        self._init_dma_channels()


class BarrierAllocator(ResourceAllocator):
    def __init__(self, kernel_size: KernelSizeComponent):
        self.kernel_size = kernel_size
        self.x_size, self.y_size = kernel_size.get_dimensions()

        # Track available barrier networks
        self.mss_barriers = {}  # mss_id -> next_available_barrier
        self.pe_barriers = {}  # (pe_x, pe_y) -> next_available 