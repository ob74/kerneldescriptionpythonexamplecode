# Multi-Dimensional Memory Management System

A sophisticated memory management system designed for kernel memory allocation with orthogonal multi-dimensional requirements and intelligent resource optimization.

## Architecture Overview

The system implements a hierarchical memory architecture with three dimensions:
- **Processing Elements (PE)**: Top-level compute units
- **Memory Sub-Systems (MSS)**: Memory controllers within each PE  
- **Slices**: Memory segments within each MSS

## Key Features

### 1. Dynamic Mapping Forking
The system starts with a universal mapping covering all coordinates and progressively forks into specialized mappings as allocation patterns diverge.

```python
# Starts with one universal mapping
manager = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=8)

# PE-specific allocation triggers forking
pe_specific = MemoryRequirement(
    size=1024,
    dimension_reqs=[
        DimensionRequirement(DimensionScope.SPECIFIC, value=0),  # PE 0 only
        DimensionRequirement(DimensionScope.ALL),                # All MSS
        DimensionRequirement(DimensionScope.ALL)                 # All slices
    ]
)
```

### 2. Requirement State Tracking and Fulfillment Details
Each memory requirement tracks its fulfillment state and detailed allocation information:

```python
# Create a requirement
req = MemoryRequirement(
    size=512,
    dimension_reqs=[
        DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # Auto-select PE
        DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # Auto-select MSS
        DimensionRequirement(DimensionScope.ALL)                    # All slices
    ],
    allocation_id="my_buffer"
)

# Check initial state
print(f"State: {req.state.value}")           # "pending"
print(f"Fulfilled: {req.is_fulfilled()}")    # False

# Allocate
success = manager.allocate_requirement(req)

# Check final state and details
if req.is_fulfilled():
    details = req.allocation_details
    print(f"State: {req.state.value}")                          # "fulfilled"
    print(f"Address: 0x{details.allocated_address:08x}")        # Allocated address
    print(f"Resolved PE: {details.resolved_pe}")                # System-chosen PE
    print(f"Resolved MSS: {details.resolved_mss}")              # System-chosen MSS
    print(f"Slices: {details.resolved_slice_values}")           # Affected slice(s)
    print(f"Mappings: {details.mapping_count_at_allocation}")   # Mapping count at time
```

### 3. Orthogonal Dimension Requirements
Memory requirements can be specified independently across dimensions:

```python
# Uniform allocation across all resources
uniform_req = MemoryRequirement(
    size=4096,
    dimension_reqs=[
        DimensionRequirement(DimensionScope.ALL),    # All PEs
        DimensionRequirement(DimensionScope.ALL),    # All MSS
        DimensionRequirement(DimensionScope.ALL)     # All slices
    ]
)

# PE-specific with auto-selected MSS
pe_specific_req = MemoryRequirement(
    size=2048,
    dimension_reqs=[
        DimensionRequirement(DimensionScope.SPECIFIC, value=1),    # PE 1 only
        DimensionRequirement(DimensionScope.SPECIFIC, value=None), # Auto-select MSS
        DimensionRequirement(DimensionScope.ALL)                   # All slices
    ]
)
```

### 4. Smart Resource Selection
The system automatically selects optimal resources based on available space and load balancing:

```python
auto_req = MemoryRequirement(
    size=1024,
    dimension_reqs=[
        DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # System chooses PE
        DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # System chooses MSS
        DimensionRequirement(DimensionScope.ALL)                    # All slices
    ]
)
```

### 5. Parallel Slice Allocation
Supports parallel allocation across slice groups with automatic distribution:

```python
parallel_req = MemoryRequirement(
    size=2048,  # 512 bytes per slice in group
    dimension_reqs=[
        DimensionRequirement(DimensionScope.ALL),
        DimensionRequirement(DimensionScope.ALL),
        DimensionRequirement(DimensionScope.GROUP, group=SliceGroup.GROUP_0_3)
    ],
    allocation_mode=SliceAllocationMode.PARALLEL
)
```

## Requirements Summary and Monitoring

The system provides comprehensive tracking of all processed requirements:

```python
# Get summary statistics
summary = manager.get_requirements_summary()
print(f"Total: {summary['total_requirements']}")
print(f"Fulfilled: {summary['fulfilled_count']}")
print(f"Pending: {summary['pending_count']}")

# Print detailed status of all requirements
manager.print_requirements_summary()
```

## Core Classes

### MappingCentricMemoryManager
Main memory manager implementing the multi-dimensional allocation system.

