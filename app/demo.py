import json
from datetime import date
from .scenarios import Hub, Demand, Disruption, evaluate


def main():
    hubs = [Hub('A', 80), Hub('B', 80), Hub('C', 40)]
    demands = [Demand('X', 60), Demand('Y', 60)]
    distances = {('A','X'): 10, ('B','X'): 20, ('B','Y'): 10, ('C','Y'): 20}
    result = evaluate(hubs, demands, distances, 100, date(2025,1,1), date(2025,1,5),
                      [Disruption(('A','B'), date(2025,1,1), 3)])
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
