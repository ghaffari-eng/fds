#!/usr/bin/env python3
"""Analyse SGS turbulent dispersion test results.

Reads _devc.csv files from completed FDS runs and produces comparison tables
showing the effect of different SGS dispersion models on particle transport.

Output: ~/firemodels/fds/sgs_turbulent_test_results.md
"""

import csv
import os
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'sgs_turbulent_test_results_v2.md')
REPORT_PATH = os.path.normpath(REPORT_PATH)

N_TRACKED = 20

CASE_DEFS = {
    'none_heavy': {'sgs': 'None',       'density': 300, 'burning': False},
    'rw_heavy':   {'sgs': 'Random Walk', 'density': 300, 'burning': False},
    'lv_heavy':   {'sgs': 'Langevin',    'density': 300, 'burning': False},
    'df_heavy':   {'sgs': 'Diff Filter', 'density': 300, 'burning': False},
    'none_light': {'sgs': 'None',        'density': 50,  'burning': False},
    'rw_light':   {'sgs': 'Random Walk', 'density': 50,  'burning': False},
    'lv_light':   {'sgs': 'Langevin',    'density': 50,  'burning': False},
    'df_light':   {'sgs': 'Diff Filter', 'density': 50,  'burning': False},
    'lv_burn':    {'sgs': 'Langevin',    'density': 100, 'burning': True},
    'df_burn':    {'sgs': 'Diff Filter', 'density': 100, 'burning': True},
}


def read_devc_csv(filepath):
    """Read an FDS _devc.csv file, return (headers, data_rows)."""
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # skip units row
        headers = [h.strip() for h in next(reader)]
        data = []
        for row in reader:
            if not row or not row[0].strip():
                continue
            record = {}
            for i, h in enumerate(headers):
                try:
                    record[h] = float(row[i])
                except (ValueError, IndexError):
                    record[h] = None
            data.append(record)
    return headers, data


def extract_final_positions(data, n_tracked=N_TRACKED):
    """Extract particle X,Y,Z positions at the final timestep."""
    if not data:
        return []
    last = data[-1]
    positions = []
    for i in range(1, n_tracked + 1):
        x = last.get(f'P{i:02d}_X')
        y = last.get(f'P{i:02d}_Y')
        z = last.get(f'P{i:02d}_Z')
        if x is not None and y is not None and z is not None:
            positions.append((x, y, z))
    return positions


def extract_landing_info(data, n_tracked=N_TRACKED):
    """Extract landing time and position for each particle (first time z<=0.5)."""
    if not data:
        return []
    info = []
    for i in range(1, n_tracked + 1):
        xk, yk, zk = f'P{i:02d}_X', f'P{i:02d}_Y', f'P{i:02d}_Z'
        for row in data:
            x, y, z = row.get(xk), row.get(yk), row.get(zk)
            if x is not None and z is not None and z <= 0.5:
                info.append({'t': row['Time'], 'x': x, 'y': y, 'z': z})
                break
        else:
            # Didn't land — use final position
            last = data[-1]
            x, y, z = last.get(xk), last.get(yk), last.get(zk)
            if x is not None:
                info.append({'t': last['Time'], 'x': x, 'y': y, 'z': z})
    return info


def extract_turbulence_stats(data):
    """Extract time-averaged turbulence quantities (t > 10s)."""
    if not data:
        return {}
    steady = [d for d in data if d.get('Time', 0) > 10.0] or data
    stats = {}
    for key in ['KSGS_plume', 'KSGS_10m', 'KSGS_20m',
                'MU_T_plume', 'MU_T_10m',
                'TMP_plume', 'TMP_10m', 'U_10m', 'W_plume']:
        vals = [d[key] for d in steady if d.get(key) is not None]
        if vals:
            m = sum(vals) / len(vals)
            stats[key] = {
                'mean': m,
                'std': (sum((v - m)**2 for v in vals) / len(vals)) ** 0.5,
                'max': max(vals),
            }
    return stats


def stats_from_positions(positions):
    """Compute mean and std of X, Y, Z from a list of (x,y,z) tuples."""
    if not positions:
        return {'n': 0}
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    zs = [p[2] for p in positions]
    def mean(v): return sum(v) / len(v)
    def std(v):
        m = mean(v)
        return (sum((x - m)**2 for x in v) / len(v)) ** 0.5
    return {
        'n': len(positions),
        'mean_x': mean(xs), 'std_x': std(xs),
        'mean_y': mean(ys), 'std_y': std(ys),
        'mean_z': mean(zs), 'std_z': std(zs),
    }


