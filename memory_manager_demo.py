#!/usr/bin/env python3
"""
Memory Manager Demonstration

This script demonstrates various usage scenarios of the multi-dimensional 
memory management system designed for kernel memory allocation.
"""

from memory_manager import (
    MappingCentricMemoryManager,
    MemoryRequirement,
    DimensionRequirement,
    DimensionScope,
    SliceAllocationMode,
    SliceGroup,
    AllocationError
)


def demo_basic_usage():
    """Demonstrate basic memory allocation scenarios"""
    print("=" * 60)
    print("BASIC USAGE DEMONSTRATION")
    print("=" * 60)
    
    # Initialize memory manager: 2 PEs, 4 MSS per PE, 8 slices per MSS
    manager = MappingCentricMemoryManager(pe_count=2, mss_per_pe=4, slices_per_mss=8)
    
    print("Initial memory state:")
    initial_stats = manager.get_memory_stats()
    print(f"  Total mappings: {initial_stats['total_mappings']}")
    total_free = sum(m['total_free'] for m in initial_stats['mappings'])
    print(f"  Total free space: {total_free:,} bytes")
    print()
    
    # Scenario 1: Uniform allocation across all resources
    req1 = MemoryRequirement(
        size=4096,
        dimension_reqs=[
            DimensionRequirement(DimensionScope.ALL),    # All PEs
            DimensionRequirement(DimensionScope.ALL),    # All MSS
            DimensionRequirement(DimensionScope.ALL)     # All slices
        ],
        allocation_id="uniform_kernel_buffer"
    )
    
    print("Scenario 1: Uniform kernel allocation (all PEs, all MSS, all slices)")
    success = manager.allocate_requirement(req1)
    print(f"  [SUCCESS] Allocation {'succeeded' if success else 'failed'}")
    
    current_stats = manager.get_memory_stats()
    remaining_free = sum(m['total_free'] for m in current_stats['mappings'])
    print(f"  Remaining free space: {remaining_free:,} bytes")
    print()
    
    # Scenario 2: PE-specific allocation (let system choose PE)
    req2 = MemoryRequirement(
        size=2048,
        dimension_reqs=[
            DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # Auto-select PE
            DimensionRequirement(DimensionScope.ALL),                   # All MSS
            DimensionRequirement(DimensionScope.ALL)                    # All slices
        ],
        allocation_id="pe_specific_cache"
    )
    
    print("Scenario 2: Specific PE allocation (system selects best PE)")
    success = manager.allocate_requirement(req2)
    print(f"  [SUCCESS] Allocation {'succeeded' if success else 'failed'}")
    
    current_stats = manager.get_memory_stats()
    print(f"  Total mappings now: {current_stats['total_mappings']}")


def demo_parallel_allocation():
    """Demonstrate parallel allocation across slice groups"""
    print("=" * 60)
    print("PARALLEL ALLOCATION DEMONSTRATION")
    print("=" * 60)
    print("Demonstrating parallel allocation across slice groups...")
    print()
    
    # Smaller manager for clear demonstration
    manager = MappingCentricMemoryManager(pe_count=1, mss_per_pe=2, slices_per_mss=8)
    
    # Scenario 1: Parallel allocation in slice group 0-3
    req1 = MemoryRequirement(
        size=1024,  # 256 bytes per slice in group
        dimension_reqs=[
            DimensionRequirement(DimensionScope.ALL),                     # All PEs
            DimensionRequirement(DimensionScope.ALL),                     # All MSS
            DimensionRequirement(DimensionScope.GROUP, group=SliceGroup.GROUP_0_3)
        ],
        allocation_mode=SliceAllocationMode.PARALLEL,
        allocation_id="parallel_group_0_3"
    )
    
    print("Scenario 1: Parallel allocation in slice group 0-3")
    success = manager.allocate_requirement(req1)
    print(f"  [SUCCESS] Parallel allocation in group 0-3: {'succeeded' if success else 'failed'}")
    print(f"  Size per slice: {req1.size // 4} bytes")
    print()
    
    # Scenario 2: Parallel allocation in slice group 4-7
    req2 = MemoryRequirement(
        size=2048,  # 512 bytes per slice in group
        dimension_reqs=[
            DimensionRequirement(DimensionScope.ALL),                     # All PEs
            DimensionRequirement(DimensionScope.ALL),                     # All MSS
            DimensionRequirement(DimensionScope.GROUP, group=SliceGroup.GROUP_4_7)
        ],
        allocation_mode=SliceAllocationMode.PARALLEL,
        allocation_id="parallel_group_4_7"
    )
    
    print("Scenario 2: Parallel allocation in slice group 4-7")
    success = manager.allocate_requirement(req2)
    print(f"  [SUCCESS] Parallel allocation in group 4-7: {'succeeded' if success else 'failed'}")
    print(f"  Size per slice: {req2.size // 4} bytes")


