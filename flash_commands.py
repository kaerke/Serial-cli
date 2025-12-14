# -*- coding: utf-8 -*-
"""
STM32 flash command handlers
"""

import os
import time
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit import print_formatted_text as pt_print

from stm32_bootloader import STM32Bootloader, STM32_FLASH_START, STM32_WRITE_BLOCK_SIZE
from hex_parser import parse_hex_file, parse_bin_file, get_chip_name
from ui_helpers import format_bytes, print_progress_bar, clear_progress_bar, style
from serial_handler import reader_paused

def print(*values, **kwargs):
    if 'style' not in kwargs:
        kwargs['style'] = style
    pt_print(*values, **kwargs)


def flash_firmware(ser, filepath, start_address=None, verify=True, erase=True, go=True):
    """Flash firmware to STM32 with enhanced progress and error handling."""
    if not ser or not ser.is_open:
        raise Exception("Not connected to serial port")
    
    # Validate file exists
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Firmware file not found: {filepath}")
    
    # Parse firmware file
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == '.hex':
            segments = parse_hex_file(filepath)
        elif ext == '.bin':
            addr = start_address if start_address else STM32_FLASH_START
            segments = parse_bin_file(filepath, addr)
        else:
            raise ValueError(f"Unsupported file format: {ext} (use .hex or .bin)")
    except Exception as e:
        raise Exception(f"Failed to parse firmware file: {e}")
    
    if not segments:
        raise Exception("No data found in firmware file")
    
    # Calculate total size
    total_size = sum(len(data) for _, data in segments)
    
    if total_size == 0:
        raise Exception("Firmware file is empty")
    
    print(HTML(f"<info>! Firmware size: {format_bytes(total_size)} ({total_size:,} bytes)</info>"))
    print(HTML(f"<info>! Segments: {len(segments)}</info>"))
    
    # Create bootloader instance
    with STM32Bootloader(ser) as bootloader:
        # Sync with bootloader
        print(HTML("<info>! Syncing with bootloader...</info>"))
        try:
            if not bootloader.sync():
                raise Exception("Failed to sync with bootloader. Make sure the chip is in bootloader mode.")
            print(HTML("<success>+ Bootloader sync OK</success>"))
        except Exception as e:
            raise Exception(f"Sync failed: {e}. Check connections and bootloader mode.")
        
        # Get device info
        try:
            bootloader.get_commands()
            chip_id = bootloader.get_id()
            chip_name = get_chip_name(chip_id)
            version = bootloader.bootloader_version
            
            print(HTML(f"<info>! Chip: 0x{chip_id:04X} ({chip_name})</info>"))
            print(HTML(f"<info>! Bootloader: v{(version >> 4) & 0x0F}.{version & 0x0F}</info>"))
        except Exception as e:
            print(HTML(f"<error>! Warning: Could not read chip info: {e}</error>"))
        
        # Erase flash
        if erase:
            print(HTML("<info>! Erasing flash memory (may take 10-30 seconds)...</info>"))
            try:
                bootloader.erase_all()
                print(HTML("<success>+ Flash erased successfully</success>"))
            except Exception as e:
                raise Exception(f"Erase failed: {e}")
    
        # Write firmware
        print(HTML(f"<info>! Writing firmware...</info>"))
        bytes_written = 0
        write_errors = 0
        max_write_errors = 3
        start_time = time.time()
        
        try:
            for seg_idx, (address, data) in enumerate(segments):
                print(HTML(f"<info>  Segment {seg_idx + 1}/{len(segments)}: 0x{address:08X} ({len(data)} bytes)</info>"))
                offset = 0
                
                while offset < len(data):
                    chunk_size = min(STM32_WRITE_BLOCK_SIZE, len(data) - offset)
                    chunk = data[offset:offset + chunk_size]
                    
                    try:
                        bootloader.write_memory(address + offset, chunk)
                    except Exception as e:
                        write_errors += 1
                        if write_errors >= max_write_errors:
                            raise Exception(f"Too many write errors at 0x{address + offset:08X}: {e}")
                        time.sleep(0.1)
                        continue
                    
                    bytes_written += chunk_size
                    offset += chunk_size
                    
                    # Progress with helper function
                    print_progress_bar(bytes_written, total_size, start_time=start_time)
            
            clear_progress_bar()
            print(HTML("<success>+ Write complete</success>"))
        except Exception as e:
            print()
            raise Exception(f"Write operation failed: {e}")
        
        # Verify
        if verify:
            print(HTML("<info>! Verifying firmware...</info>"))
            bytes_verified = 0
            verify_errors = 0
            start_time = time.time()
            
            try:
                for address, data in segments:
                    offset = 0
                    while offset < len(data):
                        chunk_size = min(256, len(data) - offset)
                        expected = data[offset:offset + chunk_size]
                        
                        try:
                            actual = bootloader.read_memory(address + offset, chunk_size)
                        except Exception as e:
                            verify_errors += 1
                            if verify_errors >= 3:
                                raise Exception(f"Read failed at 0x{address + offset:08X}: {e}")
                            time.sleep(0.1)
                            continue
                        
                        if actual != expected:
                            raise Exception(f"Mismatch at 0x{address + offset:08X}")
                        
                        bytes_verified += chunk_size
                        offset += chunk_size
                        
                        # Progress
                        print_progress_bar(bytes_verified, total_size, start_time=start_time)
                
                clear_progress_bar()
                print(HTML("<success>+ Verification passed</success>"))
            except Exception as e:
                print()
                raise Exception(f"Verification failed: {e}")
    
        # Jump to application
        if go:
            jump_addr = segments[0][0]
            print(HTML(f"<info>! Starting application at 0x{jump_addr:08X}...</info>"))
            try:
                bootloader.go(jump_addr)
                print(HTML("<success>+ Application started</success>"))
            except Exception as e:
                print(HTML(f"<info>! Note: GO command failed ({e}). This is normal on some devices.</info>"))
    
    return True


