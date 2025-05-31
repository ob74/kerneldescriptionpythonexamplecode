#!/usr/bin/env python3
"""
Focused test of the enhanced requirement tracking functionality.
This script demonstrates how the memory manager now tracks fulfillment state
and allocation details for each requirement.
"""

from memory_manager import (
    MappingCentricMemoryManager, MemoryRequirement, DimensionRequirement, 
    DimensionScope, SliceAllocationMode, SliceGroup, AllocationError
)

def test_requirement_tracking():
    """Test the new requirement tracking and fulfillment details"""
    print("REQUIREMENT TRACKING DEMONSTRATION")
    print("=" * 50)
    
    manager = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=4)
    
    print("Creating several requirements with different patterns...")
    print()
    
    # Test 1: Basic uniform allocation
    req1 = MemoryRequirement(
        size=1024,
        dimension_reqs=[
            DimensionRequirement(DimensionScope.ALL),
            DimensionRequirement(DimensionScope.ALL),
            DimensionRequirement(DimensionScope.ALL)
        ],
        allocation_id="uniform_buffer"
    )
    
    print("1. Uniform allocation across all resources")
    print(f"   Initial state: {req1.state.value}")
    print(f"   Is fulfilled: {req1.is_fulfilled()}")
    
    success = manager.allocate_requirement(req1)
    print(f"   Allocation result: {'SUCCESS' if success else 'FAILED'}")
    
    if success:
        print(f"   Final state: {req1.state.value}")
        print(f"   Is fulfilled: {req1.is_fulfilled()}")
        print(f"   Allocated address: 0x{req1.allocation_details.allocated_address:08x}")
        print(f"   Resolved PE: {req1.allocation_details.resolved_pe}")
        print(f"   Resolved MSS: {req1.allocation_details.resolved_mss}")
        print(f"   Resolved slices: {req1.allocation_details.resolved_slice_values}")
        print(f"   Mappings at allocation: {req1.allocation_details.mapping_count_at_allocation}")
    print()
    
    # Test 2: Auto-selected resources
    req2 = MemoryRequirement(
        size=512,
        dimension_reqs=[
            DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # Auto-select PE
            DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # Auto-select MSS
            DimensionRequirement(DimensionScope.ALL)                    # All slices
        ],
        allocation_id="auto_selected"
    )
    
    print("2. Auto-selected PE and MSS")
    print(f"   Initial state: {req2.state.value}")
    
    success = manager.allocate_requirement(req2)
    print(f"   Allocation result: {'SUCCESS' if success else 'FAILED'}")
    
    if success:
        print(f"   Final state: {req2.state.value}")
        print(f"   System chose PE: {req2.allocation_details.resolved_pe}")
        print(f"   System chose MSS: {req2.allocation_details.resolved_mss}")
        print(f"   Allocated address: 0x{req2.allocation_details.allocated_address:08x}")
    print()
    
    # Test 3: Parallel slice allocation
    req3 = MemoryRequirement(
        size=1024,  # 256 bytes per slice
        dimension_reqs=[
            DimensionRequirement(DimensionScope.SPECIFIC, value=1),
            DimensionRequirement(DimensionScope.SPECIFIC, value=0),
            DimensionRequirement(DimensionScope.GROUP, group=SliceGroup.GROUP_0_3)
        ],
        allocation_mode=SliceAllocationMode.PARALLEL,
        allocation_id="parallel_slices"
    )
    
    print("3. Parallel allocation in slice group")
    print(f"   Initial state: {req3.state.value}")
    
    success = manager.allocate_requirement(req3)
    print(f"   Allocation result: {'SUCCESS' if success else 'FAILED'}")
    
    if success:
        print(f"   Final state: {req3.state.value}")
        print(f"   PE: {req3.allocation_details.resolved_pe}")
        print(f"   MSS: {req3.allocation_details.resolved_mss}")
        print(f"   Slice group: {req3.allocation_details.resolved_slice_values}")
        print(f"   Size per slice: {req3.size // 4} bytes")
    print()
    
    # Show complete summary
    print("COMPLETE REQUIREMENTS SUMMARY")
    print("=" * 50)
    manager.print_requirements_summary()

if __name__ == "__main__":
    test_requirement_tracking() 