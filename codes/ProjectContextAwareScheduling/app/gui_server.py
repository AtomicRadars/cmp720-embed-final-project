import re
import os
import sys
import time
import subprocess
import webbrowser
import threading
from pathlib import Path
from typing import Dict, Any, Literal

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

APP_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = APP_DIR.parent.absolute()
CONFIG_HEADER = PROJECT_ROOT / "Core" / "Inc" / "core" / "TaskConfig.h"
AUTOMATION_SCRIPT = PROJECT_ROOT / "automate_schedulers.py"
LOG_DIR = PROJECT_ROOT / "logs" / "auto_tests"

# Add project root to sys.path to resolve offline_aco_baseline imports
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


from offline_aco_baseline.scheduler_model import (
    compute_hyperperiod_ms,
    default_project_tasks,
    generate_jobs,
)

from offline_aco_baseline.baselines import (
    pick_edf_job,
    pick_rms_job,
    run_baseline,
    pick_edf_runtime_job,
    pick_rms_runtime_job,
    run_preemptive_baseline,
    make_context_aware_picker,
    make_context_aware_runtime_picker,
    ContextAwareParams,
    ContextAwareStats,
)

from offline_aco_baseline.aco_solver import (
    ACOParams,
    ACOSolver,
)

from offline_aco_baseline.preemptive_aco_solver import (
    PreemptiveACOParams,
    PreemptiveACOSolver,
)

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


class ACORequest(BaseModel):
    solver_type: str = "non_preemptive"  # "non_preemptive" or "preemptive"
    workload_profile: str = "default"

    ant_count: int = 40
    iterations: int = 150

    pheromone_alpha: float = 1.0
    heuristic_beta: float = 3.0
    evaporation_rate: float = 0.20
    deposit_weight: float = 1000.0
    seed: int = 42

    # Non-preemptive ACO parameters
    lookahead_ms: int = 20
    memory_weight: float = 2.0
    idle_weight: float = 0.20

    # Preemptive ACO parameters
    deadline_weight: float = 4.0
    response_weight: float = 0.05
    switch_weight: float = 0.10
    segment_contention_penalty_ms: int = 2
    enable_segment_contention_time: bool = True

def task_model_to_dict(task) -> Dict[str, Any]:
    return {
        "task_id": task.task_id,
        "task_name": task.name,
        "period_ms": task.period_ms,
        "deadline_ms": task.deadline_ms,
        "wcet_ms": task.wcet_ms,
        "memory_intensity": task.memory_intensity,
        "utilization": task.wcet_ms / task.period_ms,
    }


def task_set_summary_to_dict(tasks) -> Dict[str, Any]:
    total_utilization = sum(task.wcet_ms / task.period_ms for task in tasks)

    return {
        "task_count": len(tasks),
        "total_utilization": total_utilization,
        "tasks": [task_model_to_dict(task) for task in tasks],
    }


def scheduled_job_to_dict(scheduled_job) -> Dict[str, Any]:
    return {
        "order": scheduled_job.order,
        "job": scheduled_job.job.label,
        "task": scheduled_job.job.task_name,
        "release_ms": scheduled_job.job.release_ms,
        "start_ms": scheduled_job.start_ms,
        "finish_ms": scheduled_job.finish_ms,
        "deadline_ms": scheduled_job.job.deadline_ms,
        "contention_penalty_ms": scheduled_job.contention_penalty_ms,
        "smooth_memory_penalty": scheduled_job.smooth_memory_penalty,
        "deadline_missed": scheduled_job.deadline_missed,
        "lateness_ms": scheduled_job.lateness_ms,
    }


def preemptive_scheduled_job_to_dict(scheduled_job) -> Dict[str, Any]:
    return {
        "order": scheduled_job.order,
        "job": scheduled_job.job.label,
        "task": scheduled_job.job.task_name,
        "release_ms": scheduled_job.job.release_ms,
        "start_ms": scheduled_job.start_ms,
        "finish_ms": scheduled_job.finish_ms,
        "deadline_ms": scheduled_job.job.deadline_ms,
        "contention_penalty_ms": scheduled_job.contention_penalty_ms,
        "smooth_memory_penalty": scheduled_job.smooth_memory_penalty,
        "deadline_missed": scheduled_job.deadline_missed,
        "lateness_ms": scheduled_job.lateness_ms,
        "start_delay_ms": scheduled_job.start_delay_ms,
        "response_time_ms": scheduled_job.response_time_ms,
    }


