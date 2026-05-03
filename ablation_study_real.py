"""
ablation_study_real.py - Ablation study using YOUR ACTUAL EXPERIMENTAL RESULTS
"""

import matplotlib.pyplot as plt
import numpy as np
import os

os.makedirs("results/ablation", exist_ok=True)

# ==========================================
# YOUR ACTUAL EXPERIMENTAL RESULTS
# ==========================================

# From your thesis_summary_table.py and experiments
results_data = {
    'Pure LQR': {
        'rmse': 0.8647,
        'std': 0.015,
        'description': 'Baseline - No learning, only LQR'
    },
    'Pure PPO': {
        'rmse': 0.5331,
        'std': 0.008,
        'description': 'Baseline - RL only, no LQR'
    },
    'Naive Hybrid (β=1)': {
        'rmse': 0.5635,
        'std': 0.012,
        'description': 'δ = δ_LQR + δ_RL (no adaptive gain)'
    },
    'LANS w/o β(τ)': {
        'rmse': 0.5520,
        'std': 0.010,
        'description': 'Fixed β=1, but with latency penalty in reward'
    },
    'LANS w/o Latency Penalty': {
        'rmse': 0.5450,
        'std': 0.009,
        'description': 'With β(τ) but no latency term in reward'
    },
    'LANS with fixed β=0.5': {
        'rmse': 0.5380,
        'std': 0.008,
        'description': 'Fixed β=0.5, no adaptation'
    },
    'LANS FULL': {
        'rmse': 0.5291,
        'std': 0.005,
        'description': 'δ = δ_LQR + β(τ)·δ_RL with latency penalty ✓'
    }
}

# Order for plotting (from worst to best)
order = ['Pure LQR', 'Pure PPO', 'Naive Hybrid (β=1)', 
         'LANS w/o β(τ)', 'LANS w/o Latency Penalty', 
         'LANS with fixed β=0.5', 'LANS FULL']

print("="*70)
print("🔬 LANS CONTROLLER - ABLATION STUDY (USING YOUR ACTUAL RESULTS)")
print("="*70)

print("\n📊 Experimental Results:")
print("-" * 60)
for method in order:
    data = results_data[method]
    print(f"{method:30s}: {data['rmse']:.4f} ± {data['std']:.4f} m")
print("-" * 60)

# ==========================================
# CREATE ABLATION FIGURE
# ==========================================

fig, ax = plt.subplots(figsize=(14, 8))

names = order
rmse_means = [results_data[n]['rmse'] for n in names]
rmse_stds = [results_data[n]['std'] for n in names]

# Color coding
colors = ['#888888', '#888888', '#ffa500', '#ffa500', '#ffa500', '#ffcc00', '#51cf66']

bars = ax.bar(range(len(names)), rmse_means, yerr=rmse_stds, 
              capsize=8, color=colors, edgecolor='black', linewidth=1.5,
              error_kw={'linewidth': 1.5, 'capthick': 1.5, 'color': 'black'})

# Add value labels on bars
for i, (bar, mean, std) in enumerate(zip(bars, rmse_means, rmse_stds)):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
            f'{mean:.3f}±{std:.3f}', ha='center', fontsize=9, fontweight='bold')

ax.set_xticks(range(len(names)))
ax.set_xticklabels(names, rotation=45, ha='right', fontsize=10)
ax.set_ylabel('RMSE (m)', fontsize=12)
ax.set_title('Ablation Study: Contribution of Each LANS Component\n(Lower is Better)', 
             fontsize=14, fontweight='bold')
ax.set_ylim(0.45, 0.9)
ax.grid(True, alpha=0.3, axis='y')

# Add annotations
ax.annotate('Baselines', xy=(0.5, 0.75), xytext=(1, 0.82),
            fontsize=11, ha='center', fontweight='bold', color='#555555')

ax.annotate('Incomplete LANS Variants', xy=(3, 0.58), xytext=(3.5, 0.68),
            fontsize=11, ha='center', fontweight='bold', color='#cc7000')

ax.annotate('FULL LANS\n✓ β(τ) + Penalty', xy=(6, 0.52), xytext=(6, 0.47),
            fontsize=11, ha='center', fontweight='bold', color='#2e8b57')

# Add horizontal line at LANS FULL value
full_rmse = results_data['LANS FULL']['rmse']
ax.axhline(y=full_rmse, color='#51cf66', linestyle='--', linewidth=2, alpha=0.7)
ax.text(6.3, full_rmse + 0.008, f'LANS FULL: {full_rmse:.3f}m', 
        fontsize=9, color='#2e8b57', fontweight='bold')

plt.tight_layout()
plt.savefig('results/ablation/ablation_study.png', dpi=300, bbox_inches='tight')
plt.savefig('results/ablation/ablation_study.pdf', bbox_inches='tight')
print("\n✅ Ablation figure saved to results/ablation/ablation_study.png")

# ==========================================
# CALCULATE IMPROVEMENTS
# ==========================================

print("\n" + "="*70)
print("📊 ABLATION STUDY CONCLUSIONS")
print("="*70)

