from __future__ import annotations

from dataclasses import dataclass
from math import gcd
from typing import Iterable, Optional


@dataclass(frozen=True)
class TaskModel:
    """
    Periodic real-time task model.

    C = wcet_ms
    T = period_ms
    D = deadline_ms
    M = memory_intensity

    For this project, we use implicit deadlines by default:
        D = T
    """
    task_id: int
    name: str
    period_ms: int
    wcet_ms: int
    memory_intensity: float
    deadline_ms: Optional[int] = None

    @property
    def relative_deadline_ms(self) -> int:
        return self.deadline_ms if self.deadline_ms is not None else self.period_ms

    @property
    def utilization(self) -> float:
        return self.wcet_ms / self.period_ms


@dataclass(frozen=True)
class Job:
    """
    One released instance of a periodic task.

    Example:
        Motor task has T = 10 ms.
        In a 500 ms hyperperiod, it creates 50 jobs:
            Motor_0, Motor_1, ..., Motor_49
    """
    job_id: int
    task_id: int
    task_name: str
    release_ms: int
    deadline_ms: int
    wcet_ms: int
    memory_intensity: float
    instance_no: int

    @property
    def label(self) -> str:
        return f"{self.task_name}_{self.instance_no}"


@dataclass
class ScheduledJob:
    """
    A job after it has been placed into a concrete schedule.
    """
    order: int
    job: Job
    start_ms: int
    finish_ms: int
    contention_penalty_ms: int
    smooth_memory_penalty: float
    deadline_missed: bool
    lateness_ms: int


@dataclass
class ScheduleEvaluation:
    """
    Summary of a complete schedule.
    """
    scheduled_jobs: list[ScheduledJob]
    total_time_ms: int
    deadline_misses: int
    total_lateness_ms: int
    total_contention_penalty_ms: int
    total_smooth_memory_penalty: float
    total_cost: float

@dataclass
class RuntimeJob:
    """
    Runtime state of a job during preemptive simulation.

    A normal Job is immutable: release, deadline, WCET, memory intensity.
    RuntimeJob adds changing state:
        - remaining_ms
        - first_start_ms
        - finish_ms
        - whether contention penalty was already applied
    """
    job: Job
    remaining_ms: int
    started: bool = False
    first_start_ms: Optional[int] = None
    finish_ms: Optional[int] = None
    contention_penalty_ms: int = 0
    smooth_memory_penalty: float = 0.0


@dataclass(frozen=True)
class ExecutionSegment:
    """
    One continuous execution interval of a job.

    In a preemptive system, a job can have multiple segments:
        Crypto_0: 13 -> 20
        Crypto_0: 26 -> 40
        ...
    """
    job: Job
    start_ms: int
    end_ms: int


@dataclass
class PreemptiveScheduledJob:
    """
    Completion summary of a job in preemptive simulation.
    """
    order: int
    job: Job
    start_ms: int
    finish_ms: int
    contention_penalty_ms: int
    smooth_memory_penalty: float
    deadline_missed: bool
    lateness_ms: int

    # Simulation timing metrics
    start_delay_ms: int
    response_time_ms: int


@dataclass
class PreemptiveEvaluation:
    """
    Summary of a preemptive simulation run.

    execution_segments:
        Actual CPU execution intervals.

    scheduled_jobs:
        Job completion summaries.
    """
    scheduled_jobs: list[PreemptiveScheduledJob]
    execution_segments: list[ExecutionSegment]
    total_time_ms: int
    deadline_misses: int
    total_lateness_ms: int

    # Job-activation-level penalties
    total_contention_penalty_ms: int
    total_smooth_memory_penalty: float

    # Segment/context-switch-level penalties
    total_segment_contention_penalty_ms: int
    total_segment_smooth_memory_penalty: float
    segment_contention_events: int

    # Simulation overhead proxies
    scheduler_decisions: int
    preemptions: int


    total_cost: float


def lcm(a: int, b: int) -> int:
    return abs(a * b) // gcd(a, b)


def lcm_many(values: Iterable[int]) -> int:
    values = list(values)
    if not values:
        raise ValueError("Cannot compute LCM of an empty list.")

    result = values[0]
    for value in values[1:]:
        result = lcm(result, value)

    return result


def default_project_tasks() -> list[TaskModel]:
    """
    Mirrors the current embedded configuration.

    From TaskConfig.h / SchedulerTest.h:
        T1 Motor  : T=10 ms,  C=2 ms,  M=0.10
        T2 Sensor : T=50 ms,  C=5 ms,  M=0.20
        T3 Crypto : T=500 ms, C=75 ms, M=0.90
        T4 Vision : T=20 ms,  C=4 ms,  M=0.80

    These are nominal WCET values. The synthetic contention penalty is handled
    separately during schedule evaluation.
    """
    return [
        TaskModel(task_id=0, name="Motor",  period_ms=10,  wcet_ms=2,  memory_intensity=0.10),
        TaskModel(task_id=1, name="Sensor", period_ms=50,  wcet_ms=5,  memory_intensity=0.20),
        TaskModel(task_id=2, name="Crypto", period_ms=500, wcet_ms=75, memory_intensity=0.90),
        TaskModel(task_id=3, name="Vision", period_ms=20,  wcet_ms=4,  memory_intensity=0.80),
    ]


