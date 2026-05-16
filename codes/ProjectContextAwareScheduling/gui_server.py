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
            
    return params

def write_config(params: Dict):
    content = CONFIG_HEADER.read_text()
    
    for name, value in params.items():
        # Handle float formatting with 'f' suffix
        if isinstance(value, float):
            formatted_value = f"{value:.2f}f" if "." in str(value) else f"{value:.1f}f"
        else:
            formatted_value = str(value)
            
        # Replace the value in the file
        # Pattern matches: constexpr TYPE NAME = VALUE;
        pattern = rf"(constexpr (?:UBaseType_t|uint32_t|float)\s+{name}\s+=\s+)([\d\.f]+);"
        replacement = rf"\1{formatted_value};"
        content = re.sub(pattern, replacement, content)
        
    CONFIG_HEADER.write_text(content)

@app.get("/api/params")
async def get_params():
    return parse_config()

@app.post("/api/params")
async def update_params(params: SchedulerParams):
    write_config(params.dict())
    return {"status": "success"}

@app.get("/api/run")
async def run_tests():
    def generate():
        process = subprocess.Popen(
            [sys.executable, "-u", str(AUTOMATION_SCRIPT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        for line in process.stdout:
            yield f"data: {line}\n\n"
        process.wait()
        yield "data: --- COMPLETED ---\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

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
