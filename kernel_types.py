from enum import Enum
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass
from hw_resources import ResourceScope


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