from typing import Dict, List, Optional, Tuple, Any
import math
from enum import Enum
from hw_resources import ResourceScope, NOCBroadCastResource, AXI2AHBResource
from kernel_types import (
    BufferLocationType, ChannelType, KernelSize, AllocationType,
    ResourceRequirement, MemoryRequirement, DMARequirement, BarrierRequirement, ElementField,
    KernelLocation, KernelSuperGroup
)
from bird import BirdCommandSequence, NetworkType, BroadcastType, GridDestinationType, BirdCommand, BirdCommandType
from apb_config import config_vcore, broadcast_config, barrier_config

class HWComponent:
    """Base class for hardware components"""

    def __init__(self, name: str):
        self.name = name

    def get_required_resources(self) -> List[ResourceRequirement]:
        """Returns a list of required resources"""
        return []

    def get_h_file_definitions(self) -> Dict[str, Any]:
        """Returns definitions for .h files"""
        return {}

    def get_apb_settings(self, supergroup: KernelSuperGroup) -> BirdCommandSequence:
        """Returns APB settings as a BirdCommandSequence for a specific supergroup"""
        return BirdCommandSequence(
            f"{self.name} APB settings",
            NetworkType(BroadcastType.DIRECT, GridDestinationType.APB),
            []
        )


class KernelSizeComponent(HWComponent):
    def __init__(self, size: KernelSize):
        super().__init__("KernelSize")
        self.size = size

        # Map kernel sizes to (x, y) dimensions
        self.size_mapping = {
            KernelSize.ONE_VCORE: (1, 1),
            KernelSize.SIZE_1X1: (1, 1),
            KernelSize.SIZE_1X2: (1, 2),
            KernelSize.SIZE_2X2: (2, 2),
            KernelSize.SIZE_2X4: (2, 4),
            KernelSize.SIZE_4X4: (4, 4),
            KernelSize.SIZE_4X8: (4, 8),
            KernelSize.SIZE_8X8: (8, 8),
            KernelSize.SIZE_8X16: (8, 16),
            KernelSize.SIZE_16X16: (16, 16),
        }

    def get_h_file_definitions(self) -> Dict[str, Any]:
        x_size, y_size = self.size_mapping[self.size]
        return {
            "PEG_X_SIZE": x_size,
            "PEG_Y_SIZE": y_size
        }

    def get_apb_settings(self, supergroup: KernelSuperGroup) -> BirdCommandSequence:
        """Returns APB settings for kernel size for a supergroup"""
        x_size, y_size = self.size_mapping[self.size]
        
        seq = BirdCommandSequence(
            f"Kernel Size APB settings for {self.name}",
            NetworkType(BroadcastType.SUPER_MSS_BRCST, GridDestinationType.APB),
            []
        )
        # Apply settings for each location in the supergroup
        vcore_apb_regs = config_vcore(x_size, y_size, 0)
        for addr, data in vcore_apb_regs:
            seq.add_single_command(addr, data)
        return seq

    def get_dimensions(self) -> Tuple[int, int]:
        """Get the x and y dimensions of the kernel"""
        return self.size_mapping[self.size]