def cmd_chip_info(ser):
    """Read and display chip information with improved error handling."""
    import serial_handler
    
    if not ser or not ser.is_open:
        print(HTML("<error>X Not connected. Use /connect first.</error>"))
        return
    
    serial_handler.reader_paused = True
    time.sleep(0.01)
    
    try:
        with STM32Bootloader(ser) as bootloader:
            print(HTML("<info>! Syncing with bootloader...</info>"))
            
            try:
                if not bootloader.sync():
                    print(HTML("<error>X Failed to sync. Make sure chip is in bootloader mode.</error>"))
                    print(HTML("<info>  Tip: Set BOOT0=HIGH, reset chip, then try again.</info>"))
                    return
            except TimeoutError:
                print(HTML("<error>X Sync timeout. Check:</error>"))
                print(HTML("<info>  1. BOOT0 pin is HIGH</info>"))
                print(HTML("<info>  2. TX/RX connections are correct</info>"))
                print(HTML("<info>  3. Baud rate matches bootloader (try 115200)</info>"))
                return
            except Exception as e:
                print(HTML(f"<error>X Sync error: {e}</error>"))
                return
            
            print(HTML("<success>+ Bootloader sync OK</success>"))
            
            # Get commands
            commands = bootloader.get_commands()
            version = bootloader.bootloader_version
            
            # Get chip ID
            chip_id = bootloader.get_id()
            chip_name = get_chip_name(chip_id)
            
            print(HTML("\n<header>+============================================================+</header>"))
            print(HTML("<header>|                    Chip Information                        |</header>"))
            print(HTML("<header>+============================================================+</header>"))
            line = f"<header>|</header> <success>Chip ID:</success>         0x{chip_id:04X}"
            print(HTML(line.ljust(69) + "<header>|</header>"))
            line = f"<header>|</header> <success>Chip Name:</success>       {chip_name}"
            print(HTML(line.ljust(69) + "<header>|</header>"))
            line = f"<header>|</header> <success>Bootloader:</success>      v{(version >> 4) & 0x0F}.{version & 0x0F}"
            print(HTML(line.ljust(69) + "<header>|</header>"))
            line = f"<header>|</header> <success>Ext. Erase:</success>      {'Yes' if bootloader.extended_erase else 'No'}"
            print(HTML(line.ljust(69) + "<header>|</header>"))
            
            # Show supported commands
            cmd_names = {
                0x00: "GET", 0x01: "GET_VER", 0x02: "GET_ID", 0x11: "READ",
                0x21: "GO", 0x31: "WRITE", 0x43: "ERASE", 0x44: "EXT_ERASE",
                0x63: "WP", 0x73: "WP_UN", 0x82: "RP", 0x92: "RP_UN"
            }
            supported = [cmd_names.get(c, f"0x{c:02X}") for c in commands if c in cmd_names]
            line = f"<header>|</header> <success>Commands:</success>        {', '.join(supported[:6])}"
            print(HTML(line.ljust(69) + "<header>|</header>"))
            if len(supported) > 6:
                line = f"<header>|</header>               {', '.join(supported[6:])}"
                print(HTML(line.ljust(69) + "<header>|</header>"))
            print(HTML("<header>+============================================================+</header>\n"))
        
    except Exception as e:
        print(HTML(f"<error>X Error: {e}</error>"))
    finally:
        serial_handler.reader_paused = False


