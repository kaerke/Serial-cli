# -*- coding: utf-8 -*-
"""
Serial port handler and background reader thread
"""

import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
import html
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit import print_formatted_text as pt_print
from ui_helpers import style

def print(*values, **kwargs):
    if 'style' not in kwargs:
        kwargs['style'] = style
    pt_print(*values, **kwargs)

# Performance constants
READ_BUFFER_SIZE = 4096
PACKET_TIMEOUT = 0.05
RECONNECT_DELAY = 1.0
MAX_DISPLAY_BUFFER = 8192

# Global state
ser = None
rx_bytes = 0
tx_bytes = 0
rx_needs_prefix = True
reader_paused = False
reader_lock = threading.Lock()
connection_lock = threading.Lock()

# Display settings (shared state)
show_timestamp = False
hex_mode = False
running = True


def serial_reader():
    """Background thread to read from serial port with enhanced error handling."""
    global ser, running, rx_bytes, rx_needs_prefix, reader_paused, show_timestamp, hex_mode
    
    buffer = bytearray()
    last_rx_time = 0
    consecutive_errors = 0
    max_consecutive_errors = 5
    local_rx_count = 0

    while running:
        try:
            if reader_paused:
                time.sleep(0.001)
                continue

            # Cache serial reference without lock for reading
            current_ser = ser
            if not current_ser or not current_ser.is_open:
                time.sleep(0.05)
                continue
            
            # Read available data with optimized buffer size
            try:
                if current_ser.in_waiting > 0:
                    bytes_to_read = min(current_ser.in_waiting, READ_BUFFER_SIZE)
                    data = current_ser.read(bytes_to_read)
                    
                    if data:
                        local_rx_count += len(data)
                        # Use bytearray extend for better performance than bytes concatenation
                        if isinstance(buffer, bytes):
                            buffer = bytearray(buffer)
                        buffer.extend(data)
                        
                        last_rx_time = time.time()
                        consecutive_errors = 0
                
                # Periodically sync rx_bytes (every ~1KB to reduce lock contention)
                if local_rx_count > 1024:
                    with reader_lock:
                        rx_bytes += local_rx_count
                    local_rx_count = 0
                
                # Prevent buffer overflow - optimized slicing
                if len(buffer) > MAX_DISPLAY_BUFFER:
                    # Keep the last chunk, convert back to bytearray to ensure mutable
                    buffer = buffer[-MAX_DISPLAY_BUFFER//2:]
                
                # Process buffer if not empty
                if buffer:
                    current_time = time.time()
                    is_timeout = (current_time - last_rx_time > PACKET_TIMEOUT)
                    has_newline = b'\n' in buffer
                    
                    # Print if we have a newline OR if timeout has passed
                    if has_newline or is_timeout:
                        # Prepare timestamp once
                        ts_prefix = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] " if show_timestamp else ""
                        
                        try:
                            if hex_mode:
                                # Optimized hex display: process only what we need to print
                                # For very large buffers, this is still heavy, but better than before
                                hex_str = ' '.join(f'{b:02X}' for b in buffer)
                                print(HTML(f"<rx>{ts_prefix}{hex_str}</rx>"))
                                buffer = bytearray() # Clear buffer after printing in hex mode
                            else:
                                # Text mode: try to decode
                                try:
                                    text = buffer.decode('utf-8', errors='replace')
                                    
                                    # Handle newlines properly
                                    if '\n' in text:
                                        lines = text.split('\n')
                                        # Print all complete lines
                                        for line in lines[:-1]:
                                            # Handle CR
                                            line = line.replace('\r', '')
                                            print(HTML(f"<rx>{ts_prefix}{html.escape(line)}</rx>"))
                                        
                                        # Keep the last partial line in buffer
                                        last_part = lines[-1]
                                        buffer = bytearray(last_part.encode('utf-8'))
                                    elif is_timeout:
                                        # Timeout reached, print what we have
                                        print(HTML(f"<rx>{ts_prefix}{html.escape(text)}</rx>"), end='')
                                        buffer = bytearray()
                                        
                                except UnicodeDecodeError:
                                    # Fallback for binary data mixed with text
                                    print(HTML(f"<rx>{ts_prefix}[Binary Data: {len(buffer)} bytes]</rx>"))
                                    buffer = bytearray()
                                    
                        except Exception as e:
                            print(HTML(f"<error>Display Error: {e}</error>"))
                            buffer = bytearray()
                else:
                    # Yield CPU when idle
                    time.sleep(0.002)
                    
            except (OSError, serial.SerialException):
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    # Batch update rx count before error handling
                    if local_rx_count > 0:
                        with reader_lock:
                            rx_bytes += local_rx_count
                        local_rx_count = 0
                    
                    if ser:
                        try:
                            ser.close()
                        except:
                            pass
                    
                    consecutive_errors = 0
                    time.sleep(RECONNECT_DELAY)
                else:
                    time.sleep(0.01)
                    
        except Exception:
            time.sleep(0.05)
    
    # Update final rx count and cleanup
    if local_rx_count > 0:
        with reader_lock:
            rx_bytes += local_rx_count
    
    # Cleanup on exit
    if ser:
        try:
            ser.close()
        except:
            pass


