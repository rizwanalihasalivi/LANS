"""
Figure: Lateral Trajectory Tracking Error Model
Creates a professional diagram for Section 2.3 of the paper.
"""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle, Circle, Arc
import os

# Create figures directory if it doesn't exist
os.makedirs('paper_figures', exist_ok=True)

# Set publication style
plt.rcParams.update({
    'font.size': 12,
    'axes.labelsize': 12,
    'axes.titlesize': 14,
    'legend.fontsize': 10,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'font.family': 'serif',
    'font.serif': ['Times New Roman']
})

# Create figure
fig, ax = plt.subplots(figsize=(12, 7))

# ============================================================
# 1. Draw Global Coordinate System (X, Y axes)
# ============================================================
# X-axis (horizontal)
ax.annotate('', xy=(14, 0.8), xytext=(0, 0.8),
            arrowprops=dict(arrowstyle='->', color='black', lw=1.5))
ax.text(14.2, 0.6, '$X$', fontsize=12, fontweight='bold')

# Y-axis (vertical)
ax.annotate('', xy=(0.8, 6), xytext=(0.8, 0.8),
            arrowprops=dict(arrowstyle='->', color='black', lw=1.5))
ax.text(0.5, 6.2, '$Y$', fontsize=12, fontweight='bold')

# Origin
ax.plot(0, 0.8, 'ko', markersize=4)
ax.text(-0.3, 0.6, '$O$', fontsize=12, fontweight='bold')

# ============================================================
# 2. Draw Reference Path (curved dashed line)
# ============================================================
x_path = np.linspace(1, 13, 300)
y_path = 1.5 + 2.5 * (1 - np.cos(np.pi * (x_path - 1) / 12)) / 2
ax.plot(x_path, y_path, 'k--', linewidth=2.5, label='Reference Path')

# ============================================================
# 3. Vehicle parameters
# ============================================================
veh_x = 5.8
veh_y = 1.5 + 2.5 * (1 - np.cos(np.pi * (veh_x - 1) / 12)) / 2

# Calculate vehicle heading angle (tangent to reference path)
dy_dx = (2.5 * np.pi / 12) * np.sin(np.pi * (veh_x - 1) / 12)
psi = np.arctan(dy_dx)
psi_deg = np.degrees(psi)

veh_length = 1.8
veh_width = 1.0

# ============================================================
# 4. Draw Vehicle (rectangle)
# ============================================================
rect = Rectangle((veh_x - veh_length/2, veh_y - veh_width/2),
                 veh_length, veh_width,
                 angle=psi_deg, rotation_point='center',
                 edgecolor='black', facecolor='lightgray',
                 linewidth=1.5, alpha=0.8, zorder=3)
ax.add_patch(rect)

# Draw CG (Center of Gravity)
cg = Circle((veh_x, veh_y), 0.08, color='black', fill=True, zorder=4)
ax.add_patch(cg)
ax.text(veh_x + 0.25, veh_y - 0.25, 'CG', fontsize=10)

# ============================================================
# 5. Draw Vehicle axes (x, y)
# ============================================================
# x-axis (red - forward)
ax.annotate('', xy=(veh_x + 1.3*np.cos(psi), veh_y + 1.3*np.sin(psi)),
            xytext=(veh_x, veh_y),
            arrowprops=dict(arrowstyle='->', color='red', lw=2))
ax.text(veh_x + 1.4*np.cos(psi), veh_y + 1.4*np.sin(psi) + 0.1,
        '$x$', color='red', fontsize=12, fontweight='bold')

# y-axis (blue - lateral left)
ax.annotate('', xy=(veh_x - 1.0*np.sin(psi), veh_y + 1.0*np.cos(psi)),
            xytext=(veh_x, veh_y),
            arrowprops=dict(arrowstyle='->', color='blue', lw=2))
ax.text(veh_x - 1.1*np.sin(psi) - 0.2, veh_y + 1.1*np.cos(psi) + 0.1,
        '$y$', color='blue', fontsize=12, fontweight='bold')

