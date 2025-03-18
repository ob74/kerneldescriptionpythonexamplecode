import json
from typing import Dict, List, Tuple, Any
from grid import Grid
from kernel import Kernel
from hw_components import KernelSizeComponent
from kernel_types import KernelSize, KernelLocation
from bird import BirdCommandSequence

# Application class (Stage 2 - Application Definition)
class Application:
    def __init__(self, name: str, grid: Grid):
        self.name = name
        self.grid = grid
        self.kernels: List[Tuple[Kernel, List[KernelLocation]]] = []

    def add_kernel(self, kernel: Kernel, locations: List[KernelLocation]):
        """Add a kernel at multiple locations
        
        Args:
            kernel: The kernel to add
            locations: List of locations where the kernel should be deployed
        """
        for location in locations:
            assert self.grid.allocate_kernel(kernel.size_component, location)
        self.kernels.append((kernel, locations))

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
        for kernel, locations in self.kernels:
            # Get kernel's BIRD sequence for each location
            for location in locations:
                kernel_sequences = kernel.generate_bird_sequence(location)
                
                # Add all sequences from the kernel
                for sequence in kernel_sequences:
                    # Switch network if needed
                    if sequence.network_type != current_network:
                        network_config = self.grid.get_apb_settings(sequence.network_type)
                        all_sequences.append(network_config)
                        current_network = sequence.network_type
                    all_sequences.append(sequence)
        
        return all_sequences