def cmd_flash(ser, filepath, start_address=None):
    """Flash firmware command handler."""
    import serial_handler
    
    if not ser or not ser.is_open:
        print(HTML("<error>X Not connected. Use /connect first.</error>"))
        return
    
    if not os.path.exists(filepath):
        print(HTML(f"<error>X File not found: {filepath}</error>"))
        return
    
    serial_handler.reader_paused = True
    time.sleep(0.01)
    try:
        print(HTML(f"\n<header>+============================================================+</header>"))
        print(HTML(f"<header>|                   Flashing Firmware                        |</header>"))
        print(HTML(f"<header>+============================================================+</header>"))
        print(HTML(f"<info>! File: {filepath}</info>"))
        
        flash_firmware(ser, filepath, start_address, verify=True, erase=True, go=True)
        
        print(HTML("\n<success>+ Flashing completed successfully!</success>\n"))
        
    except Exception as e:
        print(HTML(f"\n<error>X Flashing failed: {e}</error>\n"))
    finally:
        serial_handler.reader_paused = False


def cmd_verify(ser, filepath, start_address=None):
    """Verify firmware command handler."""
    import serial_handler
    
    if not ser or not ser.is_open:
        print(HTML("<error>X Not connected. Use /connect first.</error>"))
        return
    
    if not os.path.exists(filepath):
        print(HTML(f"<error>X File not found: {filepath}</error>"))
        return
    
    serial_handler.reader_paused = True
    time.sleep(0.01)
    try:
        # Parse firmware file
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.hex':
            segments = parse_hex_file(filepath)
        elif ext == '.bin':
            addr = start_address if start_address else STM32_FLASH_START
            segments = parse_bin_file(filepath, addr)
        else:
            print(HTML(f"<error>X Unsupported file format: {ext}</error>"))
            return
        
        total_size = sum(len(data) for _, data in segments)
        
        with STM32Bootloader(ser) as bootloader:
            print(HTML("<info>! Syncing with bootloader...</info>"))
            if not bootloader.sync():
                print(HTML("<error>X Failed to sync. Make sure chip is in bootloader mode.</error>"))
                return
            
            bootloader.get_commands()
            
            print(HTML(f"<info>! Verifying {total_size:,} bytes...</info>"))
            bytes_verified = 0
            
            for address, data in segments:
                offset = 0
                while offset < len(data):
                    chunk_size = min(256, len(data) - offset)
                    expected = data[offset:offset + chunk_size]
                    
                    actual = bootloader.read_memory(address + offset, chunk_size)
                    
                    if actual != expected:
                        print(HTML(f"\n<error>X Verification failed at address 0x{address + offset:08X}</error>"))
                        return
                    
                    bytes_verified += chunk_size
                    offset += chunk_size
                    
                    progress = int((bytes_verified / total_size) * 100)
                    bar_len = 40
                    filled = int(bar_len * bytes_verified / total_size)
                    bar = '█' * filled + '░' * (bar_len - filled)
                    print(f"\r  [{bar}] {progress}% ({bytes_verified:,}/{total_size:,} bytes)", end='', flush=True)
            
            print()
            print(HTML("<success>+ Verification passed!</success>\n"))
        
    except Exception as e:
        print(HTML(f"\n<error>X Verification error: {e}</error>\n"))
    finally:
        serial_handler.reader_paused = False


