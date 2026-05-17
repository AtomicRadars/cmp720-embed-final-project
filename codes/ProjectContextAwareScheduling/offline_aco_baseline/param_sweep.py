from __future__ import annotations

from dataclasses import dataclass

from .scheduler_model import (
    compute_hyperperiod_ms,
    default_project_tasks,
    generate_jobs,
)

from .baselines import (
    ContextAwareParams,
    ContextAwareStats,
    make_context_aware_runtime_picker,
    pick_edf_runtime_job,
    run_preemptive_baseline,
)


@dataclass(frozen=True)
class SweepResult:
    alpha: float
    threshold: float
    safety_margin_ms: int

    deadline_misses: int
    total_lateness_ms: int

    segment_contention_events: int
    segment_contention_penalty_ms: int
    segment_smooth_memory_penalty: float

    avg_start_delay_ms: float
    max_start_delay_ms: int
    avg_response_time_ms: float
    max_response_time_ms: int

    scheduler_decisions: int
    preemptions: int

    swap_success: int
    penalty_triggered: int
    alternatives_lower_memory: int
    rejected_by_penalty_threshold: int
    rejected_by_candidate_slack: int
    rejected_by_safety_check: int
    rejected_no_alternative: int

    total_cost: float


def summarize_timing(evaluation) -> tuple[float, int, float, int]:
    completed = evaluation.scheduled_jobs

    if not completed:
        return 0.0, 0, 0.0, 0

    avg_start_delay = sum(job.start_delay_ms for job in completed) / len(completed)
    max_start_delay = max(job.start_delay_ms for job in completed)

    avg_response_time = sum(job.response_time_ms for job in completed) / len(completed)
    max_response_time = max(job.response_time_ms for job in completed)

    return avg_start_delay, max_start_delay, avg_response_time, max_response_time


def run_context_aware_sweep() -> list[SweepResult]:
    tasks = default_project_tasks()
    hyperperiod_ms = compute_hyperperiod_ms(tasks)
    jobs = generate_jobs(tasks, hyperperiod_ms)

    alpha_values = [1.0, 2.0, 5.0, 10.0]
    threshold_values = [0.15, 0.10, 0.05, 0.01]
    safety_values = [2, 1, 0]

    results: list[SweepResult] = []

    for alpha in alpha_values:
        for threshold in threshold_values:
            for safety in safety_values:
                params = ContextAwareParams(
                    memory_alpha=alpha,
                    penalty_threshold=threshold,
                    safety_margin_ms=safety,
                )

                stats = ContextAwareStats()
                picker = make_context_aware_runtime_picker(params, stats)

                result = run_preemptive_baseline(
                    name="Preemptive Context-Aware",
                    jobs=jobs,
                    picker=picker,
                )

                e = result.evaluation

                (
                    avg_start_delay,
                    max_start_delay,
                    avg_response_time,
                    max_response_time,
                ) = summarize_timing(e)

                results.append(
                    SweepResult(
                        alpha=alpha,
                        threshold=threshold,
                        safety_margin_ms=safety,

                        deadline_misses=e.deadline_misses,
                        total_lateness_ms=e.total_lateness_ms,

                        segment_contention_events=e.segment_contention_events,
                        segment_contention_penalty_ms=e.total_segment_contention_penalty_ms,
                        segment_smooth_memory_penalty=e.total_segment_smooth_memory_penalty,

                        avg_start_delay_ms=avg_start_delay,
                        max_start_delay_ms=max_start_delay,
                        avg_response_time_ms=avg_response_time,
                        max_response_time_ms=max_response_time,

                        scheduler_decisions=e.scheduler_decisions,
                        preemptions=e.preemptions,

                        swap_success=stats.swap_success,
                        penalty_triggered=stats.penalty_triggered,
                        alternatives_lower_memory=stats.alternatives_lower_memory,
                        rejected_by_penalty_threshold=stats.rejected_by_penalty_threshold,
                        rejected_by_candidate_slack=stats.rejected_by_candidate_slack,
                        rejected_by_safety_check=stats.rejected_by_safety_check,
                        rejected_no_alternative=stats.rejected_no_alternative,

                        total_cost=e.total_cost,
                    )
                )

    return results


def print_sweep_results(results: list[SweepResult]) -> None:
    print("\nContext-Aware parameter sweep / preemptive model")
    print("================================================")

    # Sort primarily by swap success descending, then cost ascending.
    sorted_results = sorted(
        results,
        key=lambda r: (
            -r.swap_success,
            r.deadline_misses,
            r.segment_contention_penalty_ms,
            r.segment_smooth_memory_penalty,
            r.total_cost,
        ),
    )

    header = (
        "alpha  thr    saf | miss late | segEv segPen segSmooth | "
        "swap trig altLow | rejThr rejSlack rejSafe rejNoAlt | cost"
    )
    print(header)
    print("-" * len(header))

    for r in sorted_results:
        print(
            f"{r.alpha:>5.1f} "
            f"{r.threshold:>5.2f} "
            f"{r.safety_margin_ms:>4} | "
            f"{r.deadline_misses:>4} "
            f"{r.total_lateness_ms:>4} | "
            f"{r.segment_contention_events:>5} "
            f"{r.segment_contention_penalty_ms:>6} "
            f"{r.segment_smooth_memory_penalty:>9.2f} | "
            f"{r.swap_success:>4} "
            f"{r.penalty_triggered:>4} "
            f"{r.alternatives_lower_memory:>6} | "
            f"{r.rejected_by_penalty_threshold:>6} "
            f"{r.rejected_by_candidate_slack:>8} "
            f"{r.rejected_by_safety_check:>7} "
            f"{r.rejected_no_alternative:>8} | "
            f"{r.total_cost:>8.2f}"
        )


def main() -> None:
    results = run_context_aware_sweep()
    print_sweep_results(results)


if __name__ == "__main__":
    main()