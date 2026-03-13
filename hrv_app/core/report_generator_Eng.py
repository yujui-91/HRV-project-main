import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch

from .plotting import create_taichi_plot


def _setup_font():
    plt.rcParams['font.sans-serif'] = [
        'Arial', 'Helvetica',
        'Microsoft JhengHei', 'SimHei', 'sans-serif',
    ]
    plt.rcParams['axes.unicode_minus'] = False


def generate_report(output_path, patient_info, hrv_results,
                    analysis_text, recommendation_text):
    """
    Generate a single-page A4 PDF report with updated layout.
    """
    _setup_font()

    metrics = hrv_results['metrics']

    # 建立 A4 尺寸畫布
    fig = plt.figure(figsize=(8.27, 11.69))

    
    gs = GridSpec(4, 1, figure=fig,
                  height_ratios=[0.08, 0.1, 0.4, 0.45], 
                  hspace=0.35,
                  left=0.1, right=0.9, top=0.95, bottom=0.05) 

    # === Row 0: 標題 ===
    ax_title = fig.add_subplot(gs[0])
    ax_title.axis('off')
    ax_title.text(0.5, 0.5, 'KMUH Autonomic Nervous System Report -- HRV Analysis',
                  ha='center', va='center', fontsize=14, fontweight='bold')

    # === Row 1: 病患資訊 (所有資訊放這裡) ===
    ax_info = fig.add_subplot(gs[1])
    ax_info.axis('off')
    record_num = patient_info.get('record_number', '--')
    name = patient_info.get('name', '--')
    exam_time = patient_info.get('exam_time', '--')
    birth_date = patient_info.get('birth_date', '--')

    p_bbox = FancyBboxPatch((0.1, 0.05), 0.8, 0.9,
                        boxstyle="round,pad=0.05",
                        fc="#F8F9F9", ec="#DCDCDC", lw=1.5,
                        edgecolor='gray',
                        transform=ax_info.transAxes, clip_on=False)
    ax_info.add_patch(p_bbox)

    # 繪製左半部
    left_text = f"Name: {name}\nDate of Birth: {birth_date}"
    ax_info.text(0.10, 0.5, left_text,
                ha='left', va='center',
                fontsize=11, linespacing=2.5,
                transform=ax_info.transAxes)

    # 繪製右半部 (文字塊置於右半框中央)
    right_text = f"Patient ID: {record_num}\nDate Received: {exam_time}"
    ax_info.text(0.53, 0.5, right_text,
                ha='left', va='center',
                fontsize=11, linespacing=2.5,
                transform=ax_info.transAxes)

    # === Row 2: 中間區塊 (左：太極圖 | 右：數值指標) ===
    # 使用 subgridspec 將 Row 2 拆成 1列2欄
    gs_middle = gs[2].subgridspec(1, 2, wspace=0.15)
    
    # --- 左側：太極圖 ---
    ax_taichi = fig.add_subplot(gs_middle[0, 0])
    ax_taichi.axis('off') 

    lf_hf = metrics.get('HRV_LF_HF', 1.0) or 1.0
    lf_nu = metrics.get('LFnu')
    hf_nu = metrics.get('HFnu')
    
    create_taichi_plot(lf_hf, lf_nu, hf_nu, ax=ax_taichi, lang='en')

    table_data = [
        ['', 'Baseline', 'Stress', 'Recovery'],
        ['HR', metrics.get('HR_mean', '--'), '', ''],
        ['SDNN', metrics.get('HRV_SDNN', '--'), '', ''],
        ['RMSSD', metrics.get('HRV_RMSSD', '--'), '', ''],
        ['LF', metrics.get('HRV_LF', '--'), '', ''],
        ['HF', metrics.get('HRV_HF', '--'), '', ''],
        ['LF/HF', metrics.get('HRV_LF_HF', '--'), '', '']
    ]


    # --- 右側：數值指標表格 ---
    ax_metrics = fig.add_subplot(gs_middle[0, 1])
    ax_metrics.axis('off')

    # 建立表格
    table = ax_metrics.table(
        cellText=table_data,
        cellLoc='center',
        loc='center',
        bbox=[0, 0, 1, 1] # 讓表格填滿整個 ax 區域
    )

    # 設定表格樣式
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    
    # 遍歷單元格調整外觀
    for (row, col), cell in table.get_celld().items():
        # 設定邊框顏色與線條寬度
        cell.set_edgecolor('#DCDCDC')
        cell.set_linewidth(1.0)
        
        # 設定第一列(Header)與第一欄(標籤)的底色
        if row == 0:
            cell.set_facecolor('#F2F2F2') # 淺灰色標題
            cell.get_text().set_weight('bold')
        elif col == 0:
            cell.set_facecolor('#F8F9F9') # 極淺灰標籤
        else:
            cell.set_facecolor('white')
            
        # 調整單元格高度
        cell.set_height(0.15)


    # === Row 3: 底部區塊 (Analysis & Recommendation) ===
    ax_text = fig.add_subplot(gs[3])
    ax_text.axis('off')

    text_bbox = FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                                boxstyle="round,pad=0.05",
                                fc="#F8F9F9", ec="#DCDCDC", lw=1.5,
                                transform=ax_text.transAxes, clip_on=False)
    ax_text.add_patch(text_bbox)

    wrap_width = 88
    analysis_wrapped = textwrap.fill(analysis_text, width=wrap_width, break_long_words=False)
    recommendation_wrapped = textwrap.fill(recommendation_text, width=wrap_width, break_long_words=False)

    line_h = 0.055
    y = 0.90

    ax_text.text(0.06, y, '[ Analysis ]',
                 ha='left', va='top', fontsize=11, fontweight='bold',
                 transform=ax_text.transAxes)
    y -= line_h * 1.5

    ax_text.text(0.06, y, analysis_wrapped,
                 ha='left', va='top', fontsize=11,
                 transform=ax_text.transAxes, linespacing=1.8)
    n_analysis = analysis_wrapped.count('\n') + 1
    y -= (n_analysis - 1) * line_h + line_h * 2.5

    ax_text.text(0.06, y, '[ Recommendation ]',
                 ha='left', va='top', fontsize=11, fontweight='bold',
                 transform=ax_text.transAxes)
    y -= line_h * 1.5

    ax_text.text(0.06, y, recommendation_wrapped,
                 ha='left', va='top', fontsize=11,
                 transform=ax_text.transAxes, linespacing=1.8)
    
    # 存檔 PDF
    with PdfPages(output_path) as pdf:
        pdf.savefig(fig, dpi=150)
    plt.close(fig)