class IOChannel(HWComponent):
    def __init__(self, name: str, channel_type: ChannelType, buffer_size: int,
                 buffer_location: BufferLocationType, num_buffers: int = 1,
                 element_type: Optional[str] = None, element_fields: Optional[List[ElementField]] = None):
        super().__init__(name)
        self.channel_type = channel_type
        self.buffer_size = buffer_size
        self.buffer_location = buffer_location
        self.num_buffers = num_buffers
        self.element_type = element_type
        self.element_fields = element_fields or []

        # Calculate total element size
        self.element_size = sum(field.size for field in self.element_fields) if self.element_fields else 0

    def get_required_resources(self) -> List[ResourceRequirement]:
        requirements = []

        # Determine the appropriate scope and quantity based on buffer location
        if self.buffer_location == BufferLocationType.MSS000:
            # Single memory block in MSS000
            requirements.append(MemoryRequirement(
                size=self.buffer_size * self.num_buffers,
                scope=ResourceScope.ONE_MSS
            ))

            # DMA requirements
            if self.channel_type in [ChannelType.PACKED_BUFFER_QUEUE_INPUT, ChannelType.BUFFER_QUEUE_INPUT]:
                requirements.append(DMARequirement(
                    scope=ResourceScope.ONE_MSS,
                    is_input=True
                ))
            elif self.channel_type in [ChannelType.PACKED_BUFFER_QUEUE_OUTPUT, ChannelType.BUFFER_QUEUE_OUTPUT]:
                requirements.append(DMARequirement(
                    scope=ResourceScope.ONE_MSS,
                    is_input=False
                ))

        elif self.buffer_location == BufferLocationType.PE00:
            # Split across 4 MSS
            for _ in range(4):
                requirements.append(MemoryRequirement(
                    size=self.buffer_size * self.num_buffers // 4,
                    scope=ResourceScope.ONE_MSS
                ))

            # DMA requirements
            if self.channel_type in [ChannelType.PACKED_BUFFER_QUEUE_INPUT, ChannelType.BUFFER_QUEUE_INPUT]:
                for _ in range(4):
                    requirements.append(DMARequirement(
                        scope=ResourceScope.ONE_MSS,
                        is_input=True
                    ))
            elif self.channel_type in [ChannelType.PACKED_BUFFER_QUEUE_OUTPUT, ChannelType.BUFFER_QUEUE_OUTPUT]:
                for _ in range(4):
                    requirements.append(DMARequirement(
                        scope=ResourceScope.ONE_MSS,
                        is_input=False
                    ))

        elif self.buffer_location == BufferLocationType.SPREAD:
            # Evenly distributed across all MSS
            # For simplicity, assuming 8 MSS
            for _ in range(8):
                requirements.append(MemoryRequirement(
                    size=self.buffer_size * self.num_buffers // 8,
                    scope=ResourceScope.ONE_MSS
                ))

            # DMA requirements
            if self.channel_type in [ChannelType.PACKED_BUFFER_QUEUE_INPUT, ChannelType.BUFFER_QUEUE_INPUT]:
                for _ in range(8):
                    requirements.append(DMARequirement(
                        scope=ResourceScope.ONE_MSS,
                        is_input=True
                    ))
            elif self.channel_type in [ChannelType.PACKED_BUFFER_QUEUE_OUTPUT, ChannelType.BUFFER_QUEUE_OUTPUT]:
                for _ in range(8):
                    requirements.append(DMARequirement(
                        scope=ResourceScope.ONE_MSS,
                        is_input=False
                    ))

        # Add barrier requirements for auxiliary channels
        if self.channel_type == ChannelType.AUXILIARY_INPUT:
            requirements.append(BarrierRequirement(
                scope=ResourceScope.PE_GROUP,
                count=1
            ))

        return requirements

    def get_h_file_definitions(self) -> Dict[str, Any]:
        defs = {
            f"{self.name.upper()}_BUFFER_SIZE": self.buffer_size,
            f"{self.name.upper()}_NUM_BUFFERS": self.num_buffers,
        }

        if self.element_fields and self.element_type:
            defs[f"{self.name.upper()}_ELEMENT_TYPE"] = self.element_type

            if self.channel_type in [ChannelType.PACKED_BUFFER_QUEUE_INPUT, ChannelType.PACKED_BUFFER_QUEUE_OUTPUT]:
                defs[f"{self.name.upper()}_ELEMENTS_PER_BUFFER"] = self.buffer_size // self.element_size

        # Add struct definition if element fields are provided
        if self.element_fields and self.element_type:
            struct_def = f"typedef struct {self.element_type} {{\n"
            for field in self.element_fields:
                struct_def += f"    {field.get_c_type()} {field.name};\n"
            struct_def += f"}} {self.element_type};\n"
            defs[f"STRUCT_{self.element_type.upper()}"] = struct_def

        return defs

    def get_apb_settings(self, supergroup: KernelSuperGroup) -> BirdCommandSequence:
        """Returns APB settings for IO channel for a supergroup"""
        seq = BirdCommandSequence(
            f"IO Channel APB settings for {self.name}",
            NetworkType(BroadcastType.SUPER_PE_BRCST, GridDestinationType.APB),
            []
        )

        # Apply settings for each location in the supergroup
        for location in supergroup.get_kernel_locations():
            base_address = 0x50000000 + (location.x * 0x10000) + (location.y * 0x1000)
            if location.is_vcore:
                base_address += location.vcore * 0x100

            # Channel type configuration
            channel_type_val = self.channel_type.value
            seq.add_single_command(base_address + 0x100, channel_type_val.__hash__() & 0xFFFFFFFF)

            # Buffer location configuration
            if self.buffer_location == BufferLocationType.MSS000:
                seq.add_single_command(base_address + 0x104, 0x1)
            elif self.buffer_location == BufferLocationType.PE00:
                seq.add_single_command(base_address + 0x104, 0x2)
            elif self.buffer_location == BufferLocationType.SPREAD:
                seq.add_single_command(base_address + 0x104, 0x3)

            # Buffer size and count
            seq.add_single_command(base_address + 0x108, self.buffer_size)
            seq.add_single_command(base_address + 0x10C, self.num_buffers)

        return seq


