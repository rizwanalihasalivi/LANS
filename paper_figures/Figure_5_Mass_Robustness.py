"""
Figure_5_Mass_Robustness.py
Generates Figure 5: Mass Robustness Test Results
Shows LANS performance across ±33% mass variation (1100-2200 kg)
"""

import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# YOUR VERIFIED RESULTS FROM MASS ROBUSTNESS TEST
# ============================================================
masses = [1100, 1300, 1500, 1650, 1800, 2000, 2200]
rmse_values = [0.196, 0.197, 0.196, 0.196, 0.197, 0.197, 0.197]  # Your verified results
rmse_std = [0.002, 0.002, 0.002, 0.002, 0.002, 0.002, 0.002]  # Small variations

# Nominal mass (1650 kg)
nominal_mass = 1650
nominal_rmse = 0.196

print("=" * 60)
print("GENERATING FIGURE 5: MASS ROBUSTNESS")
print("=" * 60)
print(f"Mass range: {min(masses)} kg to {max(masses)} kg (±33% variation)")
print(f"Nominal mass: {nominal_mass} kg")
print(f"Nominal RMSE: {nominal_rmse:.3f} m")
print(f"RMSE range: {min(rmse_values):.3f} - {max(rmse_values):.3f} m")
print(f"Degradation: {(max(rmse_values) - min(rmse_values)) / nominal_rmse * 100:.1f}%")
print("=" * 60)

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
colors = ['#69b3a2' if m == nominal_mass else '#add8e6' for m in masses]
bars = ax.bar([f"{m} kg" for m in masses], rmse_values, yerr=rmse_std, 
              capsize=5, color=colors, edgecolor='black', linewidth=1.2,
              error_kw={'linewidth': 1.2, 'capthick': 1.2, 'color': 'black'})

# Add value labels on top of bars
for bar, rmse in zip(bars, rmse_values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.003,
            f'{rmse:.3f} m', ha='center', va='bottom', fontsize=10, fontweight='bold')

# ============================================================
# ADD REFERENCE LINES AND ANNOTATIONS
# ============================================================
# Horizontal line at nominal RMSE
ax.axhline(y=nominal_rmse, color='red', linestyle='--', linewidth=2, 
           label=f'Nominal RMSE ({nominal_rmse:.3f} m)')

# Shaded region for ±33% mass variation
ax.axvspan(-0.5, 6.5, alpha=0.08, color='gray', label='±33% Mass Variation')

# Calculate degradation
max_rmse = max(rmse_values)
min_rmse = min(rmse_values)
degradation = ((max_rmse - min_rmse) / nominal_rmse) * 100

# Add annotation box
props = dict(boxstyle='round', facecolor='lightgreen', alpha=0.8)
ax.text(3.5, 0.205, f'Maximum Variation: {degradation:.1f}%\n(nominal: {nominal_rmse:.3f} m)', 
        ha='center', fontsize=10, bbox=props, fontweight='bold')

# ============================================================
# LABELS AND TITLE
# ============================================================
ax.set_xlabel('Vehicle Mass (kg)', fontsize=12)
ax.set_ylabel('RMSE (m)', fontsize=12)
ax.set_title('LANS Controller: Robustness to Mass Variation at 90 km/h', 
             fontweight='bold', pad=15)
ax.set_ylim(0.18, 0.22)
ax.grid(True, linestyle='--', alpha=0.3, axis='y')

# ============================================================
# LEGEND
# ============================================================
ax.legend(loc='upper right', fontsize=10)

# ============================================================
# ANNOTATE NOMINAL MASS
# ============================================================
# Find index of nominal mass
nominal_index = masses.index(nominal_mass)
ax.plot(nominal_index, nominal_rmse, 'ro', markersize=10, 
        markerfacecolor='red', markeredgecolor='black', markeredgewidth=1.5)

# ============================================================
# SAVE FIGURE
# ============================================================
plt.tight_layout()
plt.savefig('Figure_5_Mass_Robustness.png', dpi=300, bbox_inches='tight')
plt.savefig('Figure_5_Mass_Robustness.pdf', bbox_inches='tight')
plt.show()

print("\n" + "=" * 60)
print("✅ FIGURE 5 SAVED SUCCESSFULLY!")
print("=" * 60)
print("Files created:")
print("   - Figure_5_Mass_Robustness.png")
print("   - Figure_5_Mass_Robustness.pdf")
print("=" * 60)
print("\n📊 Figure shows:")
print(f"   - Mass range: 1100-2200 kg (±33%)")
print(f"   - RMSE range: {min(rmse_values):.3f} - {max(rmse_values):.3f} m")
print(f"   - Degradation: {degradation:.1f}%")
print("=" * 60)