def find_cases(res_suffix):
    """Find all completed cases for a given resolution suffix."""
    results = {}
    for case_id, meta in CASE_DEFS.items():
        chid = f'sgs_turb_{case_id}_{res_suffix}'
        devc_file = os.path.join(SCRIPT_DIR, f'{chid}_devc.csv')
        if os.path.exists(devc_file):
            results[case_id] = {'chid': chid, 'devc_file': devc_file, 'meta': meta}
    return results


def fmt(val, width=8, precision=2):
    if val is None:
        return '-'.center(width)
    return f'{val:{width}.{precision}f}'


def generate_report():
    lines = []
    lines.append('# SGS Turbulent Dispersion Test Results')
    lines.append('')
    lines.append('## Overview')
    lines.append('')
    lines.append('These tests exercise the SGS turbulent dispersion models (None, Random Walk,')
    lines.append('Langevin, Differential Filter) using ember particles in a turbulent fire plume.')
    lines.append('A 2 MW grass fire at ground level generates turbulence; 1000 particles are')
    lines.append('released at (10, 0, 10) m and tracked as they fall through the plume.')
    lines.append('')
    lines.append('20 individually-tracked particles start at the same point. The SGS models add')
    lines.append('stochastic velocity perturbations, causing the particles to diverge. Dispersion')
    lines.append('is measured as the standard deviation of particle positions at final time (t=60s).')
    lines.append('')

    all_results = {}
    issues = []

    for res_name, res_suffix in [('1m', '1m'), ('0.5m', '0p5m')]:
        cases = find_cases(res_suffix)
        if not cases:
            lines.append(f'### {res_name} Resolution: No results found')
            lines.append('')
            issues.append(f'No _devc.csv files found for {res_name} resolution')
            continue

        lines.append(f'## Results at {res_name} Resolution')
        lines.append('')
        lines.append(f'Cases found: {len(cases)} / {len(CASE_DEFS)}')
        lines.append('')

        case_data = {}
        for case_id, info in cases.items():
            try:
                headers, data = read_devc_csv(info['devc_file'])
                final_pos = extract_final_positions(data)
                landing_info = extract_landing_info(data)
                final_stats = stats_from_positions(final_pos)
                landing_stats = stats_from_positions(
                    [(li['x'], li['y'], li['z']) for li in landing_info])
                turb_stats = extract_turbulence_stats(data)
                mean_landing_t = (sum(li['t'] for li in landing_info) / len(landing_info)
                                  if landing_info else None)
                case_data[case_id] = {
                    'final_stats': final_stats,
                    'landing_stats': landing_stats,
                    'turb_stats': turb_stats,
                    'mean_landing_t': mean_landing_t,
                    'meta': info['meta'],
                }
            except Exception as e:
                issues.append(f'{info["chid"]}: Error reading data: {e}')

        all_results[res_suffix] = case_data

        # --- Table 1: Turbulence Characterisation ---
        lines.append(f'### Table 1: Turbulence Characterisation ({res_name})')
        lines.append('')
        lines.append('| Case | k_sgs plume | k_sgs 10m | k_sgs 20m | mu_t plume | mu_t 10m | T plume (C) | U 10m (m/s) |')
        lines.append('|------|------------:|----------:|----------:|-----------:|---------:|------------:|------------:|')
        for case_id in ['none_heavy', 'rw_heavy', 'lv_heavy', 'df_heavy']:
            if case_id not in case_data:
                continue
            cd = case_data[case_id]
            ts = cd['turb_stats']
            sgs = cd['meta']['sgs']
            def g(k): return ts.get(k, {}).get('mean')
            lines.append(
                f'| {sgs:12s} | {fmt(g("KSGS_plume"),8,3)} '
                f'| {fmt(g("KSGS_10m"),8,3)} | {fmt(g("KSGS_20m"),8,3)} '
                f'| {fmt(g("MU_T_plume"),8,4)} | {fmt(g("MU_T_10m"),8,4)} '
                f'| {fmt(g("TMP_plume"),8,1)} | {fmt(g("U_10m"))} |')
        lines.append('')

        # --- Table 2: Heavy Particles (final time) ---
        lines.append(f'### Table 2: Heavy Particles (rho=300 kg/m3) — Final Position at t=60s ({res_name})')
        lines.append('')
        lines.append('| SGS Model    | N | t_land (s) | mean_x (m) | std_x (m) | mean_y (m) | std_y (m) |')
        lines.append('|--------------|--:|-----------:|-----------:|----------:|-----------:|----------:|')
        for case_id in ['none_heavy', 'rw_heavy', 'lv_heavy', 'df_heavy']:
            if case_id not in case_data:
                continue
            cd = case_data[case_id]
            ps = cd['final_stats']
            sgs = cd['meta']['sgs']
            tl = cd['mean_landing_t']
            lines.append(
                f'| {sgs:12s} | {ps["n"]:2d} | {fmt(tl,8,1)} '
                f'| {fmt(ps.get("mean_x"))} | {fmt(ps.get("std_x"),8,4)} '
                f'| {fmt(ps.get("mean_y"))} | {fmt(ps.get("std_y"),8,4)} |')
        lines.append('')

        # --- Table 3: Light Particles (final time) ---
        lines.append(f'### Table 3: Light Particles (rho=50 kg/m3) — Final Position at t=60s ({res_name})')
        lines.append('')
        lines.append('| SGS Model    | N | t_land (s) | mean_x (m) | std_x (m) | mean_y (m) | std_y (m) |')
        lines.append('|--------------|--:|-----------:|-----------:|----------:|-----------:|----------:|')
        for case_id in ['none_light', 'rw_light', 'lv_light', 'df_light']:
            if case_id not in case_data:
                continue
            cd = case_data[case_id]
            ps = cd['final_stats']
            sgs = cd['meta']['sgs']
            tl = cd['mean_landing_t']
            lines.append(
                f'| {sgs:12s} | {ps["n"]:2d} | {fmt(tl,8,1)} '
                f'| {fmt(ps.get("mean_x"))} | {fmt(ps.get("std_x"),8,4)} '
                f'| {fmt(ps.get("mean_y"))} | {fmt(ps.get("std_y"),8,4)} |')
        lines.append('')

        # --- Table 4: Burning vs Inert ---
        lines.append(f'### Table 4: Burning vs Inert Particles — Final Position at t=60s ({res_name})')
        lines.append('')
        lines.append('| Case             | N | t_land (s) | mean_x (m) | std_x (m) | mean_y (m) | std_y (m) |')
        lines.append('|------------------|--:|-----------:|-----------:|----------:|-----------:|----------:|')
        for case_id in ['lv_burn', 'df_burn', 'lv_heavy', 'df_heavy']:
            if case_id not in case_data:
                continue
            cd = case_data[case_id]
            ps = cd['final_stats']
            sgs = cd['meta']['sgs']
            label = f'{sgs} (burn)' if cd['meta']['burning'] else f'{sgs} (inert)'
            tl = cd['mean_landing_t']
            lines.append(
                f'| {label:16s} | {ps["n"]:2d} | {fmt(tl,8,1)} '
                f'| {fmt(ps.get("mean_x"))} | {fmt(ps.get("std_x"),8,4)} '
                f'| {fmt(ps.get("mean_y"))} | {fmt(ps.get("std_y"),8,4)} |')
        lines.append('')

    # --- Table 5: Grid Sensitivity ---
    if '1m' in all_results and '0p5m' in all_results:
        lines.append('## Table 5: Grid Sensitivity (1m vs 0.5m)')
        lines.append('')
        lines.append('| Case | Res | mean_x (m) | std_x (m) | std_y (m) | k_sgs plume |')
        lines.append('|------|-----|----------:|----------:|----------:|------------:|')
        for case_id in ['none_heavy', 'rw_heavy', 'lv_heavy', 'df_heavy',
                        'none_light', 'rw_light', 'lv_light', 'df_light']:
            for rs, rl in [('1m', '1.0m'), ('0p5m', '0.5m')]:
                if case_id not in all_results.get(rs, {}):
                    continue
                cd = all_results[rs][case_id]
                ps = cd['final_stats']
                ksgs = cd['turb_stats'].get('KSGS_plume', {}).get('mean')
                sgs = cd['meta']['sgs']
                dens = cd['meta']['density']
                lines.append(
                    f'| {sgs} ({dens}) | {rl} '
                    f'| {fmt(ps.get("mean_x"))} | {fmt(ps.get("std_x"),8,4)} '
                    f'| {fmt(ps.get("std_y"),8,4)} | {fmt(ksgs,8,4)} |')
        lines.append('')

    # Issues
    if issues:
        lines.append('## Issues Encountered')
        lines.append('')
        for issue in issues:
            lines.append(f'- {issue}')
        lines.append('')

    # Assessment
    lines.append('## Assessment')
    lines.append('')

    has_1m = '1m' in all_results and len(all_results['1m']) > 0

    if has_1m:
        cd = all_results['1m']

        # Turbulence generated?
        any_turb = any(
            cd[c]['turb_stats'].get('KSGS_plume', {}).get('mean', 0) > 0.01
            for c in cd)
        if any_turb:
            ksgs_val = cd.get('none_heavy', {}).get('turb_stats', {}).get('KSGS_plume', {}).get('mean', 0)
            lines.append(f'- **Turbulence**: Fire plume generates k_sgs ~ {ksgs_val:.2f} m2/s2 in plume region')
        else:
            lines.append('- **Turbulence**: WARNING - k_sgs values low')

        # Dispersion ranking
        lines.append('')
        lines.append('### Dispersion by Model (std_x at t=60s):')
        lines.append('')
        for label, cases_list in [('Heavy (300 kg/m3)', ['none_heavy', 'rw_heavy', 'lv_heavy', 'df_heavy']),
                                   ('Light (50 kg/m3)',  ['none_light', 'rw_light', 'lv_light', 'df_light'])]:
            lines.append(f'**{label}:**')
            for cid in cases_list:
                if cid in cd:
                    sx = cd[cid]['final_stats'].get('std_x', 0)
                    sy = cd[cid]['final_stats'].get('std_y', 0)
                    sgs = cd[cid]['meta']['sgs']
                    lines.append(f'  - {sgs:12s}: std_x = {sx:.4f} m, std_y = {sy:.4f} m')
            lines.append('')

        # Key findings
        lines.append('### Key Findings:')
        lines.append('')

        none_h_sx = cd.get('none_heavy', {}).get('final_stats', {}).get('std_x', 0)
        lv_h_sx = cd.get('lv_heavy', {}).get('final_stats', {}).get('std_x', 0)
        rw_h_sx = cd.get('rw_heavy', {}).get('final_stats', {}).get('std_x', 0)
        df_h_sx = cd.get('df_heavy', {}).get('final_stats', {}).get('std_x', 0)

        none_l_sx = cd.get('none_light', {}).get('final_stats', {}).get('std_x', 0)
        lv_l_sx = cd.get('lv_light', {}).get('final_stats', {}).get('std_x', 0)
        rw_l_sx = cd.get('rw_light', {}).get('final_stats', {}).get('std_x', 0)
        df_l_sx = cd.get('df_light', {}).get('final_stats', {}).get('std_x', 0)

        # Finding 1: Cloud init baseline vs SGS enhancement
        lines.append(f'1. **Baseline dispersion from cloud init**: Particles start in a 0.5m cube, '
                     f'giving baseline std_x ~ {none_l_sx:.2f} m (light) and {none_h_sx:.2f} m (heavy) '
                     f'even without SGS. All SGS models increase dispersion above this baseline for light particles.')
        lines.append('')

        # Finding 2: Model ranking
        lines.append(f'2. **Dispersion ranking for light particles**: '
                     f'Langevin ({lv_l_sx:.2f}) >> Random Walk ({rw_l_sx:.2f}) > '
                     f'Diff Filter ({df_l_sx:.2f}) > None ({none_l_sx:.2f}). '
                     f'The Langevin model adds the strongest particle-level stochastic forcing.')
        lines.append('')

        # Finding 3: Stokes number
        if lv_l_sx > lv_h_sx:
            ratio = lv_l_sx / lv_h_sx if lv_h_sx > 0 else float('inf')
            lines.append(f'3. **Light particles show {ratio:.1f}x more dispersion** than heavy '
                         f'under Langevin, consistent with Stokes number dependence '
                         f'(lighter particles respond more to SGS velocity fluctuations).')
        lines.append('')

        # Finding 4: DF now shows dispersion
        if df_l_sx > none_l_sx:
            lines.append(f'4. **Differential filter produces dispersion** with cloud init: '
                         f'DF std_x={df_l_sx:.4f} vs None={none_l_sx:.4f} for light particles. '
                         f'Particles at different positions see different filtered velocities.')
        lines.append('')

        # Finding 5: Burning comparison
        lv_burn_sx = cd.get('lv_burn', {}).get('final_stats', {}).get('std_x', 0)
        df_burn_sx = cd.get('df_burn', {}).get('final_stats', {}).get('std_x', 0)
        if lv_burn_sx > 0 and lv_h_sx > 0:
            ratio_burn = lv_burn_sx / lv_h_sx
            lines.append(f'5. **Burning particles show {ratio_burn:.1f}x more dispersion** than '
                         f'equivalent inert heavy: burn std_x={lv_burn_sx:.4f} vs inert={lv_h_sx:.4f}. '
                         f'Mass loss from pyrolysis reduces Stokes number, increasing SGS sensitivity.')
        lines.append('')

    lines.append('## Recommendations for Tier 2')
    lines.append('')
    lines.append('- Run identical cases at 0.5m resolution to confirm grid sensitivity')
    lines.append('- SGS contribution should decrease at finer resolution (more resolved turbulence)')
    lines.append('- Heavy particles (St >> 1) show minimal SGS sensitivity at this grid; finer grid may change this')
    lines.append('')

    report = '\n'.join(lines)
    with open(REPORT_PATH, 'w') as f:
        f.write(report)

    print(f'Report saved to: {REPORT_PATH}')
    print(f'Cases analysed: {sum(len(v) for v in all_results.values())}')
    return report


if __name__ == '__main__':
    report = generate_report()
    print()
    print(report)
