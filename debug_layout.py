"""
Generate a detailed debug PDF showing exact container boundaries,
FancyBboxPatch areas (including pad expansion), text anchor points,
and coordinate annotations.

Page 1: Overall report layout
Page 2: Taichi diagram internal layout (data coordinates)
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch, Rectangle

plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False


def page1_overall_layout(pdf):
    """Page 1: Full report layout with all containers."""
    fig = plt.figure(figsize=(8.27, 11.69))

    gs = GridSpec(4, 1, figure=fig,
                  height_ratios=[0.08, 0.1, 0.4, 0.45],
                  hspace=0.35,
                  left=0.1, right=0.9, top=0.95, bottom=0.05)

    def mark_axes(ax, label, color):
        for sp in ax.spines.values():
            sp.set_visible(True)
            sp.set_edgecolor(color)
            sp.set_linewidth(2)
        ax.set_xticks([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.tick_params(labelsize=6, colors='gray')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.text(0.01, 0.99, label, ha='left', va='top', fontsize=8,
                fontweight='bold', color=color, transform=ax.transAxes)

    # Row 0: Title
    ax0 = fig.add_subplot(gs[0])
    mark_axes(ax0, 'Row 0 axes (title)', '#FF6B6B')
    ax0.axhline(0.5, color='gray', ls=':', lw=0.5)
    ax0.axvline(0.5, color='gray', ls=':', lw=0.5)
    ax0.plot(0.5, 0.5, 'x', color='#FF6B6B', ms=8, mew=2)
    ax0.text(0.5, 0.42, 'text(0.5, 0.5) ha=center', ha='center', fontsize=7, color='#FF6B6B')

    # Row 1: Patient Info
    ax1 = fig.add_subplot(gs[1])
    mark_axes(ax1, 'Row 1 axes (patient info)', '#4ECDC4')

    p_bbox = FancyBboxPatch((0.1, 0.05), 0.8, 0.9,
                              boxstyle="round,pad=0.05",
                              fc="none", ec="blue", lw=1.5, ls='--',
                              transform=ax1.transAxes, clip_on=False)
    ax1.add_patch(p_bbox)
    logical = Rectangle((0.1, 0.05), 0.8, 0.9,
                          fill=False, ec='red', lw=1, ls=':',
                          transform=ax1.transAxes, clip_on=False)
    ax1.add_patch(logical)
    ax1.text(0.5, -0.15, 'Blue dashed = visible (pad=0.05)  |  Red dotted = logical rect',
             ha='center', fontsize=6, color='gray', transform=ax1.transAxes)

    # Updated text anchor points
    for x, label in [(0.05, 'left text\nx=0.05'), (0.53, 'right text\nx=0.53')]:
        ax1.plot(x, 0.5, 'o', color='red', ms=6)
        ax1.text(x, 0.25, label, ha='center', fontsize=6, color='red',
                 transform=ax1.transAxes)

    ax1.axvline(0.5, color='gray', ls=':', lw=0.5)

    # Row 2: Taichi + Table
    gs_middle = gs[2].subgridspec(1, 2, wspace=0.15)

    ax2L = fig.add_subplot(gs_middle[0, 0])
    mark_axes(ax2L, 'Row 2 Col 0 (taichi)', '#45B7D1')
    ax2L.text(0.5, 0.5, 'Taichi diagram\n(see Page 2 for detail)',
              ha='center', va='center', fontsize=8, color='#45B7D1',
              transform=ax2L.transAxes)

    ax2R = fig.add_subplot(gs_middle[0, 1])
    mark_axes(ax2R, 'Row 2 Col 1 (table)', '#45B7D1')
    ax2R.text(0.5, 0.5, 'Table fills\nbbox=[0,0,1,1]',
              ha='center', va='center', fontsize=8, color='#45B7D1',
              transform=ax2R.transAxes)

    # Row 3: Analysis
    ax3 = fig.add_subplot(gs[3])
    mark_axes(ax3, 'Row 3 axes (analysis & recommendation)', '#96CEB4')

    text_bbox = FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                                 boxstyle="round,pad=0.05",
                                 fc="none", ec="blue", lw=1.5, ls='--',
                                 transform=ax3.transAxes, clip_on=False)
    ax3.add_patch(text_bbox)
    logical3 = Rectangle((0.02, 0.02), 0.96, 0.96,
                           fill=False, ec='red', lw=1, ls=':',
                           transform=ax3.transAxes, clip_on=False)
    ax3.add_patch(logical3)
    ax3.text(0.5, -0.06,
             'Blue = visible (pad extends to -0.03 ~ 1.03, clip_on=False!)\n'
             'Red = logical rect (0.02, 0.02) w=0.96 h=0.96',
             ha='center', fontsize=6, color='gray', transform=ax3.transAxes)

    anchors = [
        (0.06, 0.90, '[ Analysis ] bold  (0.06, 0.90)'),
        (0.06, 0.82, 'body text  (0.06, ~0.82)'),
        (0.06, 0.50, '[ Recommendation ] bold  (0.06, ~dynamic)'),
        (0.06, 0.42, 'body text  (0.06, ~dynamic)'),
    ]
    for x, y_pos, label in anchors:
        ax3.plot(x, y_pos, 'o', color='red', ms=4)
        ax3.text(x + 0.02, y_pos, label, ha='left', va='center',
                 fontsize=5, color='red', transform=ax3.transAxes)

    fig.text(0.5, 0.98,
             'Page 1: Overall Layout  |  GridSpec(4,1)  left=0.1 right=0.9 top=0.95 bottom=0.05 hspace=0.35\n'
             'height_ratios=[0.08, 0.1, 0.4, 0.45]  |  Figure 8.27 x 11.69 (A4)',
             ha='center', va='top', fontsize=8, color='gray', fontstyle='italic')

    for x in [0.1, 0.9]:
        fig.patches.append(
            plt.Rectangle((x, 0.05), 0.001, 0.9,
                           transform=fig.transFigure, fc='orange', alpha=0.5))
    fig.text(0.08, 0.5, 'left=0.1', ha='center', va='center', fontsize=7,
             color='orange', rotation=90, transform=fig.transFigure)
    fig.text(0.92, 0.5, 'right=0.9', ha='center', va='center', fontsize=7,
             color='orange', rotation=90, transform=fig.transFigure)

    pdf.savefig(fig, dpi=150)
    plt.close(fig)


def page2_taichi_detail(pdf):
    """Page 2: Taichi diagram internal layout in DATA coordinates."""
    fig, ax = plt.subplots(figsize=(8.27, 11.69))

    # Use the same data coordinate system as plotting.py
    xlim = (-1.2, 2.6)  # English version (wider)
    ylim = (-2.5, 1.2)
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.2, ls='--')

    # Show axes ticks for reference
    import numpy as np
    ax.set_xticks(np.arange(xlim[0], xlim[1] + 0.1, 0.5))
    ax.set_yticks(np.arange(ylim[0], ylim[1] + 0.1, 0.5))
    ax.tick_params(labelsize=7, colors='gray')

    # --- Taichi circle outline ---
    R = 1.0
    circle = mpatches.Circle((0, 0), R, fill=False, ec='black', lw=2)
    ax.add_patch(circle)
    ax.text(0, 0, 'Taichi Circle\ncenter=(0,0)\nR=1.0',
            ha='center', va='center', fontsize=9, color='black',
            bbox=dict(fc='white', alpha=0.8, ec='none'))

    # --- Legend elements ---
    legend_x = 1.25
    # Dots
    ax.scatter(legend_x, 0.3, c='black', s=150, marker='o', zorder=5)
    ax.scatter(legend_x, -0.3, c='white', s=150, marker='o',
               edgecolors='black', linewidth=1, zorder=5)
    # Text anchors
    text_offset = 0.20
    ax.plot(legend_x + text_offset, 0.3, 's', color='red', ms=6, zorder=6)
    ax.text(legend_x + text_offset + 0.05, 0.3,
            f'Sympathetic\ntext x={legend_x}+{text_offset}={legend_x+text_offset:.2f}\ny=0.3, fs=11',
            ha='left', va='center', fontsize=7, color='red')

    ax.plot(legend_x + text_offset, -0.3, 's', color='red', ms=6, zorder=6)
    ax.text(legend_x + text_offset + 0.05, -0.3,
            f'Parasympathetic\ntext x={legend_x+text_offset:.2f}\ny=-0.3, fs=11',
            ha='left', va='center', fontsize=7, color='red')

    # Legend dot positions
    ax.annotate(f'dot x={legend_x}', (legend_x, 0.3),
                xytext=(legend_x - 0.3, 0.6),
                fontsize=6, color='blue',
                arrowprops=dict(arrowstyle='->', color='blue', lw=0.8))

    # --- Info text box ---
    info_text = 'LF/HF ratio = 0.900\nLFnu = 42.9%\nHFnu = 57.1%'
    ax.text(0, -1.4, info_text, ha='center', va='top', fontsize=11,
            linespacing=2.0,
            bbox=dict(boxstyle='round,pad=0.8', facecolor='lightgray', alpha=0.3))
    ax.plot(0, -1.4, 'x', color='red', ms=10, mew=2, zorder=6)
    ax.text(0.15, -1.35, 'info_text anchor\n(0, -1.4) va=top\nfs=11, linespacing=2.0\nbbox pad=0.8',
            ha='left', va='top', fontsize=7, color='red')

    # --- Axis limits annotations ---
    # x limits
    ax.axvline(xlim[0], color='orange', ls='--', lw=1, alpha=0.5)
    ax.axvline(xlim[1], color='orange', ls='--', lw=1, alpha=0.5)
    ax.text(xlim[0] + 0.05, ylim[1] - 0.1, f'xlim[0]={xlim[0]}',
            fontsize=7, color='orange', va='top')
    ax.text(xlim[1] - 0.05, ylim[1] - 0.1, f'xlim[1]={xlim[1]}\n(en)',
            fontsize=7, color='orange', va='top', ha='right')

    # Chinese xlim
    ax.axvline(1.6, color='purple', ls=':', lw=1, alpha=0.5)
    ax.text(1.6, ylim[1] - 0.3, 'zh xlim[1]=1.6',
            fontsize=7, color='purple', va='top', ha='center')

    # y limits
    ax.axhline(ylim[0], color='orange', ls='--', lw=1, alpha=0.5)
    ax.axhline(ylim[1], color='orange', ls='--', lw=1, alpha=0.5)
    ax.text(xlim[0] + 0.05, ylim[0] + 0.05, f'ylim[0]={ylim[0]}',
            fontsize=7, color='orange')
    ax.text(xlim[0] + 0.05, ylim[1] - 0.05, f'ylim[1]={ylim[1]}',
            fontsize=7, color='orange', va='top')

    # Key reference lines
    ax.axhline(0, color='gray', ls=':', lw=0.5, alpha=0.3)
    ax.axvline(0, color='gray', ls=':', lw=0.5, alpha=0.3)

    fig.suptitle('Page 2: Taichi Diagram Internal Layout (DATA coordinates)\n'
                 'set_aspect=equal  |  axis("off") in actual report',
                 fontsize=10, color='gray', fontstyle='italic')

    pdf.savefig(fig, dpi=150)
    plt.close(fig)


# --- Generate PDF ---
with PdfPages('debug_layout.pdf') as pdf:
    page1_overall_layout(pdf)
    page2_taichi_detail(pdf)

print("OK -> debug_layout.pdf (2 pages)")
