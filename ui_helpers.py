# -*- coding: utf-8 -*-
"""
UI helper functions for display and formatting
"""

import os
import time
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from prompt_toolkit import print_formatted_text as pt_print

# Define styles for the TUI
style = Style.from_dict({
    # Light/Pastel Color Scheme
    'rx': '#98fb98 bold',       # Pale Green (Received data)
    'tx': '#87cefa bold',       # Light Sky Blue (Transmitted data)
    'error': '#ff6b6b bold',    # Pastel Red (Errors)
    'info': '#f0e68c',          # Khaki (Information)
    'success': '#7fffd4 bold',  # Aquamarine (Success messages)
    'prompt': '#00bfff bold',   # Deep Sky Blue (Input prompt)
    
    # Status indicators
    'status.connected': 'bg:#3cb371 #ffffff bold',     # Medium Sea Green
    'status.disconnected': 'bg:#ff6347 #ffffff bold',  # Tomato
    
    # UI Elements
    'border': '#b0c4de',        # Light Steel Blue
    'header': '#dda0dd bold',   # Plum
    'timestamp': '#d3d3d3 italic', # Light Gray
    'stats': '#ffdab9',         # Peach Puff
    'highlight': '#e0ffff bold', # Light Cyan
    'key': '#ffb6c1 bold',      # Light Pink
})

def print(*values, **kwargs):
    if 'style' not in kwargs:
        # Use the locally defined style
        kwargs['style'] = style
    pt_print(*values, **kwargs)


def format_bytes(num_bytes):
    """Format bytes with appropriate units (optimized)."""
    if num_bytes < 1024:
        return f"{num_bytes:.0f} B"
    elif num_bytes < 1048576:  # 1024*1024
        return f"{num_bytes/1024:.2f} KB"
    elif num_bytes < 1073741824:  # 1024*1024*1024
        return f"{num_bytes/1048576:.2f} MB"
    else:
        return f"{num_bytes/1073741824:.2f} GB"


def print_progress_bar(current, total, prefix='', width=30, start_time=None):
    """Print a consistent progress bar with speed and ETA (Pip-style)."""
    if total <= 0:
        return
    
    progress = int((current / total) * 100)
    filled = int(width * current / total)
    
    # Fine bar style (Pip-like)
    # Filled: ━ (using 'rx' style for pale green)
    # Empty: ╺ (using 'timestamp' style for gray)
    bar_filled = '━' * filled
    bar_empty = '╺' * (width - filled)
    
    stats = ""
    if start_time:
        elapsed = time.time() - start_time
        if elapsed > 0.1: # Only show stats after a brief period to stabilize
            speed = current / elapsed
            if speed > 1024*1024:
                speed_str = f"{speed/(1024*1024):.1f} MB/s"
            elif speed > 1024:
                speed_str = f"{speed/1024:.1f} KB/s"
            else:
                speed_str = f"{speed:.0f} B/s"
            
            # ETA
            remaining = total - current
            eta = remaining / speed if speed > 0 else 0
            stats = f" <border>|</border> <highlight>{speed_str}</highlight> <border>|</border> <info>ETA: {eta:.1f}s</info>"

    # Format with consistent spacing
    # Using \r to overwrite the line
    print(HTML(f"\r  {prefix}<rx>{bar_filled}</rx><timestamp>{bar_empty}</timestamp> <success>{progress:3d}%</success> <timestamp>({format_bytes(current)}/{format_bytes(total)})</timestamp>{stats}   "), end='', flush=True)


def clear_progress_bar():
    """Clear the progress bar line."""
    # Overwrite with spaces and return carriage
    print(f"\r{' ' * 120}\r", end='', flush=True)


def print_banner():
    """Print the application banner with improved styling."""
    print(HTML("\n<border>╔════════════════════════════════════════════════════════════╗</border>"))
    print(HTML("<border>║</border>   <highlight>Python Serial Terminal</highlight> <info>+</info> <header>STM32 Flasher</header> <key>v1.1</key>              <border>║</border>"))
    print(HTML("<border>║</border>   <success>Modular Architecture</success> <border>|</border> <highlight>Performance</highlight> <border>|</border> <header>Stability</header>           <border>║</border>"))
    print(HTML("<border>╚════════════════════════════════════════════════════════════╝</border>"))
    print(HTML("<info>Type</info> <key>/help</key> <info>for commands</info> <border>|</border> <key>/list</key> <info>to scan ports</info>\n"))


