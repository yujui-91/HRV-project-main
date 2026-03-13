from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit,
    QFileDialog, QGroupBox, QMessageBox, QStatusBar, QProgressBar,
)
from PyQt6.QtCore import Qt

# from ..templates.template_data import (
#     get_dropdown_labels, get_template, get_key_by_index, CONDITION_ORDER,
# )
from ..templates import template_data as tmpl_ch
from ..templates import template_data_Eng as tmpl_en
from .workers import AnalysisWorker, ReportWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('HRV 自律神經分析系統')
        self.setMinimumSize(700, 800)
        self.active_tmpl = tmpl_ch
        self.hrv_results = None
        self.worker = None
        self.report_worker = None

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # === File selection ===
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

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # === Patient info ===
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
        layout.addWidget(patient_group)

        # === HRV Metrics ===
        metrics_group = QGroupBox('HRV 指標')
        metrics_layout = QHBoxLayout()

        self.metric_labels = {}
        for name in ['SDNN', 'LF', 'HF', 'LF/HF', 'DFA α1']:
            lbl = QLabel(f'{name}: --')
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            metrics_layout.addWidget(lbl)
            self.metric_labels[name] = lbl

        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)

        # === Status + Analysis + Recommendation ===
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
        layout.addWidget(status_group)

        # Load default template
        self._on_status_changed(0)

        # === Output ===
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
        layout.addWidget(output_group)

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
            self._load_file_info(path)

    def _load_file_info(self, path):
        """Read file header only (fast) to populate channel list and exam time."""
        try:
            from ..core.tff_reader import read_tff_header
            header = read_tff_header(path)

            self.channel_combo.clear()
            n_channels = header['n_sig']
            sig_names = header.get('sig_name', [])
            for i in range(n_channels):
                name = sig_names[i] if i < len(sig_names) else f'Channel {i}'
                self.channel_combo.addItem(f'{i}: {name}')
            self.channel_combo.setEnabled(True)
            self.analyze_btn.setEnabled(True)

            # Auto-fill exam time
            base_date = header.get('base_date', '')
            base_time = header.get('base_time', '')
            self.exam_time_edit.setText(f'{base_date} {base_time}')

            self.status_bar.showMessage(
                f'檔案載入完成 — {n_channels} 個通道, fs={header["fs"]} Hz',
                5000)
        except Exception as e:
            QMessageBox.critical(self, '錯誤', f'無法讀取檔案:\n{e}')

    def _on_analyze(self):
        path = self.file_path_edit.text()
        if not path:
            return

        channel_idx = self.channel_combo.currentIndex()
        self.analyze_btn.setEnabled(False)
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setVisible(True)

        self.worker = AnalysisWorker(path, channel_idx)
        self.worker.progress.connect(
            lambda msg: self.status_bar.showMessage(msg))
        self.worker.finished.connect(self._on_analysis_done)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.start()

    def _on_analysis_done(self, results):
        self.hrv_results = results
        metrics = results['metrics']

        self.metric_labels['SDNN'].setText(
            f'SDNN: {metrics["HRV_SDNN"]}')
        self.metric_labels['LF'].setText(
            f'LF: {metrics["HRV_LF"]}')
        self.metric_labels['HF'].setText(
            f'HF: {metrics["HRV_HF"]}')
        self.metric_labels['LF/HF'].setText(
            f'LF/HF: {metrics["HRV_LF_HF"]}')
        self.metric_labels['DFA α1'].setText(
            f'DFA α1: {metrics["HRV_DFA_alpha1"]}')

        self.analyze_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage('分析完成', 5000)

    def _on_analysis_error(self, error_msg):
        self.analyze_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, '分析錯誤', error_msg)

    # def _on_status_changed(self, index):
    #     key = get_key_by_index(index)
    #     template = get_template(key)
    #     self.analysis_text.setPlainText(template['analysis'])
    #     self.recommendation_text.setPlainText(template['recommendation'])

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
