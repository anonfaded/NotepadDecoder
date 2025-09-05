#!/usr/bin/env python3
"""
NotepadDecoder - Windows Notepad TabState .bin File Decoder

NotepadDecoder decodes UTF-16LE encoded text from Windows Notepad's TabState
.bin files. These files contain unsaved text from Notepad sessions that would
otherwise be lost.

Author: Faded (FadSec Lab)
Website: https://faded.dev

Usage:
        python notepad_decoder.py /path/to/TabState/file.bin
        python notepad_decoder.py /path/to/TabState/  # Process all main .bin files in directory
        python notepad_decoder.py   # Run the tool in interactive mode
IMPORTANT:
- You must edit the `DEFAULT_SOURCE_DIR` constant near the top of this file so it points
    to the TabState folder on your machine (it contains your Windows username).
- Example Windows path to use if running on Windows:
    C:/Users/USERNAME/AppData/Local/Packages/Microsoft.WindowsNotepad_8wekyb3d8bbwe/LocalState/TabState
    # If you are on Linux and Windows is on Dual Boot, then use the following command to find your mount point for the Windows partition:
    ls /media/USERNAME/
    # Then use the output path to set DEFAULT_SOURCE_DIR, for example:
    /media/YOUR_USERNAME/YOUR_DRIVE_ID/Users/YOUR_USERNAME/AppData/Local/Packages/Microsoft.WindowsNotepad_8wekyb3d8bbwe/LocalState/TabState

The DEFAULT_SOURCE_DIR constant is present so the script can default to your TabState
folder when you run the tool without arguments.
"""

import sys
import os
import string
import re
from pathlib import Path

# ------------------ Configuration (changeable) ------------------
# File extension for saved decoded files
OUTPUT_EXT = '.md'
# Output directory name (inside cwd, where the script is run)
OUTPUT_DIR_NAME = 'decoded_notepad_output'
# Minimum consecutive UTF-16LE ASCII chars to consider a run (CORE parameter)
MIN_UTF16_RUN = 4
# Max characters from first line to use in filename
FILENAME_MAX_LEN = 30
# Default source directory for TabState files (change to your mount point)
DEFAULT_SOURCE_DIR = '/media/YOUR_USERNAME/YOUR_DRIVE_ID/Users/YOUR_USERNAME/AppData/Local/Packages/Microsoft.WindowsNotepad_8wekyb3d8bbwe/LocalState/TabState'
# ------------------ End configuration ---------------------------

# Optional color support
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init()
    COLOR_AVAILABLE = True
except Exception:
    COLOR_AVAILABLE = False

def decode_notepad_bin(file_path):
    """
    Decode a single .bin file and extract UTF-16LE text content.

    Strategy:
    1. FIRST: Use extract_utf16le_runs()
    2. SECOND: Try offsets if runs method fails
    3. LAST: ASCII fallback
    """
    try:
        with open(file_path, 'rb') as f:
            data = f.read()

        # CORE METHOD: Extract UTF-16LE ASCII runs
        runs = extract_utf16le_runs(data, min_chars=4)
        if runs:
            return "\n\n".join(runs).strip()

        # FALLBACK: Try UTF-16LE decoding at common offsets
        for offset in [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20]:
            if offset >= len(data):
                continue

            try:
                text_data = data[offset:]
                decoded = text_data.decode('utf-16le', errors='replace')
                decoded = decoded.replace('\ufffd', '').strip()

                if len(decoded) > 5 and any(c.isalnum() for c in decoded):
                    return decoded
            except Exception:
                continue

        # LAST RESORT: ASCII strings
        return extract_printable_strings(data)

    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        return ""
    except Exception as e:
        print(f"Error decoding {file_path}: {e}")
        return ""


def extract_utf16le_runs(data, min_chars=4):
    """
    CORE LOGIC: Scan binary data for runs of UTF-16LE encoded ASCII characters.

    This looks for sequences where:
    - Low byte is printable ASCII (0x20-0x7E)
    - High byte is 0x00 (typical for English in UTF-16LE)
    """
    runs = []
    i = 0
    n = len(data)

    def is_utf16le_ascii_pair(lo, hi):
        return 0x20 <= lo <= 0x7E and hi == 0x00

    while i + 1 < n:
        j = i
        count = 0
        while j + 1 < n and is_utf16le_ascii_pair(data[j], data[j+1]):
            count += 1
            j += 2

        if count >= min_chars:
            chunk = data[i:j]
            try:
                decoded = chunk.decode('utf-16le')
                runs.append(decoded.strip())
            except Exception:
                pass
            i = j
        else:
            i += 1

    return runs


