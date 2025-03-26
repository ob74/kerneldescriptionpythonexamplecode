from enum import Enum
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass
from hw_resources import ResourceScope



class KernelSize(Enum):
    ONE_VCORE = "1Vcore"
    SIZE_1X1 = "1x1"
    SIZE_1X2 = "1x2"
    SIZE_2X2 = "2x2"
    SIZE_2X4 = "2x4"
    SIZE_4X4 = "4x4"
    SIZE_4X8 = "4x8"
    SIZE_8X8 = "8x8"
    SIZE_8X16 = "8x16"
    SIZE_16X16 = "16x16"


@dataclass
class KernelLocation:
    """Represents a kernel location in the grid.
    For regular kernels (1x1 or larger), only x and y are used.
    For ONE_VCORE kernels, x, y, and vcore are used."""
    x: int
    y: int
    vcore: Optional[int] = None

    def __post_init__(self):
        if self.vcore is not None and not (0 <= self.vcore < 4):
            raise ValueError("vcore must be between 0 and 3")

    @property
    def is_vcore(self) -> bool:
        """Returns True if this is a vcore location"""
        return self.vcore is not None

    def __str__(self) -> str:
        if self.is_vcore:
            return f"({self.x}, {self.y}, vcore{self.vcore})"
        return f"({self.x}, {self.y})"


@dataclass
class KernelSuperGroup:
    """Represents a contiguous area containing copies of the same kernel.
    The area must be a power of 2 in both dimensions."""
    x: int
    y: int
    size_x: int
    size_y: int
    kernel_size: KernelSize

    def __post_init__(self):
        # Check if sizes are powers of 2
        if not (self.size_x > 0 and (self.size_x & (self.size_x - 1) == 0)):
            raise ValueError(f"size_x must be a power of 2, got {self.size_x}")
        if not (self.size_y > 0 and (self.size_y & (self.size_y - 1) == 0)):
            raise ValueError(f"size_y must be a power of 2, got {self.size_y}")

        # Get kernel dimensions
        kernel_x, kernel_y = self._get_kernel_dimensions()
        
        # Check if supergroup size is compatible with kernel size
        if self.size_x % kernel_x != 0 or self.size_y % kernel_y != 0:
            raise ValueError(f"Supergroup size ({self.size_x}x{self.size_y}) must be multiple of kernel size ({kernel_x}x{kernel_y})")

    def _get_kernel_dimensions(self) -> Tuple[int, int]:
        """Get the x and y dimensions of the kernel based on its size"""
        size_mapping = {
            KernelSize.ONE_VCORE: (1, 1),
            KernelSize.SIZE_1X1: (1, 1),
            KernelSize.SIZE_1X2: (1, 2),
            KernelSize.SIZE_2X2: (2, 2),
            KernelSize.SIZE_2X4: (2, 4),
            KernelSize.SIZE_4X4: (4, 4),
            KernelSize.SIZE_4X8: (4, 8),
            KernelSize.SIZE_8X8: (8, 8),
            KernelSize.SIZE_8X16: (8, 16),
            KernelSize.SIZE_16X16: (16, 16),
        }
        return size_mapping[self.kernel_size]

    def get_kernel_locations(self) -> List[KernelLocation]:
        """Get all kernel locations within this supergroup"""
        kernel_x, kernel_y = self._get_kernel_dimensions()
        locations = []

        # For regular kernels
        if self.kernel_size != KernelSize.ONE_VCORE:
            for x in range(self.x, self.x + self.size_x, kernel_x):
                for y in range(self.y, self.y + self.size_y, kernel_y):
                    locations.append(KernelLocation(x, y))
        # For vcore kernels
        else:
            for x in range(self.x, self.x + self.size_x):
                for y in range(self.y, self.y + self.size_y):
                    for vcore in range(4):  # All 4 vcores
                        locations.append(KernelLocation(x, y, vcore))

        return locations

    def __str__(self) -> str:
        return f"KernelSuperGroup at ({self.x}, {self.y}) size {self.size_x}x{self.size_y} for {self.kernel_size.value} kernel"


class BufferLocationType(Enum):
    MSS000 = "MSS000"
    PE00 = "PE00"
    SPREAD = "Spread"


class ChannelType(Enum):
    PACKED_BUFFER_QUEUE_INPUT = "PackedBufferQueueInput"
    BUFFER_QUEUE_INPUT = "BufferQueueInput"
    BUFFER_QUEUE_OUTPUT = "BufferQueueOutput"
    PACKED_BUFFER_QUEUE_OUTPUT = "PackedBufferQueueOutput"
    AUXILIARY_INPUT = "AuxiliaryInput"
    SINGLE_BUFFER_OUTPUT = "SingleBufferOutput"


class AllocationType(Enum):
    MSS_DUPLICATED = "MSS_Duplicated"
    PE_DUPLICATED = "PE_Duplicated"
    MSS_DISTRIBUTED = "MSS_Distributed"
    PE_DISTRIBUTED = "PE_Distributed"


# Base Resource Requirement class
class ResourceRequirement:
    def __init__(self, scope: ResourceScope):
        self.scope = scope

    def __repr__(self):
        return f"{self.__class__.__name__}(scope={self.scope})"


class MemoryRequirement(ResourceRequirement):
    def __init__(self, size: int, scope: ResourceScope):
        super().__init__(scope)
        self.size = size

    def __repr__(self):
        return f"MemoryRequirement(size={self.size}, scope={self.scope})"


class DMARequirement(ResourceRequirement):
    def __init__(self, scope: ResourceScope, is_input: bool = True):
        super().__init__(scope)
        self.is_input = is_input

    def __repr__(self):
        return f"DMARequirement(scope={self.scope}, is_input={self.is_input})"


class BarrierRequirement(ResourceRequirement):
    def __init__(self, scope: ResourceScope, count: int = 1):
        super().__init__(scope)
        self.count = count

    def __repr__(self):
        return f"BarrierRequirement(scope={self.scope}, count={self.count})"


class ElementField:
    def __init__(self, name: str, size: int):
        self.name = name
        self.size = size

    def __repr__(self):
        return f"ElementField(name='{self.name}', size={self.size})"

    def get_c_type(self) -> str:
        """Determine C type based on size"""
        if self.size == 1:
            return "uint8_t"
        elif self.size == 2:
            return "uint16_t"
        elif self.size <= 4:
            return "uint32_t"
        elif self.size <= 8:
            return "uint64_t"
        else:
            return f"uint8_t[{self.size}]" 