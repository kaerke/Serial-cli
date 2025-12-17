# Python Serial Terminal + STM32 Flasher (v1.1)
<img width="875" height="459" alt="фад╩╫ьм╪ 2025-12-14 214809" src="https://github.com/user-attachments/assets/27c33ccd-38c5-43a9-9bc5-21b1fcf8b645" />
A powerful, modular command-line interface (CLI) tool for serial communication and STM32 firmware flashing. Built with Python and `prompt_toolkit` for a modern, interactive user experience.

## Features

*   **Dual Modes**:
    *   **Interactive Mode**: Rich TUI with autocomplete, history, and real-time monitoring.
    *   **CLI Mode**: Scriptable command-line arguments for automation (CI/CD friendly).
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

### 1. Interactive Mode

Run without arguments to enter the interactive shell:

```bash
python cli.py
```

**Interactive Commands:**

*   **Connection**:
    *   `/list` (or `/ls`): List available serial ports.
    *   `/connect <port> <baud>`: Connect to a serial port (e.g., `/connect COM3 115200`).
    *   `/disconnect`: Disconnect from the current port.

*   **Terminal Settings**:
    *   `/hex`: Toggle Hex display mode.
    *   `/timestamp`: Toggle timestamp display.
    *   `/newline`: Toggle appending `\r\n` to sent messages.
    *   `/clear` (or `/cls`): Clear the screen.

*   **STM32 Flashing**:
    *   `/chipinfo`: Read and display STM32 chip information.
    *   `/flash <file> [address]`: Flash firmware (e.g., `/flash firmware.hex`).
    *   `/verify <file> [address]`: Verify flash content against a file.
    *   `/erase`: Erase the entire flash memory.
    *   `/readmem <address> <length>`: Read memory from the device.
    *   `/go <address>`: Jump to the specified address.

*   **General**:
    *   `/help` (or `/h`, `/?`): Show help message.
    *   `/exit` (or `/quit`): Exit the application.

### 2. CLI Automation Mode

Use command-line arguments for scripting or quick operations:

*   **List Ports**:
    ```bash
    python cli.py list
    ```

*   **Flash Firmware**:
    ```bash
    python cli.py flash firmware.hex -p COM3
    # Options:
    #   -b, --baud <rate>    (Default: 115200)
    #   -a, --address <addr> (Default: 0x08000000)
    #   --no-erase           Skip chip erase
    #   --no-verify          Skip verification
    #   -r, --run            Run application after flashing
    ```

*   **Erase Chip**:
    ```bash
    python cli.py erase -p COM3
    ```

*   **Get Chip Info**:
    ```bash
    python cli.py info -p COM3
    ```

*   **Run Application**:
    ```bash
    python cli.py run -p COM3 --address 0x08000000
    ```

## Project Structure

*   `cli.py`: Main entry point and command handling.
*   `serial_handler.py`: Serial port communication and background reading thread.
*   `stm32_bootloader.py`: Implementation of the STM32 UART bootloader protocol.
*   `flash_commands.py`: High-level logic for flashing, verifying, and erasing.
*   `hex_parser.py`: Utilities for parsing Intel HEX and binary files.
*   `ui_helpers.py`: UI styling, progress bars, and formatting functions.

## License

[MIT License](LICENSE)
