from typing import Dict, List, Optional, Tuple, Union, Any
from hw_components import BroadCastNetwork, AXI2AHB
from kernel_types import KernelSize, KernelLocation, KernelSuperGroup
from bird import NetworkType, BirdCommandSequence, GridDestinationType, BroadcastType

class GridNOC:
    """Handles all network-related functionality for a grid"""
    
    def __init__(self):
        # Network components
        self.axi2ahb = AXI2AHB()
        # Command sequence for all broadcast networks
        self.broadcast_sequence = BirdCommandSequence(
            description="NOC Broadcast Network Configuration",
            network_type=NetworkType(BroadcastType.SUPER_PE_BRCST, GridDestinationType.VCORE),
            commands=[]
        )
        
        # Initialize AXI2AHB with all network types
        self._init_axi2ahb_networks()
        
    def _init_axi2ahb_networks(self):
        """Initialize AXI2AHB with all network types"""
        # Initialize for each network type
        self.axi2ahb.add_network(NetworkType(BroadcastType.DIRECT, GridDestinationType.APB))
        self.axi2ahb.add_network(NetworkType(BroadcastType.SUPER_PE_BRCST, GridDestinationType.APB))
        self.axi2ahb.add_network(NetworkType(BroadcastType.SUPER_MSS_BRCST, GridDestinationType.VCORE))
        self.axi2ahb.add_network(NetworkType(BroadcastType.SUPER_MSS_BRCST, GridDestinationType.MSS))
        
    def add_broadcast_network(self, supergroup: KernelSuperGroup, network_type: NetworkType) -> None:
        """Add a broadcast network for a specific supergroup and network type.
        
        Args:
            supergroup: The supergroup this network will serve
            network_type: The type of network to create
        """
        # Create a temporary broadcast network to get its settings
        network = BroadCastNetwork(
            f"network_{network_type.value}_{supergroup.x}_{supergroup.y}",
            len(self.broadcast_sequence.commands),  # Use command count as ID
            supergroup
        )
        # Add its settings to our sequence
        network_seq = network.get_apb_settings(supergroup)
        self.broadcast_sequence.commands.extend(network_seq.commands)
        
    def get_apb_settings(self, network_type: NetworkType) -> BirdCommandSequence:
        """Get APB settings for a specific network type."""
        if network_type.broadcast_type == BroadcastType.DIRECT:
            # For direct access, use AXI2AHB settings
            return self.axi2ahb.get_apb_settings()
            
        elif network_type.broadcast_type in [
            BroadcastType.PEG_MSS_BRCST,
            BroadcastType.SUPER_PE_BRCST,
            BroadcastType.SUPER_PE_ID_BRCST,
            BroadcastType.SUPER_MSS_BRCST,
            BroadcastType.PEG_PE_BRCST
        ]:
            # Return our pre-built broadcast sequence
            return self.broadcast_sequence
            
        else:
            raise ValueError(f"Unsupported broadcast type: {network_type.broadcast_type}")
            
    def get_network_switch(self, network_type: NetworkType) -> BirdCommandSequence:
        """Get APB settings to switch to a specific network type.
        
        Args:
            network_type: The network type to switch to
            
        Returns:
            BirdCommandSequence: The switch configuration
        """
        return self.axi2ahb.get_apb_switch(network_type) 