class VariableResidentData(HWComponent):
    def __init__(self, name: str, element_size: int, num_elements: int,
                 data_file_path: str, allocation_type: AllocationType,
                 dma_channel_required: bool = False):
        super().__init__(name)
        self.element_size = element_size
        self.num_elements = num_elements
        self.data_file_path = data_file_path
        self.allocation_type = allocation_type
        self.dma_channel_required = dma_channel_required
        self.total_size = element_size * num_elements

    def get_required_resources(self) -> List[ResourceRequirement]:
        requirements = []

        if self.allocation_type == AllocationType.MSS_DUPLICATED:
            # Duplicated across MSS, split in 2 parts
            for _ in range(2):
                requirements.append(MemoryRequirement(
                    size=self.total_size // 2,
                    scope=ResourceScope.ONE_MSS
                ))
        elif self.allocation_type == AllocationType.PE_DUPLICATED:
            # Duplicated across PE, split in 8 parts
            for _ in range(8):
                requirements.append(MemoryRequirement(
                    size=self.total_size // 8,
                    scope=ResourceScope.ONE_PE
                ))
        elif self.allocation_type == AllocationType.MSS_DISTRIBUTED:
            # Distributed across MSS
            # Assuming 8 MSS for this example, with even distribution
            for _ in range(8):
                requirements.append(MemoryRequirement(
                    size=self.total_size // 8,
                    scope=ResourceScope.ONE_MSS
                ))
        elif self.allocation_type == AllocationType.PE_DISTRIBUTED:
            # Distributed across PE
            # Assuming 16 PEs (4x4) for this example
            for _ in range(16):
                requirements.append(MemoryRequirement(
                    size=self.total_size // 16,
                    scope=ResourceScope.ONE_PE
                ))

        # Add DMA requirements if needed
        if self.dma_channel_required:
            if self.allocation_type in [AllocationType.MSS_DUPLICATED, AllocationType.MSS_DISTRIBUTED]:
                # Need DMA channels for each MSS
                count = 2 if self.allocation_type == AllocationType.MSS_DUPLICATED else 8
                for _ in range(count):
                    requirements.append(DMARequirement(
                        scope=ResourceScope.ONE_MSS,
                        is_input=True
                    ))
            elif self.allocation_type in [AllocationType.PE_DUPLICATED, AllocationType.PE_DISTRIBUTED]:
                # Need DMA channels for each PE
                count = 8 if self.allocation_type == AllocationType.PE_DUPLICATED else 16
                for _ in range(count):
                    requirements.append(DMARequirement(
                        scope=ResourceScope.ONE_PE,
                        is_input=True
                    ))

        return requirements

    def get_h_file_definitions(self) -> Dict[str, Any]:
        defs = {
            f"{self.name.upper()}_ELEMENT_SIZE": self.element_size,
            f"{self.name.upper()}_ELEMENTS": self.num_elements,
        }

        # Add allocation type specific definitions
        if self.allocation_type == AllocationType.MSS_DUPLICATED:
            defs[f"{self.name.upper()}_MSS_DUPLICATED"] = 1
            # In a real implementation, these would be filled with actual addresses
            defs[f"{self.name.upper()}_START_ADDR0"] = 0  # Placeholder
            defs[f"{self.name.upper()}_START_ADDR1"] = 0  # Placeholder
            defs[f"{self.name.upper()}_LEN0"] = self.total_size // 2
            defs[f"{self.name.upper()}_LEN1"] = self.total_size // 2

        elif self.allocation_type == AllocationType.PE_DUPLICATED:
            defs[f"{self.name.upper()}_PE_DUPLICATED"] = 1
            for i in range(8):
                defs[f"{self.name.upper()}_START_ADDR{i}"] = 0  # Placeholder
                defs[f"{self.name.upper()}_LEN{i}"] = self.total_size // 8

        elif self.allocation_type == AllocationType.MSS_DISTRIBUTED:
            defs[f"{self.name.upper()}_MSS_DISTRIBUTED"] = 1
            for i in range(2):  # Simplified to 2 for this example
                defs[f"{self.name.upper()}_START_ADDR{i}"] = 0  # Placeholder
                defs[f"{self.name.upper()}_LEN{i}"] = self.total_size // 2
                defs[f"{self.name.upper()}_LAST_MSS_LEN{i}"] = self.total_size // 2

        elif self.allocation_type == AllocationType.PE_DISTRIBUTED:
            defs[f"{self.name.upper()}_PE_DISTRIBUTED"] = 1
            for i in range(8):  # Simplified to 8 for this example
                defs[f"{self.name.upper()}_START_ADDR{i}"] = 0  # Placeholder
                defs[f"{self.name.upper()}_LEN{i}"] = self.total_size // 8
                defs[f"{self.name.upper()}_LAST_PE_LEN{i}"] = self.total_size // 8

        return defs

    def get_apb_settings(self, supergroup: KernelSuperGroup) -> BirdCommandSequence:
        """Returns APB settings for VRD for a supergroup"""
        seq = BirdCommandSequence(
            f"VRD APB settings for {self.name}",
            NetworkType(BroadcastType.SUPER_PE_BRCST, GridDestinationType.APB),
            []
        )

        # Apply settings for each location in the supergroup
        for location in supergroup.get_kernel_locations():
            base_address = 0x50000000 + (location.x * 0x10000) + (location.y * 0x1000)
            if location.is_vcore:
                base_address += location.vcore * 0x100

            # Element size and count
            seq.add_single_command(base_address + 0x200, self.element_size)
            seq.add_single_command(base_address + 0x204, self.num_elements)

            # Allocation type
            alloc_type_val = 0
            if self.allocation_type == AllocationType.MSS_DUPLICATED:
                alloc_type_val = 1
            elif self.allocation_type == AllocationType.PE_DUPLICATED:
                alloc_type_val = 2
            elif self.allocation_type == AllocationType.MSS_DISTRIBUTED:
                alloc_type_val = 3
            elif self.allocation_type == AllocationType.PE_DISTRIBUTED:
                alloc_type_val = 4
            seq.add_single_command(base_address + 0x208, alloc_type_val)

            # DMA channel required
            seq.add_single_command(base_address + 0x20C, 1 if self.dma_channel_required else 0)

        return seq


