
import heapq
from functools import total_ordering
import copy
import time
import unittest
import random

class SearchStack:
    def __init__(self):
        self.stack = []

    def enqueue_all_steps(self, items):
        self.stack.extend(items)

    def dequeue_step(self):
        return self.stack.pop()

    def empty(self):
        return len(self.stack) == 0


@total_ordering
class WrappedPlanStep:
    def __init__(self, step):
        self.step = step

    def __lt__(self, other):
        return self.step.total_cost < other.step.total_cost

    def __eq__(self, other):
        return self.step.total_cost == other.step.total_cost


class HybridQueue:
    def __init__(self):
        self.heap = []
        self.next_pop = None

    def enqueue_all_steps(self, items):
        self.enqueue_all([WrappedPlanStep(item) for item in items])

    def dequeue_step(self):
        d = self.dequeue()
        if d: return d.step

    def empty(self):
        return len(self.heap) == 0 and self.next_pop is None

    def enqueue_all(self, items):
        if self.next_pop:
            assert False
        if len(items) > 0:
            for item in items[:-1]:
                heapq.heappush(self.heap, item)
            self.next_pop = items[-1]

    def dequeue(self):
        if self.next_pop:
            result = self.next_pop
            self.next_pop = None
            return result
        elif self.heap:
            return heapq.heappop(self.heap)
        
