# -*- coding: utf-8 -*-
"""
Firmware file parsing utilities (Intel HEX and Binary)
"""

import os
from stm32_bootloader import STM32_FLASH_START


def parse_hex_file(filepath):
    """Parse Intel HEX file and return list of (address, data) tuples with validation."""
    segments = []
    current_segment = None
    base_address = 0
    line_num = 0
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line_num += 1
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                if not line.startswith(':'):
                    raise Exception(f"Line {line_num}: Invalid record (must start with ':')")
                
                # Validate minimum length
                if len(line) < 11:
                    raise Exception(f"Line {line_num}: Record too short")
                
                # Parse the record
                try:
                    byte_count = int(line[1:3], 16)
                    address = int(line[3:7], 16)
                    record_type = int(line[7:9], 16)
                    data = bytes.fromhex(line[9:9+byte_count*2])
                except ValueError as e:
                    raise Exception(f"Line {line_num}: Parse error: {e}")
                
                if record_type == 0x00:  # Data record
                    actual_address = base_address + address
                    
                    if current_segment is None:
                        current_segment = [actual_address, bytearray()]
                    
                    # Check if contiguous with current segment
                    expected_addr = current_segment[0] + len(current_segment[1])
                    if actual_address == expected_addr:
                        current_segment[1].extend(data)
                    else:
                        # Start new segment
                        if current_segment and len(current_segment[1]) > 0:
                            segments.append((current_segment[0], bytes(current_segment[1])))
                        current_segment = [actual_address, bytearray(data)]
                
                elif record_type == 0x01:  # End of file
                    if current_segment and len(current_segment[1]) > 0:
                        segments.append((current_segment[0], bytes(current_segment[1])))
                    break
                
                elif record_type == 0x02:  # Extended segment address
                    base_address = int.from_bytes(data, 'big') << 4
                
                elif record_type == 0x04:  # Extended linear address
                    base_address = int.from_bytes(data, 'big') << 16
    
    except FileNotFoundError:
        raise FileNotFoundError(f"HEX file not found: {filepath}")
    except Exception as e:
        raise Exception(f"Error parsing HEX file: {e}")
    
    return segments


def parse_bin_file(filepath, start_address=STM32_FLASH_START):
    """Parse binary file and return list of (address, data) tuples."""
    with open(filepath, 'rb') as f:
        data = f.read()
    return [(start_address, data)]


def get_chip_name(chip_id):
    """Get chip name from chip ID."""
    chip_names = {
        0x410: "STM32F1 Medium-density",
        0x411: "STM32F2xx",
        0x412: "STM32F1 Low-density",
        0x413: "STM32F405/407/415/417",
        0x414: "STM32F1 High-density",
        0x415: "STM32L4x1/L4x5/L4x6",
        0x416: "STM32L1 Medium-density",
        0x417: "STM32L0 Cat.3",
        0x418: "STM32F1 Connectivity line",
        0x419: "STM32F42x/F43x",
        0x420: "STM32F1 Medium-density VL",
        0x421: "STM32F446",
        0x422: "STM32F302xB/C/303xB/C/358",
        0x423: "STM32F401xB/C",
        0x425: "STM32L0 Cat.2",
        0x427: "STM32L1 Medium-density Plus",
        0x428: "STM32F1 High-density VL",
        0x429: "STM32L1 Cat.2",
        0x430: "STM32F1 XL-density",
        0x431: "STM32F411",
        0x432: "STM32F37x",
        0x433: "STM32F401xD/E",
        0x434: "STM32F469/479",
        0x435: "STM32L4x2",
        0x436: "STM32L1 High-density",
        0x437: "STM32L1 Medium-density Plus",
        0x438: "STM32F334",
        0x439: "STM32F302x6/8/303x6/8/328",
        0x440: "STM32F05x",
        0x441: "STM32F412",
        0x442: "STM32F030x8",
        0x444: "STM32F03x",
        0x445: "STM32F04x",
        0x446: "STM32F303xD/E/398",
        0x447: "STM32L0 Cat.5",
        0x448: "STM32F07x",
        0x449: "STM32F74x/F75x",
        0x450: "STM32H7xx",
        0x451: "STM32F76x/F77x",
        0x452: "STM32F72x/F73x",
        0x457: "STM32L0 Cat.1",
        0x458: "STM32F410",
        0x460: "STM32G0x0",
        0x461: "STM32L496/4A6",
        0x462: "STM32L45x/L46x",
        0x463: "STM32F413/423",
        0x464: "STM32L4R/S",
        0x466: "STM32G0x1",
        0x467: "STM32G0Bx/G0Cx",
        0x468: "STM32G4x1",
        0x469: "STM32G4x3",
        0x470: "STM32L4P5/L4Q5",
        0x471: "STM32L4R5/L4R7/L4R9/L4S5/L4S7/L4S9",
        0x472: "STM32L5x2",
        0x479: "STM32G4x4",
        0x480: "STM32H7Ax/H7Bx",
        0x482: "STM32U575/U585",
        0x483: "STM32H72x/H73x",
        0x495: "STM32WBx5",
        0x496: "STM32WBx0",
        0x497: "STM32WLEx",
    }
    return chip_names.get(chip_id, f"Unknown (0x{chip_id:04X})")
