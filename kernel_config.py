#!/usr/bin/env python3

import json
import pytest
from typing import Dict, List, Tuple, Any
from grid import Chip, Haps
from kernel import Kernel
from hw_components import KernelSizeComponent
from kernel_types import KernelSize, KernelLocation, KernelSuperGroup
from application import Application
from kernel_binary_parser import KernelBinary

# Create sample binaries
# Simple binary patterns for demonstration
g_vcore_pm = KernelBinary.from_file('./kernels/kern-gs.vcore.elf.ePM')
g_vcore_vm = KernelBinary.from_file('./kernels/kern-gs.vcore.elf.eVM')
g_vcore_dm = KernelBinary.from_file('./kernels/kern-gs.vcore.elf.eDMw')
s_ncore_pm = KernelBinary.from_file('./kernels/ncore-grid.ncore.elf.ePM')
s_ncore_dm = KernelBinary.from_file('./kernels/ncore-grid.ncore.elf.ePM')


# Initialize kernels
kernel_g = Kernel("G_Kernel", KernelSize.SIZE_2X2)
kernel_s = Kernel("S_Kernel", KernelSize.ONE_VCORE)
kernel_4x4 = Kernel("G_large", KernelSize.SIZE_4X4)

# Load binaries into kernels
kernel_g.add_binary(g_vcore_pm)
kernel_g.add_binary(g_vcore_dm)
kernel_s.add_binary(s_ncore_dm)
kernel_s.add_binary(s_ncore_pm)
kernel_4x4.add_binary(g_vcore_pm)

def test_haps_g_single():
    app = Application("ExampleApp", Haps())
    
    # Create a 2x2 supergroup for the 2x2 kernel at (0,0)
    g_supergroup = KernelSuperGroup(x=0, y=0, size_x=2, size_y=2, kernel_size=KernelSize.SIZE_2X2)
    app.add_kernel(kernel_g, g_supergroup)
    
    sequences = app.generate_bird_sequence()
    for sequence in sequences:
        print(sequence)
        print()  # Add extra newline between sequences
       
    assert True

def test_full_chip_g_single():
    app = Application("ExampleApp", Chip())
    
    # Create a 16x16 supergroup for the 2x2 kernel at (0,0)
    g_supergroup = KernelSuperGroup(x=0, y=0, size_x=16, size_y=16, kernel_size=KernelSize.SIZE_2X2)
    app.add_kernel(kernel_g, g_supergroup)
        
    print(app.generate_bird_sequence())
    assert True

def test_haps_gs():
    app = Application("ExampleApp", Haps())
    
    # Create a 2x2 supergroup for the 2x2 kernel at (0,0)
    g_supergroup = KernelSuperGroup(x=0, y=0, size_x=2, size_y=2, kernel_size=KernelSize.SIZE_2X2)
    
    # Create a 2x2 supergroup for the vcore kernel at (2,0)
    s_supergroup = KernelSuperGroup(x=2, y=0, size_x=2, size_y=2, kernel_size=KernelSize.ONE_VCORE)

    app.add_kernel(kernel_g, g_supergroup)
    app.add_kernel(kernel_s, s_supergroup)
        
    print(app.generate_bird_sequence())
    assert True

def example_application():
    """Example showing how to create and deploy an application with different kernel types."""
    # Create platform (example 16x16 grid)
    
    # Create application
    app = Application("ExampleApp", Chip())
    
    # Create and add first kernel (4x4)
    kernel1 = Kernel("ExampleKernel1", KernelSize.SIZE_4X4)
    kernel1.add_binary(g_vcore_pm)
    
    # Create a 8x8 supergroup for the 4x4 kernel at (0,0)
    supergroup1 = KernelSuperGroup(x=0, y=0, size_x=8, size_y=8, kernel_size=KernelSize.SIZE_4X4)
    
    print(kernel1.generate_bird_sequence(supergroup1))
    
    app.add_kernel(kernel1, supergroup1)
        
    # Create and add a vcore kernel
    kernel2 = Kernel("ExampleKernel2", KernelSize.ONE_VCORE)
    kernel2.add_binary(s_ncore_pm)
    
    # Create a 1x1 supergroup for the vcore kernel at (8,8)
    supergroup2 = KernelSuperGroup(x=8, y=8, size_x=1, size_y=1, kernel_size=KernelSize.ONE_VCORE)
    app.add_kernel(kernel2, supergroup2)
    
    # Try to add another kernel that overlaps (should fail)
    supergroup3 = KernelSuperGroup(x=2, y=2, size_x=4, size_y=4, kernel_size=KernelSize.SIZE_4X4)
    try:
        # this should fail
        app.add_kernel(kernel1, supergroup3)
        assert False
    except AssertionError:
        assert True

    # Print each sequence individually
    sequences = app.generate_bird_sequence()
    for sequence in sequences:
        print(sequence)
        print()  # Add extra newline between sequences
        
    print(app.generate_basic_sequence())
    return 0


if __name__ == "__main__":
    result = example_application()

    test_haps_g_single()
    test_full_chip_g_single()
    test_haps_gs()
    
           