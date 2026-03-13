import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from scipy.interpolate import interp1d
from scipy.signal import welch


def create_taichi_plot(lf_hf_ratio, lf_nu=None, hf_nu=None, add_legend=True,
                       ax=None, lang='zh'):
    """
    Create a Taichi (yin-yang) plot showing sympathetic/parasympathetic balance.

    Parameters
    ----------
    lf_hf_ratio : float
        LF/HF ratio.
    lf_nu : float, optional
        LF normalized units (percentage).
    hf_nu : float, optional
        HF normalized units (percentage).
    add_legend : bool
        Whether to add legend labels.
    ax : matplotlib.axes.Axes, optional
        Target axes to draw into. If None, creates a new figure.
    lang : str
        Language for labels: 'zh' (default) or 'en'.

    Returns
    -------
    fig : matplotlib.figure.Figure or None
        The figure if a new one was created, otherwise None.
    """
    total = 1 + lf_hf_ratio
    sympathetic_ratio = lf_hf_ratio / total
    parasympathetic_ratio = 1 / total

    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 6))

    R = 0.8
    r_sympathetic = R * sympathetic_ratio
    r_parasympathetic = R * parasympathetic_ratio

    # White base
    base = patches.Circle((0, 0), R, facecolor='white', edgecolor='none')
    ax.add_patch(base)

    # Right half black (sympathetic)
    right_half = patches.Wedge((0, 0), R, -90, 90,
                               facecolor='black', edgecolor='none', linewidth=0)
    ax.add_patch(right_half)

    # Bottom black circle
    bottom_circle = patches.Circle((0, -R + r_sympathetic), r_sympathetic,
                                   facecolor='black', edgecolor='none', linewidth=0)
    ax.add_patch(bottom_circle)

    # Top white circle
    top_circle = patches.Circle((0, R - r_parasympathetic), r_parasympathetic,
                                facecolor='white', edgecolor='none', linewidth=0)
    ax.add_patch(top_circle)

    # Outer border
    outer_circle = patches.Circle((0, 0), R, fill=False,
                                  edgecolor='black', linewidth=2)
    ax.add_patch(outer_circle)

    if add_legend:
        sym_label = 'Sympathetic' if lang == 'en' else '交感'
        par_label = 'Parasympathetic' if lang == 'en' else '副交感'
        legend_fs = 11
        legend_x = 1.25
        ax.scatter(legend_x, 0.3, c='black', s=150, marker='o')
        ax.text(legend_x + 0.20, 0.3, sym_label, fontsize=legend_fs, va='center')
        ax.scatter(legend_x, -0.3, c='white', s=150, marker='o',
                   edgecolors='black', linewidth=1)
        ax.text(legend_x + 0.20, -0.3, par_label, fontsize=legend_fs, va='center')

    if lf_nu is not None and hf_nu is not None:
        info_text = (f'LF/HF ratio = {lf_hf_ratio:.3f}\n'
                     f'LFnu = {lf_nu:.1f}%\nHFnu = {hf_nu:.1f}%')
    else:
        sym_pct_label = 'Sympathetic' if lang == 'en' else '交感'
        par_pct_label = 'Parasympathetic' if lang == 'en' else '副交感'
        info_text = (f'LF/HF ratio = {lf_hf_ratio:.3f}\n'
                     f'{sym_pct_label}: {sympathetic_ratio*100:.1f}%\n'
                     f'{par_pct_label}: {parasympathetic_ratio*100:.1f}%')

    ax.text(0, -1.4, info_text, ha='center', va='top', fontsize=11,
            linespacing=2.0,
            bbox=dict(boxstyle='round,pad=0.8', facecolor='lightgray', alpha=0.8))

    xlim_right = 2.6 if lang == 'en' else 1.6
    ax.set_xlim(-1.2, xlim_right)
    ax.set_ylim(-2.5, 1.2)
    ax.set_aspect('equal')
    ax.axis('off')
    if fig is not None:
        fig.tight_layout()
    return fig


