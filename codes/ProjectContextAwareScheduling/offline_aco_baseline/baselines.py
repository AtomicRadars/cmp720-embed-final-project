from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .scheduler_model import (
    Job,
    RuntimeJob,
    ExecutionSegment,
    PreemptiveScheduledJob,
    PreemptiveEvaluation,
    ScheduleEvaluation,
    compute_contention_penalty_ms,
    compute_segment_contention_penalty_ms,
    compute_smooth_memory_penalty,
    compute_segment_smooth_memory_penalty,
    evaluate_schedule,
)


@dataclass(frozen=True)
class SchedulerResult:
    name: str
    sequence: list[Job]
    evaluation: ScheduleEvaluation

@dataclass(frozen=True)
class PreemptiveSchedulerResult:
    name: str
    evaluation: PreemptiveEvaluation


def get_released_runtime_jobs(runtime_jobs: list[RuntimeJob], current_time_ms: int) -> list[RuntimeJob]:
    return [
        runtime_job
        for runtime_job in runtime_jobs
        if runtime_job.remaining_ms > 0 and runtime_job.job.release_ms <= current_time_ms
    ]


def get_next_release_time(runtime_jobs: list[RuntimeJob], current_time_ms: int) -> Optional[int]:
    future_releases = [
        runtime_job.job.release_ms
        for runtime_job in runtime_jobs
        if runtime_job.remaining_ms > 0 and runtime_job.job.release_ms > current_time_ms
    ]

    if not future_releases:
        return None

    return min(future_releases)


def get_ready_jobs(unscheduled: list[Job], current_time_ms: int) -> list[Job]:
    return [job for job in unscheduled if job.release_ms <= current_time_ms]


def jump_to_next_release_if_needed(unscheduled: list[Job], current_time_ms: int) -> int:
    if not unscheduled:
        return current_time_ms

    next_release = min(job.release_ms for job in unscheduled)
    return max(current_time_ms, next_release)


def pick_rms_job(ready_jobs: list[Job], current_time_ms: int, last_job: Optional[Job]) -> Job:
    """
    RMS baseline:
    shorter task period means higher priority.

    Since Job does not directly store period, we infer fixed priority from task_id/name.
    For this project:
        Motor  T=10
        Vision T=20
        Sensor T=50
        Crypto T=500
    """
    priority_rank = {
        "Motor": 0,
        "Vision": 1,
        "Sensor": 2,
        "Crypto": 3,
    }

    return min(
        ready_jobs,
        key=lambda job: (
            priority_rank.get(job.task_name, 999),
            job.deadline_ms,
            job.release_ms,
            job.job_id,
        ),
    )

def pick_rms_runtime_job(
    ready_jobs: list[RuntimeJob],
    current_time_ms: int,
    last_completed_job: Optional[Job],
) -> RuntimeJob:
    priority_rank = {
        "Motor": 0,
        "Vision": 1,
        "Sensor": 2,
        "Crypto": 3,
    }

    return min(
        ready_jobs,
        key=lambda runtime_job: (
            priority_rank.get(runtime_job.job.task_name, 999),
            runtime_job.job.deadline_ms,
            runtime_job.job.release_ms,
            runtime_job.job.job_id,
        ),
    )


def pick_edf_job(ready_jobs: list[Job], current_time_ms: int, last_job: Optional[Job]) -> Job:
    """
    EDF baseline:
    ready job with earliest absolute deadline wins.
    """
    return min(
        ready_jobs,
        key=lambda job: (
            job.deadline_ms,
            job.release_ms,
            job.job_id,
        ),
    )

def pick_edf_runtime_job(
    ready_jobs: list[RuntimeJob],
    current_time_ms: int,
    last_completed_job: Optional[Job],
) -> RuntimeJob:
    return min(
        ready_jobs,
        key=lambda runtime_job: (
            runtime_job.job.deadline_ms,
            runtime_job.job.release_ms,
            runtime_job.job.job_id,
        ),
    )

@dataclass(frozen=True)
class ContextAwareParams:
    memory_alpha: float = 1.0
    penalty_threshold: float = 0.15
    safety_margin_ms: int = 2

