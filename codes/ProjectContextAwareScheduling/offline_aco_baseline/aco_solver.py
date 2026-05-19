# === ACO SOLVER === 
# pheromone[A][B] = Has choosing job B after job A proven successful in the past?

# offline_aco/aco_solver.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import random
import math

from .scheduler_model import (
    Job,
    ScheduleEvaluation,
    compute_contention_penalty_ms,
    compute_smooth_memory_penalty,
    evaluate_schedule,
)


START_NODE = -1


@dataclass(frozen=True)
class ACOParams:
    """
    Parameters for the Ant Colony Optimization solver.

    ant_count:
        Number of ants per iteration.

    iterations:
        Number of optimization iterations.

    pheromone_alpha:
        How strongly ants follow pheromone trails.

    heuristic_beta:
        How strongly ants follow the heuristic desirability.

    evaporation_rate:
        How much pheromone evaporates after each iteration.

    deposit_weight:
        How much pheromone is deposited by good solutions.

    lookahead_ms:
        Allows the offline solver to intentionally idle for near-future jobs.
        This matters in non-preemptive scheduling.

    memory_weight:
        How much the heuristic avoids memory-heavy transitions.

    idle_weight:
        How much the heuristic dislikes intentional idle time.

    seed:
        Random seed for reproducible experiments.
    """
    ant_count: int = 40
    iterations: int = 150

    pheromone_alpha: float = 1.0
    heuristic_beta: float = 3.0

    evaporation_rate: float = 0.20
    deposit_weight: float = 1000.0

    lookahead_ms: int = 20
    memory_weight: float = 2.0
    idle_weight: float = 0.20

    seed: int = 42


@dataclass
class ACOIterationRecord:
    iteration: int
    best_cost: float
    best_deadline_misses: int
    best_lateness_ms: int
    best_contention_penalty_ms: int
    best_smooth_memory_penalty: float


@dataclass
class ACOResult:
    best_sequence: list[Job]
    best_evaluation: ScheduleEvaluation
    history: list[ACOIterationRecord] = field(default_factory=list)