def extract_printable_strings(data, min_len=4):
    """
    Extract ASCII printable runs from raw binary data as a fallback.

    Returns a single string with runs separated by blank lines.
    """
    runs = []
    cur = []
    for byte in data:
        if 32 <= byte <= 126:
            cur.append(chr(byte))
        else:
            if len(cur) >= min_len:
                runs.append(''.join(cur))
            cur = []

    if len(cur) >= min_len:
        runs.append(''.join(cur))

    return "\n\n".join(runs)


def make_filename_from_content(content, default_stem='decoded'):
    """
    Create a safe filename from the first non-empty line of the decoded content.

    Rules:
    - Use first non-empty line, strip and truncate to 30 characters
    - Replace spaces with underscores
    - Remove characters not in [A-Za-z0-9_-]
    - Fall back to `default_stem` if result is empty
    """
    if not content:
        return default_stem

    # Find first non-empty line
    for line in content.splitlines():
        line = line.strip()
        if line:
            first = line
            break
    else:
        return default_stem

    # Truncate to configured max length
    first = first[:FILENAME_MAX_LEN]

    # Remove characters we don't want (keep alnum, space, underscore, dash)
    first = re.sub(r'[^A-Za-z0-9 _-]', '', first)

    # Normalize whitespace -> single spaces, then replace spaces with underscores
    first = first.strip()
    first = re.sub(r'\s+', '_', first)

    # Collapse repeated underscores and strip leading/trailing underscores
    first = re.sub(r'_+', '_', first)
    first = first.strip('_')

    if not first:
        return default_stem

    return first

def create_output_directory():
    """
    Create a decoded_output directory in the current project folder.

    Returns:
        Path: Path to the output directory
    """
    current_dir = Path.cwd()
    output_dir = current_dir / OUTPUT_DIR_NAME

    if not output_dir.exists():
        output_dir.mkdir(parents=True)
        print(f"Created output directory: {output_dir}")

    return output_dir


def save_decoded_content(content, default_stem='decoded'):
    """
    Save decoded content into the output directory using a safe filename
    derived from the content (first line). Returns the Path saved to.
    """
    output_dir = create_output_directory()
    safe_name = make_filename_from_content(content, default_stem=default_stem)
    output_filename = f"{safe_name}_decoded{OUTPUT_EXT}"
    output_file = output_dir / output_filename

    counter = 1
    while output_file.exists():
        output_file = output_dir / f"{safe_name}_decoded_{counter}{OUTPUT_EXT}"
        counter += 1

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

    return output_file


