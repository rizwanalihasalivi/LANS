"""
Figure_6_ZeroShot_Generalization.py
Generates Figure 6: Zero-Shot Generalization Results
Shows LANS performance on unseen path geometries
"""

import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# YOUR VERIFIED RESULTS FROM ZERO-SHOT GENERALIZATION TEST
# ============================================================
path_types = ['DLC (Trained)', 'Sine Wave\n(Unseen)', 'Snake Path\n(Unseen)', 'Sharp Step\n(Unseen)']
rmse_values = [0.199, 1.224, 1.254, 0.173]  # Your verified results

# Calculate degradation percentages
dlc_rmse = 0.199
degradation_sine = ((1.224 - dlc_rmse) / dlc_rmse) * 100
degradation_snake = ((1.254 - dlc_rmse) / dlc_rmse) * 100
degradation_sharp = ((0.173 - dlc_rmse) / dlc_rmse) * 100

print("=" * 60)
print("GENERATING FIGURE 6: ZERO-SHOT GENERALIZATION")
print("=" * 60)
print(f"DLC (Trained) RMSE: {dlc_rmse:.3f} m")
print(f"Sine Wave RMSE: {1.224:.3f} m ({degradation_sine:.1f}% higher)")
print(f"Snake Path RMSE: {1.254:.3f} m ({degradation_snake:.1f}% higher)")
print(f"Sharp Step RMSE: {0.173:.3f} m ({degradation_sharp:.1f}% lower)")
print("=" * 60)

# ============================================================
# COLORS FOR BARS
# ============================================================
colors = ['#2ecc71', '#e74c3c', '#e74c3c', '#3498db']  # Green for DLC, Red for hard, Blue for easy

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

fig, ax = plt.subplots(figsize=(10, 6))

# ============================================================
# CREATE BAR CHART
# ============================================================
bars = ax.bar(path_types, rmse_values, color=colors, edgecolor='black', linewidth=1.5)

# Add value labels on top of bars
for bar, rmse in zip(bars, rmse_values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
            f'{rmse:.3f} m', ha='center', va='bottom', fontsize=11, fontweight='bold')

# ============================================================
# ADD DEGRADATION ANNOTATIONS
# ============================================================
# Sine wave annotation
ax.annotate(f'+{degradation_sine:.0f}%', 
            xy=(1, 1.224), xytext=(1, 1.35),
            ha='center', fontsize=10, color='red', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='red', lw=1))

# Snake path annotation
ax.annotate(f'+{degradation_snake:.0f}%', 
            xy=(2, 1.254), xytext=(2, 1.38),
            ha='center', fontsize=10, color='red', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='red', lw=1))

# Sharp step annotation
ax.annotate(f'{degradation_sharp:.0f}% better', 
            xy=(3, 0.173), xytext=(3, 0.30),
            ha='center', fontsize=10, color='green', fontweight='bold',
            arrowprops=dict(arrowstyle='->', color='green', lw=1))

# ============================================================
# ADD HORIZONTAL LINE FOR TRAINED BASELINE
# ============================================================
ax.axhline(y=dlc_rmse, color='gray', linestyle='--', linewidth=2, alpha=0.7)
ax.text(3.2, dlc_rmse + 0.02, f'Trained Baseline\n({dlc_rmse:.3f} m)', 
        fontsize=9, color='gray', ha='left')

# ============================================================
# LABELS AND TITLE
# ============================================================
ax.set_xlabel('Path Type', fontsize=12)
ax.set_ylabel('RMSE (m)', fontsize=12)
ax.set_title('Zero-Shot Generalization to Unseen Path Geometries', 
             fontweight='bold', pad=15)
ax.set_ylim(0, 1.6)
ax.grid(True, linestyle='--', alpha=0.3, axis='y')

# ============================================================
# ADD SUMMARY TEXT BOX
# =============================================-------=======
props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
summary_text = f"Summary:\n"
summary_text += f"• Sine/Snake: +{degradation_sine:.0f}% higher error (expected)\n"
summary_text += f"• Sharp Step: {degradation_sharp:.0f}% lower error\n"
summary_text += f"• LANS generalizes well to similar maneuvers"

ax.text(0.02, 0.98, summary_text, transform=ax.transAxes, fontsize=9,
        verticalalignment='top', bbox=props)

# ============================================================
# SAVE FIGURE
# ============================================================
plt.tight_layout()
plt.savefig('Figure_6_ZeroShot_Generalization.png', dpi=300, bbox_inches='tight')
plt.savefig('Figure_6_ZeroShot_Generalization.pdf', bbox_inches='tight')
plt.show()

print("\n" + "=" * 60)
print("✅ FIGURE 6 SAVED SUCCESSFULLY!")
print("=" * 60)
print("Files created:")
print("   - Figure_6_ZeroShot_Generalization.png")
print("   - Figure_6_ZeroShot_Generalization.pdf")
print("=" * 60)
print("\n📊 Figure shows:")
print(f"   - DLC (Trained): {dlc_rmse:.3f} m (baseline)")
print(f"   - Sine Wave: 1.224 m (+{degradation_sine:.0f}%)")
print(f"   - Snake Path: 1.254 m (+{degradation_snake:.0f}%)")
print(f"   - Sharp Step: 0.173 m ({degradation_sharp:.0f}% better)")
print("=" * 60)