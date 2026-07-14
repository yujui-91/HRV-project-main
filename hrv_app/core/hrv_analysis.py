import numpy as np
from core import vollmer_hrv as vh
import scipy.signal as signal
import bioread  # 處理 .acq
import mne

def analyze_hrv(ecg_signal, sampling_rate=1000, algorithm='vollmer'):
    """
    Extended HRV analysis returning metrics and intermediate data for plots.

    Parameters
    ----------
    ecg_signal : ndarray
        Preprocessed ECG signal (single channel).
    sampling_rate : int
        Sampling rate in Hz.
    algorithm : str
        'vollmer' (default) or 'rri' (5-method template-based detection).

    Returns
    -------
    results : dict
        Dictionary with keys:
        - 'metrics': dict with HRV_SDNN, HRV_LF, HRV_HF, HRV_LF_HF,
          HRV_DFA_alpha1, LFnu, HFnu
        - 'r_peaks': ndarray of R-peak sample indices
        - 'rr_intervals': ndarray of RR intervals in seconds
        - 'rr_times': ndarray of cumulative time for each RR interval
    """
    if algorithm == 'rri':
        from .rri_rpeak import analyze_rri
        return analyze_rri(ecg_signal, fs=sampling_rate)

    ecg_signal = np.asarray(ecg_signal, dtype=float).ravel()

    # 1. R-peak detection (Vollmer morphological method)
    r_peak_indices = vh.singleqrs(ecg_signal, sampling_rate)

    if len(r_peak_indices) < 2:
        return _empty_result(r_peak_indices)

    # 2. RR intervals (seconds)
    rr_raw = np.diff(r_peak_indices) / sampling_rate

    # 3. Artifact rejection
    rr_filt = vh.RRfilter(rr_raw, limit=20)
    valid = ~np.isnan(rr_filt)
    rr_clean = rr_filt[valid]

    if len(rr_clean) < 5:
        return _empty_result(r_peak_indices)

    # 4. Time domain metrics
    hr_mean = round(vh.HR(rr_clean), 2)
    hrv_sdnn = round(vh.SDNN(rr_clean, flag=1), 2)
    hrv_rmssd = round(vh.RMSSD(rr_clean, flag=1), 2)

    # 5. Frequency domain (FFT with spline interpolation)
    fft = vh.fft_val_fun(rr_clean, sampling_rate)
    hrv_lf = round(fft['LF'], 2) if not np.isnan(fft['LF']) else None
    hrv_hf = round(fft['HF'], 2) if not np.isnan(fft['HF']) else None
    hrv_lf_hf = round(fft['LFHFratio'], 2) if not np.isnan(fft['LFHFratio']) else None
    lf_nu = round(fft['pLF'], 2) if not np.isnan(fft['pLF']) else None
    hf_nu = round(fft['pHF'], 2) if not np.isnan(fft['pHF']) else None

    # 6. Nonlinear (DFA)
    alpha1, _ = vh.DFA(rr_clean)
    hrv_dfa = round(alpha1, 2) if not np.isnan(alpha1) else None

    rr_times = np.cumsum(rr_clean)

    return {
        'metrics': {
            'HRV_SDNN': hrv_sdnn,
            'HRV_LF': hrv_lf,
            'HRV_HF': hrv_hf,
            'HRV_LF_HF': hrv_lf_hf,
            'HRV_DFA_alpha1': hrv_dfa,
            'LFnu': lf_nu,
            'HFnu': hf_nu,
            'HR_mean': hr_mean,
            'HRV_RMSSD': hrv_rmssd,
        },
        'r_peaks': r_peak_indices,
        'rr_intervals': rr_clean,
        'rr_times': rr_times,
    }


def _empty_result(r_peaks):
    return {
        'metrics': {
            'HRV_SDNN': None, 'HRV_LF': None, 'HRV_HF': None,
            'HRV_LF_HF': None, 'HRV_DFA_alpha1': None,
            'LFnu': None, 'HFnu': None,
            'HR_mean': None, 'HRV_RMSSD': None,
        },
        'r_peaks': r_peaks,
        'rr_intervals': np.array([]),
        'rr_times': np.array([]),
    }