class ACOSolver:
    """
    Offline Ant Colony Optimization solver for non-preemptive job ordering.

    This is not a real-time runtime scheduler.
    It is an offline reference optimizer.

    It tries to construct a good job sequence over one hyperperiod.
    The sequence is then evaluated using evaluate_schedule().
    """

    def __init__(
        self,
        jobs: list[Job],
        params: Optional[ACOParams] = None,
    ) -> None:
        if not jobs:
            raise ValueError("ACO solver requires at least one job.")

        self.jobs = jobs
        self.params = params if params is not None else ACOParams()
        self.rng = random.Random(self.params.seed)

        self.job_count = len(jobs)

        # Pheromone matrix uses shifted index:
        # START_NODE (-1) -> row 0
        # job_id 0      -> row 1
        # job_id 1      -> row 2
        # ...
        self.pheromone = [
            [1.0 for _ in range(self.job_count)]
            for _ in range(self.job_count + 1)
        ]

        self.jobs_by_id = {job.job_id: job for job in jobs}

    def run(self) -> ACOResult:
        best_sequence: Optional[list[Job]] = None
        best_evaluation: Optional[ScheduleEvaluation] = None
        history: list[ACOIterationRecord] = []

        for iteration in range(1, self.params.iterations + 1):
            iteration_best_sequence: Optional[list[Job]] = None
            iteration_best_evaluation: Optional[ScheduleEvaluation] = None

            for _ in range(self.params.ant_count):
                sequence = self._construct_solution()
                evaluation = evaluate_schedule(sequence)

                if (
                    iteration_best_evaluation is None
                    or evaluation.total_cost < iteration_best_evaluation.total_cost
                ):
                    iteration_best_sequence = sequence
                    iteration_best_evaluation = evaluation

                if (
                    best_evaluation is None
                    or evaluation.total_cost < best_evaluation.total_cost
                ):
                    best_sequence = sequence
                    best_evaluation = evaluation

            if iteration_best_sequence is None or iteration_best_evaluation is None:
                raise RuntimeError("ACO iteration failed to construct a solution.")

            self._evaporate_pheromones()
            self._deposit_pheromones(iteration_best_sequence, iteration_best_evaluation)

            # Extra reinforcement for the global best; it stabilizes convergence a bit.
            if best_sequence is not None and best_evaluation is not None:
                self._deposit_pheromones(best_sequence, best_evaluation, scale=0.5)

            history.append(
                ACOIterationRecord(
                    iteration=iteration,
                    best_cost=best_evaluation.total_cost,
                    best_deadline_misses=best_evaluation.deadline_misses,
                    best_lateness_ms=best_evaluation.total_lateness_ms,
                    best_contention_penalty_ms=best_evaluation.total_contention_penalty_ms,
                    best_smooth_memory_penalty=best_evaluation.total_smooth_memory_penalty,
                )
            )

        if best_sequence is None or best_evaluation is None:
            raise RuntimeError("ACO failed to find a solution.")

        return ACOResult(
            best_sequence=best_sequence,
            best_evaluation=best_evaluation,
            history=history,
        )

    def _construct_solution(self) -> list[Job]:
        unscheduled = list(self.jobs)
        sequence: list[Job] = []

        current_time_ms = 0
        previous_job: Optional[Job] = None

        while unscheduled:
            candidates = self._get_candidates(unscheduled, current_time_ms)

            selected = self._choose_next_job(
                candidates=candidates,
                previous_job=previous_job,
                current_time_ms=current_time_ms,
            )

            sequence.append(selected)
            unscheduled.remove(selected)

            start_ms = max(current_time_ms, selected.release_ms)

            contention_penalty = compute_contention_penalty_ms(
                previous_job,
                selected,
            )

            current_time_ms = start_ms + selected.wcet_ms + contention_penalty
            previous_job = selected

        return sequence

    def _get_candidates(self, unscheduled: list[Job], current_time_ms: int) -> list[Job]:
        """
        Candidate set for the next ant decision.

        Normally a scheduler can only pick ready jobs.
        But because this is an offline non-preemptive optimizer, we also allow
        near-future jobs within a small lookahead window.

        This represents intentional idle time.

        Example:
            At t=13 ms, Crypto is ready but Motor_2 releases at t=20.
            A non-preemptive offline optimizer may intentionally wait until t=20
            instead of starting a long Crypto job immediately.
        """
        ready = [job for job in unscheduled if job.release_ms <= current_time_ms]

        lookahead_limit = current_time_ms + self.params.lookahead_ms
        near_future = [
            job
            for job in unscheduled
            if current_time_ms < job.release_ms <= lookahead_limit
        ]

        candidates = ready + near_future

        if candidates:
            return candidates

        # If nothing is ready or near-future, jump to the earliest future release.
        earliest_release = min(job.release_ms for job in unscheduled)
        return [job for job in unscheduled if job.release_ms == earliest_release]

    def _choose_next_job(
        self,
        candidates: list[Job],
        previous_job: Optional[Job],
        current_time_ms: int,
    ) -> Job:
        weights: list[float] = []

        for job in candidates:
            pheromone_value = self._get_pheromone(previous_job, job)
            heuristic_value = self._heuristic(previous_job, job, current_time_ms)

            weight = (
                math.pow(pheromone_value, self.params.pheromone_alpha)
                * math.pow(heuristic_value, self.params.heuristic_beta)
            )

            # Small guard against zero-probability collapse.
            weights.append(max(weight, 1e-12))

        total_weight = sum(weights)

        pick = self.rng.uniform(0.0, total_weight)
        cumulative = 0.0

        for job, weight in zip(candidates, weights):
            cumulative += weight
            if cumulative >= pick:
                return job

        return candidates[-1]

    def _heuristic(
        self,
        previous_job: Optional[Job],
        current_job: Job,
        current_time_ms: int,
    ) -> float:
        """
        Local desirability of selecting current_job next.

        Higher value means more desirable.

        Components:
        - Deadline urgency:
            Jobs with earlier deadlines are more attractive.

        - Feasibility:
            Jobs that can finish before their deadline are preferred.

        - Memory transition:
            Avoid memory-heavy transitions if possible.

        - Idle penalty:
            Intentional idle is allowed, but not free.

        - Short job preference:
            Slightly favors smaller jobs to avoid blocking many urgent jobs.
        """
        start_ms = max(current_time_ms, current_job.release_ms)
        idle_ms = start_ms - current_time_ms

        contention_penalty = compute_contention_penalty_ms(
            previous_job,
            current_job,
        )

        finish_ms = start_ms + current_job.wcet_ms + contention_penalty
        lateness_ms = max(0, finish_ms - current_job.deadline_ms)

        time_to_deadline = max(1, current_job.deadline_ms - current_time_ms)
        deadline_urgency = 1.0 / time_to_deadline

        # If a choice causes lateness, make it much less desirable.
        feasibility = 1.0 / (1.0 + 100.0 * lateness_ms)

        smooth_memory_penalty = compute_smooth_memory_penalty(
            previous_job,
            current_job,
        )
        memory_factor = 1.0 / (1.0 + self.params.memory_weight * smooth_memory_penalty)

        idle_factor = 1.0 / (1.0 + self.params.idle_weight * idle_ms)

        short_job_factor = 1.0 / (1.0 + 0.05 * current_job.wcet_ms)

        heuristic = (
            deadline_urgency
            * feasibility
            * memory_factor
            * idle_factor
            * short_job_factor
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
        sequence: list[Job],
        evaluation: ScheduleEvaluation,
        scale: float = 1.0,
    ) -> None:
        # Lower cost should deposit more pheromone.
        deposit = scale * self.params.deposit_weight / max(1.0, evaluation.total_cost)

        previous_job: Optional[Job] = None

        for job in sequence:
            row = self._row_index(previous_job)
            col = job.job_id
            self.pheromone[row][col] += deposit
            previous_job = job

    def _get_pheromone(self, previous_job: Optional[Job], current_job: Job) -> float:
        return self.pheromone[self._row_index(previous_job)][current_job.job_id]

    def _row_index(self, previous_job: Optional[Job]) -> int:
        if previous_job is None:
            return 0

        return previous_job.job_id + 1