@dataclass
class ContextAwareStats:
    calls: int = 0

    no_last_job: int = 0

    penalty_triggered: int = 0
    rejected_by_penalty_threshold: int = 0

    candidate_slack_ok: int = 0
    rejected_by_candidate_slack: int = 0

    alternatives_checked: int = 0
    alternatives_lower_memory: int = 0
    alternatives_slack_ok: int = 0

    swap_success: int = 0
    rejected_no_alternative: int = 0
    rejected_by_safety_check: int = 0

    def print_summary(self, title: str) -> None:
        print(f"\n{title}")
        print("-" * len(title))
        print(f"  calls                         : {self.calls}")
        print(f"  no last job                   : {self.no_last_job}")
        print(f"  penalty triggered             : {self.penalty_triggered}")
        print(f"  rejected by penalty threshold : {self.rejected_by_penalty_threshold}")
        print(f"  candidate slack OK            : {self.candidate_slack_ok}")
        print(f"  rejected by candidate slack   : {self.rejected_by_candidate_slack}")
        print(f"  alternatives checked          : {self.alternatives_checked}")
        print(f"  alternatives lower memory     : {self.alternatives_lower_memory}")
        print(f"  alternatives slack OK         : {self.alternatives_slack_ok}")
        print(f"  rejected by safety check      : {self.rejected_by_safety_check}")
        print(f"  rejected no alternative       : {self.rejected_no_alternative}")
        print(f"  swap success                  : {self.swap_success}")


def calculate_slack_ms(job: Job, current_time_ms: int) -> int:
    return job.deadline_ms - current_time_ms - job.wcet_ms


def pair_memory_penalty(previous_job: Optional[Job], current_job: Job, memory_alpha: float) -> float:
    if previous_job is None:
        return 0.0

    return memory_alpha * previous_job.memory_intensity * current_job.memory_intensity


def make_context_aware_picker(
    params: ContextAwareParams,
    stats: Optional[ContextAwareStats] = None,
) -> Callable[[list[Job], int, Optional[Job]], Job]:
    """
    Build a picker function that mirrors the embedded Context-Aware Scheduler.

    Base rule:
        Start from EDF candidate.

    Heuristic:
        If previous job and EDF candidate create high memory penalty,
        try to pick a lower-memory ready alternative, but only if the
        EDF candidate can safely tolerate the delay.
    """
    def pick_context_aware_job(
        ready_jobs: list[Job],
        current_time_ms: int,
        last_job: Optional[Job],
    ) -> Job:
        if stats is not None:
            stats.calls += 1

        ordered = sorted(
            ready_jobs,
            key=lambda job: (
                job.deadline_ms,
                job.release_ms,
                job.job_id,
            ),
        )

        candidate = ordered[0]

        if last_job is None:
            if stats is not None:
                stats.no_last_job += 1
            return candidate

        penalty = pair_memory_penalty(last_job, candidate, params.memory_alpha)

        if penalty <= params.penalty_threshold:
            if stats is not None:
                stats.rejected_by_penalty_threshold += 1
            return candidate

        if stats is not None:
            stats.penalty_triggered += 1

        cand_slack = calculate_slack_ms(candidate, current_time_ms)

        if cand_slack <= params.safety_margin_ms:
            if stats is not None:
                stats.rejected_by_candidate_slack += 1
            return candidate

        if stats is not None:
            stats.candidate_slack_ok += 1

        found_any_reasonable_alternative = False

        for alternative in ordered[1:]:
            if stats is not None:
                stats.alternatives_checked += 1

            if alternative.memory_intensity >= candidate.memory_intensity:
                continue

            if stats is not None:
                stats.alternatives_lower_memory += 1

            alt_slack = calculate_slack_ms(alternative, current_time_ms)

            if alt_slack <= 0:
                continue

            if stats is not None:
                stats.alternatives_slack_ok += 1

            found_any_reasonable_alternative = True

            if cand_slack > alternative.wcet_ms + params.safety_margin_ms:
                if stats is not None:
                    stats.swap_success += 1
                return alternative

            if stats is not None:
                stats.rejected_by_safety_check += 1

        if stats is not None and not found_any_reasonable_alternative:
            stats.rejected_no_alternative += 1

        return candidate

    return pick_context_aware_job


