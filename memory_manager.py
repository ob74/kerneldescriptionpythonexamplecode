from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import copy


class DimensionScope(Enum):
    ALL = "all"           # All resources in this dimension
    SPECIFIC = "specific" # One specific resource
    GROUP = "group"       # A group of resources (for slice groups)


class SliceAllocationMode(Enum):
    SERIAL = "serial"      # Normal contiguous allocation in one slice
    PARALLEL = "parallel"  # Distributed across slice group (0-3 or 4-7)


class SliceGroup(Enum):
    GROUP_0_3 = "group_0_3"  # Slices 0, 1, 2, 3
    GROUP_4_7 = "group_4_7"  # Slices 4, 5, 6, 7


class RequirementState(Enum):
    PENDING = "pending"       # Not yet allocated
    FULFILLED = "fulfilled"   # Successfully allocated


class AllocationError(Exception):
    """Raised when allocation fails"""
    pass


@dataclass(frozen=True)
class ResourceCoordinate:
    """Represents a specific resource in the hierarchy"""
    pe: int
    mss: int
    slice: int
    
    def __str__(self):
        return f"({self.pe}, {self.mss}, {self.slice})"


@dataclass
class AllocationDetails:
    """Details about how a requirement was fulfilled"""
    allocated_address: int
    resolved_pe: int
    resolved_mss: int
    resolved_slice_values: List[int]  # For slice groups, this will be [0,1,2,3] or [4,5,6,7]
    mapping_count_at_allocation: int  # How many mappings existed when this was allocated
    
    def __str__(self):
        slice_str = f"{self.resolved_slice_values}" if len(self.resolved_slice_values) > 1 else str(self.resolved_slice_values[0])
        return f"PE{self.resolved_pe}/MSS{self.resolved_mss}/Slice{slice_str} @ 0x{self.allocated_address:08x}"


@dataclass
class DimensionRequirement:
    scope: DimensionScope
    value: Optional[int] = None
    group: Optional[SliceGroup] = None
    
    def needs_selection(self) -> bool:
        return self.scope == DimensionScope.SPECIFIC and self.value is None
    
    def get_possible_values(self, dimension_size: int) -> List[int]:
        """Get all possible values for this dimension"""
        if self.scope == DimensionScope.ALL:
            return list(range(dimension_size))
        elif self.scope == DimensionScope.SPECIFIC:
            return [self.value] if self.value is not None else list(range(dimension_size))
        elif self.scope == DimensionScope.GROUP:
            return self._get_group_values(self.group)
        else:
            raise ValueError(f"Unknown scope: {self.scope}")
    
    def _get_group_values(self, group: SliceGroup) -> List[int]:
        if group == SliceGroup.GROUP_0_3:
            return [0, 1, 2, 3]
        elif group == SliceGroup.GROUP_4_7:
            return [4, 5, 6, 7]
        else:
            raise ValueError(f"Unknown slice group: {group}")


@dataclass
class MemoryRequirement:
    # Class variables for dimension sizes (shared across all instances)
    # These are defined outside dataclass field annotations to be true class variables
    pe_count = 0
    mss_per_pe = 0
    slices_per_mss = 0
    
    # Instance fields
    size: int                              # number of bytes to allocate per slice
    pe_req: DimensionRequirement           # PE dimension requirement
    mss_req: DimensionRequirement          # MSS dimension requirement  
    slice_req: DimensionRequirement        # Slice dimension requirement
    allocation_mode: SliceAllocationMode = SliceAllocationMode.SERIAL
    allocation_id: str = ""
    
    # State tracking fields
    state: RequirementState = field(default=RequirementState.PENDING)
    allocation_details: Optional[AllocationDetails] = field(default=None)
    
    # Internal list for algorithm compatibility (auto-generated)
    dimension_reqs: List[DimensionRequirement] = field(init=False)
    
    def __post_init__(self):
        """Create internal dimension_reqs list from explicit requirements"""
        self.dimension_reqs = [self.pe_req, self.mss_req, self.slice_req]
    
    @classmethod
    def set_system_dimensions(cls, pe_count: int, mss_per_pe: int, slices_per_mss: int):
        """Set the system dimension sizes for all MemoryRequirement instances"""
        cls.pe_count = pe_count
        cls.mss_per_pe = mss_per_pe
        cls.slices_per_mss = slices_per_mss
    
    def get_dimension_sizes(self) -> List[int]:
        return [MemoryRequirement.pe_count, MemoryRequirement.mss_per_pe, MemoryRequirement.slices_per_mss]
    
    def needs_any_selection(self) -> bool:
        return any(req.needs_selection() for req in self.dimension_reqs)
    
    def get_affected_coordinates(self) -> Set[ResourceCoordinate]:
        """Generate all coordinates affected by this requirement"""
        dimension_sizes = self.get_dimension_sizes()
        
        # Get possible values for each dimension
        possible_values = []
        for i, dim_req in enumerate(self.dimension_reqs):
            possible_values.append(dim_req.get_possible_values(dimension_sizes[i]))
        
        # Generate all combinations
        coords = set()
        for pe in possible_values[0]:
            for mss in possible_values[1]:
                for slice_id in possible_values[2]:
                    coords.add(ResourceCoordinate(pe, mss, slice_id))
        
        return coords
    
    def total_allocation_size(self) -> int:
        """
        Calculate the total number of bytes that will be allocated for this requirement.
        Returns size * number_of_affected_coordinates based on the requirement scopes.
        For parallel allocation mode, the effective size per coordinate is size // 4.
        """
        dimension_sizes = self.get_dimension_sizes()
        
        # Calculate affected count for each dimension based on scope
        affected_counts = []
        for i, dim_req in enumerate(self.dimension_reqs):
            if dim_req.scope == DimensionScope.ALL:
                affected_counts.append(dimension_sizes[i])
            elif dim_req.scope == DimensionScope.SPECIFIC:
                # For SPECIFIC scope, always count as 1 regardless of whether value is resolved
                affected_counts.append(1)
            elif dim_req.scope == DimensionScope.GROUP:
                # For GROUP scope, count the group size
                group_values = dim_req._get_group_values(dim_req.group)
                affected_counts.append(len(group_values))
            else:
                raise ValueError(f"Unknown scope: {dim_req.scope}")
        
        # Total coordinates = product of affected counts across all dimensions
        total_coordinates = 1
        for count in affected_counts:
            total_coordinates *= count
        
        # For parallel allocation, the effective size per coordinate is divided by 4
        effective_size = self.size
        if self.allocation_mode == SliceAllocationMode.PARALLEL:
            effective_size = self.size // 4
        
        return effective_size * total_coordinates
    
    def mark_fulfilled(self, allocated_address: int, resolved_req: 'MemoryRequirement', mapping_count: int):
        """Mark this requirement as fulfilled with allocation details"""
        # Extract resolved values
        resolved_pe = resolved_req.dimension_reqs[0].value
        resolved_mss = resolved_req.dimension_reqs[1].value
        
        # Handle slice values (could be single value or group)
        slice_req = resolved_req.dimension_reqs[2]
        if slice_req.scope == DimensionScope.GROUP:
            resolved_slice_values = slice_req.get_possible_values(8)  # 8 slices per MSS
        else:
            resolved_slice_values = [slice_req.value]
        
        self.allocation_details = AllocationDetails(
            allocated_address=allocated_address,
            resolved_pe=resolved_pe,
            resolved_mss=resolved_mss,
            resolved_slice_values=resolved_slice_values,
            mapping_count_at_allocation=mapping_count
        )
        self.state = RequirementState.FULFILLED
    
    def is_fulfilled(self) -> bool:
        """Check if this requirement has been fulfilled"""
        return self.state == RequirementState.FULFILLED
    
    def get_fulfillment_summary(self) -> str:
        """Get a human-readable summary of how this requirement was fulfilled"""
        if not self.is_fulfilled():
            return f"❌ {self.allocation_id}: PENDING (not yet allocated)"
        
        details = self.allocation_details
        mode_str = "PARALLEL" if self.allocation_mode == SliceAllocationMode.PARALLEL else "SERIAL"
        size_str = f"{self.size:,} bytes"
        
        return f"✅ {self.allocation_id}: {size_str} {mode_str} at {details} (mappings: {details.mapping_count_at_allocation})"