def interactive_mode():
    """
    Simple interactive CLI: choose directory, then choose single file or all.
    """
    # Helper to print header consistently and clearly
    def print_header():
        # clear screen first
        try:
            os.system('clear')
        except Exception:
            pass

        title = "Notepad TabState Decoder"
        banner = "█▓▒░⡷⠂  𝓟𝓻𝓸𝓳𝓮𝓬𝓽 𝓫𝔂 𝓕𝓪𝓭𝓢𝓮𝓬 𝓛𝓪𝓫 ⠐⢾░▒▓█"
        discord = "Join community: https://discord.gg/kvAZvdkuuN"

        # concise header: title, indented banner, and discord link in red
        if COLOR_AVAILABLE:
            print(Fore.CYAN + Style.BRIGHT + f" {title} " + Style.RESET_ALL)
            print(Fore.MAGENTA + "\t\t" + banner + Style.RESET_ALL)
            print(Fore.RED + Style.DIM + discord + Style.RESET_ALL)
        else:
            print(title)
            print('\t\t' + banner)
            print(discord)


    # Initial screen
    print_header()

    # NOTE for user: remind to edit DEFAULT_SOURCE_DIR to match your system
    note = "Edit DEFAULT_SOURCE_DIR in the script."
    if COLOR_AVAILABLE:
        print(Style.DIM + Fore.YELLOW + note + Style.RESET_ALL)
        # show default path in blue
        print('Default path: ' + Fore.BLUE + '/media/YOUR_USERNAME/YOUR_DRIVE_ID/Users/YOUR_USERNAME/AppData/Local/Packages/Microsoft.WindowsNotepad_8wekyb3d8bbwe/LocalState/TabState' + Style.RESET_ALL)
    else:
        print(note)
        print('Default path: ' + '/media/YOUR_USERNAME/YOUR_DRIVE_ID/Users/YOUR_USERNAME/AppData/Local/Packages/Microsoft.WindowsNotepad_8wekyb3d8bbwe/LocalState/TabState')
        print('Press Enter to continue or type a directory path. Type "e" to exit.')

    # Simplified initial prompt (print instructions once)
    instruction = "Press Enter to continue or type a directory path. Type 'e' to exit."
    if COLOR_AVAILABLE:
        print(Style.DIM + instruction + Style.RESET_ALL)
        dir_input = input(Fore.RED + '  ❯ ' + Style.RESET_ALL).strip()
    else:
        print(instruction)
        dir_input = input('  ❯ ').strip()

    # Special exits
    if dir_input.lower() == 'e':
        # Goodbye message
        if COLOR_AVAILABLE:
            print(Fore.MAGENTA + '\nGoodbye from NotepadDecoder (FadSec Lab) — Join community: https://discord.gg/kvAZvdkuuN' + Style.RESET_ALL)
        else:
            print('\nGoodbye from FadSec Lab — Join community: https://discord.gg/kvAZvdkuuN')
        return


    # Determine directory: Enter -> default, else path
    if not dir_input:
        dir_path = Path(DEFAULT_SOURCE_DIR)
    else:
        dir_path = Path(dir_input).expanduser()

    if not dir_path.exists() or not dir_path.is_dir():
        print(f"Directory not found: {dir_path}")
        return

    # After first Enter, clear and show header + main screen
    print_header()

    # Count all .bin files first
    all_bin_files = list(dir_path.glob('*.bin'))
    total_bin_count = len(all_bin_files)
    
    # Filter to only main .bin files (exclude .0.bin, .1.bin, etc.)
    bin_files = sorted([f for f in all_bin_files if not f.name.endswith(('.0.bin', '.1.bin', '.2.bin', '.3.bin', '.4.bin', '.5.bin', '.6.bin', '.7.bin', '.8.bin', '.9.bin'))])
    
    if not bin_files:
        print(f"No .bin files found in {dir_path}")
        return

    filtered_count = total_bin_count - len(bin_files)
    summary = f"Found {len(bin_files)} main .bin files"
    if filtered_count > 0:
        summary += f" ({filtered_count} numbered files excluded)"
    summary += f" in {dir_path}"
    
    if COLOR_AVAILABLE:
        print(Fore.YELLOW + summary + Style.RESET_ALL + '\n')
    else:
        print(summary + '\n')

    # Table column widths (adjustable)
    idx_w = 4
    name_w = 40
    size_w = 10
    prev_w = 60

    def colored(s, color):
        if COLOR_AVAILABLE:
            return color + s + Style.RESET_ALL
        return s

    hdr_idx = 'Idx'.ljust(idx_w)
    hdr_name = 'Filename'.ljust(name_w)
    hdr_size = 'Size'.rjust(size_w)
    hdr_prev = 'Preview'.ljust(prev_w)

    header = f"{hdr_idx}  {hdr_name}  {hdr_size}  {hdr_prev}"
    sep = '-' * (idx_w + name_w + size_w + prev_w + 6)
    if COLOR_AVAILABLE:
        print(colored(header, Fore.CYAN + Style.BRIGHT))
        print(colored(sep, Fore.BLUE))
    else:
        print(header)
        print(sep)

    # Show a numbered table with a short preview (first non-empty line)
    for i, bf in enumerate(bin_files):
        preview = ''
        try:
            content = decode_notepad_bin(str(bf))
            for line in content.splitlines():
                if line.strip():
                    preview = line.strip()
                    break
        except Exception:
            preview = '<could not preview>'

        name = (bf.name[:name_w-3] + '...') if len(bf.name) > name_w else bf.name
        size = str(bf.stat().st_size) + ' B'
        if len(preview) > prev_w:
            preview = preview[:prev_w-3] + '...'

        row = f"{str(i).ljust(idx_w)}  {name.ljust(name_w)}  {size.rjust(size_w)}  {preview.ljust(prev_w)}"
        # highlight rows with likely content
        if COLOR_AVAILABLE and preview and not preview.startswith('<'):
            print(colored(row, Fore.GREEN))
        else:
            print(row)

    # Show available commands in a styled box (after file list)
    title_line = '📜 Available Commands'
    if COLOR_AVAILABLE:
        # Heading and top border entirely red
        top = Fore.RED + '╭' + '─ ' + title_line + Style.RESET_ALL
        print(top)

        # Rows: box pipe and arrow in red; option key blue; description white
        red_pipe = Fore.RED + '│' + Style.RESET_ALL
        red_arrow = Fore.RED + '→' + Style.RESET_ALL

        s_line = Fore.RED + '│' + Style.RESET_ALL + ' ' + Fore.RED + '→' + Style.RESET_ALL + ' ' + Fore.BLUE + 's' + Style.RESET_ALL + ' : ' + Fore.WHITE + 'Select a single file by number' + Style.RESET_ALL
        a_line = Fore.RED + '│' + Style.RESET_ALL + ' ' + Fore.RED + '→' + Style.RESET_ALL + ' ' + Fore.BLUE + 'a' + Style.RESET_ALL + ' : ' + Fore.WHITE + 'Process all files (each saved separately)' + Style.RESET_ALL
        e_line = Fore.RED + '│' + Style.RESET_ALL + ' ' + Fore.RED + '→' + Style.RESET_ALL + ' ' + Fore.BLUE + 'e' + Style.RESET_ALL + ' : ' + Fore.WHITE + 'Exit' + Style.RESET_ALL

        print(s_line)
        print(a_line)
        print(e_line)

        bottom = Fore.RED + '╰' + '─' * (len(title_line) + 2) + Style.RESET_ALL
        print(bottom)
    else:
        pipe_sym = '│'
        arrow_sym = '→'
        box_lines = [
            f"╭─ {title_line}",
            f"{pipe_sym} {arrow_sym} s : Select a single file by number",
            f"{pipe_sym} {arrow_sym} a : Process all files (each saved separately)",
            f"{pipe_sym} {arrow_sym} e : Exit",
            "╰" + "─" * (len(title_line) + 2)
        ]

        for bl in box_lines:
            print(bl)

    # Prompt for an action: label in yellow, red arrow for input
    if COLOR_AVAILABLE:
        # print the label then show a red arrow as the input prompt
        print(Fore.YELLOW + '\nChoose option (s/a/e): ' + Style.RESET_ALL, end='')
        choice = input(Fore.RED + '  ❯ ' + Style.RESET_ALL).strip().lower()
    else:
        choice = input('\nChoose option (s/a/e): ').strip().lower()
    if choice == 'e':
        if COLOR_AVAILABLE:
            print(Fore.MAGENTA + '\nGoodbye from NotepadDecoder (FadSec Lab) — Join community: https://discord.gg/kvAZvdkuuN' + Style.RESET_ALL)
        else:
            print('\nGoodbye from FadSec Lab — Join community: https://discord.gg/kvAZvdkuuN')
        return
    if choice == 'q':
        return
    if choice == 's':
        if COLOR_AVAILABLE:
            idx = input(Fore.RED + 'Enter file number: ' + Style.RESET_ALL).strip()
        else:
            idx = input('Enter file number: ').strip()

        if not idx.isdigit() or int(idx) < 0 or int(idx) >= len(bin_files):
            print('Invalid selection')
            return
        sel = bin_files[int(idx)]
        print(f"Decoding {sel.name}...")
        content = decode_notepad_bin(str(sel))
        if content:
            out = save_decoded_content(content, default_stem=sel.stem)
            print(f"Saved: {out}")
        else:
            print('No readable content found.')
        return
    if choice == 'a':
        print(f"Processing all {len(bin_files)} files...")
        for bf in bin_files:
            print(f"Decoding {bf.name}...")
            content = decode_notepad_bin(str(bf))
            if content:
                out = save_decoded_content(content, default_stem=bf.stem)
                print(f"  Saved: {out.name}")
            else:
                print(f"  No readable content in {bf.name}")
        return
    print('Unknown option')

