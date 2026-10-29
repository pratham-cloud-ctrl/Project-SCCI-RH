"""Scientific figures from saved numerical and acquisition receipts."""
import hashlib
import gzip
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'results/stage3/numerical'
OUT = ROOT/'docs/stage3/figures'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'svg.hashsalt': 'scci_rh-stage3-continuation', 'savefig.facecolor': 'white'})
COLORS = {'legacy_endpoint': '#b75532', 'midpoint_exact_cascade': '#126c84'}


def read(name):
    contents = (DATA/name).read_bytes()
    if name.endswith('.gz'): contents = gzip.decompress(contents)
    return json.loads(contents)


def save(fig, stem):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT/f'{stem}.png', dpi=170)
    fig.savefig(OUT/f'{stem}.svg', metadata={'Date': None})
    svg = OUT/f'{stem}.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8')
    plt.close(fig)


def motor_figure():
    d = read('motor-convergence-summary.json')
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.6))
    for method, color in COLORS.items():
        steps = sorted({r['body_step_s'] for case in d['fixed_input_cases'] for r in case['runs'] if r['method'] == method}, reverse=True)
        for ax, key, scale in ((axes[0], 'maximum_position_difference_m', 1000),
                               (axes[1], 'same_support_velocity_difference_m_per_s', 1)):
            values = [max(r['differences_from_independent_reference'][key] for case in d['fixed_input_cases'] for r in case['runs']
                          if r['method'] == method and r['body_step_s'] == step)*scale for step in steps]
            ax.plot(np.array(steps)*1000, values, 'o-', color=color,
                    label='Original endpoint updates' if method == 'legacy_endpoint' else 'Event-split midpoint + exact cascade')
            ax.set_yscale('log'); ax.set_xscale('log', base=2)
            ax.set_xticks(np.array(steps)*1000, [f'{s*1000:g}' for s in steps]); ax.invert_xaxis()
            ax.set_xlabel('Private body step (ms)'); ax.grid(alpha=.2, which='both')
    axes[0].axhline(.15, color='#64748b', linestyle='--', label='Frozen 0.15 mm allocation')
    axes[1].axhline(.01, color='#64748b', linestyle='--', label='Frozen 0.01 m/s allocation')
    axes[0].set_ylabel('Maximum position error (mm)'); axes[1].set_ylabel('Same-support velocity error (m/s)')
    axes[0].set_title('Independent coupled-ODE reference'); axes[1].set_title('Velocity retains the same 5 ms support')
    for ax in axes: ax.legend(fontsize=8, loc='best')
    fig.suptitle('Motor integration: numerical correction without extra observations', fontsize=14, y=.97)
    fig.text(.5, .025, 'Maximum across 12 declared fixed-input cases. Decisions: 200 Hz; contacts: 4 kHz. Biological parameters remain chosen assumptions.',
             ha='center', fontsize=9, color='#475569')
    fig.subplots_adjust(top=.81, bottom=.20, wspace=.31)
    save(fig, 'motor-numerical-verification')


def pressure_figure():
    d = read('pressure-convergence-summary.json')
    fig, ax = plt.subplots(figsize=(11.6, 4.6))
    for label, color in (('baseline', '#126c84'), ('fallback', '#845bb2'), ('stress', '#b75532')):
        chosen = [(i, g) for i, g in enumerate(d['groups']) if label in g['section']]
        # Section spellings come directly from the receipt; preserve all groups.
        if not chosen: continue
        x = [i for i, _ in chosen]
        y = [max(p['maximum_policy_pressure_difference_mmHg'] for p in g['comparisons']) for _, g in chosen]
        ax.scatter(x, y, s=25, color=color, label=label.capitalize())
    sensitive = [(i, max(p['maximum_policy_pressure_difference_mmHg'] for p in g['comparisons']))
                 for i, g in enumerate(d['groups']) if any(p['changed_frame_decision_count'] for p in g['comparisons'])]
    if sensitive:
        ax.scatter(*zip(*sensitive), s=75, facecolors='none', edgecolors='#182431', linewidths=1,
                   label='At least one frame decision changes')
    ax.axhline(.2, linestyle='--', color='#64748b', label='Frozen maximum-sample allocation')
    ax.set_ylim(-.005, .225); ax.set_ylabel('Maximum pressure difference (mmHg)')
    ax.set_xlabel('Matched scenario / seed / policy group (136 groups; three grids each)')
    ax.grid(axis='y', alpha=.2); ax.legend(fontsize=9, loc='upper left')
    ax.set_title('408 integrated pressure runs: small numerical differences with discrete sensitivities', fontsize=13, pad=16)
    fig.text(.5, .025, 'Body grids: 5 / 2.5 / 1.25 ms. Sensor and policy schedules, actual noise and fresh delivery adapters are held fixed.',
             ha='center', fontsize=9, color='#475569')
    fig.subplots_adjust(top=.83, bottom=.18)
    save(fig, 'pressure-numerical-verification')


def acquisition_figure():
    d = read('acquisition-qualification.json.gz')
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.6))
    colors = {'single_artifact': '#126c84', 'train_40hz': '#b75532', 'missing_block': '#845bb2'}
    for run in d['runs']:
        if run['qualification_mode'] != 'bounded_residual' or run['case'] == 'clean': continue
        time = [r['available_time_s'] for r in run['rows']]
        bound = [max(r['feature_error_bound_uv']) for r in run['rows']]
        axes[0].plot(time, bound, color=colors[run['case']], label=run['case'].replace('_', ' ').capitalize())
        axes[1].plot(time, np.cumsum([r['valid'] for r in run['rows']])/200, color=colors[run['case']])
    axes[0].axhline(2.4, color='#64748b', linestyle='--', label='Chosen 2.4 µV feature allocation')
    axes[0].set_yscale('symlog', linthresh=.5); axes[0].set_ylabel('Maximum feature contamination bound (µV)')
    axes[0].set_ylim(0., max(max(r['feature_error_bound_uv']) for run in d['runs'] for r in run['rows'])*1.25)
    axes[1].set_ylabel('Cumulative qualified packet duration (s)')
    axes[0].set_title('Missing range-bounded digital inputs'); axes[1].set_title('Raw coverage alone cannot qualify history')
    axes[0].legend(fontsize=8)
    for ax in axes: ax.set_xlabel('Observation availability (s)'); ax.grid(alpha=.2)
    fig.suptitle('Acquisition qualification: explicit residual allowance', fontsize=14, y=.97)
    fig.text(.5, .025, 'Counterfactual digital input bound: ±5 mV. This is a conservative numerical filter witness, not physical amplifier recovery.',
             ha='center', fontsize=9, color='#475569')
    fig.subplots_adjust(top=.81, bottom=.20, wspace=.32)
    save(fig, 'acquisition-qualification')


if __name__ == '__main__':
    motor_figure(); pressure_figure(); acquisition_figure()
    print('Three scientific SVG/PNG pairs generated from saved receipts.')
