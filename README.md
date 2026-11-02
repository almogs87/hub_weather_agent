# Weather Risk Intelligence Agent

First milestone: deterministic daily network scenario engine. No real hub locations have been selected. This is not yet the complete assignment submission: live weather, trends, API, LLM, chat and evaluation cases for the agent remain to be implemented.

Requires Python 3.11+; this milestone uses only the standard library.

From this directory:

```powershell
python -m unittest discover -s tests -v
python -m app.demo
```

The demo returns JSON for three abstract hubs and two demand areas. A regional event closes A and B for three days. It produces 240 unserved demand-days and returns to baseline service on January 4 of the synthetic 2025 timeline.

The allocator maximizes served divisible demand, then minimizes total demand-distance using a residual-network minimum-cost maximum-flow algorithm. This avoids greedy assignments stranding demand. Stable ID ordering resolves equal-cost choices reproducibly. Capacity is enforced each day; unavailable hubs have null utilization rather than a division by zero.

Missing distance links are ineligible. Service components prevent mainland road backup to Alaska or Hawaii. Distances are supplied scenario inputs, not measured road travel. Overlapping outages use the lowest available-capacity fraction. Recovery is linear and explicitly configured. Unserved demand is not carried forward as backlog.

Source modules: `app/scenarios.py` (models, validation, allocator, simulation), `app/demo.py` (synthetic demonstration), `tests/test_scenarios.py` (acceptance and edge cases).

Do not interpret synthetic closures, recovery periods or capacities as observed company data or calibrated weather probabilities. The full AI conversation must be exported separately for the assignment; this repository does not yet include that export.
