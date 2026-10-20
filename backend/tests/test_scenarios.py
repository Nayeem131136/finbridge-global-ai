import pytest
from run_eval import SCENARIOS, run_scenario


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario(sc):
    r = run_scenario(sc)
    assert r["passed"], r["errors"]
