# offline_aco/preemptive_aco_solver.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import math
import random

from .scheduler_model import (
    Job,
    RuntimeJob,
    ExecutionSegment,
    PreemptiveScheduledJob,
    PreemptiveEvaluation,
    compute_contention_penalty_ms,
    compute_smooth_memory_penalty,
)

from .baselines import (
    get_released_runtime_jobs,
    get_next_release_time,
    compute_segment_contention_penalty_ms,
    compute_segment_smooth_memory_penalty,
)


@dataclass(frozen=True)
class PreemptiveACOParams:
    ant_count: int = 50
    iterations: int = 200

    pheromone_alpha: float = 1.0
    heuristic_beta: float = 3.0

    evaporation_rate: float = 0.20
    deposit_weight: float = 1000.0

    memory_weight: float = 3.0
    deadline_weight: float = 4.0
    response_weight: float = 0.05
    switch_weight: float = 0.10

    contention_threshold: float = 0.5
    job_start_contention_penalty_ms: int = 30
    segment_contention_penalty_ms: int = 2
    enable_segment_contention_time: bool = True

    deadline_miss_cost: float = 1_000_000.0
    lateness_cost: float = 10_000.0
    job_contention_cost: float = 1.0
    segment_contention_cost: float = 1.0
    smooth_memory_cost: float = 10.0
    segment_smooth_memory_cost: float = 10.0
    response_time_cost: float = 0.0

    seed: int = 42


@dataclass
class PreemptiveACOIterationRecord:
    iteration: int
    best_cost: float
    best_deadline_misses: int
    best_lateness_ms: int
    best_segment_contention_penalty_ms: int
    best_segment_smooth_memory_penalty: float
    best_total_time_ms: int


@dataclass
class PreemptiveACOResult:
    best_evaluation: PreemptiveEvaluation
    history: list[PreemptiveACOIterationRecord] = field(default_factory=list)