def segment_to_dict(index: int, segment) -> Dict[str, Any]:
    return {
        "index": index,
        "job": segment.job.label,
        "task": segment.job.task_name,
        "start_ms": segment.start_ms,
        "end_ms": segment.end_ms,
        "duration_ms": segment.end_ms - segment.start_ms,
    }


def non_preemptive_evaluation_to_dict(evaluation) -> Dict[str, Any]:
    return {
        "summary": {
            "deadline_misses": evaluation.deadline_misses,
            "total_lateness_ms": evaluation.total_lateness_ms,
            "total_contention_penalty_ms": evaluation.total_contention_penalty_ms,
            "total_smooth_memory_penalty": evaluation.total_smooth_memory_penalty,
            "total_cost": evaluation.total_cost,
            "total_time_ms": evaluation.total_time_ms,
        },
        "schedule": [
            scheduled_job_to_dict(job)
            for job in evaluation.scheduled_jobs
        ],
    }


def preemptive_evaluation_to_dict(evaluation) -> Dict[str, Any]:
    completed = evaluation.scheduled_jobs

    if completed:
        avg_start_delay = sum(job.start_delay_ms for job in completed) / len(completed)
        max_start_delay = max(job.start_delay_ms for job in completed)
        avg_response_time = sum(job.response_time_ms for job in completed) / len(completed)
        max_response_time = max(job.response_time_ms for job in completed)
    else:
        avg_start_delay = 0.0
        max_start_delay = 0
        avg_response_time = 0.0
        max_response_time = 0

    return {
        "summary": {
            "deadline_misses": evaluation.deadline_misses,
            "total_lateness_ms": evaluation.total_lateness_ms,

            "job_start_contention_penalty_ms": evaluation.total_contention_penalty_ms,
            "job_start_smooth_memory_penalty": evaluation.total_smooth_memory_penalty,

            "segment_contention_events": evaluation.segment_contention_events,
            "segment_contention_penalty_ms": evaluation.total_segment_contention_penalty_ms,
            "segment_smooth_memory_penalty": evaluation.total_segment_smooth_memory_penalty,

            "scheduler_decisions": evaluation.scheduler_decisions,
            "preemptions": evaluation.preemptions,

            "avg_start_delay_ms": avg_start_delay,
            "max_start_delay_ms": max_start_delay,
            "avg_response_time_ms": avg_response_time,
            "max_response_time_ms": max_response_time,

            "total_cost": evaluation.total_cost,
            "total_time_ms": evaluation.total_time_ms,
        },
        "completed_jobs": [
            preemptive_scheduled_job_to_dict(job)
            for job in evaluation.scheduled_jobs
        ],
        "segments": [
            segment_to_dict(index, segment)
            for index, segment in enumerate(evaluation.execution_segments)
        ],
    }


def non_preemptive_aco_result_to_dict(result) -> Dict[str, Any]:
    return {
        "summary": non_preemptive_evaluation_to_dict(result.best_evaluation)["summary"],
        "schedule": non_preemptive_evaluation_to_dict(result.best_evaluation)["schedule"],
        "history": [
            {
                "iteration": record.iteration,
                "best_cost": record.best_cost,
                "deadline_misses": record.best_deadline_misses,
                "lateness_ms": record.best_lateness_ms,
                "contention_penalty_ms": record.best_contention_penalty_ms,
                "smooth_memory_penalty": record.best_smooth_memory_penalty,
            }
            for record in result.history
        ],
    }


def preemptive_aco_result_to_dict(result) -> Dict[str, Any]:
    evaluation_dict = preemptive_evaluation_to_dict(result.best_evaluation)

    return {
        "summary": evaluation_dict["summary"],
        "completed_jobs": evaluation_dict["completed_jobs"],
        "segments": evaluation_dict["segments"],
        "history": [
            {
                "iteration": record.iteration,
                "best_cost": record.best_cost,
                "deadline_misses": record.best_deadline_misses,
                "lateness_ms": record.best_lateness_ms,
                "segment_contention_penalty_ms": record.best_segment_contention_penalty_ms,
                "segment_smooth_memory_penalty": record.best_segment_smooth_memory_penalty,
                "total_time_ms": record.best_total_time_ms,
            }
            for record in result.history
        ],
    }