def calculate_runtime_slack_ms(runtime_job: RuntimeJob, current_time_ms: int) -> int:
    return runtime_job.job.deadline_ms - current_time_ms - runtime_job.remaining_ms


def make_context_aware_runtime_picker(
    params: ContextAwareParams,
    stats: Optional[ContextAwareStats] = None,
) -> Callable[[list[RuntimeJob], int, Optional[Job]], RuntimeJob]:
    """
    Segment-aware preemptive Context-Aware picker.

    Uses the last executed segment's job instead of the last completed job.
    This aligns the heuristic with segment-level memory transition metrics.
    """
    def pick_context_aware_runtime_job(
        ready_jobs: list[RuntimeJob],
        current_time_ms: int,
        last_executed_job: Optional[Job],
    ) -> RuntimeJob:
        if stats is not None:
            stats.calls += 1

        ordered = sorted(
            ready_jobs,
            key=lambda runtime_job: (
                runtime_job.job.deadline_ms,
                runtime_job.job.release_ms,
                runtime_job.job.job_id,
            ),
        )

        candidate = ordered[0]

        if last_executed_job is None:
            if stats is not None:
                stats.no_last_job += 1
            return candidate

        # Continuing the same job is not a memory transition.
        if last_executed_job.job_id == candidate.job.job_id:
            if stats is not None:
                stats.rejected_by_penalty_threshold += 1
            return candidate

        penalty = pair_memory_penalty(
            last_executed_job,
            candidate.job,
            params.memory_alpha,
        )

        if penalty <= params.penalty_threshold:
            if stats is not None:
                stats.rejected_by_penalty_threshold += 1
            return candidate

        if stats is not None:
            stats.penalty_triggered += 1

        cand_slack = calculate_runtime_slack_ms(candidate, current_time_ms)

        if cand_slack <= params.safety_margin_ms:
            if stats is not None:
                stats.rejected_by_candidate_slack += 1
            return candidate

        if stats is not None:
            stats.candidate_slack_ok += 1

        found_any_reasonable_alternative = False

        for alternative in ordered[1:]:
            if stats is not None:
                stats.alternatives_checked += 1

            if alternative.job.memory_intensity >= candidate.job.memory_intensity:
                continue

            if stats is not None:
                stats.alternatives_lower_memory += 1

            alt_slack = calculate_runtime_slack_ms(alternative, current_time_ms)

            if alt_slack <= 0:
                continue

            if stats is not None:
                stats.alternatives_slack_ok += 1

            found_any_reasonable_alternative = True

            if cand_slack > alternative.remaining_ms + params.safety_margin_ms:
                if stats is not None:
                    stats.swap_success += 1
                return alternative

            if stats is not None:
                stats.rejected_by_safety_check += 1

        if stats is not None and not found_any_reasonable_alternative:
            stats.rejected_no_alternative += 1

        return candidate

    return pick_context_aware_runtime_job


def simulate_priority_scheduler(
    jobs: list[Job],
    pick_job: Callable[[list[Job], int, Optional[Job]], Job],
    *,
    contention_threshold: float = 0.5,
    contention_penalty_ms: int = 30,
) -> list[Job]:
    """
    Generic non-preemptive online scheduler simulation.

    At each decision point:
      1. Find jobs whose release time has arrived.
      2. Pick one ready job using the scheduler rule.
      3. Advance simulated time by WCET + possible contention penalty.
      4. Repeat until all jobs are scheduled.

    This is not a perfect FreeRTOS trace simulator.
    It is a job-level ordering simulator for comparing scheduling policies.
    """
    unscheduled = list(jobs)
    sequence: list[Job] = []

    current_time_ms = 0
    last_job: Optional[Job] = None

    while unscheduled:
        ready = get_ready_jobs(unscheduled, current_time_ms)

        if not ready:
            current_time_ms = jump_to_next_release_if_needed(unscheduled, current_time_ms)
            ready = get_ready_jobs(unscheduled, current_time_ms)

        selected = pick_job(ready, current_time_ms, last_job)

        sequence.append(selected)
        unscheduled.remove(selected)

        penalty = compute_contention_penalty_ms(
            last_job,
            selected,
            contention_threshold=contention_threshold,
            contention_penalty_ms=contention_penalty_ms,
        )

        current_time_ms += selected.wcet_ms + penalty
        last_job = selected

    return sequence

