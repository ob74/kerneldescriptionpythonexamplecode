from enum import Enum
from typing import List, Union
from dataclasses import dataclass

class NetworkType(Enum):
    DIRECT = "direct"
    MSS_BRCST = "mss_broadcast"
    ALL_PE_BRCST = "all_pe_broadcast"
    PE_ID_BRCST = "pe_id_broadcast"

class BirdCommandType(Enum):
    SINGLE = "single"
    DMA = "dma"

@dataclass
class BirdCommand:
    type: BirdCommandType
    dst_addr: int
    data: Union[int, List[int]]  # single 32-bit value for SINGLE, list of values for DMA

    def __post_init__(self):
        if self.type == BirdCommandType.SINGLE and not isinstance(self.data, int):
            raise ValueError("SINGLE command must have int data")
        if self.type == BirdCommandType.DMA and not isinstance(self.data, list):
            raise ValueError("DMA command must have list data")

    def to_bytes(self) -> bytes:
        """Convert command to byte sequence.
        
        Format:
        SINGLE: [type(1B)] [total_len(4B)] [dst_addr(4B)] [data(4B)]
        DMA: [type(1B)] [total_len(4B)] [dst_addr(4B)] [data_len(4B)] [data(Nx4B)]
        """
        if self.type == BirdCommandType.SINGLE:
            total_len = 13  # 1 + 4 + 4 + 4
            return (
                bytes([1]) +                          # type = 1 for SINGLE
                total_len.to_bytes(4, 'little') +     # total length
                self.dst_addr.to_bytes(4, 'little') + # destination address
                self.data.to_bytes(4, 'little')       # data
            )
        else:  # DMA
            data_bytes = b''.join(x.to_bytes(4, 'little') for x in self.data)
            total_len = 13 + len(data_bytes)  # 1 + 4 + 4 + 4 + data_len
            return (
                bytes([2]) +                          # type = 2 for DMA
                total_len.to_bytes(4, 'little') +     # total length
                self.dst_addr.to_bytes(4, 'little') + # destination address
                len(self.data).to_bytes(4, 'little') +# number of data words
                data_bytes                            # data
            )

@dataclass
class BirdCommandSequence:
    description: str
    network_type: NetworkType
    commands: List[BirdCommand]

    def add_command(self, command: BirdCommand):
        self.commands.append(command)

    def add_single_command(self, dst_addr: int, data: int):
        self.commands.append(BirdCommand(BirdCommandType.SINGLE, dst_addr, data))

    def add_dma_command(self, dst_addr: int, data: List[int]):
        self.commands.append(BirdCommand(BirdCommandType.DMA, dst_addr, data))

    def to_bytes(self) -> bytes:
        """Convert entire sequence to byte sequence."""
        return b''.join(cmd.to_bytes() for cmd in self.commands)

    def __str__(self) -> str:
        lines = [
            f"Command Sequence: {self.description}",
            f"Network Type: {self.network_type.value}",
            "Commands:"
        ]
        
        for i, cmd in enumerate(self.commands, 1):
            lines.append(f"\n{i}. {cmd.type.value.upper()} command to 0x{cmd.dst_addr:08X}")
            if cmd.type == BirdCommandType.SINGLE:
                lines.append(f"   Data: 0x{cmd.data:08X}")
            else:  # DMA
                lines.append(f"   Data ({len(cmd.data)} words):")
                # Split data into chunks of 8
                for j in range(0, len(cmd.data), 8):
                    chunk = cmd.data[j:j+8]
                    hex_chunk = [f"0x{x:08X}" for x in chunk]
                    lines.append(f"   {' '.join(hex_chunk)}")
        
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "network_type": self.network_type.value,
            "commands": [
                {
                    "type": cmd.type.value,
                    "dst_addr": cmd.dst_addr,
                    "data": cmd.data
                } for cmd in self.commands
            ]
        }

@dataclass
class Grid:
    """Class representing the grid configuration for BIRD commands."""
    
    def __init__(self):
        # Initialize empty settings for each network type
        self.axi2ahb_settings = []  # List of (addr, data) tuples for AXI2AHB settings
        self.noc_brcst_settings = []  # List of (addr, data) tuples for NOC broadcast settings
        
    def add_axi2ahb_setting(self, addr: int, data: int):
        """Add an AXI2AHB bridge setting.
        
        Args:
            addr: APB address for the setting
            data: Value to write to the address
        """
        self.axi2ahb_settings.append((addr, data))
        
    def add_noc_brcst_setting(self, addr: int, data: int):
        """Add a NOC broadcast network setting.
        
        Args:
            addr: APB address for the setting
            data: Value to write to the address
        """
        self.noc_brcst_settings.append((addr, data))
        
    def get_apb_settings(self, network_type: NetworkType) -> BirdCommandSequence:
        """Get APB settings for a specific network type.
        
        Args:
            network_type: The type of network to get settings for
            
        Returns:
            BirdCommandSequence containing the APB settings for the specified network
            
        Raises:
            ValueError: If network_type is not supported
        """
        if network_type == NetworkType.DIRECT:
            # For direct access, we need AXI2AHB settings
            sequence = BirdCommandSequence(
                description="AXI2AHB Bridge Configuration",
                network_type=NetworkType.DIRECT,
                commands=[]
            )
            for addr, data in self.axi2ahb_settings:
                sequence.add_single_command(addr, data)
                
        elif network_type in [NetworkType.MSS_BRCST, NetworkType.ALL_PE_BRCST, NetworkType.PE_ID_BRCST]:
            # For broadcast access, we need NOC broadcast settings
            sequence = BirdCommandSequence(
                description="NOC Broadcast Network Configuration",
                network_type=network_type,
                commands=[]
            )
            for addr, data in self.noc_brcst_settings:
                sequence.add_single_command(addr, data)
                
        else:
            raise ValueError(f"Unsupported network type: {network_type}")
            
        return sequence 