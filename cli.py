# -*- coding: utf-8 -*-
"""
Python Serial Terminal + STM32 Flasher - Main Entry Point
Modular architecture with separated concerns
"""

import sys
import argparse
import threading
import html
import shlex
import serial
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
    cmd_read_memory, cmd_go, flash_firmware
)

# Global configuration
append_newline = True


class CommandRegistry:
    """Registry for CLI commands."""
    def __init__(self):
        self.commands = {}
        self.completers = {}

    def register(self, name, description, completer=None, aliases=None):
        """Decorator to register a command."""
        def decorator(func):
            cmd_info = {
                'func': func,
                'desc': description,
                'usage': func.__doc__,
                'aliases': aliases or []
            }
            self.commands[name] = cmd_info
            self.completers[name] = completer
            
            if aliases:
                for alias in aliases:
                    self.commands[alias] = cmd_info
                    self.completers[alias] = completer
            return func
        return decorator

    def get_completer_dict(self):
        """Get the dictionary for NestedCompleter."""
        return self.completers

    def execute(self, cmd_name, parts, session):
        """Execute a command."""
        if cmd_name in self.commands:
            try:
                self.commands[cmd_name]['func'](parts, session)
            except Exception as e:
                print(HTML(f"<error>Error executing {cmd_name}: {e}</error>"))
        else:
            print(HTML(f"<error>Unknown command: {cmd_name}</error>"))
            print(HTML("<info>Type <success>/help</success> to see available commands.</info>"))

    def print_help(self):
        """Print available commands."""
        print(HTML("\n<header>Available Commands:</header>"))
        seen_funcs = set()
        for name, info in sorted(self.commands.items()):
            if info['func'] in seen_funcs:
                continue
            seen_funcs.add(info['func'])
            
            alias_str = ""
            if info['aliases']:
                alias_str = f" (or {', '.join(info['aliases'])})"
            
            print(HTML(f"  <key>{name:<15}</key> <info>{info['desc']}{alias_str}</info>"))
        print()


# Initialize registry
registry = CommandRegistry()


def print(*values, **kwargs):
    """Enhanced print function with style support."""
    if 'style' not in kwargs:
        kwargs['style'] = style
    pt_print(*values, **kwargs)


def parse_int(value):
    """Parse integer from string (supports hex with 0x prefix)."""
    try:
        return int(value, 0)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid integer: {value}")


