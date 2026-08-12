from PyQt6.QtCore import QThread, pyqtSignal
from hrv_app.core.tff_reader import read_tff_file
from hrv_app.core.preprocessing import preprocess_ecg
from hrv_app.core.hrv_analysis import analyze_hrv
from hrv_app.core.report_generator import generate_report
from hrv_app.core.edf_reader import read_edf_file
from hrv_app.core.acq_reader import read_acq_file
from hrv_app.core.abf_reader import read_abf_file
from hrv_app.core.hrv_analysis import analyze_hrv, calculate_skna_metrics
import os

class FileLoadWorker(QThread):
    """Background thread for reading TFF, EDF, or ACQ files (signal + markers)."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            # 1. 取得副檔名並強制轉成小寫 (例如: '.tff', '.edf', '.acq')
            ext = os.path.splitext(self.file_path)[1].lower()
            
            # 2. 根據副檔名進行分流讀取
            if ext == '.tff':
                file_data = read_tff_file(self.file_path)
            elif ext == '.edf':
                file_data = read_edf_file(self.file_path)
            elif ext == '.acq':
                file_data = read_acq_file(self.file_path)
            elif ext == '.abf':
                file_data = read_abf_file(self.file_path)
            else:
                # 如果是不支援的格式，主動拋出錯誤
                raise ValueError(f"不支援的檔案格式: {ext}")
            
            # 3. 將統包好的標準字典資料傳回給 GUI 主視窗
            self.finished.emit(file_data)
            
        except Exception as e:
            # 捕捉任何讀檔期間發生的錯誤（例如沒安讀檔套件、檔案損壞等）
            self.error.emit(str(e))


def _overall_askna(segment, fs, window_sec):
    """aSKNA = 整流後帶通訊號的平均絕對電壓 (μV)；無訊號或 fs 不足 2000Hz 時回傳 None。"""
    if segment is None or fs <= 2000 or len(segment) == 0:
        return None
    if window_sec <= 0:
        window_sec = 5.0
    _, _, overall = calculate_skna_metrics(segment, fs, window_sec=window_sec)
    return round(float(overall), 4)


class AnalysisWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, file_path, file_data=None,
                 phase_ranges=None, algorithm='vollmer'):
        super().__init__()
        self.file_path = file_path
        self.file_data = file_data
        self.phase_ranges = phase_ranges
        self.algorithm = algorithm

    def run(self):
        try:
            if self.file_data is not None:
                file_data = self.file_data
            else:
                self.progress.emit("讀取 檔案...")
                # 這裡原本是寫死 read_tff_file，建議根據副檔名讀取，但如果你外面已經讀好傳進來就沒差
                file_data = self.file_data 

            self.progress.emit("訊號前處理（濾波 + 降取樣）...")
            
            # ============ 各檔案格式：數值單位 對照表 ============
            # aSKNA 須以 μV 計算，各格式單位在此都會先換算成 μV。
            #
            #  格式 | 讀取套件           | 預設單位                 | → μV
            #  ---- | ------------------ | ------------------------ | -----
            #  .acq | bioread            | mV                       | ×1000
            #  .edf | MNE                | mV，但MNE 讀取時會轉成 V | ×1e6
            #  .abf | neo AxonIO         | μV                       | ×1
            #  .tff | 自製ME6000讀取套件 | μV                       | ×1
            #
            # 通道定義（統一格式）：ch1=胸腔貼片(ECG)→全部指標；ch2=頸部貼片→僅 aSKNA
            import os
            ext = os.path.splitext(self.file_path)[1].lower()
            _TO_UV = {'.acq': 1000.0, '.abf': 1.0, '.edf': 1_000_000.0, '.tff': 1.0}
            to_uv = _TO_UV.get(ext, 1.0)

            signal_matrix = file_data['signal']
            if signal_matrix.ndim == 1:
                signal_matrix = signal_matrix.reshape(-1, 1)
            ch1_signal_raw = signal_matrix[:, 0] * to_uv
            ch2_signal_raw = (signal_matrix[:, 1] * to_uv
                              if signal_matrix.shape[1] > 1 else None)
            # ======================================================================

            original_fs = file_data['fs']

            # 取出【降頻處理後】的 ch1 訊號，給 HRV 專用
            ecg_processed = preprocess_ecg(ch1_signal_raw, original_fs=original_fs)
            ds_factor = original_fs / 1000
            phases = {}

            if self.phase_ranges and any(v is not None for v in self.phase_ranges.values()):
                for phase_name in ['baseline', 'stress', 'recovery']:
                    r = self.phase_ranges.get(phase_name)
                    if r is None:
                        phases[phase_name] = None
                        continue
                        
                    # --- HRV 使用降取樣訊號 ---
                    start_ds = int(r[0] / ds_factor)
                    end_ds = int(r[1] / ds_factor)
                    segment_ds = ecg_processed[start_ds:end_ds]
                    
                    # --- SKNA 使用原始高頻訊號 ---
                    start_raw = int(r[0])
                    end_raw = int(r[1])

                    self.progress.emit(f"HRV & SKNA 分析中（{phase_name}）...")
                    try:
                        # 1. 執行 HRV 分析 (ch1)
                        phase_res = analyze_hrv(
                            segment_ds, sampling_rate=1000,
                            algorithm=self.algorithm)

                        # 2. 動態計算所選區間的秒數 (作為 aSKNA 的 Window)
                        window_sec = (end_raw - start_raw) / original_fs

                        # 3. 執行 SKNA 分析 (ch1 與 ch2)
                        phase_res['metrics']['aSKNA_ch1'] = _overall_askna(
                            ch1_signal_raw[start_raw:end_raw],
                            original_fs, window_sec)
                        phase_res['metrics']['aSKNA_ch2'] = _overall_askna(
                            ch2_signal_raw[start_raw:end_raw]
                            if ch2_signal_raw is not None else None,
                            original_fs, window_sec)

                        phases[phase_name] = phase_res
                    except Exception as e:
                        print(f"Error in {phase_name}: {e}")
                        phases[phase_name] = None
            else:
                self.progress.emit("HRV & SKNA 分析中 (全段)...")
                phase_res = analyze_hrv(
                    ecg_processed, sampling_rate=1000,
                    algorithm=self.algorithm)

                # 全段訊號處理
                window_sec = len(ch1_signal_raw) / original_fs
                phase_res['metrics']['aSKNA_ch1'] = _overall_askna(
                    ch1_signal_raw, original_fs, window_sec)
                phase_res['metrics']['aSKNA_ch2'] = _overall_askna(
                    ch2_signal_raw, original_fs, window_sec)

                phases['baseline'] = phase_res
                phases['stress'] = None
                phases['recovery'] = None

            baseline = phases.get('baseline')
            metrics = baseline['metrics'] if baseline else {}

            results = {
                'phases': phases,
                'metrics': metrics,
                'file_data': file_data,
            }
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))



class ReportWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, output_path, patient_info, hrv_results, 
                 analysis_text, recommendation_text, lang='中文'): # 增加 lang 參數
        
        super().__init__()
        self.output_path = output_path
        self.patient_info = patient_info
        self.hrv_results = hrv_results
        self.analysis_text = analysis_text
        self.recommendation_text = recommendation_text
        self.lang = lang # 儲存語言

    def run(self):
        try:
            self.progress.emit("正在生成 PDF 報告...")
            
            # 根據語言決定使用的導入
            if self.lang == 'English':
                from hrv_app.core.report_generator_Eng import generate_report
            else:
                from hrv_app.core.report_generator import generate_report
            
            generate_report(
                self.output_path,
                self.patient_info,
                self.hrv_results,
                self.analysis_text,
                self.recommendation_text
            )
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))
