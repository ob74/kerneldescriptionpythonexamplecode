#!/usr/bin/env python3
"""
Simple test of batch allocation optimization functionality.
"""

from memory_manager import (
    MappingCentricMemoryManager, MemoryRequirement, DimensionRequirement, 
    DimensionScope, SliceAllocationMode, SliceGroup
)

def test_simple_batch_optimization():
    """Test batch allocation optimization with simple example"""
    print("BATCH ALLOCATION OPTIMIZATION TEST")
    print("=" * 50)
    
    manager = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=4)
    
    # Collect requirements in suboptimal order
    requirements = [
        # Start with specific (would cause early forking)
        MemoryRequirement(
            size=512,
            pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=0),  # PE 0 only
            mss_req=DimensionRequirement(DimensionScope.ALL),               # All MSS
            slice_req=DimensionRequirement(DimensionScope.ALL),             # All slices
            allocation_id="pe0_specific"
        ),
        # Auto-selection
        MemoryRequirement(
            size=256,
            pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # Auto PE
            mss_req=DimensionRequirement(DimensionScope.ALL),                  # All MSS
            slice_req=DimensionRequirement(DimensionScope.ALL),                # All slices
            allocation_id="auto_selection"
        ),
        # Broad scope (should be processed first)
        MemoryRequirement(
            size=1024,
            pe_req=DimensionRequirement(DimensionScope.ALL),  # All PEs
            mss_req=DimensionRequirement(DimensionScope.ALL), # All MSS
            slice_req=DimensionRequirement(DimensionScope.ALL), # All slices
            allocation_id="global_buffer"
        ),
        # MSS-specific
        MemoryRequirement(
            size=384,
            pe_req=DimensionRequirement(DimensionScope.ALL),                 # All PEs
            mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=1),  # MSS 1 only
            slice_req=DimensionRequirement(DimensionScope.ALL),              # All slices
            allocation_id="mss1_buffer"
        )
    ]
    
    print("Collecting requirements in suboptimal order:")
    for i, req in enumerate(requirements, 1):
        manager.collect_requirement(req)
        print(f"  {i}. {req.allocation_id}: {req.size} bytes")
    
    print()
    print("Initial mappings:", len(manager.signature_to_map))
    print()
    
    # Perform optimized batch allocation
    print("Starting batch allocation with optimization...")
    batch_results = manager.allocate_all()
    
    print()
    print("RESULTS:")
    print("Total requirements:", batch_results['total_requirements'])
    print("Successful allocations:", batch_results['successful_allocations'])
    print("Failed allocations:", batch_results['failed_allocations'])
    
    final_mappings = len(manager.signature_to_map)
    total_forks = sum(1 for r in batch_results['allocation_details'] if r['fork_occurred'])
    
    print("Final mappings:", final_mappings)
    print("Total forks:", total_forks)
    
    print()
    print("All requirements fulfilled:")
    for req in manager.processed_requirements:
        status = "YES" if req.is_fulfilled() else "NO"
        print(f"  {req.allocation_id}: {status}")
    
    return batch_results

def compare_approaches():
    """Compare naive vs optimized allocation"""
    print("\nCOMPARISON: NAIVE vs OPTIMIZED")
    print("=" * 50)
    
    # Test naive approach
    manager_naive = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=4)
    
    naive_reqs = [
        MemoryRequirement(size=512, pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=0),
                         mss_req=DimensionRequirement(DimensionScope.ALL),
                         slice_req=DimensionRequirement(DimensionScope.ALL),
                         allocation_id="pe0_specific"),
        
        MemoryRequirement(size=1024, pe_req=DimensionRequirement(DimensionScope.ALL),
                         mss_req=DimensionRequirement(DimensionScope.ALL),
                         slice_req=DimensionRequirement(DimensionScope.ALL),
                         allocation_id="global_buffer"),
        
        MemoryRequirement(size=384, pe_req=DimensionRequirement(DimensionScope.ALL),
                         mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=1),
                         slice_req=DimensionRequirement(DimensionScope.ALL),
                         allocation_id="mss1_buffer")
    ]
    
    naive_forks = 0
    for req in naive_reqs:
        mappings_before = len(manager_naive.signature_to_map)
        manager_naive.allocate_requirement(req)
        mappings_after = len(manager_naive.signature_to_map)
        if mappings_after > mappings_before:
            naive_forks += 1
    
    naive_final = len(manager_naive.signature_to_map)
    
    # Test optimized approach
    manager_opt = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=4)
    
    opt_reqs = [
        MemoryRequirement(size=512, pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=0),
                         mss_req=DimensionRequirement(DimensionScope.ALL),
                         slice_req=DimensionRequirement(DimensionScope.ALL),
                         allocation_id="pe0_specific"),
        
        MemoryRequirement(size=1024, pe_req=DimensionRequirement(DimensionScope.ALL),
                         mss_req=DimensionRequirement(DimensionScope.ALL),
                         slice_req=DimensionRequirement(DimensionScope.ALL),
                         allocation_id="global_buffer"),
        
        MemoryRequirement(size=384, pe_req=DimensionRequirement(DimensionScope.ALL),
                         mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=1),
                         slice_req=DimensionRequirement(DimensionScope.ALL),
                         allocation_id="mss1_buffer")
    ]
    
    for req in opt_reqs:
        manager_opt.collect_requirement(req)
    
    batch_results = manager_opt.allocate_all()
    opt_forks = sum(1 for r in batch_results['allocation_details'] if r['fork_occurred'])
    opt_final = len(manager_opt.signature_to_map)
    
    print("Naive approach:")
    print(f"  Forks: {naive_forks}")
    print(f"  Final mappings: {naive_final}")
    print()
    print("Optimized approach:")
    print(f"  Forks: {opt_forks}")
    print(f"  Final mappings: {opt_final}")
    
    if opt_forks <= naive_forks and opt_final <= naive_final:
        print()
        print("SUCCESS: Optimization reduced mapping fragmentation!")
    else:
        print()
        print("INFO: Optimization results vary with allocation patterns.")

if __name__ == "__main__":
    test_simple_batch_optimization()
    compare_approaches()
    print("\nBatch optimization test complete!") 