def simulate_preemptive_scheduler(
    jobs: list[Job],
    pick_runtime_job: Callable[[list[RuntimeJob], int, Optional[Job]], RuntimeJob],
    *,
    contention_threshold: float = 0.5,
    contention_penalty_ms: int = 30,
    segment_contention_penalty_ms: int = 2,
    enable_segment_contention_time: bool = True,
    memory_alpha: float = 1.0,
    deadline_miss_cost: float = 1_000_000.0,
    lateness_cost: float = 10_000.0,
    contention_cost: float = 1.0,
    segment_contention_cost: float = 1.0,
    smooth_memory_cost: float = 10.0,
    segment_smooth_memory_cost: float = 10.0,
) -> PreemptiveEvaluation:
    """
    Event-based preemptive scheduler simulation.

    Difference from the earlier version:
      - Tracks segment-level memory transitions.
      - Optionally adds small segment-level contention overhead.
      - Tracks simulated scheduler decisions and preemptions.
      - Computes start delay and response time per job.
    """
    runtime_jobs = [
        RuntimeJob(job=job, remaining_ms=job.wcet_ms)
        for job in jobs
    ]

    current_time_ms = 0

    # Last completed job is close to the firmware's GetLastExecuted... model.
    last_completed_job: Optional[Job] = None

    # Last executed segment is a stronger preemptive/cache-interference model.
    last_executed_segment_job: Optional[Job] = None

    execution_segments: list[ExecutionSegment] = []
    completed_jobs: list[PreemptiveScheduledJob] = []

    total_contention_penalty_ms = 0
    total_smooth_memory_penalty = 0.0

    total_segment_contention_penalty_ms = 0
    total_segment_smooth_memory_penalty = 0.0
    segment_contention_events = 0

    total_lateness_ms = 0
    deadline_misses = 0
    completion_order = 0

    scheduler_decisions = 0
    preemptions = 0
    previously_selected_job_id: Optional[int] = None

    while any(runtime_job.remaining_ms > 0 for runtime_job in runtime_jobs):
        ready = get_released_runtime_jobs(runtime_jobs, current_time_ms)

        if not ready:
            next_release = get_next_release_time(runtime_jobs, current_time_ms)
            if next_release is None:
                break

            current_time_ms = next_release
            ready = get_released_runtime_jobs(runtime_jobs, current_time_ms)

        scheduler_decisions += 1
        selected = pick_runtime_job(ready, current_time_ms, last_executed_segment_job)

        if (
            previously_selected_job_id is not None
            and previously_selected_job_id != selected.job.job_id
        ):
            preemptions += 1

        previously_selected_job_id = selected.job.job_id

        # Job-activation penalty: applied only once when a job starts for the first time.
        if not selected.started:
            selected.started = True
            selected.first_start_ms = current_time_ms

            selected.contention_penalty_ms = compute_contention_penalty_ms(
                last_completed_job,
                selected.job,
                contention_threshold=contention_threshold,
                contention_penalty_ms=contention_penalty_ms,
            )

            selected.smooth_memory_penalty = compute_smooth_memory_penalty(
                last_completed_job,
                selected.job,
                memory_alpha,
            )

            selected.remaining_ms += selected.contention_penalty_ms

            total_contention_penalty_ms += selected.contention_penalty_ms
            total_smooth_memory_penalty += selected.smooth_memory_penalty

        # Segment-level transition metric/overhead.
        segment_smooth_penalty = compute_segment_smooth_memory_penalty(
            last_executed_segment_job,
            selected.job,
            memory_alpha=memory_alpha,
        )

        segment_contention_penalty = compute_segment_contention_penalty_ms(
            last_executed_segment_job,
            selected.job,
            contention_threshold=contention_threshold,
            segment_contention_penalty_ms=segment_contention_penalty_ms,
        )

        total_segment_smooth_memory_penalty += segment_smooth_penalty

        if segment_contention_penalty > 0:
            segment_contention_events += 1
            total_segment_contention_penalty_ms += segment_contention_penalty

            if enable_segment_contention_time:
                # This models small cache/memory reload overhead caused by switching
                # from one memory-heavy job to another.
                selected.remaining_ms += segment_contention_penalty

        next_release = get_next_release_time(runtime_jobs, current_time_ms)

        if next_release is None:
            run_for_ms = selected.remaining_ms
        else:
            time_until_next_release = next_release - current_time_ms
            run_for_ms = min(selected.remaining_ms, time_until_next_release)

        if run_for_ms <= 0:
            current_time_ms = next_release if next_release is not None else current_time_ms
            continue

        segment_start = current_time_ms
        segment_end = current_time_ms + run_for_ms

        execution_segments.append(
            ExecutionSegment(
                job=selected.job,
                start_ms=segment_start,
                end_ms=segment_end,
            )
        )

        selected.remaining_ms -= run_for_ms
        current_time_ms = segment_end
        last_executed_segment_job = selected.job

        if selected.remaining_ms == 0:
            selected.finish_ms = current_time_ms

            start_ms = (
                selected.first_start_ms
                if selected.first_start_ms is not None
                else selected.finish_ms
            )

            lateness_ms = max(0, selected.finish_ms - selected.job.deadline_ms)
            deadline_missed = lateness_ms > 0

            if deadline_missed:
                deadline_misses += 1
                total_lateness_ms += lateness_ms

            start_delay_ms = start_ms - selected.job.release_ms
            response_time_ms = selected.finish_ms - selected.job.release_ms

            completed_jobs.append(
                PreemptiveScheduledJob(
                    order=completion_order,
                    job=selected.job,
                    start_ms=start_ms,
                    finish_ms=selected.finish_ms,
                    contention_penalty_ms=selected.contention_penalty_ms,
                    smooth_memory_penalty=selected.smooth_memory_penalty,
                    deadline_missed=deadline_missed,
                    lateness_ms=lateness_ms,
                    start_delay_ms=start_delay_ms,
                    response_time_ms=response_time_ms,
                )
            )

            completion_order += 1
            last_completed_job = selected.job

    total_cost = (
        deadline_miss_cost * deadline_misses
        + lateness_cost * total_lateness_ms
        + contention_cost * total_contention_penalty_ms
        + segment_contention_cost * total_segment_contention_penalty_ms
        + smooth_memory_cost * total_smooth_memory_penalty
        + segment_smooth_memory_cost * total_segment_smooth_memory_penalty
    )

    return PreemptiveEvaluation(
        scheduled_jobs=completed_jobs,
        execution_segments=execution_segments,
        total_time_ms=current_time_ms,
        deadline_misses=deadline_misses,
        total_lateness_ms=total_lateness_ms,
        total_contention_penalty_ms=total_contention_penalty_ms,
        total_smooth_memory_penalty=total_smooth_memory_penalty,
        total_segment_contention_penalty_ms=total_segment_contention_penalty_ms,
        total_segment_smooth_memory_penalty=total_segment_smooth_memory_penalty,
        segment_contention_events=segment_contention_events,
        scheduler_decisions=scheduler_decisions,
        preemptions=preemptions,
        total_cost=total_cost,
    )

