

def broadcast_config(
        broadcast_type: int,            # 0, 1, 2, 3, 4 only
        broadcast_group_number: int,   # 1-6 only
        pe_number: int,                # 8 bit number that includes {x,y} nibbles
        group_start_pe: int,           
        group_size: int,                # size of group (lg2)
        supergroup_size: int,          # size of supergroup (lg2)
        group_size_x: int = -1,        # size_x of peg. if not given will be group_size / 2
        supergroup_size_x: int = -1     # size_x of supergroup. if not given will be supergroup_size / 2
):
    reg_list = [(0x1000, 0x5000), (0x1004, 0x0000), (0x1008, 0x0000), (0x100C, 0x0000), (0x1010, 0x0000), (0x1014, 0x0000)]
  
    return reg_list


def barrier_config(
        pe_group: int,
        group_offset: int,
        pe_address: int,
        barrier0_type: int,
        barrier1_type: int,
        mask: int  = 0,
        debug_flah = False,
        break_on_error = False,
        error_mask = 0x0000000000000000,   
        break_to_global = False,
        break_to_ncore = False,
        noc_exclude = False,
        de_jitter = False,
        group_size_x = -1

):
    reg_list = [(0x1000, 0x5000), (0x1004, 0x0000), (0x1008, 0x0000), (0x100C, 0x0000), (0x1010, 0x0000), (0x1014, 0x0000)]

    return reg_list

def config_vcore(
        size_x: int,
        size_y: int,
        swap_mode: int
):
    reg_list = [(0x1000, 0x5000), (0x1004, 0x0000), (0x1008, 0x0000), (0x100C, 0x0000), (0x1010, 0x0000), (0x1014, 0x0000)]

    return reg_list

def start_axi2ahb(
        cluster_number: int
):
    reg_list = [(0x1000, 0x5000), (0x1004, 0x0000), (0x1008, 0x0000), (0x100C, 0x0000), (0x1010, 0x0000), (0x1014, 0x0000)]

    return reg_list

def switch_axi2ahb_netowrk(
        network_string: str, # assumes 2 char string. first char is the brcst network number, second is the dst_type (sbits).
        cluster_number: int
):
    reg_list = [(0x1000, 0x5000), (0x1004, 0x0000), (0x1008, 0x0000), (0x100C, 0x0000), (0x1010, 0x0000), (0x1014, 0x0000)]

    return reg_list

    