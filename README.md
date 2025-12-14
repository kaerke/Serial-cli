<img width="875" height="459" alt="屏幕截图 2025-12-14 214809" src="https://github.com/user-attachments/assets/27c33ccd-38c5-43a9-9bc5-21b1fcf8b645" />
# Python Serial Terminal + STM32 Flasher

A powerful, modular command-line interface (CLI) tool for serial communication and STM32 firmware flashing. Built with Python and `prompt_toolkit` for a modern, interactive user experience.

## Features

*   **Serial Terminal**:
    *   Interactive command-line interface with autocomplete.
    *   Real-time data monitoring (RX/TX).
    *   Hex and Text display modes.
    *   Timestamping support.
    *   Configurable newline settings (CRLF/RAW).
*   **STM32 Flasher**:
    *   Built-in support for STM32 UART Bootloader protocol.
    *   Flash firmware from `.hex` or `.bin` files.
    *   Verify flash content.
    *   Erase chip.
    *   Read memory dumps.
    *   Jump to address (Go command).
    *   Automatic chip identification.
*   **User Experience**:
    *   Context-aware command completion (ports, baud rates, files).
    *   Color-coded output for better readability.
    *   Progress bars for long operations.

## Installation

1.  **Prerequisites**:
    *   Python 3.6 or higher.

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Starting the Application

You can run the application using the provided scripts or directly via Python:

*   **Windows (Batch)**: Double-click `run.bat` or run `.\run.bat` in CMD.
*   **Windows (PowerShell)**: Run `.\run.ps1`.
*   **Python**:
    ```bash
    python cli.py
    ```

### Common Commands

*   **Connection**:
    *   `/list`: List available serial ports.
    *   `/connect <port> <baud>`: Connect to a serial port (e.g., `/connect COM3 115200`).
    *   `/disconnect`: Disconnect from the current port.

*   **Terminal Settings**:
    *   `/hex`: Toggle Hex display mode.
    *   `/timestamp`: Toggle timestamp display.
    *   `/newline`: Toggle appending `\r\n` to sent messages.
    *   `/clear`: Clear the screen.

*   **STM32 Flashing**:
    *   `/chipinfo`: Read and display STM32 chip information.
    *   `/flash <file> [address]`: Flash firmware (e.g., `/flash firmware.hex`).
    *   `/verify <file> [address]`: Verify flash content against a file.
    *   `/erase`: Erase the entire flash memory.
    *   `/readmem <address> <length>`: Read memory from the device.
    *   `/go <address>`: Jump to the specified address.

*   **General**:
    *   `/help`: Show help message.
    *   `/exit`: Exit the application.

## Project Structure

*   `cli.py`: Main entry point and command handling.
*   `serial_handler.py`: Serial port communication and background reading thread.
*   `stm32_bootloader.py`: Implementation of the STM32 UART bootloader protocol.
*   `flash_commands.py`: High-level logic for flashing, verifying, and erasing.
*   `hex_parser.py`: Utilities for parsing Intel HEX and binary files.
*   `ui_helpers.py`: UI styling, progress bars, and formatting functions.

## License

[MIT License](LICENSE)
