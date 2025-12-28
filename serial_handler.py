# -*- coding: utf-8 -*-
"""
Serial port handler and background reader thread
"""

import serial
import serial.tools.list_ports
import threading
import time
import re
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
READ_BUFFER_SIZE = 16384      # Increased buffer for high-speed data
PACKET_TIMEOUT = 0.05         # Increased latency (50ms) to prevent fragmented output
RECONNECT_DELAY = 0.5         # Faster reconnect
MAX_DISPLAY_BUFFER = 32768    # Larger display buffer

# Global state
manager = None

class SerialManager:
    """Manages serial port connection and background reading."""
    
    def __init__(self):
        self.ser = None
        self.rx_bytes = 0
        self.tx_bytes = 0
        self.reader_paused = False
        self.reader_lock = threading.Lock()
        self.connection_lock = threading.Lock()
        self.show_timestamp = False
        self.hex_mode = False
        self.running = True
        self.thread = None

    def start_reader(self):
        """Start the background reader thread."""
        if self.thread and self.thread.is_alive():
            return
        self.running = True
        self.thread = threading.Thread(target=self._serial_reader, daemon=True)
        self.thread.start()

    def stop_reader(self):
        """Stop the background reader thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

    def _serial_reader(self):
        """Background thread to read from serial port with enhanced error handling."""
        buffer = bytearray()
        last_rx_time = 0
        consecutive_errors = 0
        max_consecutive_errors = 5
        local_rx_count = 0

        while self.running:
            try:
                if self.reader_paused:
                    time.sleep(0.001)
                    continue

                # Cache serial reference without lock for reading
                current_ser = self.ser
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
                        with self.reader_lock:
                            self.rx_bytes += local_rx_count
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
                            ts_prefix = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] " if self.show_timestamp else ""
                            
                            try:
                                if self.hex_mode:
                                    # Optimized hex display: process only what we need to print
                                    hex_str = ' '.join(f'{b:02X}' for b in buffer)
                                    print(HTML(f"<rx>{ts_prefix}{hex_str}</rx>"))
                                    buffer = bytearray() # Clear buffer after printing in hex mode
                                else:
                                    # Text mode: try to decode
                                    try:
                                        # Simplify: Ignore non-ASCII characters (Chinese, etc.)
                                        text = buffer.decode('ascii', errors='ignore')
                                        
                                        # Sanitize control characters that break XML parsing
                                        # Keep \t (0x09), \n (0x0A), \r (0x0D)
                                        # Remove 0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F
                                        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
                                        
                                        # Handle newlines properly
                                        if '\n' in text:
                                            lines = text.split('\n')
                                            # Batch print all complete lines for performance
                                            if len(lines) > 1:
                                                # Construct a single HTML block for all complete lines
                                                html_parts = []
                                                for line in lines[:-1]:
                                                    clean_line = line.replace('\r', '')
                                                    html_parts.append(f"<rx>{ts_prefix}{html.escape(clean_line)}</rx>")
                                                
                                                if html_parts:
                                                    print(HTML('\n'.join(html_parts)))
                                            
                                            # Keep the last partial line in buffer
                                            last_part = lines[-1]
                                            buffer = bytearray(last_part.encode('utf-8'))
                                        elif is_timeout:
                                            # Timeout reached, print what we have
                                            if text:
                                                print(HTML(f"<rx>{ts_prefix}{html.escape(text)}</rx>"))
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
                        time.sleep(0.0005)
                        
                except (OSError, serial.SerialException):
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        # Batch update rx count before error handling
                        if local_rx_count > 0:
                            with self.reader_lock:
                                self.rx_bytes += local_rx_count
                            local_rx_count = 0
                        
                        if self.ser:
                            try:
                                self.ser.close()
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
            with self.reader_lock:
                self.rx_bytes += local_rx_count
        
        # Cleanup on exit
        if self.ser:
            try:
                self.ser.close()
            except:
                pass

    def list_ports(self):
        """List available serial ports."""
        ports = serial.tools.list_ports.comports()
        if not ports:
            print(HTML("<info>! No serial ports found.</info>"))
        else:
            print(HTML("\n<header>── Available Serial Ports ────────────────────────────────</header>"))
            for i, p in enumerate(ports, 1):
                print(HTML(f"  <success>{i}.</success> {p.device:<10} {p.description}"))
            print(HTML("<header>──────────────────────────────────────────────────────────</header>\n"))

    def get_available_ports(self):
        """Return a list of available port names."""
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port_name, baud_rate):
        """Connect to a serial port with improved error handling."""
        with self.connection_lock:
            if self.ser and self.ser.is_open:
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
                self.ser = new_ser
                with self.reader_lock:
                    self.rx_bytes = 0
                    self.tx_bytes = 0
                
                print(HTML(f"<success>+ Successfully connected to {port_name} at {baud_rate:,} baud.</success>"))
                return True
                
            except serial.SerialException as e:
                print(HTML(f"<error>X Serial error: {e}</error>"))
                self.ser = None
                return False
            except ValueError as e:
                print(HTML(f"<error>X Invalid parameter: {e}</error>"))
                self.ser = None
                return False
            except Exception as e:
                print(HTML(f"<error>X Failed to connect: {e}</error>"))
                self.ser = None
                return False

    def disconnect(self):
        """Disconnect from the current serial port with proper cleanup."""
        with self.connection_lock:
            if self.ser:
                try:
                    if self.ser.is_open:
                        # Clear buffers before closing
                        try:
                            self.ser.reset_input_buffer()
                            self.ser.reset_output_buffer()
                        except:
                            pass
                        
                        self.ser.close()
                        print(HTML("<success>+ Disconnected.</success>"))
                    else:
                        print(HTML("<info>! Port already closed.</info>"))
                except Exception as e:
                    print(HTML(f"<error>X Error during disconnect: {e}</error>"))
                finally:
                    self.ser = None
            else:
                print(HTML("<info>! Not connected.</info>"))

    def get_state(self):
        """Get current serial connection state (thread-safe read)."""
        return self.ser

    def get_stats(self):
        """Get current RX/TX statistics."""
        with self.reader_lock:
            return self.rx_bytes, self.tx_bytes

    def send_data(self, data):
        """Send data to serial port with error handling."""
        current_ser = self.ser
        if not current_ser or not current_ser.is_open:
            return False, "Not connected"
        
        try:
            current_ser.write(data)
            with self.reader_lock:
                self.tx_bytes += len(data)
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

# Initialize global manager
manager = SerialManager()