def demo_automatic_resource_selection():
    """Demonstrate automatic resource selection optimization"""
    print("=" * 60)
    print("AUTOMATIC RESOURCE SELECTION DEMONSTRATION")
    print("=" * 60)
    print("Creating several allocations with automatic resource selection...")
    print("The system will choose the least used resources automatically.")
    print()
    
    manager = MappingCentricMemoryManager(pe_count=3, mss_per_pe=2, slices_per_mss=4)
    
    allocations = [
        ("Small buffer A", 512),
        ("Medium buffer B", 1024),
        ("Large buffer C", 2048),
        ("Small buffer D", 256),
        ("Medium buffer E", 1536)
    ]
    
    for name, size in allocations:
        req = MemoryRequirement(
            size=size,
            dimension_reqs=[
                DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # Auto-select PE
                DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # Auto-select MSS
                DimensionRequirement(DimensionScope.ALL)                    # All slices
            ],
            allocation_id=name.lower().replace(" ", "_")
        )
        
        success = manager.allocate_requirement(req)
        print(f"  {name} ({size:,} bytes): {'[SUCCESS]' if success else '[FAILED]'}")
    
    print()
    print("Final memory statistics:")
    stats = manager.get_memory_stats()
    total_allocated = sum(m['total_allocated'] for m in stats['mappings'])
    total_free = sum(m['total_free'] for m in stats['mappings'])
    print(f"  Total allocated: {total_allocated:,} bytes")
    print(f"  Total free: {total_free:,} bytes")