def get_tasks_for_workload_profile(profile: str):
    """
    Returns a task set for the offline ACO solver.

    Profiles:
      - default: mirrors the current embedded project task set
      - memory_stress: creates more memory-heavy interactions and more low-memory filler opportunities
      - high_utilization: increases CPU load to make scheduling tighter
    """
    profile = profile.strip().lower()

    if profile == "default":
        return default_project_tasks()

    # Import TaskModel locally to avoid breaking startup if file layout changes.
    from offline_aco_baseline.scheduler_model import TaskModel

    if profile == "memory_stress":
        return [
            TaskModel(
                task_id=0,
                name="Motor",
                period_ms=10,
                deadline_ms=10,
                wcet_ms=2,
                memory_intensity=0.10,
            ),
            TaskModel(
                task_id=1,
                name="Sensor",
                period_ms=25,
                deadline_ms=25,
                wcet_ms=2,
                memory_intensity=0.20,
            ),
            TaskModel(
                task_id=2,
                name="Crypto",
                period_ms=500,
                deadline_ms=500,
                wcet_ms=75,
                memory_intensity=0.90,
            ),
            TaskModel(
                task_id=3,
                name="Vision",
                period_ms=20,
                deadline_ms=20,
                wcet_ms=4,
                memory_intensity=0.80,
            ),
            TaskModel(
                task_id=4,
                name="Logger",
                period_ms=50,
                deadline_ms=50,
                wcet_ms=2,
                memory_intensity=0.05,
            ),
            TaskModel(
                task_id=5,
                name="Compress",
                period_ms=100,
                deadline_ms=100,
                wcet_ms=10,
                memory_intensity=0.85,
            ),
        ]

    if profile == "high_utilization":
        return [
            TaskModel(
                task_id=0,
                name="Motor",
                period_ms=10,
                deadline_ms=10,
                wcet_ms=3,
                memory_intensity=0.10,
            ),
            TaskModel(
                task_id=1,
                name="Sensor",
                period_ms=50,
                deadline_ms=50,
                wcet_ms=7,
                memory_intensity=0.20,
            ),
            TaskModel(
                task_id=2,
                name="Crypto",
                period_ms=500,
                deadline_ms=500,
                wcet_ms=100,
                memory_intensity=0.90,
            ),
            TaskModel(
                task_id=3,
                name="Vision",
                period_ms=20,
                deadline_ms=20,
                wcet_ms=6,
                memory_intensity=0.80,
            ),
        ]

    raise ValueError(f"Unknown workload profile: {profile}")

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
        
        # Check if COM port exists before starting build/test pipeline
        try:
            import serial
            import serial.tools.list_ports
        except ImportError:
            yield "data: Installing missing pyserial dependency...\n\n"
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pyserial"])
                import serial
                import serial.tools.list_ports
            except Exception as e:
                yield f"data: Error: Failed to install pyserial dependency: {str(e)}\n\n"
                yield "data: --- COMPLETED ---\n\n"
                return
        
        ports = [p.device.upper() for p in serial.tools.list_ports.comports()]
        selected_port = runtime_settings["COM_PORT"].upper()
        if selected_port not in ports:
            available = [p.device for p in serial.tools.list_ports.comports()]
            available_str = ", ".join(available) if available else "None"
            yield f"data: Error: The selected COM Port '{runtime_settings['COM_PORT']}' does not exist or is not connected!\n\n"
            yield f"data: Available system ports: {available_str}\n\n"
            yield f"data: Aborting build and test sequence.\n\n"
            yield "data: --- COMPLETED ---\n\n"
            return

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