def compute_hyperperiod_ms(tasks: list[TaskModel]) -> int:
    return lcm_many(task.period_ms for task in tasks)


def generate_jobs(tasks: list[TaskModel], hyperperiod_ms: Optional[int] = None) -> list[Job]:
    """
    Generate all jobs released in one hyperperiod.

    A task with period T releases jobs at:
        0, T, 2T, ... < hyperperiod
    """
    if hyperperiod_ms is None:
        hyperperiod_ms = compute_hyperperiod_ms(tasks)

    jobs: list[Job] = []
    next_job_id = 0

    for task in tasks:
        instance_no = 0

        for release_ms in range(0, hyperperiod_ms, task.period_ms):
            deadline_ms = release_ms + task.relative_deadline_ms

            jobs.append(
                Job(
                    job_id=next_job_id,
                    task_id=task.task_id,
                    task_name=task.name,
                    release_ms=release_ms,
                    deadline_ms=deadline_ms,
                    wcet_ms=task.wcet_ms,
                    memory_intensity=task.memory_intensity,
                    instance_no=instance_no,
                )
            )

            next_job_id += 1
            instance_no += 1

    # Sort by release time first, then deadline, for deterministic display.
    jobs.sort(key=lambda job: (job.release_ms, job.deadline_ms, job.task_id, job.instance_no))
    return jobs


def compute_contention_penalty_ms(
    previous_job: Optional[Job],
    current_job: Job,
    contention_threshold: float = 0.5,
    contention_penalty_ms: int = 30,
) -> int:
    """
    Embedded synthetic contention model:

    If a memory-heavy job follows another memory-heavy job, the current job
    receives extra execution time.

    This mirrors the firmware logic:
        if last_memory_intensity > CONTENTION_THRESHOLD:
            SimulateHeavyWorkload(CONTENTION_PENALTY_MS)

    Here we additionally require current_job to be memory-heavy too, because
    the penalty represents high-memory after high-memory adjacency.
    """
    if previous_job is None:
        return 0

    previous_is_memory_heavy = previous_job.memory_intensity > contention_threshold
    current_is_memory_heavy = current_job.memory_intensity > contention_threshold

    if previous_is_memory_heavy and current_is_memory_heavy:
        return contention_penalty_ms

    return 0


def compute_smooth_memory_penalty(
    previous_job: Optional[Job],
    current_job: Job,
    memory_alpha: float = 1.0,
) -> float:
    """
    Smooth pairwise penalty from the proposal:

        P(prev, current) = alpha * M_prev * M_current

    This is not execution time by itself; it is a scoring metric.
    """
    if previous_job is None:
        return 0.0

    return memory_alpha * previous_job.memory_intensity * current_job.memory_intensity

def compute_segment_contention_penalty_ms(
    previous_job: Optional[Job],
    current_job: Job,
    *,
    contention_threshold: float = 0.5,
    segment_contention_penalty_ms: int = 2,
) -> int:
    """
    Segment-level contention model.

    This models context-switch/resume-level memory interference:
    if a memory-heavy segment follows another memory-heavy segment,
    we add a small overhead.

    Unlike the job-start penalty, this can happen multiple times in a
    preemptive schedule.
    """
    if previous_job is None:
        return 0

    # Do not penalize immediate continuation of the same job.
    if previous_job.job_id == current_job.job_id:
        return 0

    previous_is_memory_heavy = previous_job.memory_intensity > contention_threshold
    current_is_memory_heavy = current_job.memory_intensity > contention_threshold

    if previous_is_memory_heavy and current_is_memory_heavy:
        return segment_contention_penalty_ms

    return 0


def compute_segment_smooth_memory_penalty(
    previous_job: Optional[Job],
    current_job: Job,
    *,
    memory_alpha: float = 1.0,
) -> float:
    """
    Segment-level smooth transition metric.

    This is a metric, not necessarily execution time.
    """
    if previous_job is None:
        return 0.0

    if previous_job.job_id == current_job.job_id:
        return 0.0

    return memory_alpha * previous_job.memory_intensity * current_job.memory_intensity

