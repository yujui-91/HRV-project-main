from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit,
    QFileDialog, QGroupBox, QMessageBox, QStatusBar, QProgressBar,
    QFrame, QStackedWidget, QDoubleSpinBox
)
from PyQt6.QtCore import Qt

from hrv_app.templates import template_data as tmpl_ch
from hrv_app.templates import template_data_Eng as tmpl_en
from hrv_app.gui.workers import AnalysisWorker, FileLoadWorker, ReportWorker
import numpy as np

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
        self.file_path_edit.setPlaceholderText('選擇訊號檔案 (*.tff, *.edf, *.acq, *.abf)...')
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

        # === Segment selection (Marker or Manual) === (left)
        self.segment_group = QGroupBox('分析區段選擇')
        self.segment_group.setEnabled(False)
        segment_layout = QVBoxLayout()

        # 模式選擇
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel('選擇模式:'))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(['標記模式 (Marker)', '手動輸入時間 (Manual)'])
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        segment_layout.addLayout(mode_layout)

        # 建立堆疊面板以切換兩種模式的 UI
        self.segment_stack = QStackedWidget()

        # --- Page 0: Marker Mode ---
        marker_page = QWidget()
        marker_layout = QVBoxLayout(marker_page)
        marker_layout.setContentsMargins(0, 0, 0, 0)

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
        self.segment_stack.addWidget(marker_page)

        # --- Page 1: Manual Time Mode ---
        manual_page = QWidget()
        manual_layout = QVBoxLayout(manual_page)
        manual_layout.setContentsMargins(0, 0, 0, 0)

        # 單位統一為秒，已移除手動模式的時間單位下拉選單

        manual_grid = QGridLayout()
        manual_grid.addWidget(QLabel(''), 0, 0)
        manual_grid.addWidget(QLabel('開始時間 (秒)'), 0, 1)
        manual_grid.addWidget(QLabel('結束時間 (秒)'), 0, 2)

        # 設定三個區段的手動輸入秒數預設值
        defaults = {
            'baseline': (0.0, 300.0),
            'stress': (301.0, 660.0),
            'recovery': (661.0, 1020.0)
        }

        self.manual_inputs = {}
        for row, (phase_key, phase_label) in enumerate([
            ('baseline', 'Baseline'),
            ('stress', 'Stress'),
            ('recovery', 'Recovery'),
        ], start=1):
            manual_grid.addWidget(QLabel(f'{phase_label}:'), row, 0)
            start_spin = QDoubleSpinBox()
            start_spin.setRange(0, 999999)
            start_spin.setDecimals(2)
            start_spin.setValue(defaults[phase_key][0]) # 設定開始時間預設值
            
            end_spin = QDoubleSpinBox()
            end_spin.setRange(0, 999999)
            end_spin.setDecimals(2)
            end_spin.setValue(defaults[phase_key][1]) # 設定結束時間預設值
            
            manual_grid.addWidget(start_spin, row, 1)
            manual_grid.addWidget(end_spin, row, 2)
            
            self.manual_inputs[phase_key] = {'start': start_spin, 'end': end_spin}

        manual_layout.addLayout(manual_grid)
        self.segment_stack.addWidget(manual_page)

        segment_layout.addWidget(self.segment_stack)
        self.segment_group.setLayout(segment_layout)
        left_layout.addWidget(self.segment_group)

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

        # === HRV Metrics === (left)
        metrics_group = QGroupBox('HRV 指標對照 (Baseline / Stress / Recovery)')
        metrics_layout = QGridLayout()

        phases = ['baseline', 'stress', 'recovery']
        self.display_metrics = ['HR', 'SDNN', 'RMSSD', 'LF', 'HF', 'LF/HF', 'aSKNA']

        metrics_layout.addWidget(QLabel('指標名稱'), 0, 0)
        for i, p_name in enumerate(['Baseline', 'Stress', 'Recovery'], 1):
            lbl = QLabel(p_name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-weight: bold; color: #2E86C1;")
            metrics_layout.addWidget(lbl, 0, i)

        self.metric_labels = {}
        for p in phases:
            self.metric_labels[p] = {}

        for row, m_name in enumerate(self.display_metrics, 1):
            metrics_layout.addWidget(QLabel(f"{m_name}:"), row, 0)
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

        # === Status bar ===
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
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

    # --- Slots ---

    def _on_mode_changed(self, index):
        """切換 標記模式/手動時間 面板"""
        self.segment_stack.setCurrentIndex(index)

    def _on_browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '選擇訊號檔案', '',
            '選擇訊號檔案 (*.tff *.TFF *.edf *.EDF *.acq *.ACQ *.abf *.ABF);;All Files (*)'
            )
        if path:
            self.file_path_edit.setText(path)
            self._load_full_file(path)

    def _load_full_file(self, path):
        self.analyze_btn.setEnabled(False)
        self.segment_group.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage('讀取檔案中...')

        self.file_load_worker = FileLoadWorker(path)
        self.file_load_worker.finished.connect(self._on_file_loaded)
        self.file_load_worker.error.connect(self._on_file_load_error)
        self.file_load_worker.start()

    def _on_file_loaded(self, file_data):
        self._file_data = file_data
        self.progress_bar.setVisible(False)

        self.channel_combo.clear()
        n_channels = file_data.get('n_sig', 0)
        sig_names = file_data.get('sig_name', [])
        for i in range(n_channels):
            name = sig_names[i] if i < len(sig_names) else f'Channel {i}'
            self.channel_combo.addItem(f'{i}: {name}')
        self.channel_combo.setEnabled(True)
        self.analyze_btn.setEnabled(True)

        base_date = file_data.get('base_date', '')
        base_time = file_data.get('base_time', '')
        self.exam_time_edit.setText(f'{base_date} {base_time}')

        markers = file_data.get('markers')
        fs = file_data.get('fs', 1) or 1
        self._populate_markers(markers, fs)

        n_markers = len(markers) if markers is not None else 0
        self.status_bar.showMessage(
            f'檔案載入完成 — {n_channels} 個通道, fs={fs} Hz, {n_markers} 個標記', 5000)


    def _on_file_load_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.status_bar.clearMessage()
        QMessageBox.critical(self, '錯誤', f'無法讀取檔案:\n{error_msg}')



    def _populate_markers(self, markers, fs):
        self._raw_markers = list(markers) if markers is not None else []
        if not fs:
            fs = 1

        marker_items = []
        for i, sample_idx in enumerate(self._raw_markers):
            time_sec = sample_idx / fs
            marker_items.append(f'Marker {i + 1} ({time_sec:.2f}秒)')

        if marker_items:
            self.marker_list_label.setText('偵測到的標記: ' + ', '.join(marker_items))
        else:
            self.marker_list_label.setText('此檔案無標記')

        for combo in self.phase_combos.values():
            combo.clear()
            combo.addItem('-- 未選擇 --')
            for item in marker_items:
                combo.addItem(item)

        # 只要成功讀取檔案，就允許使用區段選擇
        self.segment_group.setEnabled(True)
        
        # 若檔案無標記，自動切換至「手動輸入時間」模式
        if not self._raw_markers:
            self.mode_combo.setCurrentIndex(1)

    def _get_phase_ranges(self):
        """根據當前模式 (Marker/Manual) 讀取區段，並回傳原始取樣率對應的 Index"""
        phases = {}
        mode = self.mode_combo.currentIndex()
        
        if mode == 0:  # Marker 模式
            if not self._raw_markers:
                return None
            for phase in ['baseline', 'stress', 'recovery']:
                start_idx = self.phase_combos[f'{phase}_start'].currentIndex() - 1
                end_idx = self.phase_combos[f'{phase}_end'].currentIndex() - 1
                if start_idx >= 0 and end_idx >= 0:
                    phases[phase] = (self._raw_markers[start_idx],
                                     self._raw_markers[end_idx])
                else:
                    phases[phase] = None
        
        else:  # 手動輸入時間模式
            if not self._file_data:
                return None
            fs = self._file_data.get('fs', 1)
            
            # 單位統一為秒，不需再透過 multiplier 換算
            for phase in ['baseline', 'stress', 'recovery']:
                start_val = self.manual_inputs[phase]['start'].value()
                end_val = self.manual_inputs[phase]['end'].value()
                
                # 如果起訖時間皆為 0，視為未選擇該區段
                if start_val == 0.0 and end_val == 0.0:
                    phases[phase] = None
                else:
                    start_idx = int(start_val * fs)
                    end_idx = int(end_val * fs)
                    phases[phase] = (start_idx, end_idx)

        return phases

    def _on_analyze(self):
        path = self.file_path_edit.text()
        if not path:
            return

        phase_ranges = self._get_phase_ranges()

        if phase_ranges:
            for phase, r in phase_ranges.items():
                if r is not None and r[0] >= r[1]:
                    QMessageBox.warning(
                        self, '區段錯誤',
                        f'{phase} 的起始時間/標記必須在結束時間/標記之前')
                    return

        channel_idx = self.channel_combo.currentIndex()
        self.analyze_btn.setEnabled(False)
        self.progress_bar.setRange(0, 0)
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
        
        mapping = {
            'HR': 'HR_mean',
            'SDNN': 'HRV_SDNN',
            'RMSSD': 'HRV_RMSSD',
            'LF': 'HRV_LF',
            'HF': 'HRV_HF',
            'LF/HF': 'HRV_LF_HF',
            'aSKNA': 'aSKNA'
        }

        phases = ['baseline', 'stress', 'recovery']
        
        for p in phases:
            p_data = results.get('phases', {}).get(p) or {}
            p_metrics = p_data.get('metrics') or {}

            if p == 'baseline' and not p_metrics:
                p_metrics = results.get('metrics') or {}

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
        current_lang = self.lang_combo.currentText()
        self.report_worker = ReportWorker(
            output_path,
            patient_info,
            self.hrv_results,
            self.analysis_text.toPlainText(),
            self.recommendation_text.toPlainText(),
            lang=current_lang,
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
        if index == 0:
            self.active_tmpl = tmpl_ch
        else:
            self.active_tmpl = tmpl_en
        
        self.status_combo.blockSignals(True)
        current_idx = self.status_combo.currentIndex()
        self.status_combo.clear()
        self.status_combo.addItems(self.active_tmpl.get_dropdown_labels())
        self.status_combo.setCurrentIndex(current_idx if current_idx >= 0 else 0)
        self.status_combo.blockSignals(False)
        
        self._on_status_changed(self.status_combo.currentIndex())

    def _on_status_changed(self, index):
        if index < 0: return
        key = self.active_tmpl.get_key_by_index(index)
        template = self.active_tmpl.get_template(key)
        self.analysis_text.setPlainText(template['analysis'])
        self.recommendation_text.setPlainText(template['recommendation'])