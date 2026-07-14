from PyQt6.QtCore import QThread, pyqtSignal
from core.tff_reader import read_tff_file
from core.preprocessing import preprocess_ecg
from core.hrv_analysis import analyze_hrv
from core.report_generator import generate_report
from core.edf_reader import read_edf_file
from core.acq_reader import read_acq_file
from core.abf_reader import read_abf_file
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


class AnalysisWorker(QThread):
    """Background thread for running the full HRV analysis pipeline."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, file_path, channel_index=0, file_data=None,
                 phase_ranges=None, algorithm='vollmer'):
        super().__init__()
        self.file_path = file_path
        self.channel_index = channel_index
        self.file_data = file_data
        self.phase_ranges = phase_ranges
        self.algorithm = algorithm

    def run(self):
        try:
            if self.file_data is not None:
                file_data = self.file_data
            else:
                self.progress.emit("讀取 TFF 檔案...")
                file_data = read_tff_file(self.file_path)

            self.progress.emit("訊號前處理（濾波 + 降取樣）...")
            ecg_signal = file_data['signal'][:, self.channel_index]
            ecg_processed = preprocess_ecg(ecg_signal,
                                           original_fs=file_data['fs'])

            ds_factor = file_data['fs'] / 1000
            phases = {}

            if self.phase_ranges and any(v is not None for v in self.phase_ranges.values()):
                for phase_name in ['baseline', 'stress', 'recovery']:
                    r = self.phase_ranges.get(phase_name)
                    if r is None:
                        phases[phase_name] = None
                        continue
                    start_ds = int(r[0] / ds_factor)
                    end_ds = int(r[1] / ds_factor)
                    segment = ecg_processed[start_ds:end_ds]
                    self.progress.emit(f"HRV 分析中（{phase_name}）...")
                    try:
                        phases[phase_name] = analyze_hrv(
                            segment, sampling_rate=1000,
                            algorithm=self.algorithm)
                    except Exception:
                        phases[phase_name] = None
            else:
                self.progress.emit("HRV 分析中...")
                phases['baseline'] = analyze_hrv(
                    ecg_processed, sampling_rate=1000,
                    algorithm=self.algorithm)
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


# workers.py 修改建議

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
                from ..core.report_generator_Eng import generate_report
            else:
                from ..core.report_generator import generate_report
            
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
