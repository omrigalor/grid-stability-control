from grid_stability_control import Grid, simulate, summarize


def test_fast_response_improves_frequency_nadir() -> None:
    controlled = summarize(simulate(seed=9, controlled=True))
    baseline = summarize(simulate(seed=9, controlled=False))
    assert controlled["frequency_nadir_hz"] > baseline["frequency_nadir_hz"]
    assert controlled["final_frequency_hz"] > baseline["final_frequency_hz"]
    assert controlled["peak_battery_power_pu"] > 0.0


def test_power_and_energy_constraints_hold() -> None:
    grid = Grid()
    states = simulate(seed=4, loss_pu=0.18)
    for state in states:
        assert all(abs(p) <= limit + 1e-12 for p, limit in zip(state.battery_power, grid.battery_limit))
        assert all(abs(e) <= limit + 1e-12 for e, limit in zip(state.battery_energy, grid.battery_energy_limit))


def test_seeded_simulation_is_reproducible() -> None:
    assert summarize(simulate(seed=21)) == summarize(simulate(seed=21))