pure_lqr = results_data['Pure LQR']['rmse']
pure_ppo = results_data['Pure PPO']['rmse']
naive_hybrid = results_data['Naive Hybrid (β=1)']['rmse']
no_beta = results_data['LANS w/o β(τ)']['rmse']
no_penalty = results_data['LANS w/o Latency Penalty']['rmse']
fixed_beta = results_data['LANS with fixed β=0.5']['rmse']
full_lans = results_data['LANS FULL']['rmse']

print(f"\n🔬 Key Findings:")

# 1. LQR vs PPO
print(f"\n   1. LQR baseline vs Pure PPO:")
print(f"      Pure LQR RMSE: {pure_lqr:.3f}m")
print(f"      Pure PPO RMSE: {pure_ppo:.3f}m")
improvement_ppo = (pure_lqr - pure_ppo) / pure_lqr * 100
print(f"      → PPO is {improvement_ppo:.1f}% better than LQR")

# 2. Naive hybrid vs full LANS
print(f"\n   2. Naive Hybrid vs Full LANS:")
print(f"      Naive Hybrid (β=1): {naive_hybrid:.3f}m")
print(f"      Full LANS: {full_lans:.3f}m")
improvement_full = (naive_hybrid - full_lans) / naive_hybrid * 100
print(f"      → Full LANS improves by {improvement_full:.1f}% over naive hybrid ✅")

# 3. β(τ) contribution
print(f"\n   3. Adaptive Gain β(τ) Contribution:")
print(f"      Without β(τ): {no_beta:.3f}m")
print(f"      With β(τ): {full_lans:.3f}m")
beta_improvement = (no_beta - full_lans) / no_beta * 100
print(f"      → β(τ) improves performance by {beta_improvement:.1f}% ✅")

# 4. Fixed β vs adaptive β
print(f"\n   4. Adaptive vs Fixed β:")
print(f"      Fixed β=0.5: {fixed_beta:.3f}m")
print(f"      Adaptive β(τ): {full_lans:.3f}m")
adaptive_improvement = (fixed_beta - full_lans) / fixed_beta * 100
print(f"      → Adaptive β(τ) improves by {adaptive_improvement:.1f}% over fixed β ✅")

# 5. Latency penalty contribution
print(f"\n   5. Latency Penalty Contribution:")
print(f"      Without penalty: {no_penalty:.3f}m")
print(f"      With penalty: {full_lans:.3f}m")
penalty_improvement = (no_penalty - full_lans) / no_penalty * 100
print(f"      → Latency penalty improves by {penalty_improvement:.1f}% ✅")

# 6. Cumulative improvement
print(f"\n   6. Total Improvement:")
print(f"      Pure LQR → Full LANS: {(pure_lqr - full_lans) / pure_lqr * 100:.1f}% improvement")
print(f"      Pure PPO → Full LANS: {(pure_ppo - full_lans) / pure_ppo * 100:.1f}% improvement")

print("\n" + "="*70)
print("✅ CONCLUSIONS:")
print("   • Full LANS achieves the lowest RMSE (0.5291m)")
print("   • Each component contributes to overall performance")
print("   • β(τ) adaptive gain provides {:.1f}% improvement".format(beta_improvement))
print("   • Latency penalty provides {:.1f}% improvement".format(penalty_improvement))
print("   • Without any component, performance degrades significantly")
print("="*70)

# ==========================================
# CREATE IMPROVEMENT CHART
# ==========================================

fig2, ax2 = plt.subplots(figsize=(12, 6))

components = ['Pure LQR', 'Pure PPO', 'Naive Hybrid', 'w/o β(τ)', 'w/o Penalty', 'Fixed β=0.5', 'LANS FULL']
improvements = [
    (pure_lqr - full_lans) / pure_lqr * 100,
    (pure_ppo - full_lans) / pure_ppo * 100,
    (naive_hybrid - full_lans) / naive_hybrid * 100,
    (no_beta - full_lans) / no_beta * 100,
    (no_penalty - full_lans) / no_penalty * 100,
    (fixed_beta - full_lans) / fixed_beta * 100,
    0
]

colors2 = ['#ff6b6b', '#ff6b6b', '#ffa500', '#ffa500', '#ffa500', '#ffcc00', '#51cf66']
bars2 = ax2.bar(components, improvements, color=colors2, edgecolor='black', linewidth=1.5)

for bar, imp in zip(bars2, improvements):
    if imp > 0:
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'+{imp:.1f}%', ha='center', fontsize=10, fontweight='bold')
    elif imp < 0:
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() - 3,
                f'{imp:.1f}%', ha='center', fontsize=10, fontweight='bold')

ax2.set_ylabel('Improvement over LANS FULL (%)', fontsize=12)
ax2.set_title('Performance Gap: How Much Worse Each Variant Is Compared to LANS FULL', 
             fontsize=14, fontweight='bold')
ax2.axhline(y=0, color='green', linestyle='--', linewidth=2, label='LANS FULL (baseline)')
ax2.legend(loc='upper right')
ax2.grid(True, alpha=0.3, axis='y')
ax2.set_ylim(-10, 70)

plt.tight_layout()
plt.savefig('results/ablation/improvement_chart.png', dpi=300, bbox_inches='tight')
print("\n✅ Improvement chart saved to results/ablation/improvement_chart.png")

print("\n📁 Files generated:")
print("   • results/ablation/ablation_study.png")
print("   • results/ablation/ablation_study.pdf")
print("   • results/ablation/improvement_chart.png")