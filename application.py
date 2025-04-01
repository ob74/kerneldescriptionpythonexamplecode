import json
from typing import Dict, List, Tuple, Any
from grid import Grid
from kernel import Kernel
from hw_components import KernelSizeComponent
from kernel_types import KernelSize, KernelLocation, KernelSuperGroup
from bird import BirdCommandSequence
from network import BroadCastNetwork, GridDestinationType

# Application class (Stage 2 - Application Definition)
class Application:
    def __init__(self, name: str, grid: Grid):
        self.name = name
        self.grid = grid
        self.kernels: List[Tuple[Kernel, KernelSuperGroup]] = []

    def add_kernel(self, kernel: Kernel, supergroup: KernelSuperGroup):
        """Add a kernel at multiple locations defined by a supergroup
        
        Args:
            kernel: The kernel to add
            supergroup: The supergroup defining where the kernel should be deployed
        """
        # Verify kernel size matches supergroup
        if kernel.size_component.size != supergroup.kernel_size:
            raise ValueError(f"Kernel size {kernel.size_component.size} does not match supergroup kernel size {supergroup.kernel_size}")
            
        # Allocate all locations in the supergroup
        for location in supergroup.get_kernel_locations():
            assert self.grid.allocate_kernel(kernel.size_component, location)
            
        # Add networks to the grid based on kernel type and supergroup
        # we need broadcast networks for both PE and MSS access
        # PE broadcast network
        pe_network = BroadCastNetwork(f"pe_network_{kernel.name}", 1, supergroup)
        self.grid.add_noc_brcst_setting(0x60001000, 1)  # Network ID 1
        self.grid.add_axi2ahb_bridge(pe_network, GridDestinationType.VCORE)
        
        # MSS broadcast network
        mss_network = BroadCastNetwork(f"mss_network_{kernel.name}", 2, supergroup)
        self.grid.add_noc_brcst_setting(0x60002000, 2)  # Network ID 2
        self.grid.add_axi2ahb_bridge(mss_network, GridDestinationType.MSS)
            
        self.kernels.append((kernel, supergroup))

    def generate_basic_sequence(self) -> bytes:
        """Convert a Bird list of command sequences to bytes.
        
        Args:
            command_sequences: List of BirdCommandSequence objects
            
        Returns:
            bytes: Complete binary sequence
        """
        result = bytearray()
        for sequence in self.generate_bird_sequence():
            result.extend(sequence.to_bytes())
        return bytes(result)

    def generate_bird_sequence(self) -> List[BirdCommandSequence]:
        """Generate the complete BIRD sequence for the application.
        
        Returns:
            List of BirdCommandSequence objects containing all initialization commands
        """
        all_sequences = []
        current_network = None
        
        # Collect all command sequences from kernels
        for kernel, supergroup in self.kernels:
            kernel_sequences = kernel.generate_bird_sequence(supergroup)
            
            # Add all sequences from the kernel
            for sequence in kernel_sequences:
                # Switch network if needed
                if sequence.network_type != current_network:
                    network_config = self.grid.get_apb_settings(sequence.network_type)
                    all_sequences.append(network_config)
                    current_network = sequence.network_type
                all_sequences.append(sequence)
        
        return all_sequences