def process_directory(directory_path):
    """
    Process all main .bin files in a directory (excludes .0.bin, .1.bin, etc.).

    Args:
        directory_path (str): Path to directory containing .bin files
    """
    # Count all .bin files first
    all_bin_files = list(Path(directory_path).glob('*.bin'))
    total_bin_count = len(all_bin_files)
    
    # Filter to only main .bin files (exclude .0.bin, .1.bin, etc.)
    bin_files = list([f for f in all_bin_files if not f.name.endswith(('.0.bin', '.1.bin', '.2.bin', '.3.bin', '.4.bin', '.5.bin', '.6.bin', '.7.bin', '.8.bin', '.9.bin'))])

    if not bin_files:
        print(f"No .bin files found in {directory_path}")
        return

    filtered_count = total_bin_count - len(bin_files)
    summary = f"Found {len(bin_files)} main .bin files"
    if filtered_count > 0:
        summary += f" ({filtered_count} numbered files excluded)"
    summary += ". Processing..."
    
    print(summary)

    # Create output directory
    output_dir = create_output_directory()

    for bin_file in bin_files:
        print(f"\n{'='*60}")
        print(f"Processing: {bin_file.name}")
        print(f"{'='*60}")

        content = decode_notepad_bin(str(bin_file))

        if content:
            # Show preview (limit to avoid encoding issues in terminal)
            # Only show content that looks like valid English text
            lines = content.split('\n')[:5]  # First 5 lines
            valid_lines = []

            for line in lines:
                # Check if line contains mostly English characters
                if line and any(c.isascii() and c.isalpha() for c in line):
                    # Clean the line for terminal display — allow full ASCII punctuation
                    clean_line = ''.join(c if c.isascii() and (c.isalnum() or c.isspace() or c in string.punctuation) else '?' for c in line)
                    if clean_line.strip():
                        valid_lines.append(clean_line.strip())

            if valid_lines:
                for line in valid_lines[:3]:  # Show up to 3 valid lines
                    print(line)
            else:
                print("[Content found but may contain non-English characters]")

            if len(content) > 500:
                print(f"\n[... {len(content) - 500} more characters ...]")

            # Create a readable filename from content (first non-empty line)
            safe_name = make_filename_from_content(content, default_stem=bin_file.stem)
            output_filename = f"{safe_name}_decoded.md"
            output_file = output_dir / output_filename
            # avoid collisions: add suffix if exists
            counter = 1
            base = output_file.with_suffix('')
            while output_file.exists():
                output_file = output_dir / f"{safe_name}_decoded_{counter}.md"
                counter += 1

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"\nSaved decoded content to: {output_file}")
        else:
            print("No readable content found.")