def evaluate_schedule(
    job_sequence: list[Job],
    *,
    contention_threshold: float = 0.5,
    contention_penalty_ms: int = 30,
    memory_alpha: float = 1.0,
    deadline_miss_cost: float = 1_000_000.0,
    lateness_cost: float = 10_000.0,
    contention_cost: float = 1.0,
    smooth_memory_cost: float = 10.0,
) -> ScheduleEvaluation:
    """
    Evaluate a non-preemptive job sequence.

    Important:
    - A job cannot start before its release time.
    - If the CPU reaches a point where the next selected job is not released yet,
      the CPU idles until that job's release time.
    - Deadline miss is detected by finish_time > absolute_deadline.
    - Contention penalty increases execution time when memory-heavy jobs are adjacent.

    The total cost is designed so that deadline misses dominate memory penalties.
    """
    current_time_ms = 0
    previous_job: Optional[Job] = None

    scheduled: list[ScheduledJob] = []

    deadline_misses = 0
    total_lateness_ms = 0
    total_contention_penalty_ms = 0
    total_smooth_memory_penalty = 0.0

    for order, job in enumerate(job_sequence):
        # Respect release time. If selected too early, CPU idles.
        start_ms = max(current_time_ms, job.release_ms)

        contention_penalty = compute_contention_penalty_ms(
            previous_job,
            job,
            contention_threshold=contention_threshold,
            contention_penalty_ms=contention_penalty_ms,
        )

        smooth_penalty = compute_smooth_memory_penalty(
            previous_job,
            job,
            memory_alpha=memory_alpha,
        )

        effective_execution_ms = job.wcet_ms + contention_penalty
        finish_ms = start_ms + effective_execution_ms

        lateness_ms = max(0, finish_ms - job.deadline_ms)
        deadline_missed = lateness_ms > 0

        if deadline_missed:
            deadline_misses += 1
            total_lateness_ms += lateness_ms

        total_contention_penalty_ms += contention_penalty
        total_smooth_memory_penalty += smooth_penalty

        scheduled.append(
            ScheduledJob(
                order=order,
                job=job,
                start_ms=start_ms,
                finish_ms=finish_ms,
                contention_penalty_ms=contention_penalty,
                smooth_memory_penalty=smooth_penalty,
                deadline_missed=deadline_missed,
                lateness_ms=lateness_ms,
            )
        )

        current_time_ms = finish_ms
        previous_job = job

    total_cost = (
        deadline_miss_cost * deadline_misses
        + lateness_cost * total_lateness_ms
        + contention_cost * total_contention_penalty_ms
        + smooth_memory_cost * total_smooth_memory_penalty
    )

    return ScheduleEvaluation(
        scheduled_jobs=scheduled,
        total_time_ms=current_time_ms,
        deadline_misses=deadline_misses,
        total_lateness_ms=total_lateness_ms,
        total_contention_penalty_ms=total_contention_penalty_ms,
        total_smooth_memory_penalty=total_smooth_memory_penalty,
        total_cost=total_cost,
    )


def print_task_summary(tasks: list[TaskModel]) -> None:
    print("Task set:")
    total_utilization = 0.0

    for task in tasks:
        total_utilization += task.utilization
        print(
            f"  T{task.task_id} {task.name:<8} "
            f"T={task.period_ms:>4} ms, "
            f"D={task.relative_deadline_ms:>4} ms, "
            f"C={task.wcet_ms:>4} ms, "
            f"M={task.memory_intensity:.2f}, "
            f"U={task.utilization * 100:>5.1f}%"
        )

    print(f"Total nominal utilization: {total_utilization * 100:.1f}%")


def print_job_summary(jobs: list[Job], max_rows: int = 20) -> None:
    print(f"\nGenerated jobs: {len(jobs)}")
    print(f"Showing first {min(max_rows, len(jobs))} jobs:")

    for job in jobs[:max_rows]:
        print(
            f"  {job.label:<10} "
            f"release={job.release_ms:>4} ms, "
            f"deadline={job.deadline_ms:>4} ms, "
            f"C={job.wcet_ms:>3} ms, "
            f"M={job.memory_intensity:.2f}"
        )


"""
def main() -> None:
    tasks = default_project_tasks()
    hyperperiod_ms = compute_hyperperiod_ms(tasks)
    jobs = generate_jobs(tasks, hyperperiod_ms)

    print_task_summary(tasks)
    print(f"\nHyperperiod: {hyperperiod_ms} ms")
    print_job_summary(jobs)

    # Very naive baseline: simply execute jobs in release-time order.
    # This is not EDF yet. It is only a smoke test for the evaluator.
    evaluation = evaluate_schedule(jobs)

    print("\nSmoke-test schedule: release-time order")
    print(f"  Total finish time              : {evaluation.total_time_ms} ms")
    print(f"  Deadline misses                : {evaluation.deadline_misses}")
    print(f"  Total lateness                 : {evaluation.total_lateness_ms} ms")
    print(f"  Total contention penalty       : {evaluation.total_contention_penalty_ms} ms")
    print(f"  Total smooth memory penalty    : {evaluation.total_smooth_memory_penalty:.2f}")
    print(f"  Total cost                     : {evaluation.total_cost:.2f}")

    if evaluation.deadline_misses:
        print("\nFirst missed jobs:")
        shown = 0
        for scheduled_job in evaluation.scheduled_jobs:
            if scheduled_job.deadline_missed:
                print(
                    f"  {scheduled_job.job.label:<10} "
                    f"start={scheduled_job.start_ms:>4}, "
                    f"finish={scheduled_job.finish_ms:>4}, "
                    f"deadline={scheduled_job.job.deadline_ms:>4}, "
                    f"lateness={scheduled_job.lateness_ms:>4}"
                )
                shown += 1
                if shown >= 10:
                    break


if __name__ == "__main__":
    main()
"""