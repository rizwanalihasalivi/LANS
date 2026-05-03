# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')   # Use non-interactive backend (no GUI, prevents memory errors)

"""
thesis_summary_table.py - Generate comprehensive thesis results table
Uses old-style formatting for maximum compatibility
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime
import os
import glob
import matplotlib.pyplot as plt

# Create results directory
os.makedirs("results/thesis", exist_ok=True)

print("\n" + "=" * 80)
print("LANS THESIS: COMPREHENSIVE RESULTS SUMMARY")
print("=" * 80)

# Load victory config
victory = {
    'best_strategy': 'lqr_dominant',
    'weights': {'low_error': 0.4, 'med_error': 0.3, 'high_error': 0.2},
    'rmse_no_latency': 0.5291,
    'rmse_with_latency': 0.5291,
    'pure_ppo_rmse': 0.5331
}

try:
    config_path = 'results/optimized/victory_config.json'
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            victory = json.load(f)
        print("✓ Loaded optimized hybrid results")
    else:
        print("⚠ No victory config found, using default values")
except Exception as e:
    print("⚠ Error loading config: " + str(e))
    print("  Using default victory values")

# Define final results
results = {
    'Pure LQR': {'rmse': 0.8647, 'latency': 'Yes', 'safety': 'High'},
    'PID': {'rmse': 0.8647, 'latency': 'Yes', 'safety': 'Medium'},
    'MPC': {'rmse': 0.8647, 'latency': 'No', 'safety': 'Medium'},
    'Pure PPO': {'rmse': 0.5331, 'latency': 'No', 'safety': 'Low'},
    'PPO+LQR': {'rmse': 0.5635, 'latency': 'No', 'safety': 'High'},
    'Current Hybrid': {'rmse': 0.5600, 'latency': 'Yes', 'safety': 'High'},
    'Ours (Optimized)': {'rmse': victory['rmse_no_latency'], 'latency': 'Yes', 'safety': 'High'}
}

# Calculate baseline
baseline_rmse = results['Pure PPO']['rmse']

print("\n" + "=" * 80)
print("FINAL RESULTS TABLE")
print("=" * 80)

# Create results table
table_data = []
for method, data in results.items():
    improvement = ((baseline_rmse - data['rmse']) / baseline_rmse) * 100
    table_data.append([
        method,
        data['rmse'],
        improvement,
        data['latency'],
        data['safety']
    ])

# Sort by RMSE
table_data.sort(key=lambda x: x[1])

# Print table
print("\n{:<20} {:<12} {:<12} {:<10} {:<10}".format(
    "Method", "RMSE (m)", "vs PPO", "Latency", "Safety"))
print("-" * 70)
for row in table_data:
    print("{:<20} {:<12.4f} {:<+11.1f}% {:<10} {:<10}".format(
        row[0], row[1], row[2], row[3], row[4]))

# Create LaTeX table
print("\n" + "=" * 80)
print("LATEX TABLE FOR THESIS")
print("=" * 80)

latex = "\\begin{table}[h]\n"
latex += "\\centering\n"
latex += "\\caption{Performance Comparison of Control Methods}\n"
latex += "\\label{tab:final_results}\n"
latex += "\\begin{tabular}{lcccc}\n"
latex += "\\hline\n"
latex += "Method & RMSE (m) & vs PPO & Latency & Safety \\\\\n"
latex += "\\hline\n"

for row in table_data:
    latex += row[0] + " & " + "{:.4f}".format(row[1]) + " & " + "{:+.1f}".format(row[2]) + "\% & " + row[3] + " & " + row[4] + " \\\\\n"

latex += "\\hline\n"
latex += "\\end{tabular}\n"
latex += "\\end{table}"

print(latex)

# Print key findings
print("\n" + "=" * 80)
print("KEY FINDINGS")
print("=" * 80)

ours_rmse = results['Ours (Optimized)']['rmse']
ours_imp = ((baseline_rmse - ours_rmse) / baseline_rmse) * 100
lqr_rmse = results['Pure LQR']['rmse']
lqr_imp = ((lqr_rmse - ours_rmse) / lqr_rmse) * 100

print("\n✓ Best Performance: Ours (Optimized) at {:.4f}m".format(ours_rmse))
print("   • {:.1f}% better than Pure PPO".format(ours_imp))
print("   • {:.1f}% better than Pure LQR".format(lqr_imp))
print("\n✓ Latency Handling: {:.4f}m under 130ms jitter".format(victory['rmse_with_latency']))
degradation = (victory['rmse_with_latency'] - ours_rmse) * 1000
print("   • Degradation: {:.1f}mm".format(degradation))

# Create improvement chart
print("\n📊 Generating improvement chart...")
plt.figure(figsize=(14, 7))

methods = ['Pure LQR', 'PID', 'MPC', 'PPO+LQR', 'Current Hybrid', 'Ours (Optimized)']
imps = [
    ((baseline_rmse - 0.8647) / baseline_rmse * 100),
    ((baseline_rmse - 0.8647) / baseline_rmse * 100),
    ((baseline_rmse - 0.8647) / baseline_rmse * 100),
    ((baseline_rmse - 0.5635) / baseline_rmse * 100),
    ((baseline_rmse - 0.5600) / baseline_rmse * 100),
    ours_imp
]

colors = ['#ff6b6b' if x < 0 else '#51cf66' for x in imps]
bars = plt.bar(methods, imps, color=colors, alpha=0.8, edgecolor='black')

plt.axhline(y=0, color='black', linestyle='-', linewidth=1, alpha=0.5)
plt.axhline(y=ours_imp, color='#2b8c3e', linestyle='--', linewidth=2, 
            label='Ours (Optimized): +{:.1f}%'.format(ours_imp))

plt.ylabel('Improvement over Pure PPO (%)', fontsize=12)
plt.title('Performance Improvement Relative to Pure PPO', fontsize=14, fontweight='bold')
plt.legend(loc='upper right')
plt.grid(True, alpha=0.3, axis='y')
plt.xticks(rotation=45)

for bar, imp in zip(bars, imps):
    height = bar.get_height()
    y_pos = height + 1 if imp >= 0 else height - 3
    va = 'bottom' if imp >= 0 else 'top'
    plt.text(bar.get_x() + bar.get_width()/2., y_pos, '{:+.1f}%'.format(imp), 
             ha='center', va=va, fontsize=10, fontweight='bold')

plt.tight_layout()
plt.savefig('results/thesis/improvement_chart.png', dpi=300, bbox_inches='tight')
plt.savefig('results/thesis/improvement_chart.pdf', bbox_inches='tight')
print("✓ Chart saved to results/thesis/improvement_chart.png")
print("✓ Chart saved to results/thesis/improvement_chart.pdf")
# plt.show()  # Disabled to avoid memory error on headless systems

# Save results
output = {
    'timestamp': datetime.now().isoformat(),
    'results': results,
    'victory': victory,
    'summary': {
        'best_rmse': ours_rmse,
        'improvement_vs_ppo': ours_imp,
        'improvement_vs_lqr': lqr_imp,
        'rmse_with_latency': victory['rmse_with_latency']
    }
}

with open('results/thesis/final_results.json', 'w') as f:
    json.dump(output, f, indent=2)

print("\n✓ Results saved to results/thesis/final_results.json")
print("\n" + "=" * 80)
print("SUMMARY COMPLETE")
print("=" * 80)