def print_help():
    """Print available commands with improved formatting."""
    print(HTML("\n<border>╭─ Command Help ────────────────────────────────────────────────╮</border>"))
    print(HTML("<border>│</border> <header>Serial Communication:</header>                                         <border>│</border>"))
    print(HTML("<border>│</border>   <key>/list</key>                List available serial ports            <border>│</border>"))
    print(HTML("<border>│</border>   <key>/connect</key> <info>PORT BAUD</info>  Connect (ex: /connect COM3 115200)      <border>│</border>"))
    print(HTML("<border>│</border>   <key>/disconnect</key>         Disconnect from current port            <border>│</border>"))
    print(HTML("<border>│</border>   <key>/stats</key>              Display connection statistics           <border>│</border>"))
    print(HTML("<border>│</border>   <key>/clear</key>              Clear the screen                        <border>│</border>"))
    print(HTML("<border>│</border>   <key>/newline</key>            Toggle appending \\r\\n (CRLF)            <border>│</border>"))
    print(HTML("<border>│</border>   <key>/timestamp</key>          Toggle timestamp display                <border>│</border>"))
    print(HTML("<border>│</border>   <key>/hex</key>                Toggle hex mode display                 <border>│</border>"))
    print(HTML("<border>├───────────────────────────────────────────────────────────────┤</border>"))
    print(HTML("<border>│</border> <header>STM32 Flashing:</header>                                               <border>│</border>"))
    print(HTML("<border>│</border>   <key>/bootloader</key>         Show bootloader mode guide              <border>│</border>"))
    print(HTML("<border>│</border>   <key>/chipinfo</key>           Read chip ID and bootloader version     <border>│</border>"))
    print(HTML("<border>│</border>   <key>/flash</key> <info>FILE [ADDR]</info>  Flash firmware (.hex or .bin)           <border>│</border>"))
    print(HTML("<border>│</border>   <key>/verify</key> <info>FILE [ADDR]</info> Verify firmware against chip            <border>│</border>"))
    print(HTML("<border>│</border>   <key>/erase</key>              Erase all flash memory                  <border>│</border>"))
    print(HTML("<border>│</border>   <key>/readmem</key> <info>ADDR LEN</info>   Read memory (ex:/readmem 0x8000000 256) <border>│</border>"))
    print(HTML("<border>│</border>   <key>/go</key> <info>ADDR</info>            Jump to address and execute             <border>│</border>"))
    print(HTML("<border>├───────────────────────────────────────────────────────────────┤</border>"))
    print(HTML("<border>│</border> <header>Tips:</header>                                                         <border>│</border>"))
    print(HTML("<border>│</border>   • Direct text input sends data to serial port               <border>│</border>"))
    print(HTML("<border>│</border>   • Use <highlight>Ctrl+C</highlight> to cancel current input line                   <border>│</border>"))
    print(HTML("<border>│</border>   • Common baud rates: 9600, 115200, 921600                   <border>│</border>"))
    print(HTML("<border>│</border>   <key>/exit</key> to quit                                               <border>│</border>"))
    print(HTML("<border>╰───────────────────────────────────────────────────────────────╯</border>\n"))


