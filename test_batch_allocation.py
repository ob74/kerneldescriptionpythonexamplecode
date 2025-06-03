#!/usr/bin/env python3
"""
Test script for batch allocation with requirement ordering optimization.
Demonstrates how collect_requirement() and allocate_all() minimize conflicts.
"""

from memory_manager import (
    MappingCentricMemoryManager, MemoryRequirement, DimensionRequirement, 
    DimensionScope, SliceAllocationMode, SliceGroup
)

def test_batch_allocation_optimization():
    """Test batch allocation with requirement ordering"""
    print("BATCH ALLOCATION WITH OPTIMIZATION DEMONSTRATION")
    print("=" * 60)
    
    manager = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=8)
    
    print("Creating a complex mix of requirements to demonstrate ordering...")
    print()
    
    # Create requirements in deliberately suboptimal order
    requirements = [
        # Start with specific requirements (would normally cause early forking)
        MemoryRequirement(
            size=512,
            pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=0),  # PE 0 specific
            mss_req=DimensionRequirement(DimensionScope.ALL),               # All MSS
            slice_req=DimensionRequirement(DimensionScope.ALL),             # All slices
            allocation_id="pe0_specific_buffer"
        ),
        
        # Auto-selection requirements (system needs to choose)
        MemoryRequirement(
            size=256,
            pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # Auto PE
            mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=None), # Auto MSS
            slice_req=DimensionRequirement(DimensionScope.ALL),                # All slices
            allocation_id="auto_selected_cache"
        ),
        
        # Parallel slice group allocation
        MemoryRequirement(
            size=1024,  # 256 bytes per slice
            pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=1),                 # PE 1
            mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=0),                # MSS 0
            slice_req=DimensionRequirement(DimensionScope.GROUP, group=SliceGroup.GROUP_0_3), # Slice group 0-3
            allocation_mode=SliceAllocationMode.PARALLEL,
            allocation_id="parallel_slice_data"
        ),
        
        # Broad scope requirement (should be processed first for efficiency)
        MemoryRequirement(
            size=2048,
            pe_req=DimensionRequirement(DimensionScope.ALL),  # All PEs
            mss_req=DimensionRequirement(DimensionScope.ALL), # All MSS
            slice_req=DimensionRequirement(DimensionScope.ALL), # All slices
            allocation_id="global_shared_buffer"
        ),
        
        # MSS-specific requirement
        MemoryRequirement(
            size=768,
            pe_req=DimensionRequirement(DimensionScope.ALL),                 # All PEs
            mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=1),  # MSS 1 specific
            slice_req=DimensionRequirement(DimensionScope.ALL),              # All slices
            allocation_id="mss1_controller_buffer"
        ),
        
        # Another auto-selection with different size
        MemoryRequirement(
            size=1536,
            pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # Auto PE
            mss_req=DimensionRequirement(DimensionScope.ALL),                  # All MSS
            slice_req=DimensionRequirement(DimensionScope.SPECIFIC, value=None), # Auto slice
            allocation_id="auto_pe_slice_buffer"
        ),
        
        # Small specific allocation
        MemoryRequirement(
            size=128,
            pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=1),   # PE 1
            mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=1),  # MSS 1
            slice_req=DimensionRequirement(DimensionScope.SPECIFIC, value=3), # Slice 3
            allocation_id="pe1_mss1_slice3_metadata"
        )
    ]
    
    print(f"Collecting {len(requirements)} requirements (in suboptimal order):")
    for i, req in enumerate(requirements, 1):
        manager.collect_requirement(req)
        scope_desc = manager._describe_requirement_scope(req)
        print(f"  {i}. {req.allocation_id}: {scope_desc} ({req.size:,} bytes)")
    
    print()
    print("Initial state:")
    initial_stats = manager.get_memory_stats()
    print(f"  Mappings: {initial_stats['total_mappings']}")
    print()
    
    # Now allocate all in optimized order
    print("🚀 Starting batch allocation with optimization...")
    print("=" * 60)
    
    batch_results = manager.allocate_all()
    
    print("=" * 60)
    print("BATCH ALLOCATION RESULTS")
    print("=" * 60)
    
    print(f"Total requirements processed: {batch_results['total_requirements']}")
    print(f"✅ Successful allocations: {batch_results['successful_allocations']}")
    print(f"❌ Failed allocations: {batch_results['failed_allocations']}")
    print()
    
    # Validate that total requested matches total allocated
    assert manager.total_requested_allocations() == manager.total_allocated_bytes(), \
        f"Validation failed: requested={manager.total_requested_allocations()} != allocated={manager.total_allocated_bytes()}"
    
    # Show final state
    final_stats = manager.get_memory_stats()
    print(f"Final mapping count: {final_stats['total_mappings']}")
    
    total_allocated = sum(m['total_allocated'] for m in final_stats['mappings'])
    total_free = sum(m['total_free'] for m in final_stats['mappings'])
    utilization = total_allocated / (total_allocated + total_free) * 100
    
    print(f"Total allocated: {total_allocated:,} bytes")
    print(f"Total free: {total_free:,} bytes")
    print(f"Memory utilization: {utilization:.1f}%")
    print()
    
    # Show allocation sequence analysis
    print("ALLOCATION SEQUENCE ANALYSIS")
    print("=" * 60)
    
    fork_count = 0
    for result in batch_results['allocation_details']:
        if result['fork_occurred']:
            fork_count += 1
    
    print(f"Total forks during allocation: {fork_count}")
    print(f"Average mappings per allocation: {sum(r['mappings_after'] for r in batch_results['allocation_details']) / len(batch_results['allocation_details']):.1f}")
    print()
    
    # Show detailed requirement tracking
    manager.print_requirements_summary()
    
    return batch_results