def create_rr_tachogram(rr_intervals, rr_times):
    """
    Create RR interval time series plot.

    Parameters
    ----------
    rr_intervals : ndarray
        RR intervals in seconds.
    rr_times : ndarray
        Cumulative time in seconds for each RR interval.

    Returns
    -------
    fig : matplotlib.figure.Figure
    """
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(rr_times, rr_intervals, color='black', linewidth=0.5)
    ax.set_facecolor('#FFFFCC')
    ax.set_xlabel('time (s)')
    ax.set_ylabel('sec')
    ax.set_title('RR Tachogram', fontweight='bold', color='red')
    fig.tight_layout()
    return fig


def create_poincare_plot(rr_intervals):
    """
    Create Poincaré plot (Global Return Map): RR(n) vs RR(n+1).

    Parameters
    ----------
    rr_intervals : ndarray
        RR intervals in seconds.

    Returns
    -------
    fig : matplotlib.figure.Figure
    """
    rr_n = rr_intervals[:-1]
    rr_n1 = rr_intervals[1:]

    fig, ax = plt.subplots(figsize=(4, 4))
    ax.scatter(rr_n, rr_n1, s=2, color='steelblue', alpha=0.5)
    ax.set_xlabel('RRn')
    ax.set_ylabel('RRn+1')
    ax.set_title('Global Return map', fontweight='bold')
    ax.set_aspect('equal')

    # Identity line
    all_vals = np.concatenate([rr_n, rr_n1])
    min_val, max_val = all_vals.min(), all_vals.max()
    margin = (max_val - min_val) * 0.05
    ax.plot([min_val - margin, max_val + margin],
            [min_val - margin, max_val + margin], 'k--', alpha=0.3)
    ax.set_xlim(min_val - margin, max_val + margin)
    ax.set_ylim(min_val - margin, max_val + margin)

    fig.tight_layout()
    return fig


def create_spectrum_plot(rr_intervals, rr_times, lf_hf_ratio, lf_nu, hf_nu):
    """
    Create Power Spectral Density plot of RR tachogram with LF/HF annotations.

    Parameters
    ----------
    rr_intervals : ndarray
        RR intervals in seconds.
    rr_times : ndarray
        Cumulative time in seconds.
    lf_hf_ratio : float
        LF/HF ratio.
    lf_nu : float
        LF normalized units (%).
    hf_nu : float
        HF normalized units (%).

    Returns
    -------
    fig : matplotlib.figure.Figure
    """
    # Interpolate to uniform sampling (4 Hz, standard for HRV)
    interp_fs = 4.0
    t_uniform = np.arange(rr_times[0], rr_times[-1], 1.0 / interp_fs)
    f_interp = interp1d(rr_times, rr_intervals, kind='cubic',
                        fill_value='extrapolate')
    rr_uniform = f_interp(t_uniform)

    # Welch PSD
    freqs, psd = welch(rr_uniform, fs=interp_fs,
                       nperseg=min(256, len(rr_uniform)))

    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(freqs, psd, color='black', linewidth=0.8)

    # Shade LF (0.04-0.15 Hz) and HF (0.15-0.4 Hz) bands
    lf_mask = (freqs >= 0.04) & (freqs <= 0.15)
    hf_mask = (freqs >= 0.15) & (freqs <= 0.4)
    ax.fill_between(freqs[lf_mask], psd[lf_mask], alpha=0.3, color='blue',
                    label='LF')
    ax.fill_between(freqs[hf_mask], psd[hf_mask], alpha=0.3, color='green',
                    label='HF')

    # Annotations
    psd_max = psd.max() if psd.max() > 0 else 1
    ax.text(0.5, 0.95, f'LF/HF ratio = {lf_hf_ratio:.3f}',
            transform=ax.transAxes, ha='center', va='top', fontweight='bold')
    ax.text(0.095, psd_max * 0.7, f'LFnu\n{lf_nu:.2f}%', ha='center',
            fontsize=9)
    ax.text(0.275, psd_max * 0.7, f'HFnu\n{hf_nu:.2f}%', ha='center',
            fontsize=9)

    ax.set_title('Spectrum of RR Tachogram', fontweight='bold')
    ax.set_xlabel('Frequency (Hz)')
    ax.set_xlim(0, 0.5)
    fig.tight_layout()
    return fig