class SliceMemoryMap:
    def __init__(self, slice_size: int = 1024*1024):  # 1MB default
        self.slice_size = slice_size
        self.allocations = []  # List of (start, size, allocation_id)
        self.next_address = 0
    
    def get_total_allocated(self) -> int:
        """Return total allocated bytes in this map"""
        return sum(size for _, size, _ in self.allocations)
    
    def get_total_free(self) -> int:
        """Return total free bytes in this map"""
        return self.slice_size - self.get_total_allocated()
    
    def get_largest_free_block(self) -> int:
        """Return size of largest contiguous free block"""
        if not self.allocations:
            return self.slice_size
        
        # Calculate gaps between allocations
        sorted_allocs = sorted(self.allocations, key=lambda x: x[0])
        max_gap = 0
        
        # Check gap before first allocation
        if sorted_allocs:
            max_gap = max(max_gap, sorted_allocs[0][0])
        
        # Check gaps between allocations
        for i in range(len(sorted_allocs) - 1):
            current_end = sorted_allocs[i][0] + sorted_allocs[i][1]
            next_start = sorted_allocs[i + 1][0]
            gap = next_start - current_end
            max_gap = max(max_gap, gap)
        
        # Check gap after last allocation
        if sorted_allocs:
            last_end = sorted_allocs[-1][0] + sorted_allocs[-1][1]
            max_gap = max(max_gap, self.slice_size - last_end)
        
        return max_gap
    
    def can_accommodate(self, size: int) -> bool:
        """Check if this map can accommodate an allocation of given size"""
        return self.get_largest_free_block() >= size
    
    def get_free_ranges(self) -> List[Tuple[int, int]]:
        """Get list of (start, end) free ranges"""
        if not self.allocations:
            return [(0, self.slice_size)]
        
        sorted_allocs = sorted(self.allocations, key=lambda x: x[0])
        free_ranges = []
        
        # Range before first allocation
        if sorted_allocs[0][0] > 0:
            free_ranges.append((0, sorted_allocs[0][0]))
        
        # Ranges between allocations
        for i in range(len(sorted_allocs) - 1):
            current_end = sorted_allocs[i][0] + sorted_allocs[i][1]
            next_start = sorted_allocs[i + 1][0]
            if next_start > current_end:
                free_ranges.append((current_end, next_start))
        
        # Range after last allocation
        last_end = sorted_allocs[-1][0] + sorted_allocs[-1][1]
        if last_end < self.slice_size:
            free_ranges.append((last_end, self.slice_size))
        
        return free_ranges
    
    def allocate_serial(self, size: int, allocation_id: str) -> Optional[int]:
        """Normal contiguous allocation"""
        free_ranges = self.get_free_ranges()
        for start, end in free_ranges:
            if end - start >= size:
                self.allocations.append((start, size, allocation_id))
                return start
        return None
    
    def allocate_at_address(self, address: int, size: int, allocation_id: str) -> bool:
        """Allocate at specific address"""
        # Check if address range is free
        free_ranges = self.get_free_ranges()
        for start, end in free_ranges:
            if start <= address and address + size <= end:
                self.allocations.append((address, size, allocation_id))
                return True
        return False
    
    def clone(self) -> 'SliceMemoryMap':
        """Create a deep copy of this memory map"""
        new_map = SliceMemoryMap(self.slice_size)
        new_map.allocations = self.allocations.copy()
        new_map.next_address = self.next_address
        return new_map


