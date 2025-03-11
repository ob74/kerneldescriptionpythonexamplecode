import json
from typing import Dict, List, Tuple, Any
from grid import Grid
from kernel import Kernel
from hw_components import KernelSizeComponent
from kernel_types import KernelSize, KernelLocation

# Application class (Stage 2 - Application Definition)
class Application:
    def __init__(self, name: str, platform: Grid):
        self.name = name
        self.platform = platform
        self.kernels = {}  # Dict[str, Tuple[Kernel, List[KernelLocation]]]

    def add_kernel(self, kernel: Kernel, locations: List[KernelLocation]) -> bool:
        """Add a kernel to the application with its deployment locations.
        
        Args:
            kernel: The kernel to add
            locations: List of KernelLocation objects specifying where to deploy the kernel
            
        Returns:
            bool: True if kernel was successfully added, False if any location is invalid
        """
        # Try to allocate kernel at all locations
        for location in locations:
            if not self.platform.allocate_kernel(kernel.size_component, location):
                return False
                
        # If all allocations successful, store kernel and its locations
        self.kernels[kernel.name] = (kernel, locations)
        return True

    def generate_basic_sequence(self, bird_sequence: Dict[str, Any]) -> bytes:
        """Generate BASIC sequence from BIRD sequence.
        
        Args:
            bird_sequence: Combined BIRD sequence from all kernels
            
        Returns:
            bytes: The encoded BASIC sequence
        """
        result = bytearray()

        # Add APB settings
        for addr, data in bird_sequence.get("APB", []):
            # Type = 1 for single write
            result.extend(b'\x01')
            # Length = 8 (4 bytes addr + 4 bytes data)
            result.extend(b'\x08')
            # Address (4 bytes)
            result.extend(addr.to_bytes(4, byteorder='little'))
            # Data (4 bytes)
            result.extend(data.to_bytes(4, byteorder='little'))

        # Add VRD info
        for vrd in bird_sequence.get("MSS_VRD", []):
            # Type = 2 for VRD info
            result.extend(b'\x02')
            # Length = 8 + len(vrd_name)
            name_bytes = vrd["vrd_name"].encode('utf-8')
            result.extend((8 + len(name_bytes)).to_bytes(4, byteorder='little'))
            # VRD name
            result.extend(name_bytes)
            # VRD size (4 bytes)
            result.extend(vrd["vrd_size"].to_bytes(4, byteorder='little'))
            # Destination address (4 bytes)
            result.extend(vrd["dst_addr"].to_bytes(4, byteorder='little'))

        # Add PM binaries as DMA write commands
        for pm_binary in bird_sequence.get("PM_BINARIES", []):
            binary_data = pm_binary["data"]
            data_length = len(binary_data)
            
            # Generate a DMA write command for each destination address
            for dst_addr in pm_binary["dst_addrs"]:
                # Type = 4 for DMA write
                result.extend(b'\x04')
                # Length = data length + 8 (4 for dst_addr + 4 for data_length)
                result.extend((data_length + 8).to_bytes(4, byteorder='little'))
                # Destination address (4 bytes)
                result.extend(dst_addr.to_bytes(4, byteorder='little'))
                # Data length (4 bytes)
                result.extend(data_length.to_bytes(4, byteorder='little'))
                # Binary data
                result.extend(binary_data)

        return bytes(result)

    def deploy(self) -> Dict[str, Any]:
        """Deploy all kernels in the application.
        
        Returns:
            Dict containing:
                - h_files: Dict of kernel header files
                - apb_list: List of all APB settings
                - bird_sequence: Combined BIRD sequence for all kernels
                - basic_sequence: Combined BASIC sequence for all kernels
                
        Raises:
            RuntimeError: If any kernel is not built (no PM binary set)
        """
        # First verify all kernels are built
        for kernel_name, (kernel, _) in self.kernels.items():
            if not kernel.is_built:
                raise RuntimeError(f"Kernel {kernel_name} is not built. Set PM binary before deployment.")
        
        result = {
            "h_files": {},
            "apb_list": [],
            "bird_sequence": {
                "APB": [],
                "MSS_FIXED": [],
                "MSS_VRD": [],
                "PM_BINARIES": []
            }
        }
        
        for kernel_name, (kernel, locations) in self.kernels.items():
            # Generate header file
            kernel.allocate_resources()
            result["h_files"][kernel_name] = kernel.generate_h_file_content()
            
            # Generate APB settings and BIRD sequence for each location
            for location in locations:
                # Get APB settings
                result["apb_list"].extend(kernel.generate_apb_settings(location))
                
                # Generate and combine BIRD sequence
                bird_seq = kernel.generate_bird_sequence(location)
                result["bird_sequence"]["APB"].extend(bird_seq["APB"])
                result["bird_sequence"]["MSS_FIXED"].extend(bird_seq["MSS_FIXED"])
                result["bird_sequence"]["MSS_VRD"].extend(bird_seq["MSS_VRD"])
                result["bird_sequence"]["PM_BINARIES"].append(bird_seq["PM_BINARY"])
        
        # Generate BASIC sequence from combined BIRD sequence
        result["basic_sequence"] = self.generate_basic_sequence(result["bird_sequence"])
        return result