class BroadCastNetwork(HWComponent):
    """Represent the NOC configuration for a specific Broadcast Network"""

    def __init__(self, name: str, noc_network_id: int, supergroup: KernelSuperGroup):
        super().__init__(name)
        self.noc_network_id = noc_network_id
        self.supergroup = supergroup

    def get_required_resources(self) -> List[ResourceRequirement]:
        """Returns a list of required resources"""
        # Get the first location from the supergroup to determine PE coordinates
        first_location = self.supergroup.get_kernel_locations()[0]
        return [NOCBroadCastResource(brcst_id=self.noc_network_id)]

    def wrap_apb_generator(self):

        kernel_x_size, kernel_y_size = self.supergroup._get_kernel_dimensions()
        first_location = self.supergroup.get_kernel_locations()[0]

        return broadcast_config(
                    broadcast_type = 0,
                    broadcast_group_number = self.noc_network_id,
                    pe_number = first_location.x * 0x10 + first_location.y,
                    group_start_pe = first_location.x * 0x10 + first_location.y,
                    group_size = math.log2(kernel_x_size * kernel_y_size),
                    supergroup_size = math.log2(self.supergroup.size_x * self.supergroup.size_y),
                    group_size_x = math.log2(kernel_x_size),
                    supergroup_size_x = math.log2(self.supergroup.size_x),
        )

    def get_apb_settings(self) -> BirdCommandSequence:
        """Returns APB settings for the broadcast network"""
        # For broadcast networks, we don't need to iterate through locations
        # as the settings apply to the entire network
        brcs_apb_regs = self.wrap_apb_generator()

        return BirdCommandSequence(
            f"NOC Broadcast Network {self.name} APB settings",
            NetworkType(BroadcastType.DIRECT, GridDestinationType.APB),
            [BirdCommand(BirdCommandType.SINGLE, addr, data) for addr, data in brcs_apb_regs]
        )
        

