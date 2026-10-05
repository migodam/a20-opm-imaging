#!/usr/bin/env python3
"""Offline, phase-separated display of the recorded mixed replay errors.

Selection uses only the standard library. Matplotlib is imported lazily when
the caller requests rendering. No physics, labels, reference generation, or
scientific gate calculation is performed.
"""
from __future__ import annotations

import time
_PROCESS_START = time.process_time()
_WALL_START = time.perf_counter()

import argparse
import csv
import json
import math
from pathlib import Path
import sys


def load_records(path):
    records, issues = [], []
    with Path(path).open(encoding='utf-8') as handle:
        for line_number, raw in enumerate(handle, 1):
            raw = raw.rstrip('\r\n')
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
                if not isinstance(row, dict):
                    raise ValueError('JSONL row is not an object')
            except (ValueError, TypeError) as error:
                issues.append({'line': line_number, 'error': str(error), 'raw_json_line': raw})
                continue
            records.append({'line': line_number, 'raw_json_line': raw, 'row': row})
    return records, issues


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _axis(value):
    """Recognize malformed numeric axes so their cell is invalid, not missing."""
    if isinstance(value, bool):
        return None, False
    if isinstance(value, int):
        return value, True
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value), False
    if isinstance(value, str) and value.isdigit():
        return int(value), False
    return None, False


def _single_classification(record, floor):
    row = record['row']
    if not record['axes_valid']:
        return 'invalid', 'axes are not registered integer fields'
    if row.get('fullfallback_used') or row.get('full_fallback_used'):
        return 'invalid', 'full fallback; not a reduced representation result'
    relative_status = str(row.get('relative_H_status', ''))
    energy = _number(row.get('reference_H_energy'))
    if ('REFERENCE_ENERGY_BELOW' in relative_status or 'ZERO_REFERENCE' in relative_status
            or (energy is not None and 0 <= energy <= floor*floor)):
        return 'zero_reference', 'reference energy at or below registered denominator floor'
    if row.get('status') != 'OK':
        return 'invalid', 'recorded status='+str(row.get('status'))
    if row.get('reference_status') not in (
            'VERIFIED_SAVED_CONSTRAINED_REFERENCE', 'VERIFIED_NEW_CONSTRAINED_REFERENCE'):
        return 'invalid', 'recorded reference is missing or unverified'
    if energy is None or energy < 0:
        return 'invalid', 'reference energy missing, nonfinite, or negative'
    error = _number(row.get('relative_H_step_error'))
    if error is None or error < 0:
        return 'invalid', 'registered H-step error missing, nonfinite, or negative'
    return 'valid', 'unique recorded OK row with a nonzero verified reference'


def select_cells(records, frozen, run_id=None):
    parents = frozen['parents']
    iterations = frozen['replay_iterations']
    degrees = frozen['replay_degrees']
    if len(parents) != 6 or len(set(parents)) != 6:
        raise ValueError('Expected six distinct frozen parents')
    if iterations != [0, 17] or degrees != list(range(6)):
        raise ValueError('Expected registered states [0,17] and degrees [0,1,2,3,4,5]')
    threshold = _number(frozen['replay_median_H_error_gate'])
    floor = _number(frozen['replay_H_relative_floor'])
    if threshold != .05 or floor is None or floor <= 0:
        raise ValueError('Expected registered 0.05 threshold and positive H denominator floor')
    groups = {(iteration, parent, degree): [] for iteration in iterations
              for parent in parents for degree in degrees}
    ignored, off_grid = 0, []
    for record in records:
        row = record['row']
        if row.get('method') != 'mixed' or (run_id is not None and row.get('run_id') != run_id):
            ignored += 1
            continue
        parent, parent_ok = _axis(row.get('parent_object_id'))
        iteration, iteration_ok = _axis(row.get('iteration'))
        degree, degree_ok = _axis(row.get('degree'))
        key = iteration, parent, degree
        if key not in groups:
            off_grid.append({'line': record['line'], 'parent_object_id': row.get('parent_object_id'),
                             'iteration': row.get('iteration'), 'degree': row.get('degree')})
            continue
        item = dict(record, axes_valid=parent_ok and iteration_ok and degree_ok)
        groups[key].append(item)
    cells = []
    for (iteration, parent, degree), contributors in groups.items():
        if not contributors:
            classification, reason = 'missing', 'no mixed row for this frozen cell'
        elif len(contributors) != 1:
            classification, reason = 'duplicate', str(len(contributors))+' rows; none selected as a substitute'
        else:
            classification, reason = _single_classification(contributors[0], floor)
        error = (float(contributors[0]['row']['relative_H_step_error'])
                 if classification == 'valid' else None)
        cells.append({'iteration': iteration, 'parent_object_id': parent, 'degree': degree,
                      'display_class': classification, 'display_reason': reason,
                      'plotted_H_step_error': error, 'raw_row_count': len(contributors),
                      'source_lines': [item['line'] for item in contributors],
                      'row_ids': [item['row'].get('row_id') for item in contributors],
                      'records': contributors})
    return {'cells': cells, 'parents': parents, 'iterations': iterations, 'degrees': degrees,
            'registered_threshold': threshold, 'registered_H_denominator_floor': floor,
            'run_id_filter': run_id, 'ignored_rows': ignored, 'off_grid_mixed_rows': off_grid,
            'gate_recomputed': False, 'missing_values_substituted_with_zero': False}


