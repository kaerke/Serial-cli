# -*- coding: utf-8 -*-
"""
STM32 UART Bootloader Protocol Implementation
"""

import serial
import struct
import time
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit import print_formatted_text as pt_print
from ui_helpers import style

def print(*values, **kwargs):
    if 'style' not in kwargs:
        kwargs['style'] = style
    pt_print(*values, **kwargs)

# STM32 Bootloader Commands
STM32_CMD_GET = 0x00
STM32_CMD_GET_VERSION = 0x01
STM32_CMD_GET_ID = 0x02
STM32_CMD_READ_MEMORY = 0x11
STM32_CMD_GO = 0x21
STM32_CMD_WRITE_MEMORY = 0x31
STM32_CMD_ERASE = 0x43
STM32_CMD_EXTENDED_ERASE = 0x44
STM32_CMD_WRITE_PROTECT = 0x63
STM32_CMD_WRITE_UNPROTECT = 0x73
STM32_CMD_READOUT_PROTECT = 0x82
STM32_CMD_READOUT_UNPROTECT = 0x92

# Response codes
STM32_ACK = 0x79
STM32_NACK = 0x1F

# Default settings
STM32_FLASH_START = 0x08000000
STM32_TIMEOUT = 5.0
STM32_WRITE_BLOCK_SIZE = 256