def setup_parser():
    """Configure command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Python Serial Terminal + STM32 Flasher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                # Start interactive mode
  %(prog)s list                           # List serial ports
  %(prog)s flash firmware.hex -p COM3     # Flash firmware
  %(prog)s erase -p COM3                  # Erase chip
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Common arguments
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--port', '-p', required=True, help='Serial port (e.g. COM3)')
    common.add_argument('--baud', '-b', type=int, default=115200, help='Baud rate (default: 115200)')

    # Command: list
    subparsers.add_parser('list', help='List available serial ports')

    # Command: flash
    flash_parser = subparsers.add_parser('flash', parents=[common], help='Flash firmware')
    flash_parser.add_argument('file', help='Firmware file (.hex or .bin)')
    flash_parser.add_argument('--address', '-a', type=parse_int, help='Start address (default: 0x08000000)')
    flash_parser.add_argument('--no-erase', action='store_true', help='Skip chip erase')
    flash_parser.add_argument('--no-verify', action='store_true', help='Skip verification')
    flash_parser.add_argument('--run', '-r', action='store_true', help='Run application after flashing')

    # Command: erase
    subparsers.add_parser('erase', parents=[common], help='Erase entire chip')

    # Command: run
    run_parser = subparsers.add_parser('run', parents=[common], help='Jump to application address')
    run_parser.add_argument('--address', '-a', type=parse_int, default=0x08000000, help='Address to jump to')

    # Command: info
    subparsers.add_parser('info', parents=[common], help='Get chip information')

    return parser


def run_cli_command(args):
    """Execute CLI commands (non-interactive)."""
    # Handle list command (no serial connection needed)
    if args.command == 'list':
        serial_handler.manager.list_ports()
        return

    # For other commands, establish connection
    try:
        ser = serial.Serial(
            port=args.port,
            baudrate=args.baud,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1
        )
    except Exception as e:
        print(HTML(f"<error>Error opening serial port {args.port}: {e}</error>"))
        sys.exit(1)

    try:
        if args.command == 'flash':
            print(HTML(f"<info>Flashing {args.file}...</info>"))
            flash_firmware(
                ser, 
                args.file, 
                start_address=args.address, 
                verify=not args.no_verify, 
                erase=not args.no_erase, 
                go=args.run
            )
        
        elif args.command == 'erase':
            print(HTML(f"<info>Erasing chip on {args.port}...</info>"))
            cmd_erase(ser)
            
        elif args.command == 'run':
            print(HTML(f"<info>Jumping to 0x{args.address:08X}...</info>"))
            cmd_go(ser, args.address)
            
        elif args.command == 'info':
            cmd_chip_info(ser)
            
    except Exception as e:
        print(HTML(f"<error>Operation failed: {e}</error>"))
        sys.exit(1)
    finally:
        if ser.is_open:
            ser.close()


# --- Command Handlers ---

@registry.register('/exit', 'Exit the application', aliases=['/quit'])
def handle_exit(parts, session):
    serial_handler.manager.stop_reader()
    serial_handler.manager.disconnect()
    print(HTML("\n<success>Goodbye!</success>\n"))
    sys.exit(0)

@registry.register('/help', 'Show help message', aliases=['/h', '/?'])
def handle_help(parts, session):
    registry.print_help()

@registry.register('/list', 'List available serial ports', aliases=['/ls'])
def handle_list(parts, session):
    serial_handler.manager.list_ports()

@registry.register('/disconnect', 'Disconnect from serial port')
def handle_disconnect(parts, session):
    serial_handler.manager.disconnect()

@registry.register('/stats', 'Show connection statistics')
def handle_stats(parts, session):
    show_stats(serial_handler.manager.get_state())

@registry.register('/clear', 'Clear the screen', aliases=['/cls'])
def handle_clear(parts, session):
    clear_screen()

@registry.register('/newline', 'Toggle appending newline (CRLF)')
def handle_newline(parts, session):
    global append_newline
    append_newline = not append_newline
    status = "+ Enabled" if append_newline else "- Disabled"
    print(HTML(f"<info>Append newline (\\r\\n): {status}</info>"))

@registry.register('/timestamp', 'Toggle timestamp display')
def handle_timestamp(parts, session):
    serial_handler.manager.show_timestamp = not serial_handler.manager.show_timestamp
    status = "+ Enabled" if serial_handler.manager.show_timestamp else "- Disabled"
    print(HTML(f"<info>Timestamp display: {status}</info>"))

@registry.register('/hex', 'Toggle hex display mode')
def handle_hex(parts, session):
    serial_handler.manager.hex_mode = not serial_handler.manager.hex_mode
    status = "+ Enabled" if serial_handler.manager.hex_mode else "- Disabled"
    print(HTML(f"<info>Hex mode: {status}</info>"))

@registry.register('/connect', 'Connect to serial port', completer=None) # Completer is dynamic
def handle_connect(parts, session):
    port = parts[1] if len(parts) > 1 else session.prompt(HTML("<info>Port: </info>")).strip()
    if not port:
        print(HTML("<error>X Port is required.</error>"))
        return
        
    baud_str = parts[2] if len(parts) > 2 else session.prompt(HTML("<info>Baud rate: </info>")).strip()
    if not baud_str:
        print(HTML("<error>X Baud rate is required.</error>"))
        return

    try:
        baud = int(baud_str)
        serial_handler.manager.connect(port, baud)
    except ValueError:
        print(HTML("<error>X Baud rate must be an integer.</error>"))

@registry.register('/bootloader', 'Show bootloader wiring guide')
def handle_bootloader(parts, session):
    show_bootloader_guide()

@registry.register('/chipinfo', 'Read STM32 chip information')
def handle_chipinfo(parts, session):
    cmd_chip_info(serial_handler.manager.get_state())

@registry.register('/flash', 'Flash firmware to STM32', completer=PathCompleter())
def handle_flash(parts, session):
    filepath = parts[1] if len(parts) > 1 else session.prompt(HTML("<info>Firmware file: </info>")).strip()
    if not filepath:
        print(HTML("<error>X Firmware file is required.</error>"))
        return

    start_addr = None
    if len(parts) >= 3:
        try:
            start_addr = int(parts[2], 0)
        except ValueError:
            print(HTML("<error>X Invalid address format.</error>"))
            return
    elif len(parts) < 2:
        addr_str = session.prompt(HTML("<info>Start Address (optional): </info>")).strip()
        if addr_str:
            try:
                start_addr = int(addr_str, 0)
            except ValueError:
                print(HTML("<error>X Invalid address format.</error>"))
                return
    
    cmd_flash(serial_handler.manager.get_state(), filepath, start_addr)

@registry.register('/verify', 'Verify firmware on STM32', completer=PathCompleter())
def handle_verify(parts, session):
    filepath = parts[1] if len(parts) > 1 else session.prompt(HTML("<info>Firmware file: </info>")).strip()
    if not filepath:
        print(HTML("<error>X Firmware file is required.</error>"))
        return

    start_addr = None
    if len(parts) >= 3:
        try:
            start_addr = int(parts[2], 0)
        except ValueError:
            print(HTML("<error>X Invalid address format.</error>"))
            return
    elif len(parts) < 2:
        addr_str = session.prompt(HTML("<info>Start Address (optional): </info>")).strip()
        if addr_str:
            try:
                start_addr = int(addr_str, 0)
            except ValueError:
                print(HTML("<error>X Invalid address format.</error>"))
                return

    cmd_verify(serial_handler.manager.get_state(), filepath, start_addr)

@registry.register('/erase', 'Erase STM32 flash memory')
def handle_erase(parts, session):
    cmd_erase(serial_handler.manager.get_state())

@registry.register('/readmem', 'Read memory from STM32')
def handle_readmem(parts, session):
    address_str = parts[1] if len(parts) > 1 else session.prompt(HTML("<info>Address: </info>")).strip()
    if not address_str:
        print(HTML("<error>X Address is required.</error>"))
        return
    
    length_str = parts[2] if len(parts) > 2 else session.prompt(HTML("<info>Length: </info>")).strip()
    if not length_str:
        print(HTML("<error>X Length is required.</error>"))
        return

    try:
        address = int(address_str, 0)
        length = int(length_str, 0)
        if length > 0 and length <= 4096:
            cmd_read_memory(serial_handler.manager.get_state(), address, length)
        else:
            print(HTML("<error>X Length must be between 1 and 4096.</error>"))
    except ValueError:
        print(HTML("<error>X Invalid address or length format.</error>"))

@registry.register('/go', 'Jump to address and execute')
def handle_go(parts, session):
    address_str = parts[1] if len(parts) > 1 else session.prompt(HTML("<info>Address: </info>")).strip()
    if not address_str:
        print(HTML("<error>X Address is required.</error>"))
        return

    try:
        address = int(address_str, 0)
        cmd_go(serial_handler.manager.get_state(), address)
    except ValueError:
        print(HTML("<error>X Invalid address format.</error>"))


def interactive_main():
    """Interactive mode entry point."""
    global append_newline

    # Interactive Mode
    print_banner()
    
    # History for command recall
    history = InMemoryHistory()

    # Start background thread for reading
    serial_handler.manager.start_reader()

    session = PromptSession(style=style, history=history)

    # Static completer definitions
    baud_rates = ['9600', '115200', '230400', '460800', '921600']
    baud_completer = WordCompleter(baud_rates, ignore_case=True)
    
    # patch_stdout ensures that background prints don't mess up the input line
    with patch_stdout():
        while True:
            try:
                # Dynamic completer components
                ports = serial_handler.manager.get_available_ports()
                if not ports:
                    ports = ['No_Ports_Found']
                
                # Construct the nested dictionary
                # We use WordCompleter for the last level to ensure ignore_case works
                port_dict = {p: baud_completer for p in ports}
                
                # Merge dynamic ports into the command structure
                current_dict = registry.get_completer_dict().copy()
                current_dict['/connect'] = port_dict
                
                completer = NestedCompleter.from_nested_dict(current_dict)
                
                # Build prompt (cache serial state without lock for speed)
                current_ser = serial_handler.manager.get_state()
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
                if serial_handler.manager.show_timestamp:
                    mode_parts.append("TIME")
                if serial_handler.manager.hex_mode:
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
                    # Use shlex to handle quoted paths correctly (e.g. "C:\My Documents\file.bin")
                    # posix=False handles Windows backslashes better
                    try:
                        # Use shlex to handle quoted paths correctly (e.g. "C:\My Documents\file.bin")
                        # posix=False handles Windows backslashes better, but preserves quotes
                        parts_raw = shlex.split(text, posix=False)
                        parts = [p.strip('"\'') for p in parts_raw]
                    except ValueError:
                        print(HTML("<error>X Error parsing command. Check your quotes.</error>"))
                        continue
                        
                    cmd = parts[0].lower()
                    registry.execute(cmd, parts, session)
                    

                else:
                    # Send data to serial port
                    current_ser = serial_handler.manager.get_state()
                    
                    if current_ser and current_ser.is_open:
                        try:
                            # Prepare data once
                            msg = text + "\r\n" if append_newline else text
                            data_to_send = msg.encode('utf-8')
                            
                            # Send data
                            success, error = serial_handler.manager.send_data(data_to_send)
                            
                            if success:
                                # Display sent message (optimized)
                                ts = f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] " if serial_handler.manager.show_timestamp else ""
                                
                                if serial_handler.manager.hex_mode:
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
                serial_handler.manager.stop_reader()
                break
            except Exception as e:
                print(HTML(f"<error>X Error: {e}</error>"))


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        parser = setup_parser()
        args = parser.parse_args()
        run_cli_command(args)
    else:
        interactive_main()


if __name__ == "__main__":
    main()