@app.get("/api/results")
async def get_results():
    # Find all logs
    log_files = list(LOG_DIR.glob("*.log"))
    if not log_files:
        return {"status": "no logs found"}

    # Group by timestamp (YYYYMMDDTHHMMSS)
    runs = {}
    for f in log_files:
        # Expected: SchedName_Timestamp.log
        parts = f.stem.rsplit('_', 1)
        if len(parts) == 2:
            ts = parts[1]
            if ts not in runs: runs[ts] = []
            runs[ts].append(f)
            
    if not runs: return {"status": "no valid runs found"}
    
    # Get the latest run
    latest_ts = sorted(runs.keys())[-1]
    latest_logs = runs[latest_ts]
    
    results = {}
    for log_path in latest_logs:
        sched_name = log_path.stem.rsplit('_', 1)[0]
        # Clean duration suffix if present (e.g. "EDFSch_test_10s" -> "EDFSch_test")
        sched_name = re.sub(r'_\d+s$', '', sched_name)
        lines = log_path.read_text(encoding='utf-8').splitlines()
        
        task_map = {0: "Motor", 1: "Sensor", 2: "Crypto", 3: "Vision"}
        metrics = []
        
        latest_motor = {"sp": 100.0, "mv": 0.0, "out": 0.0}
        latest_sensor = {"raw": 0.0, "filtered": 0.0}
        
        motor_pattern = r"Task1_MotorControl! SP:\s*([\d\.-]+),\s*MV:\s*([\d\.-]+)\s*\(x1000\),\s*OUT:\s*([\d\.-]+)"
        sensor_pattern = r"Task2_SensorAcquisition! RAW:\s*([\d\.-]+),\s*FILTERED:\s*([\d\.-]+)"
        metrics_pattern = r"\[TS:\s*(\d+)\s*ms\]\s*\[Metrics\]\s*Task\s*(\d)\s*-\s*Prio:\s*\d+\s*\|\s*Jobs:\s*(\d+)\s*\|\s*Misses:\s*(\d+)\s*\|\s*DMR:\s*(\d+)%(?:\s*\|\s*Jitter:\s*([\d\.]+)\s*ms\s*\|\s*Contention:\s*(\d+)\s*ms\s*\|\s*Overhead:\s*(\d+)\s*cycles)?"
        
        for line in lines:
            # Parse motor params
            motor_match = re.search(motor_pattern, line)
            if motor_match:
                latest_motor["sp"] = float(motor_match.group(1))
                latest_motor["mv"] = float(motor_match.group(2)) / 1000.0
                latest_motor["out"] = float(motor_match.group(3)) / 1000.0
                continue
                
            # Parse sensor params
            sensor_match = re.search(sensor_pattern, line)
            if sensor_match:
                latest_sensor["raw"] = float(sensor_match.group(1))
                latest_sensor["filtered"] = float(sensor_match.group(2))
                continue
                
            # Parse metrics
            metrics_match = re.search(metrics_pattern, line)
            if metrics_match:
                ts = int(metrics_match.group(1))
                task_id = int(metrics_match.group(2))
                jobs = int(metrics_match.group(3))
                misses = int(metrics_match.group(4))
                dmr = int(metrics_match.group(5))
                
                pt = {
                    "ts": ts,
                    "task": task_map.get(task_id, f"Task{task_id}"),
                    "jobs": jobs,
                    "misses": misses,
                    "dmr": dmr
                }
                
                # Optionals for proposal-aligned evaluation metrics
                pt["jitter"] = float(metrics_match.group(6)) if metrics_match.group(6) is not None else 0.0
                pt["contention"] = int(metrics_match.group(7)) if metrics_match.group(7) is not None else 0
                pt["overhead"] = int(metrics_match.group(8)) if metrics_match.group(8) is not None else 0
                
                # Append task-specific parameters
                if task_id == 0:
                    pt["sp"] = latest_motor["sp"]
                    pt["mv"] = latest_motor["mv"]
                    pt["out"] = latest_motor["out"]
                elif task_id == 1:
                    pt["raw"] = latest_sensor["raw"]
                    pt["filtered"] = latest_sensor["filtered"]
                    
                metrics.append(pt)
                
        results[sched_name] = metrics
        
    return {"timestamp": latest_ts, "data": results}

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
    index_path = APP_DIR / "index.html"
    return index_path.read_text(encoding='utf-8')