"""
This is a derived work of the Pyhop planner written by Dana Nau.

Alterations are authored by Gabriel Ferrer.

It incorporates the anytime planning algorithm from SHOP3
(https://github.com/shop-planner/shop3).

This software is adapted from:

Pyhop, version 1.2.2 -- a simple SHOP-like planner written in Python.
Author: Dana S. Nau, 2013.05.31

Copyright 2013 Dana S. Nau - http://www.cs.umd.edu/~nau

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

class State:
    def __init__(self, name):
        self.__name__ = name

    def __repr__(self):
        return '\n'.join([f"{self.__name__}.{name} = {val}" for (name, val) in vars(self).items() if name != "__name__"])


class TaskList:
    def __init__(self, options=None, completed=False):
        self.completed = completed
        if options and len(options) > 0:
            self.options = options if type(options[0]) == list else [options]
        else:
            self.options = [[]] if completed else []

    def __repr__(self):
        return f"TaskList(options={self.options},completed={self.completed})"

    def add_option(self, option):
        self.options.append(option)

    def add_options(self, option_seq):
        for option in option_seq:
            self.add_option(option)

    def complete(self):
        return self.completed

    def failed(self):
        return len(self.options) == 0 and not self.completed

    def in_progress(self):
        return not self.complete() and not self.failed()


class Planner:
    def __init__(self, verbose=0, copy_func=copy.deepcopy, cost_func=lambda state, step: 1):
        self.copy_func = copy_func
        self.cost_func = cost_func
        self.operators = {}
        self.methods = {}
        self.verbose = verbose

    def declare_operators(self, *op_list):
        self.operators.update({op.__name__:op for op in op_list})

    def declare_methods(self, *method_list):
        self.methods.update({method.__name__:method for method in method_list})

    def print_operators(self):
        print(f'OPERATORS: {", ".join(self.operators)}')

    def print_methods(self):
        print(f'METHODS: {", ".join(self.methods)}')

    def log(self, min_verbose, msg):
        if self.verbose >= min_verbose:
            print(msg)

    def log_state(self, min_verbose, msg, state):
        if self.verbose >= min_verbose:
            print(msg)
            print(state)

    def pyhop(self, state, tasks, verbose=0):
        for plan in self.pyhop_generator(state, tasks, verbose):
            if plan:
                return plan

    def anyhop(self, state, tasks, max_seconds=None, verbose=0, disable_branch_bound=False, enable_hybrid_queue=False):
        start_time = time.time()
        plan_times = []
        for plan in self.pyhop_generator(state, tasks, verbose, disable_branch_bound, yield_cost=True,
                                         enable_hybrid_queue=enable_hybrid_queue):
            elapsed_time = time.time() - start_time
            if max_seconds and elapsed_time > max_seconds:
                break
            if plan:
                plan_times.append((plan[0], plan[1], elapsed_time))
        return plan_times

    def pyhop_generator(self, state, tasks, verbose=0, disable_branch_bound=False, yield_cost=False, enable_hybrid_queue=False):
        self.verbose = verbose
        self.log(1, f"** anyhop, verbose={self.verbose}: **\n   state = {state.__name__}\n   tasks = {tasks}")
        options = HybridQueue() if enable_hybrid_queue else SearchStack()
        options.enqueue_all_steps([PlanStep([], tasks, state, self.copy_func, self.cost_func)])
        lowest_cost = None
        while not options.empty():
            candidate = options.dequeue_step()
            if disable_branch_bound or lowest_cost is None or candidate.total_cost < lowest_cost:
                self.log(2, f"depth {candidate.depth()} tasks {candidate.tasks}")
                self.log(3, f"plan: {candidate.plan}")
                if candidate.complete():
                    self.log(3, f"depth {candidate.depth()} returns plan {candidate.plan}")
                    self.log(1, f"** result = {candidate.plan}\n")
                    lowest_cost = candidate.total_cost
                    if yield_cost:
                        yield candidate.plan, candidate.total_cost
                    else:
                        yield candidate.plan
                else:
                    options.enqueue_all_steps(candidate.successors(self))
                    yield None
            else:
                yield None

    def anyhop_best(self, state, tasks, max_seconds=None, verbose=0):
        plans = self.anyhop(state, tasks, max_seconds, verbose)
        return plans[-1][0]

    def anyhop_stats(self, state, tasks, max_seconds=None, verbose=0):
        plans = self.anyhop(state, tasks, max_seconds, verbose)
        return [(len(plan), cost, time) for (plan, cost, time) in plans]


class PlanStep:
    def __init__(self, plan, tasks, state, copy_func, cost_func, current_cost=0, past_cost=0):
        self.copy_func = copy_func
        self.cost_func = cost_func
        self.plan = plan
        self.tasks = tasks
        self.state = state
        self.total_cost = past_cost + current_cost
        self.current_cost = current_cost

    def depth(self):
        return len(self.plan)

    def complete(self):
        return len(self.tasks) == 0

    def successors(self, planner):
        options = []
        self.add_operator_options(options, planner)
        self.add_method_options(options, planner)
        if len(options) == 0:
            planner.log(3, f"depth {self.depth()} returns failure")
        return options

    def add_operator_options(self, options, planner):
        next_task = self.next_task()
        if type(next_task[0]) == list:
            print(f"next_task: {next_task}")
        if next_task[0] in planner.operators:
            planner.log(3, f"depth {self.depth()} action {next_task}")
            operator = planner.operators[next_task[0]]
            newstate = operator(self.copy_func(self.state), *next_task[1:])
            planner.log_state(3, f"depth {self.depth()} new state:", newstate)
            if newstate:
                options.append(PlanStep(self.plan + [next_task], self.tasks[1:], newstate, self.copy_func, self.cost_func, past_cost=self.total_cost, current_cost=self.cost_func(self.state, next_task)))

    def add_method_options(self, options, planner):
        next_task = self.next_task()
        if next_task[0] in planner.methods:
            planner.log(3, f"depth {self.depth()} method instance {next_task}")
            method = planner.methods[next_task[0]]
            subtask_options = method(self.state, *next_task[1:])
            if subtask_options is not None:
                for subtasks in subtask_options.options:
                    planner.log(3, f"depth {self.depth()} new tasks: {subtasks}")
                    options.append(PlanStep(self.plan, subtasks + self.tasks[1:], self.state, self.copy_func, self.cost_func, past_cost=self.total_cost))

    def next_task(self):
        result = self.tasks[0]
        if type(result) is tuple:
            return result
        else:
            return tuple([result])



def forall(seq,cond):
    """True if cond(x) holds for all x in seq, otherwise False."""
    for x in seq:
        if not cond(x): return False
    return True


def find_if(cond,seq):
    """
    Return the first x in seq such that cond(x) holds, if there is one.
    Otherwise return None.
    """
    for x in seq:
        if cond(x):
            return x


class Oset:
    def __init__(self, items=None):
        self.items = {}
        if items:
            for item in items:
                self.add(item)

    def __eq__(self, other):
        return self.items == other.items

    def __repr__(self):
        return f'Oset({[item for item in self.items]})'

    def __contains__(self, item):
        return item in self.items

    def __len__(self):
        return len(self.items)

    def add(self, item):
        self.items[item] = None

    def get_first(self):
        for item in self.items:
            return item

    def discard(self, item):
        if item in self.items:
            del self.items[item]

    def __iter__(self):
        return self.items.__iter__()


def go(state, robot, start, end):
    if state.loc[robot] == start and end in state.connected[start] and end not in state.visited[robot]:
        state.loc[robot] = end
        state.visited[robot].add(end)
        return state


def find_route(state, robot, start, end):
    if start == end:
        return TaskList(completed=True)
    elif state.connected[start] == end:
        return TaskList([('go', robot, start, end)])
    else:
        return TaskList([[('go', robot, start, neighbor), 
                          ('find_route', robot, neighbor, end)] 
                         for neighbor in state.connected[start]])
    
def pick_up(state, robot, item):
    if state.loc[robot] == state.loc[item]:
        state.loc[item] = robot
        state.visited[robot] = set()
        return state
        
def put_down(state, robot, item):
    if state.loc[item] == robot:
        state.loc[item] = state.loc[robot]
        state.visited[robot] = set()
        return state
    
def deliver(state, item, end):
    if state.loc[item] == end:
        return TaskList(completed=True)
    else:
        return TaskList([('find_route', 'Robot1', state.loc['Robot1'], state.loc[item]),
                         ('pick_up', 'Robot1', item),
                         ('find_route', 'Robot1', state.loc[item], end), 
                         ('put_down', 'Robot1', item)])


