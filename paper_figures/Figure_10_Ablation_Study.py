"""
Figure_10_Ablation_Study.py
Generates Figure 10: Ablation Study - Contribution of Each LANS Component
Shows RMSE for each configuration (LQR, PPO, w/o LQR, w/o Latency, w/o Adaptive, Full LANS)
"""

import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# YOUR VERIFIED RESULTS FROM ABLATION STUDY
# ============================================================
configs = [
    'Pure LQR', 
    'Pure PPO', 
    'w/o LQR\nBaseline', 
    'w/o Latency\nPenalty', 
    'w/o Adaptive\nBounding', 
    'LANS (Full)'
]

rmse_values = [0.151, 0.236, 0.240, 0.235, 0.238, 0.199]
improvements = [0, 0, 0, 0, 0, 0]  # Will calculate relative to Full LANS

# Calculate percentage change relative to Full LANS
full_rmse = 0.199
for i, rmse in enumerate(rmse_values):
    improvements[i] = ((rmse - full_rmse) / full_rmse) * 100

print("=" * 60)
print("GENERATING FIGURE 10: ABLATION STUDY")
print("=" * 60)
print(f"Full LANS RMSE: {full_rmse:.3f} m")
print("-" * 40)
for config, rmse, imp in zip(configs, rmse_values, improvements):
    if imp > 0:
        print(f"{config:20s}: {rmse:.3f} m (+{imp:.1f}%)")
    elif imp < 0:
        print(f"{config:20s}: {rmse:.3f} m ({imp:.1f}%)")
    else:
        print(f"{config:20s}: {rmse:.3f} m (baseline)")
print("=" * 60)

# ============================================================
# COLORS FOR BARS
# ============================================================
colors = [
    '#888888',      # Pure LQR - gray
    '#e74c3c',      # Pure PPO - red
    '#f39c12',      # w/o LQR Baseline - orange
    '#f39c12',      # w/o Latency Penalty - orange
    '#f39c12',      # w/o Adaptive Bounding - orange
    '#2ecc71'       # LANS (Full) - green
]

# ============================================================
# PLOT STYLE
# ============================================================
plt.rcParams.update({
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 14,
    'legend.fontsize': 10,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'font.family': 'serif',
    'font.serif': ['Times New Roman']
})

fig, ax = plt.subplots(figsize=(12, 6))

# ============================================================
# CREATE BAR CHART
# ============================================================
bars = ax.bar(configs, rmse_values, color=colors, edgecolor='black', linewidth=1.5)

# Add value labels on top of bars
for bar, rmse, imp in zip(bars, rmse_values, improvements):
    if imp > 0:
        label = f'{rmse:.3f}m\n(+{imp:.1f}%)'
    elif imp < 0:
        label = f'{rmse:.3f}m\n({imp:.1f}%)'
    else:
        label = f'{rmse:.3f}m\n(baseline)'
    
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.003,
            label, ha='center', va='bottom', fontsize=9, fontweight='bold')

# ============================================================
# ADD HORIZONTAL LINE FOR FULL LANS BASELINE
# ============================================================
ax.axhline(y=full_rmse, color='green', linestyle='--', linewidth=2, 
           label=f'Full LANS Baseline ({full_rmse:.3f}m)', alpha=0.7)

# ============================================================
# LABELS AND TITLE
# ============================================================
ax.set_ylabel('RMSE (m)', fontsize=12)
ax.set_title('Ablation Study: Contribution of Each LANS Component', 
             fontweight='bold', pad=15)
ax.set_ylim(0.12, 0.26)
ax.grid(True, linestyle='--', alpha=0.3, axis='y')

# ============================================================
# ADD ANNOTATIONS FOR KEY FINDINGS
# ============================================================
# Arrow showing degradation when removing LQR
ax.annotate('+20.6% degradation\nwithout LQR baseline', 
            xy=(2, 0.240), xytext=(1.5, 0.255),
            arrowprops=dict(arrowstyle='->', color='orange', lw=1.5),
            fontsize=9, color='orange', ha='center')

# Arrow showing degradation when removing latency penalty
ax.annotate('+18.1% degradation\nwithout latency penalty', 
            xy=(3, 0.235), xytext=(3.5, 0.250),
            arrowprops=dict(arrowstyle='->', color='orange', lw=1.5),
            fontsize=9, color='orange', ha='center')

# Annotation for Pure LQR being better
ax.annotate('LQR achieves\n0.151m (better tracking)', 
            xy=(0, 0.151), xytext=(-0.3, 0.175),
            arrowprops=dict(arrowstyle='->', color='gray', lw=1.5),
            fontsize=9, color='gray', ha='center')

# ============================================================
# ADD LEGEND
# ============================================================
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='#888888', label='Baseline (LQR)'),
    Patch(facecolor='#e74c3c', label='Baseline (PPO)'),
    Patch(facecolor='#f39c12', label='Ablated Variants'),
    Patch(facecolor='#2ecc71', label='Full LANS (Ours)')
]
ax.legend(handles=legend_elements, loc='upper right', fontsize=10)

# ============================================================
# SAVE FIGURE
# ============================================================
plt.tight_layout()
plt.savefig('Figure_10_Ablation_Study.png', dpi=300, bbox_inches='tight')
plt.savefig('Figure_10_Ablation_Study.pdf', bbox_inches='tight')
plt.show()

print("\n" + "=" * 60)
print("✅ FIGURE 10 SAVED SUCCESSFULLY!")
print("=" * 60)
print("Files created:")
print("   - Figure_10_Ablation_Study.png")
print("   - Figure_10_Ablation_Study.pdf")
print("=" * 60)
print("\n📊 Figure shows:")
print(f"   - Pure LQR: 0.151 m")
print(f"   - Pure PPO: 0.236 m")
print(f"   - w/o LQR Baseline: 0.240 m (+20.6%)")
print(f"   - w/o Latency Penalty: 0.235 m (+18.1%)")
print(f"   - w/o Adaptive Bounding: 0.238 m (+19.6%)")
print(f"   - Full LANS: 0.199 m (baseline)")
print("=" * 60)