def run_baseline(
    name: str,
    jobs: list[Job],
    picker: Callable[[list[Job], int, Optional[Job]], Job],
) -> SchedulerResult:
    sequence = simulate_priority_scheduler(jobs, picker)
    evaluation = evaluate_schedule(sequence)
    return SchedulerResult(name=name, sequence=sequence, evaluation=evaluation)

def run_preemptive_baseline(
    name: str,
    jobs: list[Job],
    picker: Callable[[list[RuntimeJob], int, Optional[Job]], RuntimeJob],
) -> PreemptiveSchedulerResult:
    evaluation = simulate_preemptive_scheduler(jobs, picker)
    return PreemptiveSchedulerResult(name=name, evaluation=evaluation)

def print_result(result: SchedulerResult) -> None:
    e = result.evaluation

    print(f"\n{result.name}")
    print("-" * len(result.name))
    print(f"  Deadline misses             : {e.deadline_misses}")
    print(f"  Total lateness              : {e.total_lateness_ms} ms")
    print(f"  Total contention penalty    : {e.total_contention_penalty_ms} ms")
    print(f"  Smooth memory penalty       : {e.total_smooth_memory_penalty:.2f}")
    print(f"  Total cost                  : {e.total_cost:.2f}")
    print(f"  Final finish time           : {e.total_time_ms} ms")


