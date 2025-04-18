import json
from typing import Dict, List, Any, Tuple, Optional
from hw_components import HWComponent, KernelSizeComponent, IOChannel, VariableResidentData, KernelSuperGroup
from kernel_types import KernelSize, KernelLocation
from resource_allocators import MemoryAllocator
from kernel_binary_parser import KernelBinary
from hw_resources import MemoryResource
from bird import BirdCommandSequence, NetworkType, BroadcastType, GridDestinationType

VCORE_PM = 0
VCORE_PM_SIZE = 0x4000

# Kernel class (Stage 1 - Kernel Definition)
class Kernel:
    def __init__(self, name: str, size: KernelSize):
        """Initialize a kernel with a name and size.
        
        Args:
            name: The name of the kernel
            size: The KernelSize enum value specifying the kernel's size
        """
        self.name = name
        self.size_component = KernelSizeComponent(size)
        self.allocated = False
        self.is_built = False
        self.binaries: List[KernelBinary] = []
        self.io_channels: List[IOChannel] = []
        self.vrd_components: List[VariableResidentData] = []
        self.other_components: List[HWComponent] = []
        self.allocated_resources: Dict[str, Any] = {}
        self.memory_allocator = MemoryAllocator(self.size_component)

    def add_io_channel(self, channel: IOChannel):
        self.io_channels.append(channel)

    def add_vrd(self, vrd: VariableResidentData):
        self.vrd_components.append(vrd)

    def add_component(self, component: HWComponent):
        self.other_components.append(component)

    def add_binary(self, binary: KernelBinary):
        """Add a binary (PM, DM, VM) to this kernel.
        
        Args:
            binary: KernelBinaryType instance containing the binary data
        """
        self.binaries.append(binary)

    def allocate_resources(self):
        """Allocate resources for all components"""
        self.allocated = True
        self.memory_allocator.reset()

        # Get all components
        all_components = [self.size_component] + self.io_channels + self.vrd_components + self.other_components

        # Allocate resources for each component
        for component in all_components:
            requirements = component.get_required_resources()
            resources = []

            for req in requirements:
                res = self.memory_allocator.allocate(req)
                resources.append(res)

            if resources:
                self.allocated_resources[component.name] = resources

    def generate_h_file_content(self) -> str:
        """Generate header file content for kernel configuration.
        
        Returns:
            str: The complete header file content
        """
        lines = []
        lines.append("// Automatically generated kernel configuration")
        lines.append(f"// Kernel: {self.name}\n")

        lines.append("#ifndef __KERNEL_CONFIG_H__")
        lines.append("#define __KERNEL_CONFIG_H__\n")

        lines.append("#include <stdint.h>\n")

        # Get all components
        all_components = [self.size_component] + self.io_channels + self.vrd_components + self.other_components

        # Generate defines for each component
        for component in all_components:
            lines.append(f"// {component.name} configuration")

            # Get all definitions
            defs = component.get_h_file_definitions()

            # Write struct definitions first if present
            struct_keys = [k for k in defs.keys() if k.startswith("STRUCT_")]
            for key in struct_keys:
                lines.append(f"{defs[key]}")
                del defs[key]  # Remove to avoid duplication

            # Write regular defines
            for key, value in defs.items():
                if isinstance(value, str):
                    lines.append(f"#define {key} {value}")
                else:
                    lines.append(f"#define {key} {value}")

            lines.append("")  # Empty line between components

        # Add resource allocations
        lines.append("// Resource allocations")
        for component_name, resources in self.allocated_resources.items():
            lines.append(f"// Resources for {component_name}")
            for i, resource in enumerate(resources):
                if isinstance(resource, MemoryResource):
                    lines.append(f"#define {component_name.upper()}_ADDR{i} 0x{resource.address:08x}")
                    lines.append(f"#define {component_name.upper()}_SIZE{i} {resource.length}")
                    lines.append(f"#define {component_name.upper()}_END{i} 0x{resource.address + resource.length:08x}")
            lines.append("")  # Empty line between components

        lines.append("#endif // __KERNEL_CONFIG_H__")

        # Join all lines with newlines
        return "\n".join(lines)

  

    def generate_bird_sequence(self, supergroup: KernelSuperGroup) -> List[BirdCommandSequence]:
        """Generate BIRD sequence for kernel initialization for a supergroup.
        
        Args:
            supergroup: KernelSuperGroup specifying where the kernel is placed
            
        Returns:
            List of BirdCommandSequence objects containing all initialization commands
        
        Raises:
            RuntimeError: If kernel is not built (no PM binary set)
        """
        if len(self.binaries) == 0:
            raise RuntimeError(f"Kernel {self.name} is not built. Add PM binary before deployment.")

        # Allocate resources first
        self.allocate_resources()

        sequences = []

        # Add APB settings for all components
        all_components = [self.size_component] + self.io_channels + self.vrd_components + self.other_components
        for component in all_components:
            sequences.append(component.get_apb_settings(supergroup))

        # Add all binaries
        for binary in self.binaries:
            sequences.append(binary.generate_bird_sequence())

        # Add VRD entries
        for vrd in self.vrd_components:
            if vrd.name in self.allocated_resources:
                resources = self.allocated_resources[vrd.name]
                for i, resource in enumerate(resources):
                    if isinstance(resource, MemoryResource):
                        vrd_seq = BirdCommandSequence(
                            description=f"VRD {vrd.name}_{i} for {self.name}",
                            network_type=NetworkType(BroadcastType.SUPER_MSS_BRCST, GridDestinationType.MSS),
                            commands=[]
                        )
                        # Add VRD data commands...
                        sequences.append(vrd_seq)

        return sequences

    def save_to_json(self, output_file: str):
        """Save kernel configuration to JSON"""
        config = {
            "name": self.name,
            "size": self.size_component.size.value,
            "io_channels": [],
            "vrd_components": [],
        }

        # Add IO channels
        for channel in self.io_channels:
            channel_config = {
                "name": channel.name,
                "type": channel.channel_type.value,
                "buffer_size": channel.buffer_size,
                "buffer_location": channel.buffer_location.value,
                "num_buffers": channel.num_buffers,
            }

            if channel.element_type and channel.element_fields:
                channel_config["element_type"] = channel.element_type
                channel_config["element_fields"] = [
                    {"name": field.name, "size": field.size}
                    for field in channel.element_fields
                ]

            config["io_channels"].append(channel_config)

        # Add VRD components
        for vrd in self.vrd_components:
            vrd_config = {
                "name": vrd.name,
                "element_size": vrd.element_size,
                "num_elements": vrd.num_elements,
                "data_file_path": vrd.data_file_path,
                "allocation_type": vrd.allocation_type.value,
                "dma_channel_required": vrd.dma_channel_required
            }

            config["vrd_components"].append(vrd_config)

        # Save to file
        with open(output_file, 'w') as f:
            json.dump(config, f, indent=4)

    @classmethod
    def load_from_json(cls, input_file: str):
        """Load kernel configuration from JSON"""
        with open(input_file, 'r') as f:
            config = json.load(f)

        # Create kernel with size
        kernel = cls(config["name"], KernelSize(config["size"]))

        # Add IO channels
        for channel_config in config.get("io_channels", []):
            element_fields = None
            if "element_fields" in channel_config:
                element_fields = [
                    ElementField(field["name"], field["size"])
                    for field in channel_config["element_fields"]
                ]

            channel = IOChannel(
                name=channel_config["name"],
                channel_type=ChannelType(channel_config["type"]),
                buffer_size=channel_config["buffer_size"],
                buffer_location=BufferLocationType(channel_config["buffer_location"]),
                num_buffers=channel_config.get("num_buffers", 1),
                element_type=channel_config.get("element_type"),
                element_fields=element_fields
            )

            kernel.add_io_channel(channel)

        # Add VRD components
        for vrd_config in config.get("vrd_components", []):
            vrd = VariableResidentData(
                name=vrd_config["name"],
                element_size=vrd_config["element_size"],
                num_elements=vrd_config["num_elements"],
                data_file_path=vrd_config["data_file_path"],
                allocation_type=AllocationType(vrd_config["allocation_type"]),
                dma_channel_required=vrd_config.get("dma_channel_required", False)
            )

            kernel.add_vrd(vrd)

        return kernel