### MemoryRequirement
Represents a memory allocation request with:
- **State tracking**: `RequirementState.PENDING` → `RequirementState.FULFILLED`
- **Allocation details**: Address, resolved dimensions, mapping count
- **Dimension requirements**: Independent specifications for PE, MSS, and slice allocation
- **Allocation mode**: Serial or parallel slice allocation

### AllocationDetails
Contains fulfillment information:
- `allocated_address`: Virtual address where memory was allocated
- `resolved_pe`: Final PE value (for auto-selected or ALL scope)
- `resolved_mss`: Final MSS value (for auto-selected or ALL scope)  
- `resolved_slice_values`: List of affected slice indices
- `mapping_count_at_allocation`: Number of mappings when allocated

### DimensionRequirement
Specifies requirements for a single dimension (PE, MSS, or slice).

## Usage Examples

### Basic Uniform Allocation
```python
manager = MappingCentricMemoryManager(pe_count=2, mss_per_pe=4, slices_per_mss=8)

req = MemoryRequirement(
    size=4096,
    dimension_reqs=[
        DimensionRequirement(DimensionScope.ALL),
        DimensionRequirement(DimensionScope.ALL),
        DimensionRequirement(DimensionScope.ALL)
    ],
    allocation_id="kernel_buffer"
)

success = manager.allocate_requirement(req)
if success:
    print(f"Allocated at: 0x{req.allocation_details.allocated_address:08x}")
```

### Automatic Resource Selection with Tracking
```python
req = MemoryRequirement(
    size=1024,
    dimension_reqs=[
        DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # Auto-select
        DimensionRequirement(DimensionScope.SPECIFIC, value=None),  # Auto-select
        DimensionRequirement(DimensionScope.ALL)
    ],
    allocation_id="auto_buffer"
)

success = manager.allocate_requirement(req)
if req.is_fulfilled():
    details = req.allocation_details
    print(f"System chose PE {details.resolved_pe}, MSS {details.resolved_mss}")
    print(f"Allocated at 0x{details.allocated_address:08x}")
```

### Parallel Allocation with Results
```python
req = MemoryRequirement(
    size=1024,  # 256 bytes per slice
    dimension_reqs=[
        DimensionRequirement(DimensionScope.SPECIFIC, value=0),
        DimensionRequirement(DimensionScope.SPECIFIC, value=0),
        DimensionRequirement(DimensionScope.GROUP, group=SliceGroup.GROUP_0_3)
    ],
    allocation_mode=SliceAllocationMode.PARALLEL,
    allocation_id="parallel_data"
)

success = manager.allocate_requirement(req)
if req.is_fulfilled():
    print(f"Parallel allocation across slices: {req.allocation_details.resolved_slice_values}")
    print(f"Bytes per slice: {req.size // len(req.allocation_details.resolved_slice_values)}")
```

## Memory Statistics and Monitoring
```python
stats = manager.get_memory_stats()
print(f"Total mappings: {stats['total_mappings']}")
print(f"Total allocated: {sum(m['total_allocated'] for m in stats['mappings']):,} bytes")

# Review all processed requirements
manager.print_requirements_summary()
```

## Benefits

- **Intelligent Resource Management**: Dynamic mapping forking and automatic resource selection
- **Complete Transparency**: Full tracking of requirement state and allocation details
- **Scalability**: Efficiently handles complex allocation patterns with minimal overhead
- **Flexibility**: Orthogonal dimension requirements support diverse allocation patterns
- **Optimization**: Smart resource selection and load balancing
- **Consistency**: Unified approach to different allocation scenarios
- **Visibility**: Comprehensive statistics and requirement tracking

## Files

- `memory_manager.py`: Core implementation with requirement tracking
- `memory_manager_demo.py`: Interactive demonstration of all features
- `test_requirements_tracking.py`: Focused test of fulfillment tracking
- `README.md`: This documentation

## Testing

### Run Unit Tests
```bash
python memory_manager.py
```

### Run Full Demonstration
```bash
python memory_manager_demo.py
```

### Test Requirement Tracking
```bash
python test_requirements_tracking.py
```

## Design Principles

1. **Multi-dimensional Orthogonality**: Requirements in different dimensions are independent
2. **Copy-on-Write Mapping**: Shared mappings are forked only when allocation patterns diverge
3. **Intelligent Selection**: Automatic resource selection based on utilization and constraints
4. **Requirement Transparency**: Complete visibility into allocation decisions and results
5. **Conflict Resolution**: Intersection-based allocation for cross-mapping requirements
6. **Performance**: Efficient memory utilization with minimal fragmentation
 