def calculate_skna_metrics(raw_signal, fs, window_sec=5.0):
    """
    計算皮膚交感神經活性 (SKNA) 的兩個指標：iSKNA 與 aSKNA。
    依據 Kusayama et al., Nature Protocols 之方法進行實作。
    
    參數:
        raw_signal (np.array): 原始神經訊號陣列 (1D)
        fs (float): 取樣頻率 (Sampling rate)，建議 >= 2000 Hz
        window_sec (float): aSKNA 的時間視窗大小 (預設為 5 秒)
        
    回傳:
        iskna (np.array): 連續的 iSKNA 訊號陣列
        askna_windows (np.array): 每個時間視窗計算出的 aSKNA 陣列
        overall_askna (float): 整個訊號長度的全局 aSKNA 平均值
    """
    
    # ---------------------------------------------------------
    # 步驟 1: 前置處理與帶通濾波 (Band-pass filter)
    # ---------------------------------------------------------
    if fs < 2000:
        print(f"警告: 目前取樣頻率為 {fs} Hz。精確的 SKNA 分析建議取樣頻率應大於或等於 2,000 Hz。")

    # 設定 Butterworth 帶通濾波器 (500 Hz - 1000 Hz)
    # 奈奎斯特頻率 (Nyquist frequency) 為取樣頻率的一半
    nyq_freq = 0.5 * fs
    low_cutoff = 500.0 / nyq_freq
    high_cutoff = 1000.0 / nyq_freq
    
    # 使用 4 階 Butterworth 濾波器
    b_band, a_band = signal.butter(4, [low_cutoff, high_cutoff], btype='band')
    #消除心電圖（ECG，主要分布在 0.05–150 Hz）以及肌肉電位（EMG）的低頻干擾
    
    # 使用 filtfilt 進行零相位濾波 (Zero-phase filtering)，避免訊號在時間軸上產生偏移
    filtered_signal = signal.filtfilt(b_band, a_band, raw_signal)

    # ---------------------------------------------------------
    # 步驟 2: 計算 iSKNA (Integrated SKNA)
    # ---------------------------------------------------------
    # 2.1 全波整流 (Full-wave rectification)：將電壓值取絕對值
    rectified_signal = np.abs(filtered_signal)

    # 2.2 漏電積分器 (Leaky integrator)，時間常數設定為 100-ms (0.1 秒)
    tau = 0.1  # Time constant = 100 ms
    
    # 漏電積分器的數位實現是基於一階 IIR 濾波器。
    # 衰減係數 alpha 取決於取樣頻率與時間常數： alpha = exp(-dt / tau) = exp(-1 / (fs * tau))
    alpha = np.exp(-1.0 / (fs * tau))
    
    # 差分方程式: y[n] = (1 - alpha) * x[n] + alpha * y[n-1]
    # 對應的濾波器係數為 b = [1 - alpha], a = [1, -alpha]
    b_leaky = [1.0 - alpha]
    a_leaky = [1.0, -alpha]
    
    # 進行數位濾波運算得出 iSKNA
    iskna = signal.lfilter(b_leaky, a_leaky, rectified_signal)

    # ---------------------------------------------------------
    # 步驟 3: 計算 aSKNA (Average SKNA)
    # ---------------------------------------------------------
    # 計算每個時間視窗內包含的樣本總數
    samples_per_window = int(window_sec * fs)
    
    # 找出可以完整切分的視窗數量 (捨棄結尾不足一個視窗的零星資料)
    num_windows = len(rectified_signal) // samples_per_window
    truncated_signal = rectified_signal[:num_windows * samples_per_window]
    
    # 將一維陣列重塑為二維矩陣：形狀為 (視窗數量, 每個視窗的樣本數)
    reshaped_signal = truncated_signal.reshape((num_windows, samples_per_window))
    
    # 在每個視窗 (axis=1) 內計算平均絕對電壓 (即樣本總和除以樣本數)
    askna_windows = np.mean(reshaped_signal, axis=1)
    
    # 計算整段有效訊號的平均 aSKNA (全局指標)
    overall_askna = np.mean(rectified_signal)

    return iskna, askna_windows, overall_askna


# ==========================================
# 檔案讀取與使用範例 (整合至你的 Reader 中)
# ==========================================
def process_skna_from_file(file_path, file_type, target_channel_name):
    """
    根據不同的檔案類型讀取訊號並計算 SKNA。
    """
    raw_signal = None
    fs = None

    if file_type == '.acq':
        # 使用 bioread 讀取 AcqKnowledge 檔案
        data = bioread.read_file(file_path)
        for channel in data.channels:
            if target_channel_name in channel.name:
                raw_signal = channel.data
                fs = channel.samples_per_second
                break

    elif file_type == '.edf':
        # 使用 mne 讀取 EDF 檔案
        raw = mne.io.read_raw_edf(file_path, preload=True, verbose=False)
        raw_signal = raw.get_data(picks=target_channel_name)[0]
        fs = raw.info['sfreq']
        
    elif file_type == '.tff':
        # .tff 格式通常為醫院客製化導出格式 (常見於台灣自研設備或某些特定廠牌)
        # 需根據具體的資料儲存結構 (如二進位 np.float32 或是 ASCII text) 寫入讀取邏輯
        # 這裡以假設的純文字載入作為範例，請替換為你專案中 tff_reader.py 的邏輯
        print("請調用你的 tff_reader.py 來解析資料")
        # raw_signal, fs = your_tff_reader(file_path, target_channel_name)
        pass

    if raw_signal is not None and fs is not None:
        # 執行 SKNA 演算法
        iskna, askna_windows, overall_askna = calculate_skna_metrics(raw_signal, fs, window_sec=5.0)
        return iskna, askna_windows, overall_askna
    else:
        raise ValueError("找不到指定的通道或無法讀取檔案。")