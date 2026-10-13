#!/usr/bin/env python3
"""Guard CLI parity check.

Reads parity/routes.json and verifies that every GUI-reachable,
CLI-appropriate backend route has either a registered CLI command
or an explicit, documented exclusion.

Exits 0 when all routes are accounted for, 1 when gaps are found.
"""

import json
import os
import sys

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), 'routes.json')


def load_registry(path=REGISTRY_PATH):
    with open(path) as f:
        return json.load(f)


def check_parity(registry):
    routes = registry['routes']
    gaps = []
    summary = {'covered': 0, 'planned': 0, 'excluded': 0, 'internal': 0, 'gap': 0}

    for route, info in sorted(routes.items()):
        disposition = info.get('disposition', '')

        if disposition in ('excluded', 'internal'):
            if not info.get('reason'):
                gaps.append({'route': route, 'reason': f'{disposition} but no reason documented'})
                summary['gap'] += 1
            else:
                summary[disposition] += 1
            continue

        if disposition == 'covered':
            if not info.get('cli_command') and not info.get('sdk_entity'):
                gaps.append({'route': route, 'reason': 'covered but no cli_command or sdk_entity'})
                summary['gap'] += 1
            else:
                summary['covered'] += 1
            continue

        if disposition == 'planned':
            if not info.get('ticket'):
                gaps.append({'route': route, 'reason': 'planned but no ticket assigned'})
                summary['gap'] += 1
            else:
                summary['planned'] += 1
            continue

        gaps.append({'route': route, 'reason': f'unknown disposition: {disposition!r}'})
        summary['gap'] += 1

    return gaps, summary


def print_table(gaps, summary):
    total = sum(summary.values())
    print(f'Guard CLI Parity Check')
    print(f'======================')
    print(f'Total routes: {total}')
    print(f'  Covered:  {summary["covered"]}')
    print(f'  Planned:  {summary["planned"]}')
    print(f'  Excluded: {summary["excluded"]}')
    print(f'  Internal: {summary["internal"]}')
    print(f'  Gaps:     {summary["gap"]}')
    print()

    if gaps:
        print('GAPS (routes without CLI coverage or documented exclusion):')
        for gap in gaps:
            print(f'  {gap["route"]}: {gap["reason"]}')
    else:
        print('All routes accounted for.')


def print_json_summary(gaps, summary):
    output = {
        'status': 'FAIL' if gaps else 'PASS',
        'summary': summary,
        'gaps': gaps,
    }
    print(json.dumps(output, indent=2))


def main():
    json_output = '--json' in sys.argv

    registry = load_registry()
    gaps, summary = check_parity(registry)

    if json_output:
        print_json_summary(gaps, summary)
    else:
        print_table(gaps, summary)

    return 1 if gaps else 0


if __name__ == '__main__':
    sys.exit(main())