class STM32Bootloader:
    """STM32 UART Bootloader class for flashing firmware."""
    
    def __init__(self, serial_port):
        self.ser = serial_port
        self.extended_erase = False
        self.chip_id = None
        self.bootloader_version = None
        self.commands = []
        
        # Configure for STM32 Bootloader (8E1)
        self.old_parity = self.ser.parity
        self.ser.parity = serial.PARITY_EVEN
    
    def close(self):
        """Restore serial port settings."""
        if self.ser and self.ser.is_open:
            self.ser.parity = self.old_parity

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _send_byte(self, byte):
        """Send a single byte."""
        self.ser.write(bytes([byte]))
    
    def _send_command(self, cmd):
        """Send command with its complement."""
        self.ser.write(bytes([cmd, cmd ^ 0xFF]))
    
    def _wait_ack(self, timeout=STM32_TIMEOUT):
        """Wait for ACK/NACK response with improved timeout handling."""
        start_time = time.time()
        self.ser.timeout = min(0.1, timeout)
        
        while (time.time() - start_time) < timeout:
            data = self.ser.read(1)
            if data:
                if data[0] == STM32_ACK:
                    return True
                elif data[0] == STM32_NACK:
                    return False
        
        raise TimeoutError(f"Timeout waiting for ACK after {timeout:.1f}s")
    
    def _read_byte(self, timeout=STM32_TIMEOUT):
        """Read a single byte with timeout and error handling."""
        start_time = time.time()
        self.ser.timeout = min(0.1, timeout)
        
        while (time.time() - start_time) < timeout:
            data = self.ser.read(1)
            if data:
                return data[0]
        
        raise TimeoutError(f"Timeout reading byte after {timeout:.1f}s")
    
    def sync(self):
        """Synchronize with the bootloader by sending 0x7F."""
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self._send_byte(0x7F)
        return self._wait_ack(timeout=2.0)
    
    def get_commands(self):
        """Get supported commands from bootloader."""
        self._send_command(STM32_CMD_GET)
        if not self._wait_ack():
            raise Exception("GET command not acknowledged")
        
        num_bytes = self._read_byte()
        self.bootloader_version = self._read_byte()
        
        self.commands = []
        for _ in range(num_bytes):
            self.commands.append(self._read_byte())
        
        if not self._wait_ack():
            raise Exception("GET command end not acknowledged")
        
        # Check for extended erase support
        self.extended_erase = STM32_CMD_EXTENDED_ERASE in self.commands
        return self.commands
    
    def get_version(self):
        """Get bootloader version."""
        self._send_command(STM32_CMD_GET_VERSION)
        if not self._wait_ack():
            raise Exception("GET VERSION command not acknowledged")
        
        version = self._read_byte()
        self._read_byte()  # Option byte 1
        self._read_byte()  # Option byte 2
        
        if not self._wait_ack():
            raise Exception("GET VERSION command end not acknowledged")
        
        return version
    
    def get_id(self):
        """Get chip ID."""
        self._send_command(STM32_CMD_GET_ID)
        if not self._wait_ack():
            raise Exception("GET ID command not acknowledged")
        
        num_bytes = self._read_byte() + 1
        chip_id_bytes = []
        for _ in range(num_bytes):
            chip_id_bytes.append(self._read_byte())
        
        if not self._wait_ack():
            raise Exception("GET ID command end not acknowledged")
        
        self.chip_id = (chip_id_bytes[0] << 8) | chip_id_bytes[1] if len(chip_id_bytes) >= 2 else chip_id_bytes[0]
        return self.chip_id
    
    def read_memory(self, address, length):
        """Read memory from the device with enhanced error handling."""
        if length <= 0 or length > 256:
            raise ValueError(f"Invalid read length: {length} (must be 1-256)")
        
        self._send_command(STM32_CMD_READ_MEMORY)
        if not self._wait_ack():
            raise Exception("READ MEMORY command not acknowledged")
        
        # Send address with checksum
        addr_bytes = struct.pack('>I', address)
        checksum = 0
        for b in addr_bytes:
            checksum ^= b
        self.ser.write(addr_bytes + bytes([checksum]))
        
        if not self._wait_ack():
            raise Exception(f"Address 0x{address:08X} not acknowledged")
        
        # Send number of bytes to read (N-1 format)
        num_bytes = length - 1
        self.ser.write(bytes([num_bytes, num_bytes ^ 0xFF]))
        
        if not self._wait_ack():
            raise Exception("Length not acknowledged")
        
        # Read data with timeout
        data = b''
        remaining = length
        read_timeout = 2.0
        start_time = time.time()
        
        while remaining > 0:
            if time.time() - start_time > read_timeout:
                raise TimeoutError(f"Timeout reading {remaining} bytes")
            
            chunk = self.ser.read(min(remaining, 256))
            if chunk:
                data += chunk
                remaining -= len(chunk)
            else:
                time.sleep(0.01)
        
        return data
    
    def write_memory(self, address, data):
        """Write data to memory with validation and error handling."""
        if not data:
            raise ValueError("Cannot write empty data")
        
        if len(data) > 256:
            raise ValueError(f"Data too large: {len(data)} bytes (max 256)")
        
        # Check address alignment
        if address % 4 != 0:
            print(HTML(f"<info>! Warning: Address 0x{address:08X} not 4-byte aligned</info>"))
        
        self._send_command(STM32_CMD_WRITE_MEMORY)
        if not self._wait_ack():
            raise Exception("WRITE MEMORY command not acknowledged")
        
        # Send address with checksum
        addr_bytes = struct.pack('>I', address)
        checksum = 0
        for b in addr_bytes:
            checksum ^= b
        self.ser.write(addr_bytes + bytes([checksum]))
        
        if not self._wait_ack():
            raise Exception(f"Address 0x{address:08X} not acknowledged")
        
        # Pad data to be multiple of 4
        data = bytearray(data)
        while len(data) % 4 != 0:
            data.append(0xFF)
        
        # Send data with checksum (N-1 format)
        num_bytes = len(data) - 1
        checksum = num_bytes
        for b in data:
            checksum ^= b
        
        self.ser.write(bytes([num_bytes]) + bytes(data) + bytes([checksum]))
        
        # Wait for write completion with longer timeout
        if not self._wait_ack(timeout=10.0):
            raise Exception(f"Write not acknowledged at 0x{address:08X}")
        
        return True
    
    def erase_all(self):
        """Erase all flash memory (global erase)."""
        if self.extended_erase:
            return self._extended_erase_all()
        else:
            return self._standard_erase_all()
    
    def _standard_erase_all(self):
        """Standard erase (for older bootloaders)."""
        self._send_command(STM32_CMD_ERASE)
        if not self._wait_ack():
            raise Exception("ERASE command not acknowledged")
        
        # Global erase
        self.ser.write(bytes([0xFF, 0x00]))
        
        if not self._wait_ack(timeout=60.0):
            raise Exception("Erase not acknowledged")
        
        return True
    
    def _extended_erase_all(self):
        """Extended erase (mass erase)."""
        self._send_command(STM32_CMD_EXTENDED_ERASE)
        if not self._wait_ack():
            raise Exception("EXTENDED ERASE command not acknowledged")
        
        # Mass erase (0xFFFF)
        self.ser.write(bytes([0xFF, 0xFF, 0x00]))
        
        if not self._wait_ack(timeout=120.0):
            raise Exception("Mass erase not acknowledged")
        
        return True
    
    def erase_pages(self, pages):
        """Erase specific pages."""
        if self.extended_erase:
            return self._extended_erase_pages(pages)
        else:
            return self._standard_erase_pages(pages)
    
    def _standard_erase_pages(self, pages):
        """Standard page erase."""
        self._send_command(STM32_CMD_ERASE)
        if not self._wait_ack():
            raise Exception("ERASE command not acknowledged")
        
        num_pages = len(pages) - 1  # N-1 format
        checksum = num_pages
        for p in pages:
            checksum ^= p
        
        data = bytes([num_pages]) + bytes(pages) + bytes([checksum])
        self.ser.write(data)
        
        if not self._wait_ack(timeout=60.0):
            raise Exception("Page erase not acknowledged")
        
        return True
    
    def _extended_erase_pages(self, pages):
        """Extended page erase."""
        self._send_command(STM32_CMD_EXTENDED_ERASE)
        if not self._wait_ack():
            raise Exception("EXTENDED ERASE command not acknowledged")
        
        num_pages = len(pages) - 1  # N-1 format
        data = struct.pack('>H', num_pages)
        
        for page in pages:
            data += struct.pack('>H', page)
        
        checksum = 0
        for b in data:
            checksum ^= b
        data += bytes([checksum])
        
        self.ser.write(data)
        
        if not self._wait_ack(timeout=60.0):
            raise Exception("Extended page erase not acknowledged")
        
        return True
    
    def go(self, address):
        """Jump to address and execute."""
        self._send_command(STM32_CMD_GO)
        if not self._wait_ack():
            raise Exception("GO command not acknowledged")
        
        # Send address with checksum
        addr_bytes = struct.pack('>I', address)
        checksum = 0
        for b in addr_bytes:
            checksum ^= b
        self.ser.write(addr_bytes + bytes([checksum]))
        
        if not self._wait_ack():
            raise Exception("GO address not acknowledged")
        
        return True
    
    def write_unprotect(self):
        """Remove write protection."""
        self._send_command(STM32_CMD_WRITE_UNPROTECT)
        if not self._wait_ack():
            raise Exception("WRITE UNPROTECT command not acknowledged")
        
        if not self._wait_ack(timeout=10.0):
            raise Exception("WRITE UNPROTECT not acknowledged")
        
        return True
    
    def readout_unprotect(self):
        """Remove readout protection (this will erase the chip!)."""
        self._send_command(STM32_CMD_READOUT_UNPROTECT)
        if not self._wait_ack():
            raise Exception("READOUT UNPROTECT command not acknowledged")
        
        if not self._wait_ack(timeout=30.0):
            raise Exception("READOUT UNPROTECT not acknowledged")
        
        return True
