"""Multi-area grid-frequency dynamics with constrained fast-frequency response."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class Grid:
    nominal_hz: float = 60.0
    dt: float = 0.01
    inertia: tuple[float, ...] = (4.5, 5.2, 3.9)
    damping: tuple[float, ...] = (1.0, 1.15, 0.9)
    governor_gain: tuple[float, ...] = (0.24, 0.22, 0.26)
    governor_tau: tuple[float, ...] = (0.7, 0.85, 0.65)
    tie_strength: float = 0.055
    battery_limit: tuple[float, ...] = (0.08, 0.07, 0.06)
    battery_tau: float = 0.09
    battery_energy_limit: tuple[float, ...] = (0.45, 0.40, 0.35)
    battery_droop: float = 0.24
    synthetic_inertia: float = 0.07


@dataclass(frozen=True)
class State:
    time: float
    frequency: tuple[float, ...]
    angle: tuple[float, ...]
    mechanical_power: tuple[float, ...]
    battery_power: tuple[float, ...]
    battery_energy: tuple[float, ...]
    rocof: tuple[float, ...]


def initial_state(areas: int = 3) -> State:
    zeros = (0.0,) * areas
    return State(0.0, zeros, zeros, zeros, zeros, zeros, zeros)


def _clip(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def _tie_flows(angles: tuple[float, ...], strength: float) -> tuple[float, ...]:
    flows = [0.0] * len(angles)
    for left in range(len(angles) - 1):
        flow = strength * (angles[left] - angles[left + 1])
        flows[left] += flow
        flows[left + 1] -= flow
    return tuple(flows)


def step(
    state: State,
    grid: Grid,
    disturbance: tuple[float, ...],
    controlled: bool = True,
) -> State:
    areas = len(grid.inertia)
    ties = _tie_flows(state.angle, grid.tie_strength)
    battery: list[float] = []
    energy: list[float] = []
    for i in range(areas):
        target = 0.0
        if controlled:
            target = _clip(
                -grid.battery_droop * state.frequency[i]
                - grid.synthetic_inertia * state.rocof[i],
                grid.battery_limit[i],
            )
            if abs(state.battery_energy[i]) >= grid.battery_energy_limit[i] and (
                target * state.battery_energy[i] > 0
            ):
                target = 0.0
        command = state.battery_power[i] + grid.dt * (
            target - state.battery_power[i]
        ) / grid.battery_tau
        command = _clip(command, grid.battery_limit[i])
        next_energy = _clip(
            state.battery_energy[i] + command * grid.dt,
            grid.battery_energy_limit[i],
        )
        battery.append(command)
        energy.append(next_energy)

    mechanical: list[float] = []
    rocof: list[float] = []
    frequency: list[float] = []
    angle: list[float] = []
    for i in range(areas):
        governor_target = -grid.governor_gain[i] * state.frequency[i]
        mech = state.mechanical_power[i] + grid.dt * (
            governor_target - state.mechanical_power[i]
        ) / grid.governor_tau[i]
        imbalance = (
            mech
            + battery[i]
            - disturbance[i]
            - grid.damping[i] * state.frequency[i]
            - ties[i]
        )
        derivative = grid.nominal_hz * imbalance / (2.0 * grid.inertia[i])
        freq = state.frequency[i] + grid.dt * derivative
        theta = state.angle[i] + grid.dt * 2.0 * math.pi * freq
        mechanical.append(mech)
        rocof.append(derivative)
        frequency.append(freq)
        angle.append(theta)
    return State(
        state.time + grid.dt,
        tuple(frequency),
        tuple(angle),
        tuple(mechanical),
        tuple(battery),
        tuple(energy),
        tuple(rocof),
    )


def simulate(
    duration: float = 20.0,
    seed: int = 7,
    controlled: bool = True,
    event_time: float = 1.0,
    loss_pu: float = 0.12,
) -> list[State]:
    grid = Grid()
    rng = random.Random(seed)
    state = initial_state(len(grid.inertia))
    states = [state]
    for _ in range(int(duration / grid.dt)):
        load = loss_pu if state.time >= event_time else 0.0
        noise = tuple(rng.gauss(0.0, 0.00012) for _ in grid.inertia)
        disturbance = (load + noise[0], noise[1], noise[2])
        state = step(state, grid, disturbance, controlled)
        states.append(state)
    return states


def center_of_inertia_frequency(state: State, grid: Grid | None = None) -> float:
    grid = grid or Grid()
    weight = sum(grid.inertia)
    return sum(h * f for h, f in zip(grid.inertia, state.frequency)) / weight


def summarize(states: list[State]) -> dict[str, float]:
    grid = Grid()
    coi = [center_of_inertia_frequency(state, grid) for state in states]
    return {
        "frequency_nadir_hz": round(grid.nominal_hz + min(coi), 5),
        "maximum_rocof_hz_per_s": round(
            max(abs(rate) for state in states for rate in state.rocof), 5
        ),
        "final_frequency_hz": round(grid.nominal_hz + coi[-1], 5),
        "peak_battery_power_pu": round(
            max(abs(power) for state in states for power in state.battery_power), 5
        ),
        "battery_throughput_pu_s": round(
            sum(
                sum(abs(power) for power in state.battery_power) * grid.dt
                for state in states
            ),
            5,
        ),
    }