def show_stats(serial_state):
    """Display connection statistics with enhanced formatting."""
    import serial_handler
    import cli
    
    print(HTML("\n<border>╭─ Connection Statistics ──────────────────────────────────╮</border>"))
    
    if serial_state and serial_state.is_open:
        rx, tx = serial_handler.manager.get_stats()
        
        # Format with units
        rx_str = format_bytes(rx)
        tx_str = format_bytes(tx)
        total_str = format_bytes(rx + tx)
        
        print(HTML(f"<border>│</border> <info>Status:</info>      <success>Connected</success> to <highlight>{serial_state.port}</highlight> @ <highlight>{serial_state.baudrate:,}</highlight> baud   <border>│</border>"))
        print(HTML(f"<border>│</border> <stats>RX:</stats>         {rx:,} bytes ({rx_str})               <border>│</border>"))
        print(HTML(f"<border>│</border> <stats>TX:</stats>         {tx:,} bytes ({tx_str})               <border>│</border>"))
        print(HTML(f"<border>│</border> <stats>Total:</stats>      {rx + tx:,} bytes ({total_str})          <border>│</border>"))
    else:
        print(HTML(f"<border>│</border> <info>Status:</info>      <error>Not connected</error>                         <border>│</border>"))
    
    print(HTML(f"<border>│</border> <info>Timestamp:</info>    {'<success>✓ Enabled</success>' if serial_handler.manager.show_timestamp else '<error>✗ Disabled</error>'}                        <border>│</border>"))
    print(HTML(f"<border>│</border> <info>Hex Mode:</info>     {'<success>✓ Enabled</success>' if serial_handler.manager.hex_mode else '<error>✗ Disabled</error>'}                        <border>│</border>"))
    print(HTML(f"<border>│</border> <info>Newline:</info>      {'<success>✓ CRLF (\\r\\n)</success>' if cli.append_newline else '<error>✗ RAW</error>'}                   <border>│</border>"))
    print(HTML("<border>╰──────────────────────────────────────────────────────────╯</border>\n"))


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print_banner()


def show_bootloader_guide():
    """Show guide for entering bootloader mode."""
    print(HTML("\n<border>+==========================================================+</border>"))
    print(HTML("<border>|</border>             <header>STM32 Bootloader Mode Guide</header>                  <border>|</border>"))
    print(HTML("<border>+==========================================================+</border>"))
    print(HTML("<border>|</border>                                                          <border>|</border>"))
    print(HTML("<border>|</border> <info>To enter bootloader mode on STM32:</info>                       <border>|</border>"))
    print(HTML("<border>|</border>                                                          <border>|</border>"))
    print(HTML("<border>|</border> <success>Method 1: BOOT0 Pin</success>                                      <border>|</border>"))
    print(HTML("<border>|</border>   1. Set <highlight>BOOT0</highlight> pin to <highlight>HIGH</highlight> (3.3V)                        <border>|</border>"))
    print(HTML("<border>|</border>   2. Set <highlight>BOOT1</highlight> pin to <highlight>LOW</highlight> (GND) if available             <border>|</border>"))
    print(HTML("<border>|</border>   3. Reset the chip (press RESET or power cycle)         <border>|</border>"))
    print(HTML("<border>|</border>                                                          <border>|</border>"))
    print(HTML("<border>|</border> <success>Method 2: Option Bytes (some devices)</success>                    <border>|</border>"))
    print(HTML("<border>|</border>   Configure nBOOT_SEL and other boot options             <border>|</border>"))
    print(HTML("<border>|</border>                                                          <border>|</border>"))
    print(HTML("<border>|</border> <info>Hardware Connections:</info>                                    <border>|</border>"))
    print(HTML("<border>|</border>   - STM32 TX (PA9/PA2) -> USB-TTL RX                     <border>|</border>"))
    print(HTML("<border>|</border>   - STM32 RX (PA10/PA3) -> USB-TTL TX                    <border>|</border>"))
    print(HTML("<border>|</border>   - GND -> GND                                           <border>|</border>"))
    print(HTML("<border>|</border>   - Use <highlight>EVEN</highlight> parity for some STM32 families              <border>|</border>"))
    print(HTML("<border>|</border>                                                          <border>|</border>"))
    print(HTML("<border>|</border> <info>Typical Baud Rates:</info>                                      <border>|</border>"))
    print(HTML("<border>|</border>   115200, 57600, 38400, 19200, 9600                      <border>|</border>"))
    print(HTML("<border>|</border>                                                          <border>|</border>"))
    print(HTML("<border>|</border> <info>Usage Example:</info>                                           <border>|</border>"))
    print(HTML("<border>|</border>   <key>/connect</key> COM3 115200                                   <border>|</border>"))
    print(HTML("<border>|</border>   <key>/chipinfo</key>                                              <border>|</border>"))
    print(HTML("<border>|</border>   <key>/flash</key> firmware.hex                                    <border>|</border>"))
    print(HTML("<border>|</border>                                                          <border>|</border>"))
    print(HTML("<border>+==========================================================+</border>\n"))
