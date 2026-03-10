import os
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.gridspec import GridSpec

from .plotting import create_taichi_plot


def _setup_chinese_font():
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False


def generate_report(output_path, patient_info, hrv_results,
                    analysis_text, recommendation_text):
    """
    Generate a single-page A4 PDF report.

    Parameters
    ----------
    output_path : str
        Path for the output PDF file.
    patient_info : dict
        Keys: 'record_number', 'name', 'exam_time', 'birth_date'
    hrv_results : dict
        Output of analyze_hrv().
    analysis_text : str
        Analysis text (may be edited by user).
    recommendation_text : str
        Recommendation text (may be edited by user).
    """
    _setup_chinese_font()

    metrics = hrv_results['metrics']

    # Create A4-sized figure
    fig = plt.figure(figsize=(8.27, 11.69))

    gs = GridSpec(4, 1, figure=fig,
                  height_ratios=[0.06, 0.05, 0.40, 0.49],
                  hspace=0.25,
                  left=0.08, right=0.92, top=0.95, bottom=0.05)

    # === Row 0: Title ===
    ax_title = fig.add_subplot(gs[0])
    ax_title.axis('off')
    ax_title.text(0.5, 0.5, '高醫保健科自律神經報告 -- 心律變異分析',
                  ha='center', va='center', fontsize=16, fontweight='bold')

    # === Row 1: Patient info ===
    ax_info = fig.add_subplot(gs[1])
    ax_info.axis('off')
    record_num = patient_info.get('record_number', '')
    name = patient_info.get('name', '')
    exam_time = patient_info.get('exam_time', '')
    birth_date = patient_info.get('birth_date', '')

    info_text = (f'病歷號：{record_num}          '
                 f'檢查時間：{exam_time}\n'
                 f'姓名：{name}          '
                 f'出生日期：{birth_date}')
    ax_info.text(0.02, 0.5, info_text, ha='left', va='center',
                 fontsize=10,
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='#F0F0F0',
                           edgecolor='gray'))

    # === Row 2: Taichi plot ===
    ax_taichi = fig.add_subplot(gs[2])
    ax_taichi.axis('off')

    lf_hf = metrics.get('HRV_LF_HF', 1.0) or 1.0
    lf_nu = metrics.get('LFnu')
    hf_nu = metrics.get('HFnu')
    taichi_fig = create_taichi_plot(lf_hf, lf_nu, hf_nu)
    tmp_file = output_path + '.taichi.tmp.png'
    taichi_fig.savefig(tmp_file, dpi=150, bbox_inches='tight', transparent=True)
    plt.close(taichi_fig)
    taichi_img = plt.imread(tmp_file)
    ax_taichi.imshow(taichi_img, aspect='equal')
    ax_taichi.set_xlim(0, taichi_img.shape[1])
    ax_taichi.set_ylim(taichi_img.shape[0], 0)

    # === Row 3: Metrics + Analysis + Recommendation ===
    ax_text = fig.add_subplot(gs[3])
    ax_text.axis('off')

    sdnn = metrics.get('HRV_SDNN', '--')
    lf = metrics.get('HRV_LF', '--')
    hf = metrics.get('HRV_HF', '--')
    lf_hf_val = metrics.get('HRV_LF_HF', '--')
    dfa = metrics.get('HRV_DFA_alpha1', '--')

    metrics_line = (f'SDNN: {sdnn}    LF: {lf}    HF: {hf}    '
                    f'LF/HF: {lf_hf_val}    DFA α1: {dfa}')

    analysis_wrapped = textwrap.fill(analysis_text, width=60)
    recommendation_wrapped = textwrap.fill(recommendation_text, width=60)

    full_text = (
        f'HRV 指標\n'
        f'{metrics_line}\n\n'
        f'【分析】\n{analysis_wrapped}\n\n'
        f'【建議】\n{recommendation_wrapped}'
    )

    ax_text.text(0.02, 0.98, full_text, ha='left', va='top',
                 fontsize=10, transform=ax_text.transAxes,
                 linespacing=1.5,
                 bbox=dict(boxstyle='round,pad=0.5', facecolor='#FAFAFA',
                           edgecolor='gray'))

    # Save PDF
    with PdfPages(output_path) as pdf:
        pdf.savefig(fig, dpi=150)
    plt.close(fig)

    # Clean up temp file
    if os.path.exists(tmp_file):
        os.remove(tmp_file)