class AXI2AHB(HWComponent):
    """Class representing the AXI2AHB bridge configuration for all networks"""

    def __init__(self, name: str = "AXI2AHB_Bridge"):
        super().__init__(name)
        # Dictionary mapping network_type to line_id
        self.network_configs: Dict[NetworkType, int] = {}
        # Dictionary mapping line_id to network_type
        self.line_id_to_network: Dict[int, NetworkType] = {}

    def add_network(self, network_type: NetworkType):
        """Add a network configuration to the bridge.
        
        Args:
            network_type: The type of network to configure
        """
        # Find next available line_id (0-15)
        line_id = self._get_next_line_id()
        
        # Store configuration
        print(f"Adding network {network_type} to AXI2AHB bridge at line_id {line_id}")
        self.network_configs[network_type] = line_id
        self.line_id_to_network[line_id] = network_type

    def _get_next_line_id(self) -> int:
        """Find the next available line ID (0-15)"""
        used_ids = set(self.line_id_to_network.keys())
        for i in range(16):
            if i not in used_ids:
                return i
        raise ValueError("No available line IDs (all 16 are in use)")

    def get_apb_settings(self) -> BirdCommandSequence:
        """Returns APB settings for all configured networks in the AXI2AHB bridge.
        
        Returns:
            BirdCommandSequence: The configuration sequence for all networks
        """
        seq = BirdCommandSequence(
            "AXI2AHB Bridge Initial Configuration",
            NetworkType(BroadcastType.DIRECT, GridDestinationType.APB),
            []
        )
        
        for network_type, line_id in self.network_configs.items():
            base_address = 0x70000000 + (line_id * 0x1000)
            seq.add_single_command(base_address + 0x04, line_id)
            seq.add_single_command(base_address + 0x08, 1, safe=True)
            
        return seq

    def get_apb_switch(self, network_type: NetworkType) -> BirdCommandSequence:
        """Get APB settings to switch to a specific network type.
        
        Args:
            network_type: The network type to switch to
            
        Returns:
            BirdCommandSequence: The switch configuration
        """
        
        if network_type not in self.network_configs:
            raise ValueError(f"No bridge configuration for network type {network_type}")
            
        line_id = self.network_configs[network_type]
        base_address = 0x70000000 + (line_id * 0x1000)
        
        seq = BirdCommandSequence(
            description=f"AXI2AHB Bridge Switch to {network_type.value}",
            network_type=NetworkType(BroadcastType.DIRECT, GridDestinationType.APB),
            commands=[]
        )
        
        seq.add_single_command(base_address + 0x04, line_id)
        seq.add_single_command(base_address + 0x08, 1, safe=True)
        
        return seq
