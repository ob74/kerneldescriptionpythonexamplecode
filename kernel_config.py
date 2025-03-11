#!/usr/bin/env python3

import json
import pytest
from typing import Dict, List, Tuple, Any
from grid import Chip, Haps
from kernel import Kernel
from hw_components import KernelSizeComponent
from kernel_types import KernelSize, KernelLocation
from application import Application



kernel_g = Kernel("G_Kernel", KernelSize.SIZE_2X2)
kernel_s = Kernel("S_Kernel", KernelSize.ONE_VCORE)
kernel_4x4 = Kernel("G_large", KernelSize.SIZE_4X4)

def test_haps_g_single():
    app = Application("ExampleApp", Haps())
    
    g_locations = [KernelLocation(0, 0) ]

    if not app.add_kernel(kernel_g, g_locations):
        raise ValueError("Invalid kernel locations for kernel1")
        
    print(app.deploy())
    return True

def test_full_chip_g_single():
    app = Application("ExampleApp", Chip())
    
    g_locations = [KernelLocation(0, 0) ]

    if not app.add_kernel(kernel_g, g_locations):
        raise ValueError("Invalid kernel locations for kernel1")
        
    print(app.deploy())
    return True

def test_haps_gs():
    app = Application("ExampleApp", Haps())
    
    g_locations = [KernelLocation(0, 0) ]
    s_locations = [
        KernelLocation(2+x, y, vcore) for x in range(2) for y in range(2) for vcore in range (4)
    ]

    if not app.add_kernel(kernel_g, g_locations):
        raise ValueError("Invalid kernel locations for kernel_g")
    if not app.add_kernel(kernel_s, s_locations):
        raise ValueError("Invalid kernel locations for kernel_s")
        
    print(app.deploy())
    return True





def example_application():
    """Example showing how to create and deploy an application with different kernel types."""
    # Create platform (example 16x16 grid)
    
    # Create application
    app = Application("ExampleApp", Chip())
    
    # Create and add first kernel (4x4)
    kernel1 = Kernel("ExampleKernel1", KernelSize.SIZE_4X4)
    
    # Add kernel with example locations (aligned with 4x4 grid)
    locations1 = [
        KernelLocation(0, 0),
        KernelLocation(0, 4),
        KernelLocation(4, 0),
        KernelLocation(4, 4)
    ]
    if not app.add_kernel(kernel1, locations1):
        raise ValueError("Invalid kernel locations for kernel1")
        
    # Create and add a vcore kernel
    kernel2 = Kernel("ExampleKernel2", KernelSize.ONE_VCORE)
    
    # Add vcore kernel with example locations
    locations2 = [
        KernelLocation(8, 8, vcore=0),  # Using vcore 0
        KernelLocation(8, 8, vcore=1)   # Using vcore 1 in same PE
    ]
    if not app.add_kernel(kernel2, locations2):
        raise ValueError("Invalid kernel locations for kernel2")
    
    # Try to add another kernel that overlaps (should fail)
    locations3 = [
        KernelLocation(2, 2),  # This overlaps with kernel1
        KernelLocation(8, 8)   # This overlaps with kernel2's vcores
    ]
    if app.add_kernel(kernel1, locations3):
        raise ValueError("Kernel3 should not have been allocated")
    
    return app.deploy()


if __name__ == "__main__":
    result = example_application()
    print(json.dumps(result["h_files"], indent=4))
    print(json.dumps(result["apb_list"], indent=4))
    print(json.dumps(result["bird_sequence"], indent=4))

    test_haps_gs()
           