def _csv_value(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, separators=(',', ':'), ensure_ascii=False)
    return value


def _write_csv(path, rows, preferred):
    keys = set().union(*(set(row) for row in rows)) if rows else set()
    fields = [key for key in preferred if key in keys]+sorted(keys-set(preferred))
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(value) for key, value in row.items()})


def export_selection(selection, issues, output_dir, source, config_path):
    """Raw CSV has only actual contributing input rows, including duplicates.

    The separate 72-cell CSV records missing cells without fabricating raw rows.
    Full input JSON text is retained for every contributing raw row.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_rows, cell_rows = [], []
    for cell in selection['cells']:
        cell_rows.append({key: value for key, value in cell.items() if key != 'records'})
        for record in cell['records']:
            raw_rows.append(dict(record['row'],
                                 _offline_plot_source_line=record['line'],
                                 _offline_plot_display_class=cell['display_class'],
                                 _offline_plot_display_reason=cell['display_reason'],
                                 _offline_plot_raw_json_line=record['raw_json_line']))
    raw_rows.sort(key=lambda row: row['_offline_plot_source_line'])
    raw_path = output_dir/'mixed_H_step_raw_rows.csv'
    cells_path = output_dir/'mixed_H_step_cells.csv'
    _write_csv(raw_path, raw_rows, ['_offline_plot_source_line', 'run_id', 'row_id',
                                   'parent_object_id', 'iteration', 'method', 'degree',
                                   'status', 'relative_H_step_error'])
    _write_csv(cells_path, cell_rows, ['iteration', 'parent_object_id', 'degree',
                                      'display_class', 'plotted_H_step_error', 'raw_row_count'])
    manifest = {key: value for key, value in selection.items() if key != 'cells'}
    manifest.update(input_path=str(Path(source).resolve()), config_path=str(Path(config_path).resolve()),
                    input_parse_issues=issues, cells=cell_rows,
                    raw_csv_scope='all and only actual input rows contributing to the plotted 72 cells; no missing-row placeholders',
                    cell_numbers='four significant figures in figure; full recorded precision in raw CSV',
                    threshold_scope='registered pooled replay screening threshold shown as context; no gate recomputation')
    manifest_path = output_dir/'mixed_H_step_selection.json'
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    return {'raw_csv': str(raw_path), 'cells_csv': str(cells_path), 'selection_json': str(manifest_path)}


def _cell_label(cell):
    if cell['display_class'] == 'valid':
        return format(cell['plotted_H_step_error'], '.4g')
    labels = {'missing': 'MISSING', 'duplicate': 'DUPLICATE',
              'zero_reference': 'ZERO REF', 'invalid': 'INVALID'}
    label = labels[cell['display_class']]
    if cell['display_class'] == 'duplicate':
        label += ' ('+str(cell['raw_row_count'])+')'
    elif cell['display_class'] == 'invalid' and cell['records']:
        row = cell['records'][0]['row']
        label += '\nFULL FALLBACK' if row.get('fullfallback_used') or row.get('full_fallback_used') else '\n'+str(row.get('status', 'bad row'))
    numbers = [_number(item['row'].get('relative_H_step_error')) for item in cell['records']]
    numbers = [number for number in numbers if number is not None]
    if numbers:
        label += '\nreported H: '+', '.join(format(number, '.3g') for number in numbers[:2])
        if len(numbers) > 2:
            label += ', ...'
    return label


def render_heatmap(selection, output_dir):
    # This function is not called by the worker's stdlib fixture validation.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import SymLogNorm
    from matplotlib.patches import Patch

    lookup = {(cell['iteration'], cell['parent_object_id'], cell['degree']): cell
              for cell in selection['cells']}
    valid_values = [cell['plotted_H_step_error'] for cell in selection['cells']
                    if cell['display_class'] == 'valid']
    threshold = selection['registered_threshold']
    maximum = max([threshold]+valid_values)
    norm = SymLogNorm(linthresh=threshold, linscale=.5, vmin=0., vmax=maximum, base=10)
    cmap = plt.get_cmap('viridis').copy()
    cmap.set_bad('#d8d8d8')
    fig = plt.figure(figsize=(15, 7.5))
    grid = fig.add_gridspec(1, 3, width_ratios=[1, 1, .045], wspace=.15)
    axes = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])]
    color_axis = fig.add_subplot(grid[0, 2])
    for axis, iteration in zip(axes, selection['iterations']):
        values = [[lookup[iteration, parent, degree]['plotted_H_step_error']
                   if lookup[iteration, parent, degree]['display_class'] == 'valid' else math.nan
                   for degree in selection['degrees']] for parent in selection['parents']]
        image = axis.imshow(values, cmap=cmap, norm=norm, interpolation='nearest', aspect='equal')
        axis.set_title('Frozen state: iteration '+str(iteration), fontsize=13, pad=12)
        axis.set_xlabel('Registered basis degree', fontsize=11)
        axis.set_xticks(range(6), [str(degree) for degree in selection['degrees']])
        axis.set_yticks(range(6), [str(parent) for parent in selection['parents']])
        axis.set_ylabel('Frozen parent object', fontsize=11)
        axis.set_xticks([index-.5 for index in range(7)], minor=True)
        axis.set_yticks([index-.5 for index in range(7)], minor=True)
        axis.grid(which='minor', color='white', linewidth=1.)
        axis.tick_params(which='minor', bottom=False, left=False)
        for row, parent in enumerate(selection['parents']):
            for column, degree in enumerate(selection['degrees']):
                cell = lookup[iteration, parent, degree]
                color = '#222222'
                if cell['display_class'] == 'valid':
                    red, green, blue, _ = cmap(norm(cell['plotted_H_step_error']))
                    color = 'white' if .2126*red+.7152*green+.0722*blue < .5 else '#111111'
                axis.text(column, row, _cell_label(cell), ha='center', va='center',
                          color=color, fontsize=10 if cell['display_class'] == 'valid' else 7)
    colorbar = fig.colorbar(image, cax=color_axis)
    ticks = sorted(set([0., threshold, maximum]))
    colorbar.set_ticks(ticks)
    colorbar.set_ticklabels([format(value, '.4g') for value in ticks])
    colorbar.ax.axhline(threshold, color='#d62728', linewidth=1.5)
    colorbar.set_label('Recorded relative full-H step error', fontsize=10)
    fig.suptitle('Mixed OPM: recorded H-step error by frozen state', fontsize=16, y=.98)
    fig.text(.5, .935, 'Registered pooled replay screening threshold: 0.05 (context)', ha='center', fontsize=10)
    fig.legend(handles=[Patch(facecolor='#d8d8d8', label='Gray: missing, invalid, duplicate, or zero reference')],
               loc='lower center', bbox_to_anchor=(.5, .075), frameon=False, fontsize=10)
    fig.text(.5, .055, 'Cell numbers: 4 significant figures; raw CSV retains full precision. No gate recomputation.',
             ha='center', fontsize=9)
    fig.text(.5, .03, 'Color scale is linear up to 0.05 and logarithmic above it. Gray cells have no substituted numeric value.',
             ha='center', fontsize=9)
    fig.text(.5, .01, 'Input parse issues: '+str(selection.get('input_parse_issue_count', 0))+
             '; off-grid mixed rows: '+str(len(selection['off_grid_mixed_rows']))+
             '; epoch filter: '+str(selection['run_id_filter'] or 'none'), ha='center', fontsize=8)
    fig.subplots_adjust(left=.07, right=.92, top=.865, bottom=.18)
    output_dir = Path(output_dir)
    png = output_dir/'mixed_H_step_by_state.png'
    pdf = output_dir/'mixed_H_step_by_state.pdf'
    fig.savefig(png, dpi=220, facecolor='white')
    fig.savefig(pdf, facecolor='white')
    plt.close(fig)
    return {'png': str(png), 'pdf': str(pdf)}


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=root/'results/replay/replay.jsonl')
    parser.add_argument('--config', type=Path, default=root/'configs/frozen.json')
    parser.add_argument('--output-dir', type=Path, default=root/'results/replay/phase_plots')
    parser.add_argument('--run-id', help='Optional explicit epoch filter; duplicates within the epoch remain gray')
    parser.add_argument('--selection-only', action='store_true', help='Export the exact selected raw rows and grid without importing Matplotlib')
    args = parser.parse_args(argv)
    receipt = {'status': 'FAILED', 'gate_recomputed': False, 'physics_actions': 0,
               'run_id_filter': args.run_id}
    try:
        frozen = json.loads(args.config.read_text(encoding='utf-8'))
        records, issues = load_records(args.input)
        selection = select_cells(records, frozen, args.run_id)
        selection['input_parse_issue_count'] = len(issues)
        paths = export_selection(selection, issues, args.output_dir, args.input, args.config)
        if not args.selection_only:
            paths.update(render_heatmap(selection, args.output_dir))
        receipt.update(status='ARTIFACTS_WRITTEN', artifacts=paths,
                       input_parse_issues=len(issues), raw_contributing_rows=sum(cell['raw_row_count'] for cell in selection['cells']),
                       displayed_cells=len(selection['cells']), registered_threshold=selection['registered_threshold'],
                       display_counts={classification: sum(cell['display_class'] == classification for cell in selection['cells'])
                                       for classification in ('valid', 'missing', 'invalid', 'duplicate', 'zero_reference')})
    except Exception as error:
        receipt['error'] = type(error).__name__+': '+str(error)
    receipt.update(process_cpu_seconds=time.process_time()-_PROCESS_START,
                   wall_seconds=time.perf_counter()-_WALL_START)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir/'plot_receipt.json').write_text(json.dumps(receipt, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(receipt, allow_nan=False))
    return 0 if receipt['status'] == 'ARTIFACTS_WRITTEN' else 1


if __name__ == '__main__':
    raise SystemExit(main())
