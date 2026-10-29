"""Scientific overview from saved Stage 3 revision results, not illustration data."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/stage3/figures'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
    'axes.spines.top': False, 'axes.spines.right': False,
    'svg.hashsalt': 'scci_rh-stage3-mechanism-revision', 'savefig.facecolor': 'white'})
PASS, FAIL, INK = '#167c80', '#b35436', '#263f50'


def read(name):
    return json.loads((ROOT/'results/stage3'/name).read_text(encoding='utf-8'))


def main():
    teacher = read('resolved-teacher/summary.json')
    prediction = read('assisted-prediction/summary.json')
    source = read('source-sensitivity/summary.json')
    delivery = read('delivery-requirements/requirements.json')
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    ax = axes[0, 0]
    domains = [(g, c, teacher['libraries'][g]['qualification']['domains'][c])
               for g in ('legacy_voluntary', 'idealized_inverse') for c in ('1', '1.15')]
    values = np.array([[int(d['references'][k]['qualified']) for k in ('expert_external', 'expert_neural')]
                       for _, _, d in domains])
    from matplotlib.colors import ListedColormap
    ax.imshow(values, cmap=ListedColormap([FAIL, PASS]), vmin=0, vmax=1, aspect='auto')
    ax.set_xticks([0, 1], ['External reference', 'Neural reference'])
    ax.set_yticks(range(4), [('Original' if g == 'legacy_voluntary' else 'Inverse-model')+' / '+c+' Hz'
                            for g, c, _ in domains])
    for row in range(4):
        for col in range(2): ax.text(col, row, 'PASS' if values[row, col] else 'REJECT',
                                     color='white', ha='center', va='center', weight='bold')
    ax.set_title('A  |  Fresh aperture-resolved teacher gates', loc='left', fontweight='bold', pad=15)

    ax = axes[0, 1]
    rows = prediction['validation']
    maxima = [max(h['empirical_error_allocation_m'] for h in r['horizons'])*1000 for r in rows]
    names = ['Quarter density', 'Half density', 'Full density', 'Unassisted',
             'Faster cadence', 'Known cue shift', 'Changed response', 'Sensor offset']
    ax.barh(range(8), maxima, color=[PASS if r['qualified'] else FAIL for r in rows])
    ax.set_yticks(range(8), names); ax.invert_yaxis()
    ax.axvline(15, color=INK, ls='--', lw=1.3)
    for i, v in enumerate(maxima): ax.text(v+.8, i, f'{v:.2f}', va='center', fontsize=9)
    ax.set_xlim(0, 92); ax.set_xlabel('Maximum forecast allocation over 31 horizons (mm)')
    ax.set_title('B  |  Independent predetermined recordings', loc='left', fontweight='bold', pad=15)

    ax = axes[1, 0]
    pairs = [r for s in source['studies'] for r in s['comparisons'] if r['source_mode'] == 'informative']
    x = np.arange(len(pairs))
    features = [r['maximum_feature_difference_uv']/2.4 for r in pairs]
    predictions = [(r['maximum_position_prediction_difference_m'] or 0.)/.0015 for r in pairs]
    ax.bar(x-.19, features, .38, color=FAIL, label='Feature difference / 2.4 microvolt allocation')
    ax.bar(x+.19, predictions, .38, color=PASS, label='Position prediction difference / 1.5 mm allocation')
    ax.axhline(1, color=INK, ls='--', label='Declared allocation')
    ax.set_xticks([0, 5, 8, 9, 14, 17], ['1', '6', '9', '10', '15', '18'])
    ax.set_xlabel('Informative source-pair comparison (two subjects, three patterns)')
    ax.set_ylabel('Difference / predeclared allocation')
    ax.set_ylim(0, 9.4)
    ax.set_title('C  |  Held moving sources fail selected budgets', loc='left', fontweight='bold', pad=15)
    ax.legend(fontsize=8, frameon=False)

    ax = axes[1, 1]
    groups = []
    for forecast in (.008, .015):
        thresholds = [r for row in delivery['records'] for r in row['thresholds']
                      if r['forecast_allocation_m'] == forecast and r['direction_id'] != 'both']
        numbers = [r['maximum_uncertainty_fraction_of_nominal']*100 for r in thresholds]
        groups.append((min(numbers), max(numbers)))
    for i, (low, high) in enumerate(groups):
        ax.plot([low, high], [i, i], color=PASS, lw=8, solid_capstyle='round')
        ax.text(np.sqrt(low*high), i+.19, f'{low:.3f}–{high:.3f}%', va='center', ha='center', fontsize=9,
                bbox={'facecolor': 'white', 'edgecolor': 'none', 'pad': 1.5})
    ax.axvline(4, color=INK, ls='--')
    ax.text(4, -.48, 'Prospective 4%', ha='center', fontsize=9, color=INK,
            bbox={'facecolor': 'white', 'edgecolor': 'none', 'pad': 1.5})
    ax.set_xscale('log'); ax.set_xlim(.15, 15); ax.set_ylim(1.65, -.8)
    ax.set_yticks([0, 1], ['8 mm forecast input', '15 mm forecast input'])
    ax.set_xlabel('Single-route charge uncertainty limit (% of nominal)')
    ax.set_title('D  |  Observed-map precision requirements', loc='left', fontweight='bold', pad=15)
    ax.text(.02, .055, '8 mm is an input assumption. Actual monitor remains rejected.\n'
            'Dynamic response and circuit implementation are separate gates.', transform=ax.transAxes,
            fontsize=8, color=INK)

    fig.suptitle('Project SCCI RH | Mechanism revision and design consequences', fontsize=17,
                 weight='bold', color=INK, y=.98)
    fig.text(.5, .025, 'Finite synthetic evidence. Teacher, forecast and precision gates are distinct; no body-coupled learning or implant readiness is inferred.',
             ha='center', fontsize=10, color=INK)
    fig.subplots_adjust(left=.15, right=.97, top=.89, bottom=.11, hspace=.53, wspace=.62)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT/'mechanism-revision.png', dpi=170)
    fig.savefig(OUT/'mechanism-revision.svg', metadata={'Date': None})
    plt.close(fig)
    path = OUT/'mechanism-revision.svg'
    path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8')


if __name__ == '__main__': main()