def compare_naive_vs_optimized():
    """Compare naive sequential allocation vs optimized batch allocation"""
    print("\n" + "=" * 60)
    print("COMPARISON: NAIVE vs OPTIMIZED ALLOCATION")
    print("=" * 60)
    
    # Test same requirements with naive approach
    print("Testing NAIVE approach (allocate in original order)...")
    
    manager_naive = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=8)
    
    # Same requirements as before, in suboptimal order
    naive_requirements = [
        MemoryRequirement(size=512, pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=0),
                         mss_req=DimensionRequirement(DimensionScope.ALL),
                         slice_req=DimensionRequirement(DimensionScope.ALL),
                         allocation_id="pe0_specific"),
        
        MemoryRequirement(size=256, pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=None),
                         mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=None),
                         slice_req=DimensionRequirement(DimensionScope.ALL),
                         allocation_id="auto_selected"),
        
        MemoryRequirement(size=2048, pe_req=DimensionRequirement(DimensionScope.ALL),
                         mss_req=DimensionRequirement(DimensionScope.ALL),
                         slice_req=DimensionRequirement(DimensionScope.ALL),
                         allocation_id="global_shared"),
        
        MemoryRequirement(size=768, pe_req=DimensionRequirement(DimensionScope.ALL),
                         mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=1),
                         slice_req=DimensionRequirement(DimensionScope.ALL),
                         allocation_id="mss1_controller")
    ]
    
    naive_forks = 0
    for i, req in enumerate(naive_requirements):
        mappings_before = len(manager_naive.signature_to_map)
        manager_naive.allocate_requirement(req)
        mappings_after = len(manager_naive.signature_to_map)
        if mappings_after > mappings_before:
            naive_forks += 1
    
    naive_final_mappings = len(manager_naive.signature_to_map)
    
    # Validate naive approach
    assert manager_naive.total_requested_allocations() == manager_naive.total_allocated_bytes(), \
        f"Naive validation failed: requested={manager_naive.total_requested_allocations()} != allocated={manager_naive.total_allocated_bytes()}"
    
    # Test optimized approach
    print("Testing OPTIMIZED approach (batch allocation with ordering)...")
    
    manager_optimized = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=8)
    
    # Same requirements, but will be reordered
    optimized_requirements = [
        MemoryRequirement(size=512, pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=0),
                         mss_req=DimensionRequirement(DimensionScope.ALL),
                         slice_req=DimensionRequirement(DimensionScope.ALL),
                         allocation_id="pe0_specific"),
        
        MemoryRequirement(size=256, pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=None),
                         mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=None),
                         slice_req=DimensionRequirement(DimensionScope.ALL),
                         allocation_id="auto_selected"),
        
        MemoryRequirement(size=2048, pe_req=DimensionRequirement(DimensionScope.ALL),
                         mss_req=DimensionRequirement(DimensionScope.ALL),
                         slice_req=DimensionRequirement(DimensionScope.ALL),
                         allocation_id="global_shared"),
        
        MemoryRequirement(size=768, pe_req=DimensionRequirement(DimensionScope.ALL),
                         mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=1),
                         slice_req=DimensionRequirement(DimensionScope.ALL),
                         allocation_id="mss1_controller")
    ]
    
    for req in optimized_requirements:
        manager_optimized.collect_requirement(req)
    
    batch_results = manager_optimized.allocate_all()
    optimized_forks = sum(1 for r in batch_results['allocation_details'] if r['fork_occurred'])
    optimized_final_mappings = len(manager_optimized.signature_to_map)
    
    # Validate optimized approach
    assert manager_optimized.total_requested_allocations() == manager_optimized.total_allocated_bytes(), \
        f"Optimized validation failed: requested={manager_optimized.total_requested_allocations()} != allocated={manager_optimized.total_allocated_bytes()}"
    
    # Compare results
    print("\nCOMPARISON RESULTS:")
    print("=" * 40)
    print(f"Naive approach:")
    print(f"  Total forks: {naive_forks}")
    print(f"  Final mappings: {naive_final_mappings}")
    print()
    print(f"Optimized approach:")
    print(f"  Total forks: {optimized_forks}")
    print(f"  Final mappings: {optimized_final_mappings}")
    print()
    
    if optimized_forks <= naive_forks and optimized_final_mappings <= naive_final_mappings:
        print("✅ Optimization successful! Reduced mapping fragmentation.")
    else:
        print("⚠️  Optimization results vary - may depend on specific allocation patterns.")

if __name__ == "__main__":
    test_batch_allocation_optimization()
    compare_naive_vs_optimized()
    print("\n🎯 Batch allocation optimization demonstration complete!") 