# -*- coding: utf-8 -*-
"""
Python Serial Terminal + STM32 Flasher - Main Entry Point
Modular architecture with separated concerns
"""

import sys
import threading
import html
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import WordCompleter, NestedCompleter, PathCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit import print_formatted_text as pt_print

# Import modules
import serial_handler
from ui_helpers import (
    print_banner, print_help, show_stats, clear_screen, 
    show_bootloader_guide, style
)
from flash_commands import (
    cmd_chip_info, cmd_flash, cmd_verify, cmd_erase,
    cmd_read_memory, cmd_go
)

# Global configuration
append_newline = True


def print(*values, **kwargs):
    """Enhanced print function with style support."""
    if 'style' not in kwargs:
        kwargs['style'] = style
    pt_print(*values, **kwargs)


def main():
    """Main entry point for the CLI application."""
    global append_newline
    
    print_banner()
    
    # History for command recall
    history = InMemoryHistory()

    # Start background thread for reading
    reader_thread = threading.Thread(target=serial_handler.serial_reader, daemon=True)
    reader_thread.start()

    session = PromptSession(style=style, history=history)

    # patch_stdout ensures that background prints don't mess up the input line
    with patch_stdout():
        while True:
            try:
                # Build dynamic completer
                ports = serial_handler.get_available_ports()
                if not ports:
                    ports = ['No_Ports_Found']
                
                baud_rates = ['9600', '115200', '230400', '460800', '921600']
                baud_completer = WordCompleter(baud_rates, ignore_case=True)
                
                # Construct the nested dictionary
                # We use WordCompleter for the last level to ensure ignore_case works
                port_dict = {p: baud_completer for p in ports}
                
                nested_dict = {
                    '/list': None, 
                    '/connect': port_dict, 
                    '/disconnect': None, 
                    '/stats': None, 
                    '/clear': None,
                    '/newline': None, 
                    '/timestamp': None, 
                    '/hex': None, 
                    '/exit': None, 
                    '/help': None,
                    '/flash': PathCompleter(), 
                    '/verify': PathCompleter(), 
                    '/erase': None, 
                    '/chipinfo': None, 
                    '/readmem': None, 
                    '/go': None, 
                    '/bootloader': None
                }
                
                completer = NestedCompleter.from_nested_dict(nested_dict)
                
                # Build prompt (cache serial state without lock for speed)
                current_ser = serial_handler.get_serial_state()
                if current_ser and current_ser.is_open:
                    port_info = f"{current_ser.port}@{current_ser.baudrate//1000}k"
                    status_text = f" ✓ {port_info} "
                    status_class = "status.connected"
                else:
                    status_text = " ✗ DISCONNECTED "
                    status_class = "status.disconnected"
                
                # Build mode indicators (optimized)
                mode_parts = []
                if append_newline:
                    mode_parts.append("CRLF")
                else:
                    mode_parts.append("RAW")
                if serial_handler.show_timestamp:
                    mode_parts.append("TIME")
                if serial_handler.hex_mode:
                    mode_parts.append("HEX")
                
                mode_str = f"[{' '.join(mode_parts)}]"
                
                # Construct the prompt
                prompt_fragments = [
                    ('class:prompt', '⚡ '),
                    (f'class:{status_class}', status_text),
                    ('class:info', mode_str),
                    ('class:prompt', ' » '),
                ]
                
                text = session.prompt(prompt_fragments, completer=completer, complete_while_typing=True)
                text = text.strip()

                if not text:
                    continue

                if text.startswith('/'):
                    parts = text.split()
                    cmd = parts[0].lower()

                    if cmd == '/exit':
                        serial_handler.running = False
                        if serial_handler.ser:
                            serial_handler.ser.close()
                        print(HTML("\n<success>Goodbye!</success>\n"))
                        sys.exit(0)
                    elif cmd == '/help':
                        print_help()
                    elif cmd == '/list':
                        serial_handler.list_ports()
                    elif cmd == '/disconnect':
                        serial_handler.disconnect_serial()
                    elif cmd == '/stats':
                        show_stats(serial_handler.get_serial_state())
                    elif cmd == '/clear':
                        clear_screen()
                    elif cmd == '/newline':
                        append_newline = not append_newline
                        status = "+ Enabled" if append_newline else "- Disabled"
                        print(HTML(f"<info>Append newline (\\r\\n): {status}</info>"))
                    elif cmd == '/timestamp':
                        serial_handler.show_timestamp = not serial_handler.show_timestamp
                        status = "+ Enabled" if serial_handler.show_timestamp else "- Disabled"
                        print(HTML(f"<info>Timestamp display: {status}</info>"))
                    elif cmd == '/hex':
                        serial_handler.hex_mode = not serial_handler.hex_mode
                        status = "+ Enabled" if serial_handler.hex_mode else "- Disabled"
                        print(HTML(f"<info>Hex mode: {status}</info>"))
                    elif cmd == '/connect':
                        port = parts[1] if len(parts) > 1 else session.prompt(HTML("<info>Port: </info>")).strip()
                        if not port:
                            print(HTML("<error>X Port is required.</error>"))
                            continue
                            
                        baud_str = parts[2] if len(parts) > 2 else session.prompt(HTML("<info>Baud rate: </info>")).strip()
                        if not baud_str:
                            print(HTML("<error>X Baud rate is required.</error>"))
                            continue

                        try:
                            baud = int(baud_str)
                            serial_handler.connect_serial(port, baud)
                        except ValueError:
                            print(HTML("<error>X Baud rate must be an integer.</error>"))
                    
                    # STM32 Flashing Commands
                    elif cmd == '/bootloader':
                        show_bootloader_guide()
                    elif cmd == '/chipinfo':
                        cmd_chip_info(serial_handler.ser)
                    elif cmd == '/flash':
                        filepath = parts[1] if len(parts) > 1 else session.prompt(HTML("<info>Firmware file: </info>")).strip()
                        if not filepath:
                            print(HTML("<error>X Firmware file is required.</error>"))
                            continue

                        start_addr = None
                        if len(parts) >= 3:
                            try:
                                start_addr = int(parts[2], 0)
                            except ValueError:
                                print(HTML("<error>X Invalid address format.</error>"))
                                continue
                        elif len(parts) < 2:
                            addr_str = session.prompt(HTML("<info>Start Address (optional): </info>")).strip()
                            if addr_str:
                                try:
                                    start_addr = int(addr_str, 0)
                                except ValueError:
                                    print(HTML("<error>X Invalid address format.</error>"))
                                    continue
                        
                        cmd_flash(serial_handler.ser, filepath, start_addr)
                    elif cmd == '/verify':
                        filepath = parts[1] if len(parts) > 1 else session.prompt(HTML("<info>Firmware file: </info>")).strip()
                        if not filepath:
                            print(HTML("<error>X Firmware file is required.</error>"))
                            continue

                        start_addr = None
                        if len(parts) >= 3:
                            try:
                                start_addr = int(parts[2], 0)
                            except ValueError:
                                print(HTML("<error>X Invalid address format.</error>"))
                                continue
                        elif len(parts) < 2:
                            addr_str = session.prompt(HTML("<info>Start Address (optional): </info>")).strip()
                            if addr_str:
                                try:
                                    start_addr = int(addr_str, 0)
                                except ValueError:
                                    print(HTML("<error>X Invalid address format.</error>"))
                                    continue

                        cmd_verify(serial_handler.ser, filepath, start_addr)
                    elif cmd == '/erase':
                        cmd_erase(serial_handler.ser)
                    elif cmd == '/readmem':
                        address_str = parts[1] if len(parts) > 1 else session.prompt(HTML("<info>Address: </info>")).strip()
                        if not address_str:
                            print(HTML("<error>X Address is required.</error>"))
                            continue
                        
                        length_str = parts[2] if len(parts) > 2 else session.prompt(HTML("<info>Length: </info>")).strip()
                        if not length_str:
                            print(HTML("<error>X Length is required.</error>"))
                            continue

                        try:
                            address = int(address_str, 0)
                            length = int(length_str, 0)
                            if length > 0 and length <= 4096:
                                cmd_read_memory(serial_handler.ser, address, length)
                            else:
                                print(HTML("<error>X Length must be between 1 and 4096.</error>"))
                        except ValueError:
                            print(HTML("<error>X Invalid address or length format.</error>"))
                    elif cmd == '/go':
                        address_str = parts[1] if len(parts) > 1 else session.prompt(HTML("<info>Address: </info>")).strip()
                        if not address_str:
                            print(HTML("<error>X Address is required.</error>"))
                            continue

                        try:
                            address = int(address_str, 0)
                            cmd_go(serial_handler.ser, address)
                        except ValueError:
                            print(HTML("<error>X Invalid address format.</error>"))
                    else:
                        print(HTML(f"<error>X Unknown command: {cmd}</error>"))
                        print(HTML("<info>Type <success>/help</success> to see available commands.</info>"))
                else:
                    # Send data to serial port
                    current_ser = serial_handler.get_serial_state()
                    
                    if current_ser and current_ser.is_open:
                        try:
                            # Prepare data once
                            msg = text + "\r\n" if append_newline else text
                            data_to_send = msg.encode('utf-8')
                            
                            # Send data
                            success, error = serial_handler.send_data(data_to_send)
                            
                            if success:
                                # Display sent message (optimized)
                                ts = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] " if serial_handler.show_timestamp else ""
                                
                                if serial_handler.hex_mode:
                                    hex_str = ' '.join(f'{b:02X}' for b in data_to_send)
                                    msg_html = f"<timestamp>{ts}</timestamp><tx>TX:</tx> {hex_str}" if ts else f"<tx>TX:</tx> {hex_str}"
                                else:
                                    escaped = html.escape(text)
                                    msg_html = f"<timestamp>{ts}</timestamp><tx>TX:</tx> {escaped}" if ts else f"<tx>TX:</tx> {escaped}"
                                
                                print(HTML(msg_html))
                            else:
                                print(HTML(f"<error>X {error}</error>"))
                            
                        except UnicodeEncodeError:
                            print(HTML("<error>X Cannot encode text</error>"))
                        except Exception as e:
                            print(HTML(f"<error>X Send failed: {e}</error>"))
                    else:
                        print(HTML("<info>! Not connected. Use <success>/connect PORT BAUD</success> first.</info>"))

            except KeyboardInterrupt:
                # Allow Ctrl+C to clear line
                continue
            except EOFError:
                # Ctrl+D
                serial_handler.running = False
                break
            except Exception as e:
                print(HTML(f"<error>X Error: {e}</error>"))


if __name__ == "__main__":
    main()
