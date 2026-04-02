"""
i-TSAB Solver for Job Shop Scheduling Problem

Improved Tabu Search with Elite Set and Path Relinking.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple, Dict

from algorithms.bnb.graph import JSSPInstance

logger = logging.getLogger(__name__)


@dataclass
class JSSPSolution:
    """Represents a solution for JSSP."""
    schedule: List[List[int]]  # Machine assignments
    makespan: int = 0

    def copy(self) -> JSSPSolution:
        return JSSPSolution(schedule=[row[:] for row in self.schedule], makespan=self.makespan)


class ITSABSolver:
    """Improved Tabu Search with Elite Set and Path Relinking for JSSP."""

    def __init__(self, instance: JSSPInstance, config: ITSABConfig):
        self.instance = instance  # JSSP instance
        self.config = config
        self.best_solution: Optional[JSSPSolution] = None

    def _generate_initial_solution(self) -> JSSPSolution:
        """Generate initial solution using random or SPT heuristic."""
        if self.config.use_heuristic_init and random.random() < 0.5:
            # Use SPT (Shortest Processing Time) heuristic for half of initial solutions
            return self._generate_spt_solution()
        else:
            # Random schedule
            schedule = [[] for _ in range(self.instance.num_machines)]
            
            # Assign each job's operations to their machines
            for job in range(self.instance.num_jobs):
                for op in self.instance.operations[job]:
                    schedule[op.machine].append(job)
            
            # Shuffle each machine's schedule for diversity
            for m in range(self.instance.num_machines):
                random.shuffle(schedule[m])
            
            solution = JSSPSolution(schedule=schedule)
            solution.makespan = self._calculate_makespan(solution)
            return solution

    def _generate_spt_solution(self) -> JSSPSolution:
        """Generate initial solution using SPT (Shortest Processing Time) heuristic."""
        # Create machine sequences by SPT rule
        schedule = [[] for _ in range(self.instance.num_machines)]
        
        # For each machine, sort jobs by their operation duration on that machine
        for machine in range(self.instance.num_machines):
            job_durations = []
            for job in range(self.instance.num_jobs):
                # Find operation duration for this job on this machine
                duration = None
                for op in self.instance.operations[job]:
                    if op.machine == machine:
                        duration = op.duration
                        break
                if duration:
                    job_durations.append((job, duration))
            
            # Sort by duration (shortest first)
            job_durations.sort(key=lambda x: x[1])
            schedule[machine] = [job for job, _ in job_durations]
        
        solution = JSSPSolution(schedule=schedule)
        solution.makespan = self._calculate_makespan(solution)
        return solution
    
    def _generate_random_solution(self) -> JSSPSolution:
        """Generate pure random solution as fallback."""
        return self._generate_initial_solution()

        return start_times

    def _generate_neighbors(self, solution: JSSPSolution) -> List[JSSPSolution]:
        """Generate neighboring solutions using diverse strategies."""
        neighbors = []
        
        # Strategy 1: Critical block swaps (N5)
        critical_ops = self._find_critical_operations(solution)
        critical_blocks = self._find_critical_blocks(solution, critical_ops)
        
        for block in critical_blocks:
            if len(block) >= 2:
                machine = block[0][0]
                positions = [b[1] for b in block]
                
                # Generate swaps within block
                for i in range(len(positions)):
                    for j in range(i + 1, min(i + 4, len(positions))):
                        pos_i = positions[i]
                        pos_j = positions[j]
                        
                        new_schedule = [row[:] for row in solution.schedule]
                        new_schedule[machine][pos_i], new_schedule[machine][pos_j] = \
                            new_schedule[machine][pos_j], new_schedule[machine][pos_i]
                        
                        neighbor = JSSPSolution(schedule=new_schedule)
                        neighbor.makespan = self._calculate_makespan(neighbor)
                        neighbors.append(neighbor)
        
        # Strategy 2: Adjacent swaps on all machines (diverse exploration)
        for machine in range(self.instance.num_machines):
            schedule_len = len(solution.schedule[machine])
            if schedule_len >= 2:
                # Try adjacent swaps
                for i in range(schedule_len - 1):
                    new_schedule = [row[:] for row in solution.schedule]
                    new_schedule[machine][i], new_schedule[machine][i+1] = \
                        new_schedule[machine][i+1], new_schedule[machine][i]
                    
                    neighbor = JSSPSolution(schedule=new_schedule)
                    neighbor.makespan = self._calculate_makespan(neighbor)
                    neighbors.append(neighbor)
        
        # Strategy 3: Random swaps (escape local optima)
        attempts = 0
        target_neighbors = 25 - len(neighbors)
        while len(neighbors) < 25 and attempts < 30:
            new_schedule = [row[:] for row in solution.schedule]
            m = random.randint(0, self.instance.num_machines - 1)
            if len(new_schedule[m]) >= 2:
                i, j = random.sample(range(len(new_schedule[m])), 2)
                new_schedule[m][i], new_schedule[m][j] = new_schedule[m][j], new_schedule[m][i]
                neighbor = JSSPSolution(schedule=new_schedule)
                neighbor.makespan = self._calculate_makespan(neighbor)
                
                # Avoid exact duplicates
                is_duplicate = any(n.makespan == neighbor.makespan and n.schedule == neighbor.schedule 
                                   for n in neighbors)
                if not is_duplicate:
                    neighbors.append(neighbor)
            attempts += 1
        
        return neighbors

    def _find_critical_blocks(self, solution: JSSPSolution, critical_ops: Set[int]) -> List[List[Tuple[int, int]]]:
        """Find critical blocks: consecutive critical operations on same machine.
        Returns list of blocks, each block is [(machine, pos), ...]"""
        blocks = []
        
        for machine in range(self.instance.num_machines):
            current_block = []
            for pos, job in enumerate(solution.schedule[machine]):
                # Find operation
                op = None
                for operation in self.instance.operations[job]:
                    if operation.machine == machine:
                        op = operation
                        break
                if op and op.op_id in critical_ops:
                    current_block.append((machine, pos))
                else:
                    if len(current_block) >= 2:
                        blocks.append(current_block)
                    current_block = []
            
            if len(current_block) >= 2:
                blocks.append(current_block)
        
        return blocks

    def _calculate_makespan(self, solution: JSSPSolution) -> int:
        """Calculate makespan for a JSSP solution."""
        # solution.schedule[machine][position] = job_id
        # Need to compute start times for each operation
        
        # Initialize start times
        start_times = {}
        job_completion = {j: 0 for j in range(self.instance.num_jobs)}
        machine_completion = {m: 0 for m in range(self.instance.num_machines)}
        
        # For each machine, process operations in order
        for machine in range(self.instance.num_machines):
            current_time = 0
            for pos, job in enumerate(solution.schedule[machine]):
                # Find the operation for this job on this machine
                op = None
                for operation in self.instance.operations[job]:
                    if operation.machine == machine:
                        op = operation
                        break
                
                if op is None:
                    continue
                
                # Earliest start: max(job completion, machine completion)
                start_time = max(job_completion[job], machine_completion[machine])
                start_times[op.op_id] = start_time
                
                # Update completions
                finish_time = start_time + op.duration
                job_completion[job] = finish_time
                machine_completion[machine] = finish_time
        
        # Makespan is max completion time
        return max(job_completion.values())

    def _find_critical_operations(self, solution: JSSPSolution) -> Set[int]:
        """Find operations on the critical path (slack = 0)."""
        makespan = self._calculate_makespan(solution)
        
        # Calculate earliest start times (forward pass)
        earliest_start = self._calculate_earliest_starts(solution)
        earliest_finish = {op_id: earliest_start[op_id] + op.duration 
                          for op_id, op in enumerate(self.instance.all_ops)}
        
        # Calculate latest finish times (backward pass)
        latest_finish = {op.op_id: makespan for op in self.instance.all_ops}
        
        # Backward pass for jobs
        for job in range(self.instance.num_jobs):
            current_latest = makespan
            for op in reversed(self.instance.operations[job]):
                latest_finish[op.op_id] = current_latest
                current_latest -= op.duration
        
        # Backward pass for machines
        for machine in range(self.instance.num_machines):
            current_latest = makespan
            for pos in reversed(range(len(solution.schedule[machine]))):
                job = solution.schedule[machine][pos]
                op = None
                for operation in self.instance.operations[job]:
                    if operation.machine == machine:
                        op = operation
                        break
                if op:
                    latest_finish[op.op_id] = min(latest_finish[op.op_id], current_latest)
                    current_latest -= op.duration
        
        # Critical operations: slack = 0
        critical = set()
        for op in self.instance.all_ops:
            slack = latest_finish[op.op_id] - earliest_finish[op.op_id]
            if slack == 0:
                critical.add(op.op_id)
        
        return critical

    def _calculate_earliest_starts(self, solution: JSSPSolution) -> Dict[int, int]:
        """Calculate earliest start times for all operations."""
        start_times = {}
        job_completion = {j: 0 for j in range(self.instance.num_jobs)}
        machine_completion = {m: 0 for m in range(self.instance.num_machines)}
        
        for machine in range(self.instance.num_machines):
            current_time = 0
            for pos, job in enumerate(solution.schedule[machine]):
                op = None
                for operation in self.instance.operations[job]:
                    if operation.machine == machine:
                        op = operation
                        break
                
                if op is None:
                    continue
                
                start_time = max(job_completion[job], machine_completion[machine])
                start_times[op.op_id] = start_time
                
                finish_time = start_time + op.duration
                job_completion[job] = finish_time
                machine_completion[machine] = finish_time
        
        return start_times

    def _is_tabu(self, move: Tuple[int, int]) -> bool:
        """Check if a move is tabu."""
        return move in self.tabu_list

    def _add_to_tabu(self, move: Tuple[int, int]) -> None:
        """Add move to tabu list."""
        self.tabu_list.add(move)
        if len(self.tabu_list) > self.config.tabu_length:
            # Remove oldest (simple FIFO)
            self.tabu_list.pop()

    def RunTSAB(self, initial_solution: JSSPSolution, tabu_length: int, max_iter: int) -> JSSPSolution:
        """Run basic TSAB algorithm from initial solution with aspiration criterion."""
        current = initial_solution.copy()
        tabu_list = set()
        best = current.copy()
        
        for iteration in range(max_iter):
            candidates = self._generate_neighbors(current)
            
            # Separate admissible and tabu
            admissible = [c for c in candidates if not self._is_tabu_move(c, tabu_list)]
            tabu_candidates = [c for c in candidates if self._is_tabu_move(c, tabu_list)]
            
            # Aspiration criterion: accept tabu move if better than best known
            aspiration_moves = [c for c in tabu_candidates if c.makespan < best.makespan]
            admissible.extend(aspiration_moves)
            
            if not admissible:
                admissible = candidates
            
            if admissible:
                best_candidate = min(admissible, key=lambda x: x.makespan)
                current = best_candidate
                if current.makespan < best.makespan:
                    best = current.copy()
                
                # Add move to tabu
                move = self._get_move(current)
                tabu_list.add(move)
                if len(tabu_list) > tabu_length:
                    tabu_list.pop()
        
        return best

    def _is_tabu_move(self, solution: JSSPSolution, tabu_list: set) -> bool:
        """Check if the move to reach this solution is tabu."""
        move = self._get_move(solution)
        return move in tabu_list

    def GeneratePath(self, alpha: JSSPSolution, beta: JSSPSolution) -> List[JSSPSolution]:
        """Generate path of solutions between alpha and beta using true path relinking."""
        path = []
        current = alpha.copy()
        path.append(current)
        
        # Try to transform current solution towards beta
        max_steps = 25
        steps = 0
        
        while steps < max_steps and current.schedule != beta.schedule:
            best_neighbor = None
            best_makespan = float('inf')
            
            # Find best move to explore
            for machine in range(self.instance.num_machines):
                if len(current.schedule[machine]) < 2:
                    continue
                    
                for i in range(len(current.schedule[machine])):
                    for j in range(i + 1, len(current.schedule[machine])):
                        # Try swap
                        new_schedule = [row[:] for row in current.schedule]
                        new_schedule[machine][i], new_schedule[machine][j] = \
                            new_schedule[machine][j], new_schedule[machine][i]
                        
                        neighbor = JSSPSolution(schedule=new_schedule)
                        neighbor.makespan = self._calculate_makespan(neighbor)
                        
                        # Accept if better
                        if neighbor.makespan < best_makespan:
                            best_neighbor = neighbor
                            best_makespan = neighbor.makespan
            
            if best_neighbor:
                current = best_neighbor
                path.append(current.copy())
                steps += 1
            else:
                break
        
        # Also add beta if not already in path
        if current.schedule != beta.schedule:
            path.append(beta.copy())
        
        return path if len(path) > 1 else [alpha, beta]

    def solve(self) -> JSSPSolution:
        """Run the i-TSAB algorithm according to the pseudocode."""
        # Step 1: Initialize empty Elite Set
        ES = []
        
        # Step 2: Generate initial solutions
        for i in range(self.config.N_init):
            # b) Build initial solution x^0 randomly
            x0 = self._generate_initial_solution()
            
            # c) Local search: x = RunTSAB(x^0, L, MaxIter_init) with neighborhood N5
            x = self.RunTSAB(x0, self.config.tabu_length, self.config.MaxIter_init)
            
            # d) if x not in ES
            if not self._solution_in_ES(x, ES):
                # e) ES = ES ∪ {x}
                ES.append(x)
                
                # f) if |ES| > maxE
                if len(ES) > self.config.maxE:
                    # g) Remove worst solution from ES
                    worst_idx = max(range(len(ES)), key=lambda idx: ES[idx].makespan)
                    ES.pop(worst_idx)
        
        # Step 3: Initialize best solution x* = argmin f(x) in ES
        if ES:
            self.best_solution = min(ES, key=lambda sol: sol.makespan).copy()
        else:
            self.best_solution = self._generate_initial_solution()
        
        # Step 4: while Stop_max not reached
        iteration = 0
        while iteration < self.config.max_iterations:
            # Stage Path_Relinking
            if len(ES) >= 2:
                # Step 5: Randomly select pair (α, β) from ES
                alpha, beta = random.sample(ES, 2)
                
                # Step 6: Determine distance D(α, β)
                D = self.config.distance_func(alpha, beta)
                
                # Step 7: Generate guide solutions G = GeneratePath(α, β)
                G = self.GeneratePath(alpha, beta)
                
                # Stage Proper_Work
                # Step 8: for each guide solution x_m in G
                for x_m in G:
                    # Step 9: Deep search: x' = RunTSAB(x_m, L, MaxIter_deep) with N5
                    x_prime = self.RunTSAB(x_m, self.config.tabu_length, self.config.MaxIter_deep)
                    
                    # Step 10: if f(x') < f(x*)
                    if x_prime.makespan < self.best_solution.makespan:
                        # Step 11: Update best solution x* = x'
                        self.best_solution = x_prime.copy()
                    
                    # Step 13: if x' not in ES
                    if not self._solution_in_ES(x_prime, ES):
                        # Step 14: Update elite set ES = ES ∪ {x'}
                        ES.append(x_prime)
                        
                        # Step 15: if |ES| > maxE
                        if len(ES) > self.config.maxE:
                            # Step 16: Remove worst solution from ES
                            worst_idx = max(range(len(ES)), key=lambda idx: ES[idx].makespan)
                            ES.pop(worst_idx)
            
            iteration += 1
        
        return self.best_solution

    def _solution_in_ES(self, solution: JSSPSolution, ES: List[JSSPSolution]) -> bool:
        """Check if solution is already in Elite Set (by makespan equality for simplicity)."""
        return any(sol.makespan == solution.makespan for sol in ES)

    def _get_move(self, solution: JSSPSolution) -> Tuple[int, int]:
        """Extract the move that led to this solution (placeholder)."""
        # TODO: track actual moves
        return (0, 1)  # Dummy