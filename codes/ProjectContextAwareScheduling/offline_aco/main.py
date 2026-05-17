from __future__ import annotations

from .scheduler_model import (
    compute_hyperperiod_ms,
    default_project_tasks,
    generate_jobs,
    print_job_summary,
    print_task_summary,
)

from .baselines import (
    ContextAwareParams,
    ContextAwareStats,
    make_context_aware_picker,
    make_context_aware_runtime_picker,
    pick_edf_job,
    pick_edf_runtime_job,
    pick_rms_job,
    pick_rms_runtime_job,
    print_first_execution_segments,
    print_first_jobs,
    print_first_preemptive_completions,
    print_preemptive_result,
    print_result,
    run_baseline,
    run_preemptive_baseline,
)

from .param_sweep import (
    run_context_aware_sweep,
    print_sweep_results
)

def read_float_with_default(prompt: str, default: float) -> float:
    """
    Reads a float from user input.
    If the user presses Enter directly, returns the default value.
    """
    raw = input(f"{prompt} [default: {default}]: ").strip()

    if raw == "":
        print(f"  -> Using default value: {default}")
        return default

    try:
        return float(raw)
    except ValueError:
        print(f"  -> Invalid input '{raw}'. Using default value: {default}")
        return default


def read_int_with_default(prompt: str, default: int) -> int:
    """
    Reads an integer from user input.
    If the user presses Enter directly, returns the default value.
    """
    raw = input(f"{prompt} [default: {default}]: ").strip()

    if raw == "":
        print(f"  -> Using default value: {default}")
        return default

    try:
        return int(raw)
    except ValueError:
        print(f"  -> Invalid input '{raw}'. Using default value: {default}")
        return default


def read_context_aware_params() -> ContextAwareParams:
    print("\nContext-Aware Scheduler parameters")
    print("----------------------------------")
    print("Press Enter without typing anything to use the default value.\n")

    memory_alpha = read_float_with_default(
        "Memory alpha / pairwise penalty weight",
        1.0,
    )

    penalty_threshold = read_float_with_default(
        "Penalty threshold",
        0.15,
    )

    safety_margin_ms = read_int_with_default(
        "Safety margin in milliseconds",
        2,
    )

    params = ContextAwareParams(
        memory_alpha=memory_alpha,
        penalty_threshold=penalty_threshold,
        safety_margin_ms=safety_margin_ms,
    )

    print("\nSelected Context-Aware parameters:")
    print(f"  memory_alpha      = {params.memory_alpha}")
    print(f"  penalty_threshold = {params.penalty_threshold}")
    print(f"  safety_margin_ms  = {params.safety_margin_ms}")

    return params


def main() -> None:

    results = run_context_aware_sweep()
    print_sweep_results(results)

    """
    tasks = default_project_tasks()
    hyperperiod_ms = compute_hyperperiod_ms(tasks)
    jobs = generate_jobs(tasks, hyperperiod_ms)

    print_task_summary(tasks)
    print(f"\nHyperperiod: {hyperperiod_ms} ms")
    print_job_summary(jobs, max_rows=20)

    ca_params = read_context_aware_params()

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
    context_picker = make_context_aware_picker(ca_params, ca_stats)

    context_result = run_baseline(
        name="Context-Aware baseline",
        jobs=jobs,
        picker=context_picker,
    )

    print("\nBaseline results")
    print("================")
    print_result(rms_result)
    print_result(edf_result)
    print_result(context_result)

    print_first_jobs(edf_result, count=25)
    print_first_jobs(context_result, count=25)

    ca_stats.print_summary("Context-Aware stats / non-preemptive")

    print("\nPreemptive baseline results")
    print("===========================")

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
    context_runtime_picker = make_context_aware_runtime_picker(ca_params, ca_preemptive_stats)

    context_preemptive = run_preemptive_baseline(
        name="Preemptive Context-Aware baseline",
        jobs=jobs,
        picker=context_runtime_picker,
    )

    print_preemptive_result(rms_preemptive)
    print_preemptive_result(edf_preemptive)
    print_preemptive_result(context_preemptive)

    print_first_execution_segments(edf_preemptive, count=40)
    print_first_execution_segments(context_preemptive, count=40)

    print_first_preemptive_completions(edf_preemptive, count=25)
    print_first_preemptive_completions(context_preemptive, count=25)

    ca_preemptive_stats.print_summary("Context-Aware stats / preemptive")
    """

if __name__ == "__main__":
    main()