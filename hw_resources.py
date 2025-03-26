from enum import Enum
from typing import Optional


class ResourceScope(Enum):
    ONE_MSS = "one-mss"
    ONE_PE = "one-pe"
    PE_GROUP = "pe-group"
    FULL_GRID = "full-grid"


# Base HW Resource class
class HWResource:
    """Base class for hardware resources"""

    def __init__(self, scope: ResourceScope, pe_x: Optional[int] = None, pe_y: Optional[int] = None,
                 mss_id: Optional[int] = None):
        self.scope = scope
        self.pe_x = pe_x
        self.pe_y = pe_y
        self.mss_id = mss_id

    def __repr__(self):
        if self.scope == ResourceScope.ONE_PE and self.pe_x is not None and self.pe_y is not None:
            return f"{self.__class__.__name__}(scope={self.scope}, pe=({self.pe_x},{self.pe_y}))"
        elif self.scope == ResourceScope.ONE_MSS and self.mss_id is not None:
            return f"{self.__class__.__name__}(scope={self.scope}, mss={self.mss_id})"
        else:
            return f"{self.__class__.__name__}(scope={self.scope})"


class MemoryResource(HWResource):
    def __init__(self, address: int, length: int, scope: ResourceScope,
                 pe_x: Optional[int] = None, pe_y: Optional[int] = None,
                 mss_id: Optional[int] = None):
        super().__init__(scope, pe_x, pe_y, mss_id)
        self.address = address
        self.length = length

    def __repr__(self):
        base_repr = super().__repr__()
        return f"MemoryResource(address=0x{self.address:08x}, length={self.length}, {base_repr[base_repr.index('(') + 1:]}"


class DMAResource(HWResource):
    def __init__(self, channel_id: int, scope: ResourceScope, is_input: bool = True,
                 pe_x: Optional[int] = None, pe_y: Optional[int] = None,
                 mss_id: Optional[int] = None):
        super().__init__(scope, pe_x, pe_y, mss_id)
        self.channel_id = channel_id
        self.is_input = is_input

    def __repr__(self):
        base_repr = super().__repr__()
        return f"DMAResource(channel_id={self.channel_id}, is_input={self.is_input}, {base_repr[base_repr.index('(') + 1:]}"


class BarrierResource(HWResource):
    
    def __init__(self, barrier_id: int, scope: ResourceScope,
                 pe_x: Optional[int] = None, pe_y: Optional[int] = None,
                 mss_id: Optional[int] = None):
        super().__init__(scope, pe_x, pe_y, mss_id)
        self.barrier_id = barrier_id

    def __repr__(self):
        base_repr = super().__repr__()
        return f"BarrierResource(barrier_id={self.barrier_id}, {base_repr[base_repr.index('(') + 1:]}" 

class AXI2AHBResource(HWResource):
    
    def __init__(self, mode: int, reg_id: int):
        super().__init__()
        self.mode = mode
        self.reg_id = reg_id

    def __repr__(self):
        base_repr = super().__repr__()
        return f"AXI2AHBResource(mode={self.mode}, {self.reg_id=}, {base_repr[base_repr.index('(') + 1:]}" 

class NOCBroadCastResource(HWResource):
    
    def __init__(self, brcst_id: int):
        super().__init__(ResourceScope.FULL_GRID)
        self.brcst_id = brcst_id

    def __repr__(self):
        base_repr = super().__repr__()
        return f"NOCBroadCastResource(brcst_id={self.brcst_id}, {base_repr[base_repr.index('(') + 1:]}" 