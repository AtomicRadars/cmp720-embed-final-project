import subprocess
import sys
import time
import os
import string
import re
from datetime import datetime
from pathlib import Path

# Automatic dependency check
try:
    import serial
except ImportError:
    print("pyserial not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyserial"])
    import serial

# Configuration
COM_PORT = "COM4"
BAUD_RATE = 115200
DURATION_SECONDS = 30  # Capture duration for each scheduler
SCHEDULERS = ["NATIVE", "EDF", "CONTEXT_AWARE"]
PROJECT_ROOT = Path(__file__).parent.absolute()
LOG_DIR = PROJECT_ROOT / "Core" / "Src" / "test" / "results" / "auto_tests"
ELF_PATH = PROJECT_ROOT / "build" / "Debug" / "ProjectContextAwareScheduling.elf"

# Tool Paths (Automatic Discovery)
def setup_environment():
    # 1. Find arm-none-eabi-gcc
    user_home = Path.home()
    possible_toolchain_paths = [
        user_home / "AppData" / "Local" / "stm32cube" / "bundles" / "gnu-tools-for-stm32" / "14.3.1+st.2" / "bin",
        Path("C:/ST/STM32CubeCLT/GNU-tools-for-STM32/bin"),
    ]
    
    # 2. Find STM32_Programmer_CLI
    possible_programmer_paths = [
        Path("C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin"),
        Path("C:/ST/STM32CubeProgrammer/bin"),
    ]

    tool_paths = []
    for p in possible_toolchain_paths:
        if p.exists():
            tool_paths.append(str(p))
            break
            
    for p in possible_programmer_paths:
        if p.exists():
            tool_paths.append(str(p))
            break
            
    if tool_paths:
        print(f"Adding to PATH: {'; '.join(tool_paths)}")
        os.environ["PATH"] = ";".join(tool_paths) + ";" + os.environ["PATH"]
    else:
        print("Warning: Could not find toolchain or programmer paths automatically. Ensure they are in your system PATH.")

def run_command(cmd, cwd=None):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, text=True)
    if result.returncode != 0:
        raise Exception(f"Command failed with exit code {result.returncode}")

def main():
    setup_environment()
    if not LOG_DIR.exists():
        LOG_DIR.mkdir(parents=True)

    # Generate timestamp for this run (ISO format friendly for filenames)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    # Mapping of scheduler types to display names for filenames
    sched_file_names = {
        "NATIVE": "NativeSch_test",
        "EDF": "EDFSch_test",
        "CONTEXT_AWARE": "ContextAwareSch_test"
    }

    for sched in SCHEDULERS:
        print(f"\n>>> Processing Scheduler: {sched}")

        try:
            # 1. Configure CMake
            run_command(["cmake", "--preset", "Debug", f"-DACTIVE_SCHEDULER={sched}"], cwd=PROJECT_ROOT)

            # 2. Build
            run_command(["cmake", "--build", "--preset", "Debug"], cwd=PROJECT_ROOT)

            # 4. Capture UART Metrics (Open port BEFORE flashing to capture first bytes)
            log_name = f"{sched_file_names.get(sched, sched.lower())}_{timestamp}.log"
            log_file_path = LOG_DIR / log_name
            print(f"Capturing UART metrics on {COM_PORT} for {DURATION_SECONDS} seconds...")
            
            with serial.Serial(COM_PORT, BAUD_RATE, timeout=1) as ser:
                # Clear any stale data from previous runs
                ser.reset_input_buffer()
                
                # 3. Flash (The board resets and starts sending data immediately)
                # Ensure STM32_Programmer_CLI is in your PATH
                run_command(["STM32_Programmer_CLI", "-c", "port=SWD", "-w", str(ELF_PATH), "-v", "-rst"])

                print(f"Logging to: {log_file_path}")
                start_time = time.time()
                with open(log_file_path, "w", newline='', encoding='utf-8') as f:
                    f.write(f"--- Log started at {time.ctime()} for scheduler {sched} ---\n\n")
                    buffer = ""
                    first_task_printed = False
                    recording_started = False
                    
                    while (time.time() - start_time) < DURATION_SECONDS:
                        if ser.in_waiting > 0:
                            # Read and decode
                            buffer += ser.read(ser.in_waiting).decode('utf-8', errors='replace')
                            
                            # Process complete lines
                            if '\n' in buffer:
                                lines = buffer.split('\n')
                                # Keep the last (potentially incomplete) line in the buffer
                                buffer = lines[-1]
                                
                                for line in lines[:-1]:
                                    # Remove ANSI escape sequences
                                    clean_line = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', line)
                                    
                                    # Strip whitespace and carriage returns
                                    clean_line = clean_line.strip('\r').strip()
                                    
                                    # Filter out any remaining non-printable characters (noise)
                                    clean_line = "".join(filter(lambda x: x in string.printable, clean_line))
                                    
                                    # Wait for a valid start marker before recording
                                    # ONLY start recording on specific markers to avoid stale data
                                    if not recording_started:
                                        if "System Configuration" in clean_line or "Tasks created successfully" in clean_line:
                                            # Clean up leading noise from the very first line if needed
                                            if "System Configuration" in clean_line:
                                                clean_line = "--- System Configuration ---"
                                            elif "Tasks created successfully" in clean_line:
                                                clean_line = "Tasks created successfully" + clean_line.split("Tasks created successfully", 1)[1]
                                            
                                            recording_started = True
                                        else:
                                            continue

                                    if clean_line:
                                        # Add an empty line before Task 1 to separate groups (except if it's the very first task we print)
                                        if clean_line.startswith("Task1_MotorControl!"):
                                            if first_task_printed:
                                                f.write("\n")
                                                print("", flush=True)
                                        
                                        f.write(clean_line + "\n")
                                        f.flush()
                                        try:
                                            print(clean_line, flush=True)
                                        except UnicodeEncodeError:
                                            pass
                                        
                                        # Mark that we have started printing tasks
                                        if clean_line.startswith("Task"):
                                            first_task_printed = True
                        time.sleep(0.1)

            print(f"\nCapture completed for {sched}.")

        except Exception as e:
            print(f"ERROR: {e}")
            continue

    print("\n>>> All schedulers processed. Logs are available in", LOG_DIR)

if __name__ == "__main__":
    main()
