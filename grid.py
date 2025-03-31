from typing import Dict, List, Optional, Tuple, Union, Any, Set
from hw_components import KernelSizeComponent, BroadCastNetwork, AXI2AHB
from kernel_types import KernelSize, KernelLocation, KernelSuperGroup
from bird import NetworkType, BirdCommandSequence, GridDestinationType, BroadcastType

class Grid:
    """Represents the hardware platform grid configuration"""
    def __init__(self, size_x: int, size_y: int):
        self.size_x = size_x
        self.size_y = size_y
        # Set of regular nodes (x, y) that are allocated
        self.allocated_nodes: Set[Tuple[int, int]] = set()
        # Dict mapping (x, y) to set of allocated vcores
        self.allocated_vcores: Dict[Tuple[int, int], Set[int]] = {}
        # Network components
        self.axi2ahb = AXI2AHB()  # Get singleton instance
        self.brcst_networks: List[BroadCastNetwork] = []
        
    def add_axi2ahb_bridge(self, network: BroadCastNetwork, destination_type: GridDestinationType):
        """Add a network configuration to the AXI2AHB bridge.
        
        Args:
            network: The broadcast network to configure
            destination_type: The type of destination (VCORE, MSS, APB)
        """
        self.axi2ahb.add_network(network, destination_type)
        
    def add_noc_brcst_setting(self, addr: int, data: int):
        """Add a NOC broadcast network setting
        
        Args:
            addr: The address containing the network ID
            data: The data containing network configuration
        """
        network_id = (addr >> 12) & 0xF
        # Create a supergroup that covers the entire grid for broadcast
        supergroup = KernelSuperGroup(
            x=0, y=0,
            size_x=self.size_x, size_y=self.size_y,
            kernel_size=KernelSize.SIZE_1X1  # Use 1x1 as base size for broadcast
        )
        network = BroadCastNetwork(f"brcst_network_{network_id}", network_id, supergroup)
        self.brcst_networks.append(network)
        
    def get_apb_settings(self, network_type: NetworkType) -> BirdCommandSequence:
        """Get APB settings for a specific network type."""
        if network_type.broadcast_type == BroadcastType.DIRECT:
            # For direct access, create a dummy supergroup for the AXI2AHB settings
            supergroup = KernelSuperGroup(0, 0, 1, 1, KernelSize.SIZE_1X1)
            return self.axi2ahb.get_apb_settings(supergroup)
            
        elif network_type.broadcast_type in [
            BroadcastType.PEG_MSS_BRCST,
            BroadcastType.SUPER_PE_BRCST,
            BroadcastType.SUPER_PE_ID_BRCST
        ]:
            sequence = BirdCommandSequence(
                description="NOC Broadcast Network Configuration",
                network_type=network_type,
                commands=[]
            )
            
            # Create a supergroup that covers the entire grid
            supergroup = KernelSuperGroup(0, 0, self.size_x, self.size_y, KernelSize.SIZE_1X1)
            
            # Get settings from all broadcast networks
            for network in self.brcst_networks:
                network_seq = network.get_apb_settings(supergroup)
                sequence.commands.extend(network_seq.commands)
            
        else:
            raise ValueError(f"Unsupported broadcast type: {network_type.broadcast_type}")
            
        return sequence
        
    def _is_within_bounds(self, x: int, y: int) -> bool:
        """Check if a location is within platform dimensions"""
        return 0 <= x < self.size_x and 0 <= y < self.size_y
        
    def _is_aligned_with_kernel_size(self, x: int, y: int, kernel_x: int, kernel_y: int) -> bool:
        """Check if location coordinates align with kernel dimensions"""
        return x % kernel_x == 0 and y % kernel_y == 0
        
    def _is_area_free(self, start_x: int, start_y: int, kernel_x: int, kernel_y: int) -> bool:
        """Check if the area required for kernel placement is free"""
        for x in range(start_x, start_x + kernel_x):
            for y in range(start_y, start_y + kernel_y):
                if (x, y) in self.allocated_nodes:
                    return False
                # If any vcores are allocated in this area, it's not free
                if (x, y) in self.allocated_vcores:
                    return False
        return True

    def _is_vcore_free(self, x: int, y: int, vcore: int) -> bool:
        """Check if a specific vcore is free at the given location"""
        if (x, y) in self.allocated_nodes:
            return False
        return not ((x, y) in self.allocated_vcores and vcore in self.allocated_vcores[(x, y)])
        
    def _mark_area_allocated(self, start_x: int, start_y: int, kernel_x: int, kernel_y: int):
        """Mark an area as allocated"""
        for x in range(start_x, start_x + kernel_x):
            for y in range(start_y, start_y + kernel_y):
                self.allocated_nodes.add((x, y))

    def _mark_vcore_allocated(self, x: int, y: int, vcore: int):
        """Mark a vcore as allocated"""
        if (x, y) not in self.allocated_vcores:
            self.allocated_vcores[(x, y)] = set()
        self.allocated_vcores[(x, y)].add(vcore)
                
    def allocate_kernel(self, kernel_size: KernelSizeComponent, location: KernelLocation) -> bool:
        """Attempt to allocate a kernel at the specified location.
        
        Args:
            kernel_size: The KernelSizeComponent containing kernel dimensions
            location: KernelLocation specifying where to place the kernel
            
        Returns:
            bool: True if allocation successful, False otherwise
        """
        x, y = location.x, location.y
        
        # Check if location is within platform bounds
        if not self._is_within_bounds(x, y):
            return False

        # Handle ONE_VCORE kernels
        if kernel_size.size == KernelSize.ONE_VCORE:
            if not location.is_vcore:
                return False
            if not self._is_vcore_free(x, y, location.vcore):
                return False
            self._mark_vcore_allocated(x, y, location.vcore)
            return True

        # Handle regular kernels
        if location.is_vcore:
            return False  # Regular kernels can't be allocated to vcore locations
            
        kernel_x, kernel_y = kernel_size.get_dimensions()
        
        # Check if the end point is within bounds
        if not self._is_within_bounds(x + kernel_x - 1, y + kernel_y - 1):
            return False
            
        # Check if location aligns with kernel size
        if not self._is_aligned_with_kernel_size(x, y, kernel_x, kernel_y):
            return False
            
        # Check if area is free
        if not self._is_area_free(x, y, kernel_x, kernel_y):
            return False
            
        # If all checks pass, mark area as allocated
        self._mark_area_allocated(x, y, kernel_x, kernel_y)
        return True


class Chip(Grid):
    """Represents a 16x16 chip grid"""
    def __init__(self):
        super().__init__(16, 16)


class Haps(Grid):
    """Represents a 16x16 chip grid"""
    def __init__(self):
        super().__init__(4, 2)

