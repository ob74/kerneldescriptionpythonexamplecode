import json
from typing import Dict, List, Any, Tuple, Optional
from hw_components import HWComponent, KernelSizeComponent, IOChannel, VariableResidentData
from kernel_types import KernelSize, KernelLocation
from resource_allocators import MemoryAllocator


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
        self.pm_binary: Optional[bytes] = None
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

    def generate_apb_settings(self, location: KernelLocation) -> List[Tuple[int, int]]:
        """Generate all APB settings for the kernel at a specific location.
        
        Args:
            location: KernelLocation specifying where the kernel is placed
            
        Returns:
            List of (address, value) tuples for APB settings
        """
        apb_settings = []

        # Get all components
        all_components = [self.size_component] + self.io_channels + self.vrd_components + self.other_components

        # Generate APB settings for each component
        for component in all_components:
            component_apb = component.get_apb_settings(location)
            apb_settings.extend(component_apb)

        return apb_settings

    def set_pm_binary(self, binary: bytes):
        """Set the PM binary for this kernel.
        
        Args:
            binary: Bytes array containing the kernel's PM binary code
        """
        self.pm_binary = binary
        self.is_built = True

    def generate_bird_sequence(self, location: KernelLocation) -> Dict[str, Any]:
        """Generate BIRD sequence for kernel initialization at a specific location.
        
        Args:
            location: KernelLocation specifying where the kernel is placed
            
        Returns:
            Dict containing APB settings, MSS_FIXED data, MSS_VRD data, and PM binary
        
        Raises:
            RuntimeError: If kernel is not built (no PM binary set)
        """
        if not self.is_built:
            raise RuntimeError(f"Kernel {self.name} is not built. Set PM binary before deployment.")

        # Allocate resources first
        self.allocate_resources()

        # Calculate destination addresses for all PEs and vcores
        dst_addrs = []
        if self.size_component.size == KernelSize.ONE_VCORE:
            # For vcore kernels, just use the specific vcore
            base_addr = 0x50000000 + (location.x * 0x10000) + (location.y * 0x1000)
            if location.is_vcore:
                dst_addrs.append(base_addr + location.vcore * 0x100)
        else:
            # For regular kernels, include all PEs in the kernel area
            kernel_x, kernel_y = self.size_component.get_dimensions()
            for x in range(location.x, location.x + kernel_x):
                for y in range(location.y, location.y + kernel_y):
                    base_addr = 0x50000000 + (x * 0x10000) + (y * 0x1000)
                    # Add all 4 vcores for each PE
                    for vcore in range(4):
                        dst_addrs.append(base_addr + vcore * 0x100)

        # Create BIRD sequence
        bird = {
            "APB": self.generate_apb_settings(location),
            "MSS_FIXED": [],
            "MSS_VRD": [],
            "PM_BINARY": {
                "dst_addrs": dst_addrs,
                "data": self.pm_binary
            }
        }

        # Add VRD entries
        for vrd in self.vrd_components:
            if vrd.name in self.allocated_resources:
                resources = self.allocated_resources[vrd.name]
                for i, resource in enumerate(resources):
                    if isinstance(resource, MemoryResource):
                        bird["MSS_VRD"].append({
                            "vrd_name": f"{vrd.name}_{i}",
                            "vrd_size": resource.length,
                            "dst_addr": resource.address
                        })

        return bird

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