def print_first_jobs(result: SchedulerResult, count: int = 20) -> None:
    print(f"\nFirst {count} scheduled jobs for {result.name}:")

    for scheduled in result.evaluation.scheduled_jobs[:count]:
        miss_mark = " MISS" if scheduled.deadline_missed else ""
        penalty_mark = f" +P{scheduled.contention_penalty_ms}" if scheduled.contention_penalty_ms else ""

        print(
            f"  {scheduled.order:02d}. {scheduled.job.label:<10} "
            f"start={scheduled.start_ms:>4} "
            f"finish={scheduled.finish_ms:>4} "
            f"deadline={scheduled.job.deadline_ms:>4}"
            f"{penalty_mark}{miss_mark}"
        )


def print_preemptive_result(result: PreemptiveSchedulerResult) -> None:
    e = result.evaluation

    completed = e.scheduled_jobs

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

    print(f"\n{result.name}")
    print("-" * len(result.name))
    print(f"  Deadline misses                  : {e.deadline_misses}")
    print(f"  Total lateness                   : {e.total_lateness_ms} ms")

    print(f"  Job-start contention penalty     : {e.total_contention_penalty_ms} ms")
    print(f"  Job-start smooth memory penalty  : {e.total_smooth_memory_penalty:.2f}")

    print(f"  Segment contention events        : {e.segment_contention_events}")
    print(f"  Segment contention penalty       : {e.total_segment_contention_penalty_ms} ms")
    print(f"  Segment smooth memory penalty    : {e.total_segment_smooth_memory_penalty:.2f}")

    print(f"  Scheduler decisions              : {e.scheduler_decisions}")
    print(f"  Preemptions/context switches     : {e.preemptions}")

    print(f"  Avg start delay                  : {avg_start_delay:.2f} ms")
    print(f"  Max start delay                  : {max_start_delay} ms")
    print(f"  Avg response time                : {avg_response_time:.2f} ms")
    print(f"  Max response time                : {max_response_time} ms")

    print(f"  Total cost                       : {e.total_cost:.2f}")
    print(f"  Final finish time                : {e.total_time_ms} ms")


def print_first_preemptive_completions(result: PreemptiveSchedulerResult, count: int = 20) -> None:
    print(f"\nFirst {count} completed jobs for {result.name}:")

    for scheduled in result.evaluation.scheduled_jobs[:count]:
        miss_mark = " MISS" if scheduled.deadline_missed else ""
        penalty_mark = f" +P{scheduled.contention_penalty_ms}" if scheduled.contention_penalty_ms else ""

        print(
            f"  {scheduled.order:02d}. {scheduled.job.label:<10} "
            f"release={scheduled.job.release_ms:>4} "
            f"first_start={scheduled.start_ms:>4} "
            f"finish={scheduled.finish_ms:>4} "
            f"deadline={scheduled.job.deadline_ms:>4} "
            f"delay={scheduled.start_delay_ms:>3} "
            f"resp={scheduled.response_time_ms:>3}"
            f"{penalty_mark}{miss_mark}"
        )

def print_first_execution_segments(result: PreemptiveSchedulerResult, count: int = 30) -> None:
    print(f"\nFirst {count} execution segments for {result.name}:")

    for i, segment in enumerate(result.evaluation.execution_segments[:count]):
        print(
            f"  {i:02d}. {segment.job.label:<10} "
            f"{segment.start_ms:>4} -> {segment.end_ms:>4}"
        )

