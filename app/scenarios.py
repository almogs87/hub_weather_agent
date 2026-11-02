"""Daily divisible-demand allocation. Distances and outage effects are inputs."""
from dataclasses import dataclass
from datetime import date, timedelta
import math


@dataclass(frozen=True)
class Hub:
    id: str
    capacity: float
    component: str = 'contiguous_us'


@dataclass(frozen=True)
class Demand:
    id: str
    units: float
    component: str = 'contiguous_us'


@dataclass(frozen=True)
class Disruption:
    hub_ids: tuple[str, ...]
    start: date
    duration_days: int
    available_fraction: float = 0
    recovery_days: int = 0
    event_group_id: str = 'analyst-scenario'

    def fraction(self, day):
        offset = (day - self.start).days
        if offset < 0:
            return 1.0
        if offset < self.duration_days:
            return self.available_fraction
        step = offset - self.duration_days + 1
        if self.recovery_days == 0 or step >= self.recovery_days:
            return 1.0
        return self.available_fraction + (1 - self.available_fraction) * step / self.recovery_days


def _number(value, label, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    if value < 0 or (positive and value == 0):
        raise ValueError(f'{label} must be {"positive" if positive else "nonnegative"}')


def validate(hubs, demands, distances, max_distance, disruptions):
    _number(max_distance, 'max_distance', True)
    for label, items in [('hub', hubs), ('demand', demands)]:
        ids = [item.id for item in items]
        if not ids or any(not isinstance(i, str) or not i.strip() for i in ids) or len(ids) != len(set(ids)):
            raise ValueError(f'{label} IDs must be nonempty and unique')
        for item in items:
            if item.component not in {'contiguous_us', 'alaska', 'hawaii'}:
                raise ValueError('Unknown service component')
    for h in hubs:
        _number(h.capacity, 'capacity', True)
    for d in demands:
        _number(d.units, 'demand')
    hub_ids, demand_ids = {h.id for h in hubs}, {d.id for d in demands}
    for (h, d), distance in distances.items():
        if h not in hub_ids or d not in demand_ids:
            raise ValueError('Distance contains unknown ID')
        _number(distance, 'distance')
    for event in disruptions:
        if not event.hub_ids or len(set(event.hub_ids)) != len(event.hub_ids) or not set(event.hub_ids) <= hub_ids:
            raise ValueError('Disruption requires unique known hub IDs')
        for value, minimum in [(event.duration_days, 1), (event.recovery_days, 0)]:
            if type(value) is not int or value < minimum:
                raise ValueError('Invalid disruption duration or recovery')
        _number(event.available_fraction, 'available_fraction')
        if event.available_fraction > 1:
            raise ValueError('available_fraction must be <= 1')


def allocate(hubs, demands, distances, max_distance, capacities=None):
    """Maximum served flow, then minimum demand-distance via residual paths.

    Successive shortest augmenting paths (Bellman-Ford) permit rerouting earlier
    assignments. Sorted IDs and stable edge order break equal-cost ties.
    Missing links are ineligible, not zero-distance links.
    """
    validate(hubs, demands, distances, max_distance, [])
    hubs, demands = sorted(hubs, key=lambda x: x.id), sorted(demands, key=lambda x: x.id)
    capacities = {h.id: h.capacity for h in hubs} if capacities is None else capacities
    if set(capacities) != {h.id for h in hubs}:
        raise ValueError('Capacity overrides must match all hub IDs')
    for h in hubs:
        _number(capacities[h.id], 'available capacity')
        if capacities[h.id] > h.capacity:
            raise ValueError('Available capacity exceeds installed capacity')
    count = len(hubs) + len(demands) + 2
    source, sink = count - 2, count - 1
    graph = [[] for _ in range(count)]

    def edge(a, b, capacity, cost):
        forward = [b, len(graph[b]), capacity, cost]
        backward = [a, len(graph[a]), 0.0, -cost]
        graph[a].append(forward)
        graph[b].append(backward)
        return forward

    for i, h in enumerate(hubs):
        edge(source, i, capacities[h.id], 0)
    links = []
    for j, d in enumerate(demands):
        edge(len(hubs) + j, sink, d.units, 0)
        for i, h in enumerate(hubs):
            distance = distances.get((h.id, d.id))
            if distance is not None and distance <= max_distance and h.component == d.component:
                e = edge(i, len(hubs) + j, d.units, distance)
                links.append((h.id, d.id, e, d.units, distance))
    eps = 1e-9
    while True:
        costs, parents = [math.inf] * count, [None] * count
        costs[source] = 0
        for _ in range(count - 1):
            changed = False
            for a in range(count):
                if costs[a] == math.inf:
                    continue
                for k, e in enumerate(graph[a]):
                    b, _, remaining, cost = e
                    if remaining > eps and costs[a] + cost < costs[b] - eps:
                        costs[b], parents[b], changed = costs[a] + cost, (a, k), True
            if not changed:
                break
        if parents[sink] is None:
            break
        amount, b = math.inf, sink
        while b != source:
            a, k = parents[b]
            amount, b = min(amount, graph[a][k][2]), a
        b = sink
        while b != source:
            a, k = parents[b]
            e = graph[a][k]
            e[2] -= amount
            graph[b][e[1]][2] += amount
            b = a
    assignments = [dict(hub_id=h, demand_id=d, units=initial-e[2], distance_km=distance)
                   for h, d, e, initial, distance in links if initial-e[2] > eps]
    served = sum(a['units'] for a in assignments)
    total = sum(d.units for d in demands)
    return dict(served_units=served, unserved_units=max(0, total-served),
                served_fraction=served/total if total else 1.0,
                demand_km=sum(a['units']*a['distance_km'] for a in assignments),
                assignments=assignments,
                unserved_by_area={d.id: max(0, d.units-sum(a['units'] for a in assignments if a['demand_id']==d.id)) for d in demands},
                utilization={h.id: sum(a['units'] for a in assignments if a['hub_id']==h.id)/capacities[h.id]
                             if capacities[h.id] else None for h in hubs})


def evaluate(hubs, demands, distances, max_distance, start, end, disruptions=()):
    validate(hubs, demands, distances, max_distance, disruptions)
    if end < start:
        raise ValueError('End precedes start')
    if (end-start).days > 3660:
        raise ValueError('Scenario horizon exceeds 3661 days')
    baseline = allocate(hubs, demands, distances, max_distance)
    days = []
    day = start
    while day <= end:
        capacities = {h.id: h.capacity*min([1.0]+[e.fraction(day) for e in disruptions if h.id in e.hub_ids]) for h in hubs}
        result = allocate(hubs, demands, distances, max_distance, capacities)
        days.append(dict(date=day.isoformat(), available_capacities=capacities, **result))
        day += timedelta(days=1)
    # Only claim sustained recovery within the observed simulation horizon.
    below = [i for i, d in enumerate(days) if d['served_units'] < baseline['served_units']-1e-8]
    recovery = (days[below[-1]+1]['date'] if below and below[-1]+1 < len(days) else None)
    return dict(baseline=baseline, days=days,
                unserved_demand_days=sum(d['unserved_units'] for d in days),
                structural_unserved_demand_days=baseline['unserved_units']*len(days),
                incremental_unserved_demand_days=sum(max(0, d['unserved_units']-baseline['unserved_units']) for d in days),
                minimum_served_fraction=min(d['served_fraction'] for d in days),
                service_recovery_date=recovery,
                recovery_status='recovered_within_horizon' if recovery else ('not_recovered_within_horizon' if below else 'baseline_service_maintained'),
                assumptions=['Synthetic or analyst-supplied capacities, distances and disruptions; no calibrated event probabilities.',
                             'Divisible daily demand; unmet demand does not carry forward as backlog.',
                             'Distance eligibility assumes usable routes; no road routing or route-closure model.',
                             'Recovery means return to baseline throughput, which may already leave demand unserved.'])
