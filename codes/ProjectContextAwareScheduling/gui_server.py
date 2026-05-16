import re
import os
import sys
import time
import subprocess
import webbrowser
import threading
from pathlib import Path
from typing import Dict

# Dependency Check
try:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("Installing required dependencies (fastapi, uvicorn)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn"])
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    import uvicorn

app = FastAPI()

PROJECT_ROOT = Path(__file__).parent.absolute()
CONFIG_HEADER = PROJECT_ROOT / "Core" / "Inc" / "core" / "TaskConfig.h"
AUTOMATION_SCRIPT = PROJECT_ROOT / "automate_schedulers.py"

class SchedulerParams(BaseModel):
    TASK1_PRIORITY: int
    TASK2_PRIORITY: int
    TASK3_PRIORITY: int
    TASK4_PRIORITY: int
    TASK1_PERIOD_MS: int
    TASK2_PERIOD_MS: int
    TASK3_PERIOD_MS: int
    TASK4_PERIOD_MS: int
    ALPHA: float
    SAFETY_MARGIN_MS: int
    MEMORY_INTENSITY_THRESHOLD: float
    TASK1_MEMORY_INTENSITY: float
    TASK2_MEMORY_INTENSITY: float
    TASK3_MEMORY_INTENSITY: float
    TASK4_MEMORY_INTENSITY: float
    COM_PORT: str = "COM4"
    BAUD_RATE: int = 115200
    DURATION_SECONDS: int = 10

# Global state to store runtime settings and process
runtime_settings = {
    "COM_PORT": "COM4",
    "BAUD_RATE": 115200,
    "DURATION_SECONDS": 10
}
current_process = None

def parse_config() -> Dict:
    content = CONFIG_HEADER.read_text()
    params = {}
    
    # Regex patterns for different types
    patterns = {
        "PRIORITY": r"constexpr UBaseType_t (TASK\d_PRIORITY) = (\d+);",
        "PERIOD": r"constexpr uint32_t (TASK\d_PERIOD_MS) = (\d+);",
        "PARAMS": r"constexpr (?:float|uint32_t)\s+([A-Z_]+)\s+=\s+([\d\.f]+);",
        "INTENSITY": r"constexpr float (TASK\d_MEMORY_INTENSITY) = ([\d\.f]+);"
    }
    
    for key, pattern in patterns.items():
        matches = re.finditer(pattern, content)
        for match in matches:
            name, value = match.groups()
            # Clean up float values like "1.0f"
            clean_value = value.replace("f", "")
            params[name] = float(clean_value) if "." in clean_value or name == "ALPHA" else int(clean_value)
            
    # Add runtime settings to the params
    params.update(runtime_settings)
    return params

def write_config(params: Dict):
    content = CONFIG_HEADER.read_text()
    
    for name, value in params.items():
        # Skip runtime settings (they are already popped in update_params)
        if name in ["COM_PORT", "BAUD_RATE", "DURATION_SECONDS"]:
            continue
            
        # Handle float formatting with 'f' suffix
        if isinstance(value, float):
            formatted_value = f"{value:.2f}f"
        else:
            formatted_value = str(value)
            
        # Pattern: constexpr [TYPE] [NAME] = [VALUE];
        pattern = rf"(constexpr\s+(?:UBaseType_t|uint32_t|float)\s+{name}\s*=\s*)([\d\.f]+);"
        if re.search(pattern, content):
            content = re.sub(pattern, rf"\g<1>{formatted_value};", content)
        else:
            print(f"Warning: Could not find parameter {name} in {CONFIG_HEADER}")
        
    CONFIG_HEADER.write_text(content)

@app.get("/api/params")
async def get_params():
    return parse_config()

@app.post("/api/params")
async def update_params(params: SchedulerParams):
    try:
        p_dict = params.dict()
        
        # Update runtime settings
        runtime_settings["COM_PORT"] = p_dict.pop("COM_PORT")
        runtime_settings["BAUD_RATE"] = p_dict.pop("BAUD_RATE")
        runtime_settings["DURATION_SECONDS"] = p_dict.pop("DURATION_SECONDS")
        
        write_config(p_dict)
        return {"status": "success"}
    except Exception as e:
        print(f"Error updating params: {e}")
        return HTMLResponse(content=str(e), status_code=500)

@app.get("/api/run")
async def run_tests():
    global current_process
    def generate():
        global current_process
        cmd = [
            sys.executable, "-u", str(AUTOMATION_SCRIPT),
            "--port", runtime_settings["COM_PORT"],
            "--baud", str(runtime_settings["BAUD_RATE"]),
            "--duration", str(runtime_settings["DURATION_SECONDS"])
        ]
        current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        for line in current_process.stdout:
            yield f"data: {line}\n\n"
        
        current_process.wait()
        current_process = None
        yield "data: --- COMPLETED ---\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/stop")
async def stop_tests():
    global current_process
    if current_process:
        # Kill the process tree (Windows)
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(current_process.pid)])
        current_process = None
        return {"status": "stopped"}
    return {"status": "no process running"}

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = PROJECT_ROOT / "Core" / "Src" / "app" / "index.html"
    return index_path.read_text(encoding='utf-8')

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)
