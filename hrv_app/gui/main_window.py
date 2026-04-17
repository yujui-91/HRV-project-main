from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit,
    QFileDialog, QGroupBox, QMessageBox, QStatusBar, QProgressBar,
    QFrame,
)
from PyQt6.QtCore import Qt

from ..templates import template_data as tmpl_ch
from ..templates import template_data_Eng as tmpl_en
from .workers import AnalysisWorker, FileLoadWorker, ReportWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('HRV 自律神經分析系統')
        self.setMinimumSize(1200, 500)
        self.active_tmpl = tmpl_ch
        self.hrv_results = None
        self.worker = None
        self.report_worker = None
        self.file_load_worker = None
        self._file_data = None
        self._raw_markers = None

        self._build_ui()
        self._connect_signals()
        self._on_language_changed(0)
        
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        # === File selection === (left)
        file_group = QGroupBox('檔案選擇')
        file_layout = QGridLayout()

        file_layout.addWidget(QLabel('檔案:'), 0, 0)
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText('選擇 .TFF 檔案...')
        file_layout.addWidget(self.file_path_edit, 0, 1)
        self.browse_btn = QPushButton('瀏覽')
        file_layout.addWidget(self.browse_btn, 0, 2)

        file_layout.addWidget(QLabel('通道:'), 1, 0)
        self.channel_combo = QComboBox()
        self.channel_combo.setEnabled(False)
        file_layout.addWidget(self.channel_combo, 1, 1)
        self.analyze_btn = QPushButton('分析')
        self.analyze_btn.setEnabled(False)
        file_layout.addWidget(self.analyze_btn, 1, 2)

        file_layout.addWidget(QLabel('演算法:'), 2, 0)
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(['Vollmer', 'RRI (5-Method)'])
        file_layout.addWidget(self.algorithm_combo, 2, 1)

        file_group.setLayout(file_layout)
        left_layout.addWidget(file_group)

        # === Marker selection === (left)
        self.marker_group = QGroupBox('標記選擇')
        self.marker_group.setEnabled(False)
        marker_layout = QVBoxLayout()

        self.marker_list_label = QLabel('尚未載入標記')
        self.marker_list_label.setWordWrap(True)
        marker_layout.addWidget(self.marker_list_label)

        phase_grid = QGridLayout()
        phase_grid.addWidget(QLabel(''), 0, 0)
        phase_grid.addWidget(QLabel('起始標記'), 0, 1)
        phase_grid.addWidget(QLabel('結束標記'), 0, 2)

        self.phase_combos = {}
        for row, (phase_key, phase_label) in enumerate([
            ('baseline', 'Baseline'),
            ('stress', 'Stress'),
            ('recovery', 'Recovery'),
        ], start=1):
            phase_grid.addWidget(QLabel(f'{phase_label}:'), row, 0)
            start_combo = QComboBox()
            end_combo = QComboBox()
            phase_grid.addWidget(start_combo, row, 1)
            phase_grid.addWidget(end_combo, row, 2)
            self.phase_combos[f'{phase_key}_start'] = start_combo
            self.phase_combos[f'{phase_key}_end'] = end_combo

        marker_layout.addLayout(phase_grid)
        self.marker_group.setLayout(marker_layout)
        left_layout.addWidget(self.marker_group)

        # === Patient info === (left)
        patient_group = QGroupBox('病患資訊')
        patient_layout = QGridLayout()

        patient_layout.addWidget(QLabel('病歷號:'), 0, 0)
        self.record_num_edit = QLineEdit()
        patient_layout.addWidget(self.record_num_edit, 0, 1)
        patient_layout.addWidget(QLabel('檢查時間:'), 0, 2)
        self.exam_time_edit = QLineEdit()
        patient_layout.addWidget(self.exam_time_edit, 0, 3)

        patient_layout.addWidget(QLabel('姓名:'), 1, 0)
        self.name_edit = QLineEdit()
        patient_layout.addWidget(self.name_edit, 1, 1)
        patient_layout.addWidget(QLabel('出生日期:'), 1, 2)
        self.birth_date_edit = QLineEdit()
        patient_layout.addWidget(self.birth_date_edit, 1, 3)

        patient_group.setLayout(patient_layout)
        right_layout.addWidget(patient_group)

        # === HRV Metrics (修改為網格顯示三個階段) === (left)
        metrics_group = QGroupBox('HRV 指標對照 (Baseline / Stress / Recovery)')
        metrics_layout = QGridLayout()

        phases = ['baseline', 'stress', 'recovery']
        # 定義要顯示的指標名稱 (UI 顯示用)
        self.display_metrics = ['HR', 'SDNN', 'RMSSD', 'LF', 'HF', 'LF/HF']

        # 建立表頭 (第一列)
        metrics_layout.addWidget(QLabel('指標名稱'), 0, 0)
        for i, p_name in enumerate(['Baseline', 'Stress', 'Recovery'], 1):
            lbl = QLabel(p_name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-weight: bold; color: #2E86C1;") # 增加一點顏色區分
            metrics_layout.addWidget(lbl, 0, i)

        # 建立指標列與數值標籤
        self.metric_labels = {} # 格式為 { phase: { metric_name: QLabel } }
        for p in phases:
            self.metric_labels[p] = {}

        for row, m_name in enumerate(self.display_metrics, 1):
            # 左側指標名稱
            metrics_layout.addWidget(QLabel(f"{m_name}:"), row, 0)
            # 三個階段的數值欄位
            for col, p in enumerate(phases, 1):
                lbl = QLabel('--')
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                metrics_layout.addWidget(lbl, row, col)
                self.metric_labels[p][m_name] = lbl

        metrics_group.setLayout(metrics_layout)
        left_layout.addWidget(metrics_group)

        # === Status + Analysis + Recommendation === (right)
        status_group = QGroupBox('分析與建議')
        status_layout = QVBoxLayout()

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel('語言 (Language):'))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(['中文', 'English'])
        status_row.addWidget(self.lang_combo)

        status_row.addWidget(QLabel('狀態:'))
        self.status_combo = QComboBox()
        # 這裡先不 addItems，由後面的方法統一更新
        status_row.addWidget(self.status_combo)
        status_row.addStretch()
        status_layout.addLayout(status_row)

        status_layout.addWidget(QLabel('分析:'))
        self.analysis_text = QTextEdit()
        self.analysis_text.setMaximumHeight(120)
        status_layout.addWidget(self.analysis_text)

        status_layout.addWidget(QLabel('建議:'))
        self.recommendation_text = QTextEdit()
        self.recommendation_text.setMaximumHeight(100)
        status_layout.addWidget(self.recommendation_text)

        status_group.setLayout(status_layout)
        right_layout.addWidget(status_group)
        right_layout.addStretch()

        # Load default template
        self._on_status_changed(0)

        # === Output === (right)
        output_group = QGroupBox('PDF 報告輸出')
        output_layout = QHBoxLayout()

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText('選擇輸出路徑...')
        self.output_path_edit.setReadOnly(True)
        output_layout.addWidget(self.output_path_edit)
        self.output_browse_btn = QPushButton('瀏覽')
        output_layout.addWidget(self.output_browse_btn)
        self.export_btn = QPushButton('匯出 PDF')
        self.export_btn.setEnabled(False)
        output_layout.addWidget(self.export_btn)

        output_group.setLayout(output_layout)
        right_layout.addWidget(output_group)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)

        main_layout.addLayout(left_layout, 1)
        main_layout.addWidget(divider)
        main_layout.addLayout(right_layout, 1)

        # === Status bar with progress ===
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _connect_signals(self):
        self.browse_btn.clicked.connect(self._on_browse_file)
        self.analyze_btn.clicked.connect(self._on_analyze)
        self.status_combo.currentIndexChanged.connect(self._on_status_changed)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        self.output_browse_btn.clicked.connect(self._on_browse_output)
        self.export_btn.clicked.connect(self._on_export_pdf)

    # --- Slots ---

    



    def _on_browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '選擇 TFF 檔案', '',
            'TFF Files (*.tff *.TFF);;All Files (*)')
        if path:
            self.file_path_edit.setText(path)
            self._load_full_file(path)

    def _load_full_file(self, path):
        """Read full TFF file in background to get signal, markers, and header info."""
        self.analyze_btn.setEnabled(False)
        self.marker_group.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage('讀取檔案中...')

        self.file_load_worker = FileLoadWorker(path)
        self.file_load_worker.finished.connect(self._on_file_loaded)
        self.file_load_worker.error.connect(self._on_file_load_error)
        self.file_load_worker.start()

    def _on_file_loaded(self, file_data):
        """Handle completed file loading — populate channels, markers, exam time."""
        self._file_data = file_data
        self.progress_bar.setVisible(False)

        # Populate channel combo
        self.channel_combo.clear()
        n_channels = file_data['n_sig']
        sig_names = file_data.get('sig_name', [])
        for i in range(n_channels):
            name = sig_names[i] if i < len(sig_names) else f'Channel {i}'
            self.channel_combo.addItem(f'{i}: {name}')
        self.channel_combo.setEnabled(True)
        self.analyze_btn.setEnabled(True)

        # Auto-fill exam time
        base_date = file_data.get('base_date', '')
        base_time = file_data.get('base_time', '')
        self.exam_time_edit.setText(f'{base_date} {base_time}')

        # Populate markers
        markers = file_data.get('markers')
        fs = file_data.get('fs', 1)
        self._populate_markers(markers, fs)

        self.status_bar.showMessage(
            f'檔案載入完成 — {n_channels} 個通道, fs={fs} Hz, '
            f'{len(markers)} 個標記', 5000)

    def _on_file_load_error(self, error_msg):
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, '錯誤', f'無法讀取檔案:\n{error_msg}')

    def _populate_markers(self, markers, fs):
        """Fill marker combo boxes with simplified second-based formatting."""
        self._raw_markers = list(markers) if markers is not None else []

        # 建立標記列表文字
        marker_items = []
        for i, sample_idx in enumerate(self._raw_markers):
            time_sec = sample_idx / fs
            # 修改處：僅顯示秒數，保留兩位小數
            marker_items.append(f'Marker {i + 1} ({time_sec:.2f}秒)')

        # 更新 UI 上的標記列表顯示
        if marker_items:
            self.marker_list_label.setText('偵測到的標記: ' + ', '.join(marker_items))
        else:
            self.marker_list_label.setText('此檔案無標記')

        # 填充下拉選單 (Baseline/Stress/Recovery 的起始與結束)
        for combo in self.phase_combos.values():
            combo.clear()
            combo.addItem('-- 未選擇 --')
            for item in marker_items:
                combo.addItem(item)

        if self._raw_markers:
            self.marker_group.setEnabled(True)
        else:
            self.marker_group.setEnabled(False)

    def _get_phase_ranges(self):
        """Read combo box selections and return phase ranges as sample indices."""
        if not self._raw_markers:
            return None
        phases = {}
        for phase in ['baseline', 'stress', 'recovery']:
            start_idx = self.phase_combos[f'{phase}_start'].currentIndex() - 1
            end_idx = self.phase_combos[f'{phase}_end'].currentIndex() - 1
            if start_idx >= 0 and end_idx >= 0:
                phases[phase] = (self._raw_markers[start_idx],
                                 self._raw_markers[end_idx])
            else:
                phases[phase] = None
        return phases

    def _on_analyze(self):
        path = self.file_path_edit.text()
        if not path:
            return

        phase_ranges = self._get_phase_ranges()

        # Validate: start must be before end for selected phases
        if phase_ranges:
            for phase, r in phase_ranges.items():
                if r is not None and r[0] >= r[1]:
                    QMessageBox.warning(
                        self, '標記錯誤',
                        f'{phase} 的起始標記必須在結束標記之前')
                    return

        channel_idx = self.channel_combo.currentIndex()
        self.analyze_btn.setEnabled(False)
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setVisible(True)

        algorithm = 'vollmer' if self.algorithm_combo.currentIndex() == 0 else 'rri'
        self.worker = AnalysisWorker(
            path, channel_idx,
            file_data=self._file_data,
            phase_ranges=phase_ranges,
            algorithm=algorithm)
        self.worker.progress.connect(
            lambda msg: self.status_bar.showMessage(msg))
        self.worker.finished.connect(self._on_analysis_done)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.start()

    def _on_analysis_done(self, results):
        self.hrv_results = results
        
        # UI 名稱與分析數據 Key 的對照表
        mapping = {
            'HR': 'HR_mean',
            'SDNN': 'HRV_SDNN',
            'RMSSD': 'HRV_RMSSD',
            'LF': 'HRV_LF',
            'HF': 'HRV_HF',
            'LF/HF': 'HRV_LF_HF'
        }

        phases = ['baseline', 'stress', 'recovery']
        
        for p in phases:
            # 從結果中取得該階段的 metrics (若無該階段數據則回傳空字典)
            p_data = results.get('phases', {}).get(p, {})
            p_metrics = p_data.get('metrics', {})
            
            # 如果是 baseline 且 phases 內沒資料，嘗試抓取頂層 metrics (向下相容)
            if p == 'baseline' and not p_metrics:
                p_metrics = results.get('metrics', {})

            for ui_name, data_key in mapping.items():
                val = p_metrics.get(data_key)
                display_val = str(val) if val is not None else '--'
                self.metric_labels[p][ui_name].setText(display_val)

        self.analyze_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage('分析完成', 5000)

    def _on_analysis_error(self, error_msg):
        self.analyze_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, '分析錯誤', error_msg)

    def _on_browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, '選擇輸出路徑', '',
            'PDF Files (*.pdf);;All Files (*)')
        if path:
            if not path.lower().endswith('.pdf'):
                path += '.pdf'
            self.output_path_edit.setText(path)

    def _on_export_pdf(self):
        output_path = self.output_path_edit.text()
        if not output_path:
            QMessageBox.warning(self, '提示', '請先選擇輸出路徑')
            return
        if self.hrv_results is None:
            QMessageBox.warning(self, '提示', '請先執行分析')
            return

        patient_info = {
            'record_number': self.record_num_edit.text(),
            'name': self.name_edit.text(),
            'exam_time': self.exam_time_edit.text(),
            'birth_date': self.birth_date_edit.text(),
        }

        self.export_btn.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        current_lang = self.lang_combo.currentText() # 取得目前選單文字 ('中文' 或 'English')
        self.report_worker = ReportWorker(
            output_path,
            patient_info,
            self.hrv_results,
            self.analysis_text.toPlainText(),
            self.recommendation_text.toPlainText(),
            lang=current_lang, # 傳入語言參數
        )
        self.report_worker.progress.connect(
            lambda msg: self.status_bar.showMessage(msg))
        self.report_worker.finished.connect(self._on_report_done)
        self.report_worker.error.connect(self._on_report_error)
        self.report_worker.start()

    def _on_report_done(self, path):
        self.export_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage(f'PDF 已匯出: {path}', 8000)
        QMessageBox.information(self, '完成', f'PDF 報告已儲存至:\n{path}')

    def _on_report_error(self, error_msg):
        self.export_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, '匯出錯誤', error_msg)


    def _on_language_changed(self, index):
        # 根據索引切換當前使用的模組
        if index == 0:  # 中文
            self.active_tmpl = tmpl_ch
        else:           # 英文
            self.active_tmpl = tmpl_en
        
        # 斷開信號避免更新選單時觸發 _on_status_changed
        self.status_combo.blockSignals(True)
        current_idx = self.status_combo.currentIndex()
        self.status_combo.clear()
        self.status_combo.addItems(self.active_tmpl.get_dropdown_labels())
        self.status_combo.setCurrentIndex(current_idx if current_idx >= 0 else 0)
        self.status_combo.blockSignals(False)
        
        # 手動觸發一次內容更新
        self._on_status_changed(self.status_combo.currentIndex())

    def _on_status_changed(self, index):
        if index < 0: return
        # 將原本寫死的函數調用改為指向 self.active_tmpl
        key = self.active_tmpl.get_key_by_index(index)
        template = self.active_tmpl.get_template(key)
        self.analysis_text.setPlainText(template['analysis'])
        self.recommendation_text.setPlainText(template['recommendation'])    
