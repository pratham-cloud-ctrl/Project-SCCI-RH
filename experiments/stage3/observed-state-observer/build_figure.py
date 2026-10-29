"""Plot saved observer allocations; no fitting, capture generation or tuning."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent


def main():
    development = json.loads((ROOT/'frozen/observer-development-summary-12oct.json').read_text(encoding='utf-8'))
    confirmation = json.loads((ROOT/'frozen/observer-confirmation-summary-12oct.json').read_text(encoding='utf-8'))
    horizons = np.arange(25, 151, 5)
    drift = np.max([r['allocation_by_horizon_m'] for r in development['development']], axis=0)*1000
    temporal = np.max([r['allocation_by_horizon_m'] for r in development['temporal_calibration_holdout']], axis=0)*1000
    fresh = np.asarray(confirmation['aggregate_allocation_by_horizon_m'])*1000
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                         'axes.spines.right':False,'savefig.facecolor':'white'})
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.4), gridspec_kw={'width_ratios':[1.8, 1]})
    for values, label, color, style in (
        (drift, 'Inspected development', '#526681', '--'),
        (temporal, 'Calibration temporal holdout', '#d38c35', ':'),
        (fresh, 'Fresh sensor-noise confirmation', '#087f8c', '-')):
        axes[0].plot(horizons, values, label=label, color=color, linestyle=style, linewidth=2)
    axes[0].axhline(15, color='#9b3449', linewidth=1.5, label='Unchanged 15 mm limit')
    axes[0].set(xlabel='Forecast horizon (ms)', ylabel='Max observed error + 3 mm (mm)',
                title='Complete finite-domain forecast allocations', xlim=(25, 150), ylim=(0, 17))
    axes[0].grid(axis='y', alpha=.15)
    axes[0].legend(frameon=False, fontsize=8.5, loc='lower right')
    values = np.array([confirmation[k] for k in (
        'maximum_observed_position_grid_difference_m',
        'maximum_forecast_grid_difference_m',
        'maximum_residual_grid_difference_m')])*1e6
    axes[1].bar(['Position', 'Forecast', 'Residual'], values, color=['#526681','#087f8c','#d38c35'], width=.6)
    for i, value in enumerate(values):
        axes[1].text(i, value+.12, f'{value:.3f}', ha='center', fontsize=9)
    axes[1].set(ylabel='Max paired-grid difference (µm)',
                title='2.5 ms versus 1.25 ms body grid', ylim=(0, 6.5))
    axes[1].grid(axis='y', alpha=.15)
    fig.suptitle('Project SCCI RH | Observed-state observer, no dose', x=.06, ha='left', fontsize=14, fontweight='bold')
    fig.text(.06, .015, 'Same synthetic subject/domain; 16 new noise pairs, 32 captures. No active pilot or retained-learning claim.', fontsize=9, color='#526681')
    fig.tight_layout(rect=(.015, .06, .99, .92))
    fig.savefig(ROOT/'observer-confirmation.png', dpi=220)
    plt.close(fig)


if __name__ == '__main__':
    main()