def list_ports():
    """List available serial ports."""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print(HTML("<info>! No serial ports found.</info>"))
    else:
        print(HTML("\n<header>── Available Serial Ports ────────────────────────────────</header>"))
        for i, p in enumerate(ports, 1):
            print(HTML(f"  <success>{i}.</success> {p.device:<10} {p.description}"))
        print(HTML("<header>──────────────────────────────────────────────────────────</header>\n"))


def get_available_ports():
    """Return a list of available port names."""
    return [p.device for p in serial.tools.list_ports.comports()]



def connect_serial(port_name, baud_rate):
    """Connect to a serial port with improved error handling."""
    global ser, rx_bytes, tx_bytes
    
    with connection_lock:
        if ser and ser.is_open:
            print(HTML("<info>! Already connected. Disconnect first.</info>"))
            return False

        try:
            # Validate parameters
            if not port_name:
                print(HTML("<error>X Port name cannot be empty.</error>"))
                return False
            
            if baud_rate <= 0:
                print(HTML("<error>X Invalid baud rate.</error>"))
                return False
            
            # Attempt connection with timeout
            new_ser = serial.Serial(
                port=port_name,
                baudrate=baud_rate,
                timeout=0.1,
                write_timeout=1.0,
                inter_byte_timeout=None
            )
            
            # Test the connection
            if not new_ser.is_open:
                new_ser.open()
            
            # Clear buffers
            new_ser.reset_input_buffer()
            new_ser.reset_output_buffer()
            
            # Update global state
            ser = new_ser
            with reader_lock:
                rx_bytes = 0
                tx_bytes = 0
            
            print(HTML(f"<success>+ Successfully connected to {port_name} at {baud_rate:,} baud.</success>"))
            return True
            
        except serial.SerialException as e:
            print(HTML(f"<error>X Serial error: {e}</error>"))
            ser = None
            return False
        except ValueError as e:
            print(HTML(f"<error>X Invalid parameter: {e}</error>"))
            ser = None
            return False
        except Exception as e:
            print(HTML(f"<error>X Failed to connect: {e}</error>"))
            ser = None
            return False


def disconnect_serial():
    """Disconnect from the current serial port with proper cleanup."""
    global ser
    
    with connection_lock:
        if ser:
            try:
                if ser.is_open:
                    # Clear buffers before closing
                    try:
                        ser.reset_input_buffer()
                        ser.reset_output_buffer()
                    except:
                        pass
                    
                    ser.close()
                    print(HTML("<success>+ Disconnected.</success>"))
                else:
                    print(HTML("<info>! Port already closed.</info>"))
            except Exception as e:
                print(HTML(f"<error>X Error during disconnect: {e}</error>"))
            finally:
                ser = None
        else:
            print(HTML("<info>! Not connected.</info>"))


def get_serial_state():
    """Get current serial connection state (thread-safe read)."""
    return ser


def get_stats():
    """Get current RX/TX statistics."""
    with reader_lock:
        return rx_bytes, tx_bytes


def send_data(data):
    """Send data to serial port with error handling."""
    global tx_bytes
    
    current_ser = ser
    if not current_ser or not current_ser.is_open:
        return False, "Not connected"
    
    try:
        current_ser.write(data)
        with reader_lock:
            tx_bytes += len(data)
        return True, None
    except serial.SerialTimeoutException:
        return False, "Timeout"
    except serial.SerialException as e:
        try:
            current_ser.close()
        except:
            pass
        return False, str(e)
    except Exception as e:
        return False, str(e)