# ============================================================
# 6. Draw Lateral Error e_y (green double-headed arrow)
# ============================================================
y_ref_at_veh = 1.5 + 2.5 * (1 - np.cos(np.pi * (veh_x - 1) / 12)) / 2

# Perpendicular direction to reference path
perp_angle = psi + np.pi/2
arrow_length = 0.8
arrow_start_x = veh_x - arrow_length * np.cos(perp_angle)
arrow_start_y = veh_y - arrow_length * np.sin(perp_angle)
arrow_end_x = veh_x + arrow_length * np.cos(perp_angle)
arrow_end_y = veh_y + arrow_length * np.sin(perp_angle)

# Draw double-headed arrow
ax.annotate('', xy=(arrow_end_x, arrow_end_y), xytext=(arrow_start_x, arrow_start_y),
            arrowprops=dict(arrowstyle='<->', color='green', lw=2.5))
ax.text(veh_x + 0.4, veh_y + 0.3, '$e_y$', color='green', fontsize=12, fontweight='bold')

# ============================================================
# 7. Draw Heading Error e_psi (purple arc)
# ============================================================
arc = Arc((veh_x, veh_y), 1.6, 1.6,
          theta1=0, theta2=psi_deg,
          color='purple', linewidth=2, zorder=5)
ax.add_patch(arc)
ax.text(veh_x + 0.8, veh_y + 0.5, '$e_\\psi$', color='purple', fontsize=12, fontweight='bold')

# ============================================================
# 8. Draw a small arrow showing path tangent direction
# ============================================================
tangent_x = veh_x + 2.0 * np.cos(psi)
tangent_y = veh_y + 2.0 * np.sin(psi)
ax.annotate('', xy=(tangent_x, tangent_y), xytext=(veh_x, veh_y),
            arrowprops=dict(arrowstyle='->', color='gray', lw=1, alpha=0.5))

# ============================================================
# 9. Labels and legend
# ============================================================
ax.set_xlabel('Longitudinal Distance $X$ (m)', fontsize=12)
ax.set_ylabel('Lateral Position $Y$ (m)', fontsize=12)
ax.set_title('Lateral Trajectory Tracking Error Model', fontsize=14, fontweight='bold')

# Custom legend
ax.plot([], [], 'k--', linewidth=2, label='Reference Path')
ax.plot([], [], 's', color='lightgray', label='Vehicle')
ax.plot([], [], 'ko', label='Vehicle CG')
ax.plot([], [], 'r-', label='$x$ axis (longitudinal)')
ax.plot([], [], 'b-', label='$y$ axis (lateral)')
ax.plot([], [], 'g-', label='$e_y$ (lateral error)')
ax.plot([], [], 'purple', label='$e_\\psi$ (heading error)')
ax.legend(loc='upper right', fontsize=9, ncol=2)

# Axis limits and grid
ax.set_xlim(-1, 15)
ax.set_ylim(0.5, 6.5)
ax.grid(True, alpha=0.2, linestyle='--')

# ============================================================
# 10. Save the figure
# ============================================================
plt.tight_layout()
plt.savefig('paper_figures/fig_lateral_tracking_geometry.png', dpi=300, bbox_inches='tight')
plt.savefig('paper_figures/fig_lateral_tracking_geometry.pdf', bbox_inches='tight')
plt.show()

print("=" * 60)
print("✅ FIGURE SAVED SUCCESSFULLY!")
print("📍 PNG: paper_figures/fig_lateral_tracking_geometry.png")
print("📍 PDF: paper_figures/fig_lateral_tracking_geometry.pdf")
print("=" * 60)

# Check file size
import os
png_size = os.path.getsize('paper_figures/fig_lateral_tracking_geometry.png')
print(f"📊 PNG file size: {png_size} bytes")
if png_size > 20000:
    print("✅ File size is good. Open it with an image viewer.")
else:
    print("⚠️ File is too small. Something went wrong.")