def cmd_erase(ser):
    """Erase flash command handler."""
    import serial_handler
    
    if not ser or not ser.is_open:
        print(HTML("<error>X Not connected. Use /connect first.</error>"))
        return
    
    serial_handler.reader_paused = True
    time.sleep(0.01)
    try:
        with STM32Bootloader(ser) as bootloader:
            print(HTML("<info>! Syncing with bootloader...</info>"))
            if not bootloader.sync():
                print(HTML("<error>X Failed to sync. Make sure chip is in bootloader mode.</error>"))
                return
            
            bootloader.get_commands()
            
            print(HTML("<info>! Erasing flash memory (this may take a while)...</info>"))
            bootloader.erase_all()
            print(HTML("<success>+ Flash memory erased successfully!</success>\n"))
        
    except Exception as e:
        print(HTML(f"<error>X Erase failed: {e}</error>\n"))
    finally:
        serial_handler.reader_paused = False


def cmd_read_memory(ser, address, length):
    """Read memory command handler."""
    import serial_handler
    
    if not ser or not ser.is_open:
        print(HTML("<error>X Not connected. Use /connect first.</error>"))
        return
    
    serial_handler.reader_paused = True
    time.sleep(0.01)
    try:
        with STM32Bootloader(ser) as bootloader:
            print(HTML("<info>! Syncing with bootloader...</info>"))
            if not bootloader.sync():
                print(HTML("<error>X Failed to sync. Make sure chip is in bootloader mode.</error>"))
                return
            
            bootloader.get_commands()
            
            print(HTML(f"<info>! Reading {length} bytes from 0x{address:08X}...</info>"))
            
            data = b''
            offset = 0
            while offset < length:
                chunk_size = min(256, length - offset)
                chunk = bootloader.read_memory(address + offset, chunk_size)
                data += chunk
                offset += chunk_size
            
            # Display as hex dump
            print(HTML("\n<header>+------------------------------------------------------------+</header>"))
            print(HTML(f"<header>| Memory Dump: 0x{address:08X} - 0x{address + length - 1:08X}</header>"))
            print(HTML("<header>+------------------------------------------------------------+</header>"))
            
            for i in range(0, len(data), 16):
                hex_part = ' '.join(f'{b:02X}' for b in data[i:i+16])
                ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
                print(f"  {address + i:08X}  {hex_part.ljust(48)}  |{ascii_part}|")
            
            print()
        
    except Exception as e:
        print(HTML(f"<error>X Read memory failed: {e}</error>\n"))
    finally:
        serial_handler.reader_paused = False


def cmd_go(ser, address):
    """Jump to address command handler."""
    import serial_handler
    
    if not ser or not ser.is_open:
        print(HTML("<error>X Not connected. Use /connect first.</error>"))
        return
    
    serial_handler.reader_paused = True
    time.sleep(0.01)
    try:
        with STM32Bootloader(ser) as bootloader:
            print(HTML("<info>! Syncing with bootloader...</info>"))
            if not bootloader.sync():
                print(HTML("<error>X Failed to sync. Make sure chip is in bootloader mode.</error>"))
                return
            
            bootloader.get_commands()
            
            print(HTML(f"<info>! Jumping to address 0x{address:08X}...</info>"))
            bootloader.go(address)
            print(HTML("<success>+ Jump command sent. Device should now be running.</success>\n"))
        
    except Exception as e:
        print(HTML(f"<error>X Go command failed: {e}</error>\n"))
    finally:
        serial_handler.reader_paused = False
