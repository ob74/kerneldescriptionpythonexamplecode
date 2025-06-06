import re
from typing import List, Tuple
from enum import Enum, auto
from bird import BirdCommandSequence, NetworkType, BroadcastType, GridDestinationType, BirdCommand, BirdCommandType

class KernelBinary(Enum):
    VCORE_PM = ("ePM", 0x1000)
    VCORE_DM = ("eDMw", 0x2000)
    VCORE_VM = ("eVM", 0x3000)
    NCORE_PM = ("ePM", 0x4000)
    NCORE_DM = ("eDM", 0x5000)

    def __init__(self, file_suffix: str, offset: int):
        self.file_suffix = file_suffix
        self.offset = offset
        self._filename = None
        self._contents = None

    @classmethod
    def from_file(cls, filename: str) -> 'KernelBinary':
        for binary_type in cls:
            if filename.endswith(binary_type.file_suffix):
                instance = binary_type
                instance._filename = filename
                instance._contents = MemoryDecoder(filename, instance.offset).get_memory_contents()
                return instance
        raise ValueError(f"Unknown binary type for filename: {filename}")

    def generate_bird_sequence(self) -> BirdCommandSequence:
        """Returns APB settings for IO channel for a supergroup"""
        seq = BirdCommandSequence(
            f"Kernel Binary {self.filename}",
            NetworkType(BroadcastType.SUPER_MSS_BRCST, GridDestinationType.VCORE),
            []
        )
        for addr, bytes in self.contents:
            seq.add_dma_command( addr, bytes)
        return seq

    @property
    def contents(self) -> List[Tuple[int, bytes]]:
        if self._contents is None:
            raise ValueError("Binary type not initialized with a file. Use from_file() first.")
        return self._contents

    @property
    def filename(self) -> str:
        if self._filename is None:
            raise ValueError("Binary type not initialized with a file. Use from_file() first.")
        return self._filename


class MemoryDecoder:
    def __init__(self, filename: str, target_offset):
        self.filename = filename
        self.memory_contents = self._decode_file(target_offset)
    
    def _decode_file(self, target_offset: int) -> List[Tuple[int, bytes]]:
        memory_map = {}
        
        with open(self.filename, 'r') as file:
            for line in file:
                match = re.match(r'@(?P<addr>[0-9A-Fa-f]+)\s+(?P<data>[0-9A-Fa-f\s]+)', line)
                if match:
                    addr = target_offset + int(match.group("addr"), 16) * 4  # Convert to byte addressing
                    data = match.group("data").strip().replace(" ", "")  # Remove any spaces
                    if 0 < len(data) <= 8:
                        data = data.zfill(8)
                    try:
                        byte_data = bytes.fromhex(data)
                        memory_map[addr] = byte_data
                    except ValueError as e:
                        print(f"Warning: Invalid hex data in file {self.filename} at address {hex(addr)}: {data}")
                        print(f"Error details: {str(e)}")
                        break
        return self.align_data_segments(self._unify_memory(memory_map), 16)
    

    def align_data_segments(self,
        segments: List[Tuple[int, bytes]],
        alignment: int
    ) -> List[Tuple[int, bytes]]:
        
        if not segments:
            return []

        aligned_segments = []
        prev_end_addr = 0  # initialize previous end address

        for i, (addr, data) in enumerate(segments):
            # Find the aligned start address downward, not exceeding the current address
            aligned_start_addr = (addr // alignment) * alignment

            # Determine the start address for this segment: should not be higher than original
            start_addr = min(addr, aligned_start_addr)

            # Calculate padding before data (if aligned_start_addr < addr)
            padding_before = addr - start_addr
            data_with_padding = bytes([0] * padding_before) + data

            # Determine the maximum size to avoid overlapping with the next segment
            if i + 1 < len(segments):
                next_addr = segments[i + 1][0]
            else:
                # No next segment; assume large space
                next_addr = start_addr + len(data_with_padding) + alignment

            max_end = next_addr  # prevent overlap with next segment
            max_size = max_end - start_addr

            # Pad data to meet alignment, or truncate if needed
            size_padding = (alignment - (len(data_with_padding) % alignment)) % alignment
            total_size = len(data_with_padding) + size_padding

            if start_addr + total_size > max_end:
                total_size = max_end - start_addr
                if total_size < len(data_with_padding):
                    # truncate data to avoid overlap
                    data_with_padding = data_with_padding[:total_size]
                    total_size = len(data_with_padding)
                else:
                    # pad as much as possible
                    data_with_padding += bytes([0] * (total_size - len(data_with_padding)))

            # Append this aligned segment
            aligned_segments.append((start_addr, data_with_padding))
            prev_end_addr = start_addr + len(data_with_padding)

        return aligned_segments

    def _unify_memory(self, memory_map: dict) -> List[Tuple[int, bytes]]:
        sorted_addrs = sorted(memory_map.keys())
        unified_memory = []
        
        if not sorted_addrs:
            return unified_memory
        
        current_addr = sorted_addrs[0]
        current_data = memory_map[current_addr]
        
        for addr in sorted_addrs[1:]:
            if addr == current_addr + len(current_data):
                current_data += memory_map[addr]  # Append contiguous data
            else:
                unified_memory.append((current_addr, current_data))
                current_addr = addr
                current_data = memory_map[addr]
        
        unified_memory.append((current_addr, current_data))
        return unified_memory
    
    def get_memory_contents(self) -> List[Tuple[int, bytes]]:
        return self.memory_contents

if __name__ == "__main__":
    files = [
        "./kernels/kern-gs.vcore.elf.eDMw",
        "./kernels/kern-gs.vcore.elf.eVM",
        "./kernels/ncore-grid.ncore.elf.eDM",
        "./kernels/kern-gs.vcore.elf.ePM",
        "./kernels/ncore-grid.ncore.elf.ePM"
    ]
    
    for file in files:
        try:
            binary = KernelBinary.from_file(file)
            print(f"\nDecoding {binary.filename}")
            print(f"Binary type: {binary.name}")
            print(f"Offset: 0x{binary.offset:X}")
            print("Contents:", binary.contents)
        except ValueError as e:
            print(f"Error processing {file}: {e}")
            exit(1)
           