class MappingSignature:
    """Represents the allocation pattern signature of a mapping"""
    def __init__(self, covered_coordinates: Set[ResourceCoordinate]):
        self.covered_coordinates = frozenset(covered_coordinates)
        
    def __hash__(self):
        return hash(self.covered_coordinates)
    
    def __eq__(self, other):
        return self.covered_coordinates == other.covered_coordinates
    
    def __str__(self):
        return f"Signature({len(self.covered_coordinates)} coords)"


class IntersectionMap:
    """Temporary map representing free space common to multiple maps"""
    
    def __init__(self, constituent_maps: List[SliceMemoryMap]):
        self.constituent_maps = constituent_maps
        self.free_ranges = self._compute_intersection()
    
    def _compute_intersection(self) -> List[Tuple[int, int]]:
        """Find address ranges free in ALL constituent maps"""
        if not self.constituent_maps:
            return []
        
        # Start with free ranges from first map
        common_free = self.constituent_maps[0].get_free_ranges()
        
        # Intersect with each subsequent map
        for map_obj in self.constituent_maps[1:]:
            map_free = map_obj.get_free_ranges()
            common_free = self._intersect_ranges(common_free, map_free)
        
        return common_free
    
    def _intersect_ranges(self, ranges1: List[Tuple[int, int]], 
                         ranges2: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Compute intersection of two lists of ranges"""
        intersection = []
        for start1, end1 in ranges1:
            for start2, end2 in ranges2:
                overlap_start = max(start1, start2)
                overlap_end = min(end1, end2)
                if overlap_start < overlap_end:
                    intersection.append((overlap_start, overlap_end))
        return intersection
    
    def allocate(self, size: int) -> Optional[int]:
        """Allocate from intersection, return address or None"""
        for start, end in self.free_ranges:
            if end - start >= size:
                # Found space, allocate and update free ranges
                allocated_addr = start
                self._update_free_ranges_after_allocation(start, size)
                return allocated_addr
        return None
    
    def _update_free_ranges_after_allocation(self, address: int, size: int):
        """Update free ranges after allocation"""
        new_ranges = []
        for start, end in self.free_ranges:
            if start <= address < end:
                # This range contains the allocation
                if start < address:
                    new_ranges.append((start, address))
                if address + size < end:
                    new_ranges.append((address + size, end))
            else:
                new_ranges.append((start, end))
        self.free_ranges = new_ranges
    
    def apply_allocation_to_constituents(self, address: int, size: int, allocation_id: str):
        """Apply successful allocation to all constituent maps"""
        for map_obj in self.constituent_maps:
            map_obj.allocate_at_address(address, size, allocation_id)


class UnifiedDimensionResolver:
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
    
    def resolve_requirement(self, req: MemoryRequirement) -> MemoryRequirement:
        """Resolve all unresolved dimensions in one unified process"""
        if not req.needs_any_selection():
            return req
        
        # Find which dimensions need selection
        unresolved_dimensions = [i for i, dim_req in enumerate(req.dimension_reqs) 
                               if dim_req.needs_selection()]
        
        # Generate all possible combinations for unresolved dimensions
        best_combination = self._find_best_dimension_combination(req, unresolved_dimensions)
        
        # Apply the best combination
        resolved_req = copy.deepcopy(req)
        for dim_index, value in zip(unresolved_dimensions, best_combination):
            resolved_req.dimension_reqs[dim_index].value = value
        
        return resolved_req
    
    def _find_best_dimension_combination(self, req: MemoryRequirement, 
                                       unresolved_dimensions: List[int]) -> Tuple[int, ...]:
        """Find the best combination of values for unresolved dimensions"""
        dimension_sizes = req.get_dimension_sizes()
        
        # Generate all possible combinations for unresolved dimensions
        possible_combinations = []
        self._generate_combinations(unresolved_dimensions, dimension_sizes, [], possible_combinations)
        
        best_combination = None
        best_score = -1
        
        for combination in possible_combinations:
            score = self._evaluate_combination(req, unresolved_dimensions, combination)
            if score > best_score:
                best_score = score
                best_combination = combination
        
        if best_combination is None:
            raise AllocationError("No valid combination found for requirement")
        
        return best_combination
    
    def _generate_combinations(self, unresolved_dimensions: List[int], dimension_sizes: List[int],
                             current_combination: List[int], all_combinations: List[Tuple]):
        """Recursively generate all possible combinations"""
        if len(current_combination) == len(unresolved_dimensions):
            all_combinations.append(tuple(current_combination))
            return
        
        dim_index = unresolved_dimensions[len(current_combination)]
        for value in range(dimension_sizes[dim_index]):
            current_combination.append(value)
            self._generate_combinations(unresolved_dimensions, dimension_sizes, 
                                      current_combination, all_combinations)
            current_combination.pop()
    
    def _evaluate_combination(self, req: MemoryRequirement, unresolved_dimensions: List[int], 
                            combination: Tuple[int, ...]) -> float:
        """Evaluate how good this combination is (higher = better)"""
        # Create test requirement with this combination
        test_req = copy.deepcopy(req)
        for dim_index, value in zip(unresolved_dimensions, combination):
            test_req.dimension_reqs[dim_index].value = value
        
        # Check if this combination can be accommodated
        affected_mappings = self.memory_manager.get_affected_mappings(test_req)
        
        if len(affected_mappings) == 0:
            return -1  # Invalid combination
        
        if len(affected_mappings) == 1:
            # Single mapping - check if it can accommodate
            mapping = next(iter(affected_mappings))
            if mapping.can_accommodate(req.size):
                return mapping.get_total_free()  # Score by free space
            else:
                return -1
        else:
            # Multiple mappings - would need intersection
            # Score by minimum free space across all mappings
            min_free = min(mapping.get_total_free() for mapping in affected_mappings)
            if all(mapping.can_accommodate(req.size) for mapping in affected_mappings):
                return min_free * 0.8  # Slight penalty for cross-mapping allocation
            else:
                return -1


class MappingCentricMemoryManager:
    def __init__(self, pe_count: int, mss_per_pe: int = 4, slices_per_mss: int = 8):
        self.pe_count = pe_count
        self.mss_per_pe = mss_per_pe
        self.slices_per_mss = slices_per_mss
        
        # Set the system dimensions for all MemoryRequirement instances
        MemoryRequirement.set_system_dimensions(pe_count, mss_per_pe, slices_per_mss)
        
        # Only store mappings - derive coordinate info from them
        self.signature_to_map: Dict[MappingSignature, SliceMemoryMap] = {}
        
        # Track all requirements that have been processed
        self.processed_requirements: List[MemoryRequirement] = []
        
        # Track collected requirements waiting for batch allocation
        self.collected_requirements: List[MemoryRequirement] = []
        
        # Initialize with universal mapping covering all coordinates
        self._initialize_universal_mapping()
        
        # Initialize dimension resolver
        self.dimension_resolver = UnifiedDimensionResolver(self)
    
    def _initialize_universal_mapping(self):
        """Start with one mapping covering all coordinates"""
        all_coords = {ResourceCoordinate(pe, mss, slice_id) 
                     for pe in range(self.pe_count)
                     for mss in range(self.mss_per_pe) 
                     for slice_id in range(self.slices_per_mss)}
        
        universal_signature = MappingSignature(all_coords)
        self.signature_to_map[universal_signature] = SliceMemoryMap()
    
    def get_mapping_for_coordinate(self, coord: ResourceCoordinate) -> SliceMemoryMap:
        """Find which mapping covers this coordinate"""
        for signature, mapping in self.signature_to_map.items():
            if coord in signature.covered_coordinates:
                return mapping
        raise ValueError(f"No mapping found for coordinate {coord}")
    
    def get_affected_mappings(self, req: MemoryRequirement) -> Set[SliceMemoryMap]:
        """Get all mappings that would be affected by this requirement"""
        affected_coords = req.get_affected_coordinates()
        affected_mappings = set()
        
        for coord in affected_coords:
            mapping = self.get_mapping_for_coordinate(coord)
            affected_mappings.add(mapping)
        
        return affected_mappings
    
    def _fork_mapping_if_needed(self, req: MemoryRequirement) -> bool:
        """Fork mappings if the requirement doesn't cover all coordinates in existing mappings"""
        affected_coords = req.get_affected_coordinates()
        
        # Find all mappings that contain any of the affected coordinates
        mappings_to_check = set()
        for coord in affected_coords:
            for signature, mapping in self.signature_to_map.items():
                if coord in signature.covered_coordinates:
                    mappings_to_check.add(signature)
                    break
        
        mappings_forked = False
        
        for signature in mappings_to_check:
            mapping = self.signature_to_map[signature]
            
            # Check if this mapping covers more coordinates than just our affected ones
            mapping_coords = signature.covered_coordinates
            affected_coords_in_mapping = mapping_coords.intersection(affected_coords)
            unaffected_coords_in_mapping = mapping_coords - affected_coords
            
            # If this mapping has coordinates not affected by our requirement, we need to fork
            if len(unaffected_coords_in_mapping) > 0 and len(affected_coords_in_mapping) > 0:
                # Fork the mapping
                original_mapping = self.signature_to_map[signature]
                
                # Remove the original mapping
                del self.signature_to_map[signature]
                
                # Create new mapping for affected coordinates
                if len(affected_coords_in_mapping) > 0:
                    affected_signature = MappingSignature(affected_coords_in_mapping)
                    self.signature_to_map[affected_signature] = original_mapping.clone()
                
                # Create new mapping for unaffected coordinates
                if len(unaffected_coords_in_mapping) > 0:
                    unaffected_signature = MappingSignature(unaffected_coords_in_mapping)
                    self.signature_to_map[unaffected_signature] = original_mapping.clone()
                
                mappings_forked = True
        
        return mappings_forked
    
    def allocate_requirement(self, req: MemoryRequirement) -> bool:
        """Allocate requirement using the mapping-centric approach"""
        # Add to processed requirements list
        self.processed_requirements.append(req)
        
        # Resolve any unresolved dimensions
        resolved_req = self.dimension_resolver.resolve_requirement(req)
        
        # Fork mappings if needed (before getting affected mappings)
        self._fork_mapping_if_needed(resolved_req)
        
        # Get current mapping count for tracking
        current_mapping_count = len(self.signature_to_map)
        
        # Get affected mappings (after potential forking)
        affected_mappings = self.get_affected_mappings(resolved_req)
        
        allocated_address = None
        
        if len(affected_mappings) == 1:
            # Single mapping allocation
            mapping = next(iter(affected_mappings))
            if resolved_req.allocation_mode == SliceAllocationMode.PARALLEL:
                allocated_address = self._allocate_parallel_single_mapping(resolved_req, mapping)
            else:
                allocated_address = mapping.allocate_serial(resolved_req.size, resolved_req.allocation_id)
        else:
            # Cross-mapping allocation using intersection
            allocated_address = self._allocate_cross_mapping(resolved_req, affected_mappings)
        
        # If allocation succeeded, mark the original requirement as fulfilled
        if allocated_address is not None:
            req.mark_fulfilled(allocated_address, resolved_req, current_mapping_count)
            return True
        else:
            return False
    
    def _allocate_parallel_single_mapping(self, req: MemoryRequirement, mapping: SliceMemoryMap) -> Optional[int]:
        """Allocate parallel requirement within single mapping"""
        size_per_slice = req.size // 4
        return mapping.allocate_serial(size_per_slice, req.allocation_id)
    
    def _allocate_cross_mapping(self, req: MemoryRequirement, affected_mappings: Set[SliceMemoryMap]) -> Optional[int]:
        """Allocate requirement across multiple mappings using intersection"""
        mapping_list = list(affected_mappings)
        intersection_map = IntersectionMap(mapping_list)
        
        if req.allocation_mode == SliceAllocationMode.PARALLEL:
            size_per_slice = req.size // 4
            allocated_addr = intersection_map.allocate(size_per_slice)
        else:
            allocated_addr = intersection_map.allocate(req.size)
        
        if allocated_addr is None:
            return None
        
        # Apply allocation to all affected mappings
        allocation_size = req.size // 4 if req.allocation_mode == SliceAllocationMode.PARALLEL else req.size
        intersection_map.apply_allocation_to_constituents(allocated_addr, allocation_size, req.allocation_id)
        
        return allocated_addr
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about current memory state"""
        stats = {
            'total_mappings': len(self.signature_to_map),
            'mappings': []
        }
        
        for signature, mapping in self.signature_to_map.items():
            mapping_stats = {
                'coordinates_count': len(signature.covered_coordinates),
                'total_free': mapping.get_total_free(),
                'total_allocated': mapping.get_total_allocated(),
                'largest_free_block': mapping.get_largest_free_block(),
                'fragmentation_ratio': 1.0 - (mapping.get_largest_free_block() / max(1, mapping.get_total_free()))
            }
            stats['mappings'].append(mapping_stats)
        
        return stats
    
    def get_requirements_summary(self) -> Dict[str, Any]:
        """Get summary of all processed requirements and their fulfillment status"""
        fulfilled_count = sum(1 for req in self.processed_requirements if req.is_fulfilled())
        pending_count = len(self.processed_requirements) - fulfilled_count
        
        return {
            'total_requirements': len(self.processed_requirements),
            'fulfilled_count': fulfilled_count,
            'pending_count': pending_count,
            'requirements': self.processed_requirements
        }
    
    def total_allocated_bytes(self) -> int:
        """
        Calculate the total number of bytes allocated across all coordinates in the system.
        This multiplies each mapping's allocated bytes by the number of coordinates it covers.
        """
        total_bytes = 0
        
        for signature, memory_map in self.signature_to_map.items():
            # Get allocated bytes in this mapping
            allocated_in_mapping = memory_map.get_total_allocated()
            
            # Get number of coordinates this mapping covers
            coordinate_count = len(signature.covered_coordinates)
            
            # Each coordinate in this mapping has the same allocation pattern
            total_bytes += allocated_in_mapping * coordinate_count
        
        return total_bytes
    
    def total_requested_allocations(self) -> int:
        """
        Calculate the total number of bytes requested by all fulfilled requirements.
        This sums the total_allocation_size() for all successfully allocated requirements.
        Should equal total_allocated_bytes() for validation.
        """
        total_requested = 0
        
        for req in self.processed_requirements:
            if req.is_fulfilled():
                total_requested += req.total_allocation_size()
        
        return total_requested
    
    def print_requirements_summary(self):
        """Print a detailed summary of all requirements and their fulfillment status"""
        summary = self.get_requirements_summary()
        
        print(f"\n📋 REQUIREMENTS SUMMARY")
        print(f"{'='*60}")
        print(f"Total Requirements: {summary['total_requirements']}")
        print(f"✅ Fulfilled: {summary['fulfilled_count']}")
        print(f"❌ Pending: {summary['pending_count']}")
        print()
        
        if summary['requirements']:
            print("Detailed Status:")
            for req in summary['requirements']:
                print(f"  {req.get_fulfillment_summary()}")
        else:
            print("No requirements processed yet.")
        
        print(f"{'='*60}")

    def collect_requirement(self, req: MemoryRequirement) -> None:
        """Collect a requirement for later batch allocation"""
        self.collected_requirements.append(req)
    
    def allocate_all(self) -> Dict[str, Any]:
        """
        Allocate all collected requirements in optimal order to minimize conflicts.
        Returns summary of allocation results.
        """
        if not self.collected_requirements:
            return {
                'total_requirements': 0,
                'successful_allocations': 0,
                'failed_allocations': 0,
                'allocation_details': []
            }
        
        # Sort requirements to minimize conflicts and forking
        ordered_requirements = self._optimize_requirement_order(self.collected_requirements.copy())
        
        allocation_results = []
        successful_count = 0
        failed_count = 0
        
        print(f"Allocating {len(ordered_requirements)} requirements in optimized order...")
        print()
        
        for i, req in enumerate(ordered_requirements, 1):
            print(f"Step {i}: Allocating '{req.allocation_id}' ({req.size:,} bytes)")
            
            # Record state before allocation
            mappings_before = len(self.signature_to_map)
            
            # Attempt allocation
            success = self.allocate_requirement(req)
            
            # Record state after allocation
            mappings_after = len(self.signature_to_map)
            fork_occurred = mappings_after > mappings_before
            
            result = {
                'requirement_id': req.allocation_id,
                'size': req.size,
                'success': success,
                'mappings_before': mappings_before,
                'mappings_after': mappings_after,
                'fork_occurred': fork_occurred,
                'allocation_details': req.allocation_details if success else None
            }
            
            allocation_results.append(result)
            
            if success:
                successful_count += 1
                fork_msg = f" (forked: {mappings_before} -> {mappings_after})" if fork_occurred else " (no fork)"
                print(f"  [SUCCESS]{fork_msg}")
                if req.allocation_details:
                    print(f"  Address: 0x{req.allocation_details.allocated_address:08x}")
            else:
                failed_count += 1
                print(f"  [FAILED] Could not allocate")
            print()
        
        # Clear collected requirements after processing
        self.collected_requirements.clear()
        
        return {
            'total_requirements': len(ordered_requirements),
            'successful_allocations': successful_count,
            'failed_allocations': failed_count,
            'allocation_details': allocation_results
        }
    
    def _optimize_requirement_order(self, requirements: List[MemoryRequirement]) -> List[MemoryRequirement]:
        """
        Order requirements to minimize conflicts and mapping forking.
        Strategy: Process broadest scopes first, then progressively narrow down.
        """
        def requirement_priority(req: MemoryRequirement) -> Tuple[int, int, int, int]:
            """
            Return priority tuple for sorting. Lower values = higher priority.
            Priority order:
            1. Scope breadth (ALL > SPECIFIC > GROUP)
            2. Number of auto-selections (fewer = higher priority)
            3. Size (larger = higher priority) 
            4. Allocation mode (SERIAL > PARALLEL for consistency)
            """
            # Calculate scope breadth score (lower = broader scope)
            scope_score = 0
            for dim_req in req.dimension_reqs:
                if dim_req.scope == DimensionScope.ALL:
                    scope_score += 0  # Broadest scope
                elif dim_req.scope == DimensionScope.SPECIFIC:
                    scope_score += 1 if dim_req.value is not None else 2  # Specific > Auto-select
                elif dim_req.scope == DimensionScope.GROUP:
                    scope_score += 1  # Between ALL and SPECIFIC
            
            # Count auto-selections (more auto-selections = lower priority)
            auto_selection_count = sum(1 for dim_req in req.dimension_reqs if dim_req.needs_selection())
            
            # Size priority (larger = higher priority, so negate)
            size_priority = -req.size
            
            # Allocation mode priority (SERIAL = 0, PARALLEL = 1)
            mode_priority = 1 if req.allocation_mode == SliceAllocationMode.PARALLEL else 0
            
            return (scope_score, auto_selection_count, size_priority, mode_priority)
        
        # Sort by priority
        sorted_requirements = sorted(requirements, key=requirement_priority)
        
        print("Requirement ordering strategy:")
        print("  1. Process broadest scopes first (ALL > SPECIFIC > GROUP)")
        print("  2. Minimize auto-selections early")
        print("  3. Prioritize larger allocations")
        print("  4. Process serial allocations before parallel")
        print()
        
        for i, req in enumerate(sorted_requirements, 1):
            scope_desc = self._describe_requirement_scope(req)
            print(f"  {i}. {req.allocation_id}: {scope_desc} ({req.size:,} bytes)")
        print()
        
        return sorted_requirements
    
    def _describe_requirement_scope(self, req: MemoryRequirement) -> str:
        """Generate human-readable description of requirement scope"""
        pe_desc = self._describe_dimension_scope(req.dimension_reqs[0], "PE")
        mss_desc = self._describe_dimension_scope(req.dimension_reqs[1], "MSS") 
        slice_desc = self._describe_dimension_scope(req.dimension_reqs[2], "Slice")
        
        mode_desc = " PARALLEL" if req.allocation_mode == SliceAllocationMode.PARALLEL else ""
        
        return f"{pe_desc} × {mss_desc} × {slice_desc}{mode_desc}"
    
    def _describe_dimension_scope(self, dim_req: DimensionRequirement, dim_name: str) -> str:
        """Describe a single dimension requirement"""
        if dim_req.scope == DimensionScope.ALL:
            return f"All-{dim_name}"
        elif dim_req.scope == DimensionScope.SPECIFIC:
            if dim_req.value is not None:
                return f"{dim_name}{dim_req.value}"
            else:
                return f"Auto-{dim_name}"
        elif dim_req.scope == DimensionScope.GROUP:
            group_name = dim_req.group.value.replace("group_", "")
            return f"{dim_name}-{group_name}"
        else:
            return f"Unknown-{dim_name}"


# Unit Tests
def test_basic_serial_allocation():
    """Test basic serial allocation in shared mapping"""
    print("Testing basic serial allocation...")
    
    # Create memory manager with 2 PEs, 2 MSS, 4 slices
    manager = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=4)
    
    # Create requirement: 1KB in all PEs, all MSS, all slices (should not fork)
    req = MemoryRequirement(
        size=1024,
        pe_req=DimensionRequirement(DimensionScope.ALL),
        mss_req=DimensionRequirement(DimensionScope.ALL),
        slice_req=DimensionRequirement(DimensionScope.ALL),
        allocation_id="test_alloc_uniform"
    )
    
    # Should succeed without forking
    success = manager.allocate_requirement(req)
    assert success, "Basic allocation should succeed"
    
    # Check stats - should still have one mapping
    stats = manager.get_memory_stats()
    assert stats['total_mappings'] == 1, f"Should still have one mapping, got {stats['total_mappings']}"
    
    # Validate that total requested matches total allocated
    assert manager.total_requested_allocations() == manager.total_allocated_bytes(), \
        f"Validation failed: requested={manager.total_requested_allocations()} != allocated={manager.total_allocated_bytes()}"
    
    print("✓ Basic serial allocation test passed")


def test_pe_specific_forking():
    """Test PE-specific allocation causes mapping fork"""
    print("Testing PE-specific allocation forking...")
    
    manager = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=4)
    
    # Create requirement: 1KB in PE 0 only, all MSS, all slices (should fork)
    req = MemoryRequirement(
        size=1024,
        pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=0),
        mss_req=DimensionRequirement(DimensionScope.ALL),
        slice_req=DimensionRequirement(DimensionScope.ALL),
        allocation_id="pe0_specific"
    )
    
    # Should succeed and cause forking
    success = manager.allocate_requirement(req)
    assert success, "PE-specific allocation should succeed"
    
    # Check stats - should now have two mappings (PE 0 coords + PE 1 coords)
    stats = manager.get_memory_stats()
    assert stats['total_mappings'] == 2, f"Should have two mappings after fork, got {stats['total_mappings']}"
    
    # Validate that total requested matches total allocated
    assert manager.total_requested_allocations() == manager.total_allocated_bytes(), \
        f"Validation failed: requested={manager.total_requested_allocations()} != allocated={manager.total_allocated_bytes()}"
    
    print("✓ PE-specific allocation forking test passed")


def test_mss_specific_forking():
    """Test MSS-specific allocation causes mapping fork"""
    print("Testing MSS-specific allocation forking...")
    
    manager = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=4)
    
    # Create requirement: 1KB in all PEs, MSS 1 only, all slices (should fork)
    req = MemoryRequirement(
        size=1024,
        pe_req=DimensionRequirement(DimensionScope.ALL),
        mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=1),
        slice_req=DimensionRequirement(DimensionScope.ALL),
        allocation_id="mss1_specific"
    )
    
    # Should succeed and cause forking
    success = manager.allocate_requirement(req)
    assert success, "MSS-specific allocation should succeed"
    
    # Check stats - should now have two mappings
    stats = manager.get_memory_stats()
    assert stats['total_mappings'] == 2, f"Should have two mappings after fork, got {stats['total_mappings']}"
    
    # Validate that total requested matches total allocated
    assert manager.total_requested_allocations() == manager.total_allocated_bytes(), \
        f"Validation failed: requested={manager.total_requested_allocations()} != allocated={manager.total_allocated_bytes()}"
    
    print("✓ MSS-specific allocation forking test passed")


def test_slice_group_forking():
    """Test slice group allocation causes mapping fork"""
    print("Testing slice group allocation forking...")
    
    manager = MappingCentricMemoryManager(pe_count=1, mss_per_pe=1, slices_per_mss=8)
    
    # Create requirement: 1KB in all PEs, all MSS, slice group 0-3 only (should fork)
    req = MemoryRequirement(
        size=1024,
        pe_req=DimensionRequirement(DimensionScope.ALL),
        mss_req=DimensionRequirement(DimensionScope.ALL),
        slice_req=DimensionRequirement(DimensionScope.GROUP, group=SliceGroup.GROUP_0_3),
        allocation_mode=SliceAllocationMode.PARALLEL,
        allocation_id="slice_group_0_3"
    )
    
    # Should succeed and cause forking
    success = manager.allocate_requirement(req)
    assert success, "Slice group allocation should succeed"
    
    # Check stats - should now have two mappings (group 0-3 + group 4-7)
    stats = manager.get_memory_stats()
    assert stats['total_mappings'] == 2, f"Should have two mappings after fork, got {stats['total_mappings']}"
    
    # Validate that total requested matches total allocated
    assert manager.total_requested_allocations() == manager.total_allocated_bytes(), \
        f"Validation failed: requested={manager.total_requested_allocations()} != allocated={manager.total_allocated_bytes()}"
    
    print("✓ Slice group allocation forking test passed")


def test_automatic_resource_selection():
    """Test automatic resource selection optimization"""
    print("Testing automatic resource selection...")
    
    manager = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=4)
    
    # Create requirement: 1KB in some specific PE (unspecified), all MSS, all slices
    req = MemoryRequirement(
        size=1024,
        pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=None),
        mss_req=DimensionRequirement(DimensionScope.ALL),
        slice_req=DimensionRequirement(DimensionScope.ALL),
        allocation_id="auto_pe_selection"
    )
    
    # Should succeed with automatic PE selection and cause forking
    success = manager.allocate_requirement(req)
    assert success, "Allocation with automatic selection should succeed"
    
    # Should have forked (one PE selected, other PE remains separate)
    stats = manager.get_memory_stats()
    assert stats['total_mappings'] == 2, f"Should have two mappings after auto-selection fork, got {stats['total_mappings']}"
    
    # Validate that total requested matches total allocated
    assert manager.total_requested_allocations() == manager.total_allocated_bytes(), \
        f"Validation failed: requested={manager.total_requested_allocations()} != allocated={manager.total_allocated_bytes()}"
    
    print("✓ Automatic resource selection test passed")


def test_complex_multiple_requirements():
    """Test complex scenarios with multiple requirements of different types"""
    print("Testing complex multiple requirements scenario...")
    
    manager = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=8)
    
    # Start with universal mapping
    initial_stats = manager.get_memory_stats()
    assert initial_stats['total_mappings'] == 1, "Should start with one universal mapping"
    
    # Requirement 1: Global allocation (should not fork)
    req1 = MemoryRequirement(
        size=512,
        pe_req=DimensionRequirement(DimensionScope.ALL),
        mss_req=DimensionRequirement(DimensionScope.ALL),
        slice_req=DimensionRequirement(DimensionScope.ALL),
        allocation_id="global_data"
    )
    
    success1 = manager.allocate_requirement(req1)
    assert success1, "Global allocation should succeed"
    
    stats1 = manager.get_memory_stats()
    assert stats1['total_mappings'] == 1, f"Should still have one mapping after global alloc, got {stats1['total_mappings']}"
    
    # Validate after first allocation
    assert manager.total_requested_allocations() == manager.total_allocated_bytes(), \
        f"Validation failed after req1: requested={manager.total_requested_allocations()} != allocated={manager.total_allocated_bytes()}"
    
    # Requirement 2: PE-specific allocation (should fork)
    req2 = MemoryRequirement(
        size=256,
        pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=0),
        mss_req=DimensionRequirement(DimensionScope.ALL),
        slice_req=DimensionRequirement(DimensionScope.ALL),
        allocation_id="pe0_cache"
    )
    
    success2 = manager.allocate_requirement(req2)
    assert success2, "PE-specific allocation should succeed"
    
    stats2 = manager.get_memory_stats()
    assert stats2['total_mappings'] == 2, f"Should have two mappings after PE fork, got {stats2['total_mappings']}"
    
    # Validate after second allocation
    assert manager.total_requested_allocations() == manager.total_allocated_bytes(), \
        f"Validation failed after req2: requested={manager.total_requested_allocations()} != allocated={manager.total_allocated_bytes()}"
    
    # Requirement 3: MSS-specific allocation (should cause additional fork)
    req3 = MemoryRequirement(
        size=128,
        pe_req=DimensionRequirement(DimensionScope.ALL),
        mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=0),
        slice_req=DimensionRequirement(DimensionScope.ALL),
        allocation_id="mss0_buffer"
    )
    
    success3 = manager.allocate_requirement(req3)
    assert success3, "MSS-specific allocation should succeed"
    
    stats3 = manager.get_memory_stats()
    assert stats3['total_mappings'] >= 3, f"Should have at least three mappings after MSS fork, got {stats3['total_mappings']}"
    
    # Validate after third allocation
    assert manager.total_requested_allocations() == manager.total_allocated_bytes(), \
        f"Validation failed after req3: requested={manager.total_requested_allocations()} != allocated={manager.total_allocated_bytes()}"
    
    # Requirement 4: Slice group allocation (should cause more forking)
    req4 = MemoryRequirement(
        size=1024,
        pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=1),
        mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=1),
        slice_req=DimensionRequirement(DimensionScope.GROUP, group=SliceGroup.GROUP_0_3),
        allocation_mode=SliceAllocationMode.PARALLEL,
        allocation_id="pe1_mss1_slice_group"
    )
    
    success4 = manager.allocate_requirement(req4)
    assert success4, "Slice group allocation should succeed"
    
    final_stats = manager.get_memory_stats()
    print(f"Final mapping count: {final_stats['total_mappings']}")
    
    # Should have multiple mappings due to various forks
    assert final_stats['total_mappings'] >= 4, f"Should have at least four mappings after all forks, got {final_stats['total_mappings']}"
    
    # Final validation after all allocations
    assert manager.total_requested_allocations() == manager.total_allocated_bytes(), \
        f"Validation failed after all allocations: requested={manager.total_requested_allocations()} != allocated={manager.total_allocated_bytes()}"
    
    print("✓ Complex multiple requirements test passed")


def test_cross_mapping_allocation():
    """Test allocation that spans multiple mappings after forking"""
    print("Testing cross-mapping allocation...")
    
    manager = MappingCentricMemoryManager(pe_count=2, mss_per_pe=2, slices_per_mss=4)
    
    # First, create an allocation that causes a fork
    req1 = MemoryRequirement(
        size=512,
        pe_req=DimensionRequirement(DimensionScope.SPECIFIC, value=0),
        mss_req=DimensionRequirement(DimensionScope.ALL),
        slice_req=DimensionRequirement(DimensionScope.ALL),
        allocation_id="fork_alloc"
    )
    
    success1 = manager.allocate_requirement(req1)
    assert success1, "First allocation should succeed"
    
    # Should have forked
    stats1 = manager.get_memory_stats()
    assert stats1['total_mappings'] == 2, f"Should have two mappings after fork, got {stats1['total_mappings']}"
    
    # Validate after first allocation
    assert manager.total_requested_allocations() == manager.total_allocated_bytes(), \
        f"Validation failed after fork allocation: requested={manager.total_requested_allocations()} != allocated={manager.total_allocated_bytes()}"
    
    # Now try allocation across all PEs (should span mappings)
    req2 = MemoryRequirement(
        size=256,
        pe_req=DimensionRequirement(DimensionScope.ALL),
        mss_req=DimensionRequirement(DimensionScope.SPECIFIC, value=0),
        slice_req=DimensionRequirement(DimensionScope.SPECIFIC, value=0),
        allocation_id="cross_mapping_alloc"
    )
    
    success2 = manager.allocate_requirement(req2)
    assert success2, "Cross-mapping allocation should succeed"
    
    # Final validation after cross-mapping allocation
    assert manager.total_requested_allocations() == manager.total_allocated_bytes(), \
        f"Validation failed after cross-mapping allocation: requested={manager.total_requested_allocations()} != allocated={manager.total_allocated_bytes()}"
    
    print("✓ Cross-mapping allocation test passed")


def test_allocation_failure():
    """Test allocation failure when insufficient memory"""
    print("Testing allocation failure...")
    
    manager = MappingCentricMemoryManager(pe_count=1, mss_per_pe=1, slices_per_mss=1)
    
    # Try to allocate more than slice size
    req = MemoryRequirement(
        size=2*1024*1024,  # 2MB > 1MB slice size
        pe_req=DimensionRequirement(DimensionScope.ALL),
        mss_req=DimensionRequirement(DimensionScope.ALL),
        slice_req=DimensionRequirement(DimensionScope.ALL),
        allocation_id="too_big_alloc"
    )
    
    success = manager.allocate_requirement(req)
    assert not success, "Allocation should fail when insufficient memory"
    
    # Validate even when allocation fails (should both be 0)
    assert manager.total_requested_allocations() == manager.total_allocated_bytes(), \
        f"Validation failed for failed allocation: requested={manager.total_requested_allocations()} != allocated={manager.total_allocated_bytes()}"
    
    print("✓ Allocation failure test passed")


def run_all_tests():
    """Run all unit tests"""
    print("Running memory manager unit tests...\n")
    
    try:
        test_basic_serial_allocation()
        test_pe_specific_forking()
        test_mss_specific_forking()
        test_slice_group_forking()
        test_automatic_resource_selection()
        test_complex_multiple_requirements()
        test_cross_mapping_allocation()
        test_allocation_failure()
        
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests() 