def print_aco_result(result: ACOResult, first_jobs: int = 30) -> None:
    e = result.best_evaluation

    print("\nACO offline result")
    print("==================")
    print(f"  Deadline misses             : {e.deadline_misses}")
    print(f"  Total lateness              : {e.total_lateness_ms} ms")
    print(f"  Total contention penalty    : {e.total_contention_penalty_ms} ms")
    print(f"  Smooth memory penalty       : {e.total_smooth_memory_penalty:.2f}")
    print(f"  Total cost                  : {e.total_cost:.2f}")
    print(f"  Final finish time           : {e.total_time_ms} ms")

    print(f"\nFirst {first_jobs} jobs in ACO sequence:")
    for scheduled in e.scheduled_jobs[:first_jobs]:
        miss_mark = " MISS" if scheduled.deadline_missed else ""
        penalty_mark = f" +P{scheduled.contention_penalty_ms}" if scheduled.contention_penalty_ms else ""

        print(
            f"  {scheduled.order:02d}. {scheduled.job.label:<10} "
            f"start={scheduled.start_ms:>4} "
            f"finish={scheduled.finish_ms:>4} "
            f"deadline={scheduled.job.deadline_ms:>4}"
            f"{penalty_mark}{miss_mark}"
        )


def print_aco_history(result: ACOResult, every: int = 10) -> None:
    print("\nACO convergence history")
    print("=======================")

    for record in result.history:
        if record.iteration == 1 or record.iteration % every == 0 or record.iteration == result.history[-1].iteration:
            print(
                f"iter={record.iteration:>4} | "
                f"cost={record.best_cost:>12.2f} | "
                f"miss={record.best_deadline_misses:>3} | "
                f"late={record.best_lateness_ms:>5} | "
                f"cont={record.best_contention_penalty_ms:>4} | "
                f"smooth={record.best_smooth_memory_penalty:>7.2f}"
            )