"""Compact reproducible IEEE-style figure for Scalar SMU Native Core cycles.
Uses the original matched results CSV; ISA bars include one-time configuration cost.
"""
from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, FormatStrFormatter

BASE = Path(__file__).resolve().parent
DATA = BASE / 'native_isa_matched_summary.csv'
rows = {}
with DATA.open(newline='', encoding='utf-8') as fh:
    for r in csv.DictReader(fh):
        if r['status'] == 'PASS':
            rows[(int(r['n']), int(r['d']), int(r['tile_keys']))] = r

PANELS = [
    ([(16, 32, 4), (16, 64, 4), (16, 128, 4)],
     ['32','64','128'], '(a) Head dimension $D$', '$N=16, B=4$'),
    ([(8, 64, 4), (16, 64, 4), (24, 64, 4), (32, 64, 4)],
     ['8','16','24','32'], '(b) Sequence length $N$', '$D=64, B=4$'),
    ([(32, 64, 4), (32, 64, 8), (32, 64, 16)],
     ['4','8','16'], '(c) Tile size $B$', '$N=32, D=64$'),
]
plt.rcParams.update({
    'font.family': 'DejaVu Serif',
    'font.size': 7.3,
    'axes.labelsize': 7.2,
    'xtick.labelsize': 7,
    'ytick.labelsize': 6.6,
    'axes.linewidth': .65,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
    'svg.fonttype': 'none',
})
fig, axes = plt.subplots(1,3, figsize=(7.12, 2.48), dpi=200,
                         gridspec_kw={'wspace': .31})
width=.32
for ax, (cfgs, ticks, title, setting) in zip(axes, PANELS):
    software = np.array([int(rows[t]['software_core']) for t in cfgs], dtype=float)/1e6
    isa = np.array([int(rows[t]['isa_core']) + int(rows[t]['configuration']) for t in cfgs], dtype=float)/1e6
    speedups = software / isa
    xx=np.arange(len(cfgs))
    ax.bar(xx-width/2, software, width, label='Software + RVV', zorder=2)
    ax.bar(xx+width/2, isa, width, label='ISA Scalar SMU + RVV', zorder=2)
    ax.set_xticks(xx, ticks)
    ax.set_xlim(-.57, len(xx)-.43)
    max_y=max(software.max(), isa.max())
    ax.set_ylim(0, max_y*1.25)
    for x, y, ratio in zip(xx, np.maximum(software, isa), speedups):
        ax.annotate(f'{ratio:.3f}×', (x, y), xytext=(0,4), textcoords='offset points',
                    ha='center', va='bottom', fontsize=6.9)
    ax.set_title(title+'\n'+setting, loc='center', pad=5, fontsize=8.1, linespacing=1.4)
    ax.set_ylabel('Core cycles (million)', fontsize=6.9, labelpad=2)
    ax.grid(axis='y', alpha=.22, linewidth=.5, zorder=0)
    ax.tick_params(direction='out', width=.6, length=2.4, pad=2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

h, labs=axes[0].get_legend_handles_labels()
fig.legend(h, labs, loc='lower center', bbox_to_anchor=(.5, -.006), ncol=2,
           frameon=False, fontsize=7.6, columnspacing=2.6, handlelength=1.7)
fig.subplots_adjust(left=.064, right=.99, top=.82, bottom=.27)
for ext in ['pdf','svg','png']:
    fig.savefig(BASE / f'performance_isa.{ext}', bbox_inches='tight', pad_inches=.045,
                dpi=300 if ext=='png' else None)
print('Done:', ', '.join(str(BASE/f'performance_isa.{s}') for s in ['pdf','svg','png']))
