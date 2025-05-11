from enum import Enum
from typing import List, Union
from dataclasses import dataclass

class BroadcastType(Enum):
    DIRECT = "direct"
    PEG_MSS_BRCST = "peg_mss_broadcast"
    PEG_PE_BRCST = "peg_pe_broadcast"
    SUPER_PE_ID_BRCST = "supergroup_pe_id_broadcast"
    SUPER_PE_BRCST = "supergroup_pe_broadcast"
    SUPER_MSS_BRCST = "supergroup_mss_broadcast"

class GridDestinationType(Enum):
    VCORE = "vcore"
    MSS = "mss"
    APB = "apb"

class BirdCommandType(Enum):
    SINGLE = "single"
    SAFE_SINGLE = "safe_single"
    DMA = "dma"

class NetworkType:
    """Represents a network configuration with broadcast type and destination"""
    def __init__(self, broadcast_type: BroadcastType, destination_type: GridDestinationType):
        self.broadcast_type = broadcast_type
        self.destination_type = destination_type

    def __eq__(self, other: 'NetworkType') -> bool:
        if not isinstance(other, NetworkType):
            return False
        return (self.broadcast_type == other.broadcast_type and 
                self.destination_type == other.destination_type)

    def __hash__(self) -> int:
        return hash((self.broadcast_type, self.destination_type))

    @property
    def value(self) -> str:
        """For backwards compatibility with string representations"""
        return f"{self.broadcast_type.value}_{self.destination_type.value}"

    def __str__(self) -> str:
        """String representation of the network type"""
        return f"NetworkType({self.broadcast_type}, {self.destination_type})"

    def __repr__(self) -> str:
        """Detailed string representation for debugging"""
        return self.__str__()

@dataclass
class BirdCommand:
    type: BirdCommandType
    dst_addr: int
    data: Union[int, bytes]  # single 32-bit value for SINGLE, bytes for DMA

    def __post_init__(self):
        if self.type == BirdCommandType.SINGLE and not isinstance(self.data, int):
            raise ValueError("SINGLE command must have int data")
        if self.type == BirdCommandType.SAFE_SINGLE and not isinstance(self.data, int):
            raise ValueError("SAFE_SINGLE command must have int data")
        if self.type == BirdCommandType.DMA and not isinstance(self.data, bytes):
            raise ValueError("DMA command must have bytes data")

    def to_bytes(self) -> bytes:
        """Convert command to byte sequence.
        
        Format:
        SINGLE: [type(1B)] [dst_addr(4B)] [data(4B)]
        DMA: [type(1B)] [dst_addr(4B)] [data_len(4B)] [data(bytes)]
        """
        if self.type in [BirdCommandType.SINGLE, BirdCommandType.SAFE_SINGLE]:
            return (
                bytes([1 if self.type == BirdCommandType.SINGLE else 3]) +  # type = 1 for SINGLE, 3 for SAFE_SINGLE
                self.dst_addr.to_bytes(4, 'little') +                       # destination address
                self.data.to_bytes(4, 'little')                            # data
            )
        else:  # DMA
            return (
                bytes([2]) +                                               # type = 2 for DMA
                self.dst_addr.to_bytes(4, 'little') +                     # destination address
                (len(self.data) // 4).to_bytes(4, 'little') +            # number of 32-bit words
                self.data                                                 # data already in bytes
            )

@dataclass
class BirdCommandSequence:
    description: str
    network_type: NetworkType
    commands: List[BirdCommand]


    def add_single_command(self, dst_addr: int, data: int, safe: bool = False):
        self.commands.append(BirdCommand(
            BirdCommandType.SINGLE if not safe else BirdCommandType.SAFE_SINGLE,
            dst_addr,
            data
        ))

    def add_dma_command(self, dst_addr: int, data: bytes):
        """Add a DMA command with raw bytes data.
        
        Args:
            dst_addr: Destination address
            data: Raw bytes to be transferred
        """
        # Ensure data is a multiple of 4 bytes
        if len(data) % 16 != 0:
            raise ValueError("Data must be a multiple of 16 bytes")
        self.commands.append(BirdCommand(BirdCommandType.DMA, dst_addr, data))

    def to_bytes(self) -> bytes:
        """Convert entire sequence to byte sequence."""
        return b''.join(cmd.to_bytes() for cmd in self.commands)

    def __str__(self) -> str:
        lines = [
            "=" * 80,  # Separator line
            f"Command Sequence: {self.description}",
            f"Network Type: {self.network_type.value}",
            "-" * 40,  # Sub-separator line
            "Commands:"
        ]
        
        for i, cmd in enumerate(self.commands, 1):
            lines.append(f"\n{i}. {cmd.type.value.upper()} command")
            lines.append(f"   Destination: 0x{cmd.dst_addr:08X}")
            if cmd.type in [BirdCommandType.SINGLE, BirdCommandType.SAFE_SINGLE]:  # Check both SINGLE types
                lines.append(f"   Data: 0x{cmd.data:08X}")
            else:  # DMA
                lines.append(f"   Data ({len(cmd.data)} bytes):")
                # Split data into 32-bit words for display
                words = [cmd.data[i:i+4] for i in range(0, len(cmd.data), 4)]
                for j in range(0, len(words), 8):
                    chunk = words[j:j+8]
                    hex_chunk = [f"0x{int.from_bytes(word, 'little'):08X}" for word in chunk]
                    lines.append(f"      {' '.join(hex_chunk)}")
        
        lines.append("=" * 80)  # Closing separator line
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