@app.post("/api/aco/run")
async def run_aco_solver(params: ACORequest):
    try:
        tasks = get_tasks_for_workload_profile(params.workload_profile)
        hyperperiod_ms = compute_hyperperiod_ms(tasks)
        jobs = generate_jobs(tasks, hyperperiod_ms)

        solver_type = params.solver_type.strip().lower()

        if solver_type not in ["non_preemptive", "preemptive"]:
            return HTMLResponse(
                content=f"Invalid solver_type: {params.solver_type}",
                status_code=400,
            )

        if solver_type == "non_preemptive":
            # Baselines
            rms_result = run_baseline(
                name="Native / RMS baseline",
                jobs=jobs,
                picker=pick_rms_job,
            )

            edf_result = run_baseline(
                name="EDF baseline",
                jobs=jobs,
                picker=pick_edf_job,
            )

            ca_stats = ContextAwareStats()
            ca_picker = make_context_aware_picker(
                ContextAwareParams(
                    memory_alpha=1.0,
                    penalty_threshold=0.15,
                    safety_margin_ms=2,
                ),
                ca_stats,
            )

            ca_result = run_baseline(
                name="Context-Aware baseline",
                jobs=jobs,
                picker=ca_picker,
            )

            aco_params = ACOParams(
                ant_count=params.ant_count,
                iterations=params.iterations,
                pheromone_alpha=params.pheromone_alpha,
                heuristic_beta=params.heuristic_beta,
                evaporation_rate=params.evaporation_rate,
                deposit_weight=params.deposit_weight,
                lookahead_ms=params.lookahead_ms,
                memory_weight=params.memory_weight,
                idle_weight=params.idle_weight,
                seed=params.seed,
            )

            solver = ACOSolver(jobs=jobs, params=aco_params)
            aco_result = solver.run()

            return {
                "status": "success",
                "solver_type": "non_preemptive",
                "workload_profile": params.workload_profile,
                "hyperperiod_ms": hyperperiod_ms,
                "job_count": len(jobs),
                "task_set": task_set_summary_to_dict(tasks),
                "baselines": {
                    "rms": non_preemptive_evaluation_to_dict(rms_result.evaluation),
                    "edf": non_preemptive_evaluation_to_dict(edf_result.evaluation),
                    "context_aware": non_preemptive_evaluation_to_dict(ca_result.evaluation),
                },
                "aco": non_preemptive_aco_result_to_dict(aco_result),
                "context_aware_stats": ca_stats.__dict__,
            }

        # Preemptive mode
        rms_preemptive = run_preemptive_baseline(
            name="Preemptive Native / RMS baseline",
            jobs=jobs,
            picker=pick_rms_runtime_job,
        )

        edf_preemptive = run_preemptive_baseline(
            name="Preemptive EDF baseline",
            jobs=jobs,
            picker=pick_edf_runtime_job,
        )

        ca_preemptive_stats = ContextAwareStats()
        ca_runtime_picker = make_context_aware_runtime_picker(
            ContextAwareParams(
                memory_alpha=1.0,
                penalty_threshold=0.15,
                safety_margin_ms=2,
            ),
            ca_preemptive_stats,
        )

        ca_preemptive = run_preemptive_baseline(
            name="Preemptive Context-Aware baseline",
            jobs=jobs,
            picker=ca_runtime_picker,
        )

        preemptive_aco_params = PreemptiveACOParams(
            ant_count=params.ant_count,
            iterations=params.iterations,
            pheromone_alpha=params.pheromone_alpha,
            heuristic_beta=params.heuristic_beta,
            evaporation_rate=params.evaporation_rate,
            deposit_weight=params.deposit_weight,
            memory_weight=params.memory_weight,
            deadline_weight=params.deadline_weight,
            response_weight=params.response_weight,
            switch_weight=params.switch_weight,
            segment_contention_penalty_ms=params.segment_contention_penalty_ms,
            enable_segment_contention_time=params.enable_segment_contention_time,
            seed=params.seed,
        )

        preemptive_solver = PreemptiveACOSolver(
            jobs=jobs,
            params=preemptive_aco_params,
        )

        preemptive_aco_result = preemptive_solver.run()

        return {
            "status": "success",
            "solver_type": "preemptive",
            "workload_profile": params.workload_profile,
            "hyperperiod_ms": hyperperiod_ms,
            "job_count": len(jobs),
            "task_set": task_set_summary_to_dict(tasks),
            "baselines": {
                "rms": preemptive_evaluation_to_dict(rms_preemptive.evaluation),
                "edf": preemptive_evaluation_to_dict(edf_preemptive.evaluation),
                "context_aware": preemptive_evaluation_to_dict(ca_preemptive.evaluation),
            },
            "aco": preemptive_aco_result_to_dict(preemptive_aco_result),
            "context_aware_stats": ca_preemptive_stats.__dict__,
        }

    except Exception as e:
        print(f"Error running ACO solver: {e}")
        return HTMLResponse(content=str(e), status_code=500)

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)