class PreemptiveACOSolver:
    """
    Event-based preemptive ACO solver.

    Each ant constructs a full preemptive execution trace.

    At every scheduling decision point:
      - released jobs with remaining work are candidates
      - the ant chooses one candidate using pheromone + heuristic
      - the chosen job runs until completion or the next release event
      - then a new decision is made

    Pheromone is stored on segment transitions:
        pheromone[previous_executed_job][current_job]

    This makes the solver directly optimize the same kind of memory transition
    behavior that segment-level metrics measure.
    """

    def __init__(
        self,
        jobs: list[Job],
        params: Optional[PreemptiveACOParams] = None,
    ) -> None:
        if not jobs:
            raise ValueError("Preemptive ACO solver requires at least one job.")

        self.jobs = jobs
        self.params = params if params is not None else PreemptiveACOParams()
        self.rng = random.Random(self.params.seed)

        self.job_count = len(jobs)

        # row 0 means START/no previous segment.
        # row job_id + 1 means previous executed segment was that job.
        # col job_id means current selected job.
        self.pheromone = [
            [1.0 for _ in range(self.job_count)]
            for _ in range(self.job_count + 1)
        ]

    def run(self) -> PreemptiveACOResult:
        best_evaluation: Optional[PreemptiveEvaluation] = None
        history: list[PreemptiveACOIterationRecord] = []

        for iteration in range(1, self.params.iterations + 1):
            iteration_best: Optional[PreemptiveEvaluation] = None

            for _ in range(self.params.ant_count):
                evaluation = self._construct_preemptive_solution()

                if iteration_best is None or evaluation.total_cost < iteration_best.total_cost:
                    iteration_best = evaluation

                if best_evaluation is None or evaluation.total_cost < best_evaluation.total_cost:
                    best_evaluation = evaluation

            if iteration_best is None:
                raise RuntimeError("Preemptive ACO failed to construct an iteration solution.")

            self._evaporate_pheromones()
            self._deposit_pheromones(iteration_best)

            if best_evaluation is not None:
                self._deposit_pheromones(best_evaluation, scale=0.5)

            history.append(
                PreemptiveACOIterationRecord(
                    iteration=iteration,
                    best_cost=best_evaluation.total_cost,
                    best_deadline_misses=best_evaluation.deadline_misses,
                    best_lateness_ms=best_evaluation.total_lateness_ms,
                    best_segment_contention_penalty_ms=best_evaluation.total_segment_contention_penalty_ms,
                    best_segment_smooth_memory_penalty=best_evaluation.total_segment_smooth_memory_penalty,
                    best_total_time_ms=best_evaluation.total_time_ms,
                )
            )

        if best_evaluation is None:
            raise RuntimeError("Preemptive ACO failed to find a solution.")

        return PreemptiveACOResult(
            best_evaluation=best_evaluation,
            history=history,
        )

    def _construct_preemptive_solution(self) -> PreemptiveEvaluation:
        runtime_jobs = [
            RuntimeJob(job=job, remaining_ms=job.wcet_ms)
            for job in self.jobs
        ]

        current_time_ms = 0

        last_completed_job: Optional[Job] = None
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

            selected = self._choose_runtime_job(
                ready_jobs=ready,
                current_time_ms=current_time_ms,
                last_executed_segment_job=last_executed_segment_job,
            )

            if (
                previously_selected_job_id is not None
                and previously_selected_job_id != selected.job.job_id
            ):
                preemptions += 1

            previously_selected_job_id = selected.job.job_id

            # Firmware-like job activation penalty: applied once per job.
            if not selected.started:
                selected.started = True
                selected.first_start_ms = current_time_ms

                selected.contention_penalty_ms = compute_contention_penalty_ms(
                    last_completed_job,
                    selected.job,
                    contention_threshold=self.params.contention_threshold,
                    contention_penalty_ms=self.params.job_start_contention_penalty_ms,
                )

                selected.smooth_memory_penalty = compute_smooth_memory_penalty(
                    last_completed_job,
                    selected.job,
                    memory_alpha=1.0,
                )

                selected.remaining_ms += selected.contention_penalty_ms

                total_contention_penalty_ms += selected.contention_penalty_ms
                total_smooth_memory_penalty += selected.smooth_memory_penalty

            # Segment-level metric/overhead: aligned with preemptive behavior.
            segment_smooth_penalty = compute_segment_smooth_memory_penalty(
                last_executed_segment_job,
                selected.job,
                memory_alpha=1.0,
            )

            segment_contention_penalty = compute_segment_contention_penalty_ms(
                last_executed_segment_job,
                selected.job,
                contention_threshold=self.params.contention_threshold,
                segment_contention_penalty_ms=self.params.segment_contention_penalty_ms,
            )

            total_segment_smooth_memory_penalty += segment_smooth_penalty

            if segment_contention_penalty > 0:
                segment_contention_events += 1
                total_segment_contention_penalty_ms += segment_contention_penalty

                if self.params.enable_segment_contention_time:
                    selected.remaining_ms += segment_contention_penalty

            next_release = get_next_release_time(runtime_jobs, current_time_ms)

            if next_release is None:
                run_for_ms = selected.remaining_ms
            else:
                run_for_ms = min(selected.remaining_ms, next_release - current_time_ms)

            if run_for_ms <= 0:
                # Defensive guard; normally this should not happen because next_release is > current_time.
                if next_release is not None:
                    current_time_ms = next_release
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

        total_response_time = sum(job.response_time_ms for job in completed_jobs)

        total_cost = (
            self.params.deadline_miss_cost * deadline_misses
            + self.params.lateness_cost * total_lateness_ms
            + self.params.job_contention_cost * total_contention_penalty_ms
            + self.params.segment_contention_cost * total_segment_contention_penalty_ms
            + self.params.smooth_memory_cost * total_smooth_memory_penalty
            + self.params.segment_smooth_memory_cost * total_segment_smooth_memory_penalty
            + self.params.response_time_cost * total_response_time
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

    def _choose_runtime_job(
        self,
        ready_jobs: list[RuntimeJob],
        current_time_ms: int,
        last_executed_segment_job: Optional[Job],
    ) -> RuntimeJob:
        weights: list[float] = []

        for runtime_job in ready_jobs:
            pheromone_value = self._get_pheromone(
                last_executed_segment_job,
                runtime_job.job,
            )

            heuristic_value = self._heuristic(
                runtime_job=runtime_job,
                current_time_ms=current_time_ms,
                last_executed_segment_job=last_executed_segment_job,
            )

            weight = (
                math.pow(pheromone_value, self.params.pheromone_alpha)
                * math.pow(heuristic_value, self.params.heuristic_beta)
            )

            weights.append(max(weight, 1e-12))

        total_weight = sum(weights)

        pick = self.rng.uniform(0.0, total_weight)
        cumulative = 0.0

        for runtime_job, weight in zip(ready_jobs, weights):
            cumulative += weight
            if cumulative >= pick:
                return runtime_job

        return ready_jobs[-1]

    def _heuristic(
        self,
        runtime_job: RuntimeJob,
        current_time_ms: int,
        last_executed_segment_job: Optional[Job],
    ) -> float:
        job = runtime_job.job

        time_to_deadline = max(1, job.deadline_ms - current_time_ms)
        deadline_urgency = 1.0 / time_to_deadline

        estimated_finish = current_time_ms + runtime_job.remaining_ms
        lateness_ms = max(0, estimated_finish - job.deadline_ms)

        feasibility = 1.0 / (1.0 + self.params.deadline_weight * 100.0 * lateness_ms)

        segment_smooth_penalty = compute_segment_smooth_memory_penalty(
            last_executed_segment_job,
            job,
            memory_alpha=1.0,
        )

        segment_memory_factor = 1.0 / (
            1.0 + self.params.memory_weight * segment_smooth_penalty
        )

        segment_contention_penalty = compute_segment_contention_penalty_ms(
            last_executed_segment_job,
            job,
            contention_threshold=self.params.contention_threshold,
            segment_contention_penalty_ms=self.params.segment_contention_penalty_ms,
        )

        segment_contention_factor = 1.0 / (
            1.0 + self.params.memory_weight * segment_contention_penalty
        )

        remaining_factor = 1.0 / (1.0 + 0.05 * runtime_job.remaining_ms)

        response_age = current_time_ms - job.release_ms
        response_factor = 1.0 / (1.0 + self.params.response_weight * response_age)

        # Mildly prefer continuing the same job to avoid excessive context switching,
        # but do not make it dominant.
        if last_executed_segment_job is not None and last_executed_segment_job.job_id == job.job_id:
            switch_factor = 1.0
        else:
            switch_factor = 1.0 / (1.0 + self.params.switch_weight)

        heuristic = (
            deadline_urgency
            * feasibility
            * segment_memory_factor
            * segment_contention_factor
            * remaining_factor
            * response_factor
            * switch_factor
        )

        return max(heuristic, 1e-12)

    def _evaporate_pheromones(self) -> None:
        keep_ratio = 1.0 - self.params.evaporation_rate

        for row in range(len(self.pheromone)):
            for col in range(len(self.pheromone[row])):
                self.pheromone[row][col] *= keep_ratio
                self.pheromone[row][col] = max(self.pheromone[row][col], 1e-6)

    def _deposit_pheromones(
        self,
        evaluation: PreemptiveEvaluation,
        scale: float = 1.0,
    ) -> None:
        deposit = scale * self.params.deposit_weight / max(1.0, evaluation.total_cost)

        previous_job: Optional[Job] = None

        for segment in evaluation.execution_segments:
            current_job = segment.job

            # Do not reinforce fake self-transitions too heavily.
            # Continuing the same job is already encouraged mildly by the heuristic.
            if previous_job is not None and previous_job.job_id == current_job.job_id:
                previous_job = current_job
                continue

            row = self._row_index(previous_job)
            col = current_job.job_id

            self.pheromone[row][col] += deposit
            previous_job = current_job

    def _get_pheromone(
        self,
        previous_job: Optional[Job],
        current_job: Job,
    ) -> float:
        return self.pheromone[self._row_index(previous_job)][current_job.job_id]

    def _row_index(self, previous_job: Optional[Job]) -> int:
        if previous_job is None:
            return 0

        return previous_job.job_id + 1


def print_preemptive_aco_result(result: PreemptiveACOResult, first_segments: int = 40) -> None:
    e = result.best_evaluation

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

    print("\nPreemptive ACO offline result")
    print("=============================")
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

    print(f"\nFirst {first_segments} execution segments in Preemptive ACO:")
    for i, segment in enumerate(e.execution_segments[:first_segments]):
        print(
            f"  {i:02d}. {segment.job.label:<10} "
            f"{segment.start_ms:>4} -> {segment.end_ms:>4}"
        )


def print_preemptive_aco_history(result: PreemptiveACOResult, every: int = 10) -> None:
    print("\nPreemptive ACO convergence history")
    print("==================================")

    last_iteration = result.history[-1].iteration if result.history else 0

    for record in result.history:
        if record.iteration == 1 or record.iteration % every == 0 or record.iteration == last_iteration:
            print(
                f"iter={record.iteration:>4} | "
                f"cost={record.best_cost:>10.2f} | "
                f"miss={record.best_deadline_misses:>3} | "
                f"late={record.best_lateness_ms:>4} | "
                f"segPen={record.best_segment_contention_penalty_ms:>4} | "
                f"segSmooth={record.best_segment_smooth_memory_penalty:>7.2f} | "
                f"finish={record.best_total_time_ms:>4}"
            )