def main():
    if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)

    # If no args provided, launch interactive mode by default
    if len(sys.argv) == 1:
        interactive_mode()
        return

    if len(sys.argv) != 2:
        print("Usage:")
        print("  python notepad_decoder.py /path/to/file.bin")
        print("  python notepad_decoder.py /path/to/directory/")
        print("Run without arguments to start interactive mode.")
        sys.exit(1)

    target_path = sys.argv[1]

    if os.path.isfile(target_path):
        if not target_path.endswith('.bin'):
            print("Error: File must have .bin extension")
            sys.exit(1)

        print(f"Decoding: {target_path}")
        content = decode_notepad_bin(target_path)

        if content:
            # Create output directory for single file too
            output_dir = create_output_directory()
            bin_path = Path(target_path)
            output_filename = f"{bin_path.stem}_decoded.md"
            output_file = output_dir / output_filename

            print("\nExtracted Content:")
            print("-" * 40)

            # Show preview with improved filtering
            lines = content.split('\n')[:10]  # First 10 lines
            valid_lines = []

            for line in lines:
                # Check if line contains mostly English characters
                if line and any(c.isascii() and c.isalpha() for c in line):
                    # Clean the line for terminal display — allow full ASCII punctuation
                    clean_line = ''.join(c if c.isascii() and (c.isalnum() or c.isspace() or c in string.punctuation) else '?' for c in line)
                    if clean_line.strip():
                        valid_lines.append(clean_line.strip())

            if valid_lines:
                for line in valid_lines[:5]:  # Show up to 5 valid lines
                    print(line)
            else:
                print("[Content found but may contain non-English characters]")

            if len(content) > 1000:
                print(f"\n[... {len(content) - 1000} more characters ...]")

            # Save to file
            # Use first line to create a readable filename
            safe_name = make_filename_from_content(content, default_stem=bin_path.stem)
            output_filename = f"{safe_name}_decoded.md"
            output_file = output_dir / output_filename
            counter = 1
            while output_file.exists():
                output_file = output_dir / f"{safe_name}_decoded_{counter}.md"
                counter += 1

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"\nSaved decoded content to: {output_file}")
        else:
            print("No readable content found in the file.")

    elif os.path.isdir(target_path):
        process_directory(target_path)
    else:
        print(f"Error: {target_path} is not a valid file or directory.")
        sys.exit(1)

if __name__ == "__main__":
    main()