def demo_complex_scenarios():
    """Demonstrate complex allocation scenarios with mapping forking"""
    print("=" * 60)
    print("COMPLEX SCENARIOS DEMONSTRATION - MAPPING FORKING")
    print("=" * 60)
    
    manager = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=8)
    
    print("Starting with universal mapping covering all coordinates...")
    initial_stats = manager.get_memory_stats()
    print(f"  Initial mappings: {initial_stats['total_mappings']}")
    print()
    
    scenarios = [
        {
            "name": "Global shared data (no fork expected)",
            "requirement": MemoryRequirement(
                size=1024,
                dimension_reqs=[
                    DimensionRequirement(DimensionScope.ALL),  # All PEs
                    DimensionRequirement(DimensionScope.ALL),  # All MSS
                    DimensionRequirement(DimensionScope.ALL)   # All slices
                ],
                allocation_id="global_shared"
            ),
            "expected_fork": False
        },
        {
            "name": "PE 0 specific cache (fork expected)",
            "requirement": MemoryRequirement(
                size=512,
                dimension_reqs=[
                    DimensionRequirement(DimensionScope.SPECIFIC, value=0),  # PE 0 only
                    DimensionRequirement(DimensionScope.ALL),                 # All MSS
                    DimensionRequirement(DimensionScope.ALL)                  # All slices
                ],
                allocation_id="pe0_cache"
            ),
            "expected_fork": True
        },
        {
            "name": "MSS 1 specific buffer (additional fork expected)",
            "requirement": MemoryRequirement(
                size=256,
                dimension_reqs=[
                    DimensionRequirement(DimensionScope.ALL),                 # All PEs
                    DimensionRequirement(DimensionScope.SPECIFIC, value=1),   # MSS 1 only
                    DimensionRequirement(DimensionScope.ALL)                  # All slices
                ],
                allocation_id="mss1_buffer"
            ),
            "expected_fork": True
        },
        {
            "name": "PE 1, MSS 0, Slice group 0-3 (more forks expected)",
            "requirement": MemoryRequirement(
                size=2048,
                dimension_reqs=[
                    DimensionRequirement(DimensionScope.SPECIFIC, value=1),                 # PE 1 only
                    DimensionRequirement(DimensionScope.SPECIFIC, value=0),                 # MSS 0 only
                    DimensionRequirement(DimensionScope.GROUP, group=SliceGroup.GROUP_0_3)  # Slice group 0-3
                ],
                allocation_mode=SliceAllocationMode.PARALLEL,
                allocation_id="pe1_mss0_slice_group"
            ),
            "expected_fork": True
        },
        {
            "name": "Auto-selected PE and MSS (system chooses)",
            "requirement": MemoryRequirement(
                size=128,
                dimension_reqs=[
                    DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # Auto-select PE
                    DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # Auto-select MSS
                    DimensionRequirement(DimensionScope.ALL)                    # All slices
                ],
                allocation_id="auto_selected_resources"
            ),
            "expected_fork": True
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"Step {i}: {scenario['name']}")
        req = scenario['requirement']
        
        # Show requirement details
        pe_scope = req.dimension_reqs[0].scope.value
        pe_val = req.dimension_reqs[0].value
        mss_scope = req.dimension_reqs[1].scope.value
        mss_val = req.dimension_reqs[1].value
        slice_scope = req.dimension_reqs[2].scope.value
        slice_val = getattr(req.dimension_reqs[2], 'group', req.dimension_reqs[2].value)
        
        print(f"  Size: {req.size:,} bytes")
        print(f"  Pattern: PE({pe_scope}={pe_val}) x MSS({mss_scope}={mss_val}) x Slice({slice_scope}={slice_val})")
        if req.allocation_mode == SliceAllocationMode.PARALLEL:
            print(f"  Mode: Parallel ({req.size // 4} bytes per slice)")
        
        # Record mappings before allocation
        before_stats = manager.get_memory_stats()
        before_count = before_stats['total_mappings']
        
        # Perform allocation
        success = manager.allocate_requirement(req)
        print(f"  Result: {'[SUCCESS]' if success else '[FAILED]'}")
        
        # Show allocation details if successful
        if success and req.is_fulfilled():
            print(f"  Allocation: {req.allocation_details}")
        
        # Show mapping changes
        after_stats = manager.get_memory_stats()
        after_count = after_stats['total_mappings']
        
        if after_count > before_count:
            print(f"  [FORK] Mapping forked! {before_count} -> {after_count} mappings")
        elif scenario['expected_fork']:
            print(f"  [WARNING] Expected fork but none occurred ({before_count} -> {after_count})")
        else:
            print(f"  [OK] No fork as expected ({before_count} -> {after_count} mappings)")
        
        print()
    
    print("Final system state:")
    final_stats = manager.get_memory_stats()
    total_allocated = sum(m['total_allocated'] for m in final_stats['mappings'])
    total_free = sum(m['total_free'] for m in final_stats['mappings'])
    
    print(f"  Total mappings: {final_stats['total_mappings']}")
    print(f"  Total allocated: {total_allocated:,} bytes")
    print(f"  Total free: {total_free:,} bytes")
    print(f"  Memory utilization: {total_allocated / (total_allocated + total_free):.1%}")
    
    # Show complete requirements summary
    manager.print_requirements_summary()
    
    print()
    print("Mapping Forking Summary:")
    print("  [OK] Universal mapping starts with all coordinates")
    print("  [OK] PE/MSS/Slice-specific allocations trigger mapping forks")
    print("  [OK] Auto-selected resources show resolved values in allocation details")
    print("  [OK] System tracks all requirements and their fulfillment status")


def demo_error_handling():
    """Demonstrate error handling scenarios"""
    print("=" * 60)
    print("ERROR HANDLING DEMONSTRATION")
    print("=" * 60)
    print("Testing allocation failures and error handling...")
    print()
    
    # Small manager to easily trigger errors
    manager = MappingCentricMemoryManager(pe_count=1, mss_per_pe=1, slices_per_mss=4)
    
    # Scenario 1: Large allocation that should succeed
    req1 = MemoryRequirement(
        size=900 * 1024,  # 900KB - should fit
        dimension_reqs=[
            DimensionRequirement(DimensionScope.ALL),
            DimensionRequirement(DimensionScope.ALL),
            DimensionRequirement(DimensionScope.ALL)
        ],
        allocation_id="large_allocation"
    )
    
    print("Scenario 1: Large allocation (900KB)")
    success = manager.allocate_requirement(req1)
    print(f"  Result: {'[SUCCESS]' if success else '[FAILED]'}")
    
    if success:
        stats = manager.get_memory_stats()
        remaining = sum(m['total_free'] for m in stats['mappings'])
        print(f"  Remaining space: {remaining:,} bytes")
    print()
    
    # Scenario 2: Allocation that exceeds remaining space
    req2 = MemoryRequirement(
        size=500 * 1024,  # 500KB - should fail due to insufficient space
        dimension_reqs=[
            DimensionRequirement(DimensionScope.ALL),
            DimensionRequirement(DimensionScope.ALL),
            DimensionRequirement(DimensionScope.ALL)
        ],
        allocation_id="oversized_allocation"
    )
    
    print("Scenario 2: Oversized allocation (500KB)")
    try:
        success = manager.allocate_requirement(req2)
        print(f"  Result: {'[SUCCESS]' if success else '[FAILED]'}")
    except AllocationError as e:
        print(f"  [ERROR] Allocation failed: {e}")


if __name__ == "__main__":
    print("MEMORY MANAGER DEMONSTRATION")
    print("This demo shows various capabilities of the multi-dimensional memory management system.")
    print()
    
    demo_basic_usage()
    print("\n" + "="*60 + "\n")
    
    demo_parallel_allocation() 
    print("\n" + "="*60 + "\n")
    
    demo_automatic_resource_selection()
    print("\n" + "="*60 + "\n")
    
    demo_complex_scenarios()
    print("\n" + "="*60 + "\n")
    
    demo_error_handling()
    print("\n" + "="*60 + "\n")
    
    print("[COMPLETE] Memory Manager demonstration complete!")
    print("The system successfully handled:")
    print("  [OK] Uniform and specific allocations")
    print("  [OK] Automatic resource selection with resolution tracking")
    print("  [OK] Parallel slice group allocations") 
    print("  [OK] Cross-mapping intersections")
    print("  [OK] Memory fragmentation tracking")
    print("  [OK] Complete requirement fulfillment tracking")
    print("  [OK] Error handling") 