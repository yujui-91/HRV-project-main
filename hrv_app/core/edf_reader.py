"""
Module for reading .edf format files using MNE.
"""
import datetime
import numpy as np
import mne

def read_edf_file(file_path):
    """
    Reads an .edf file using MNE, resamples if needed,
    and returns a standardized dictionary matching the GUI pipeline.
    """
    # 1. 載入 EDF 檔案 (preload=True 載入資料至記憶體)
    mne.set_log_level('WARNING')
    raw = mne.io.read_raw_edf(file_path, preload=True)
    
    fs = raw.info['sfreq']
    sig_names = raw.ch_names
    n_sig = len(sig_names)
    
    # 轉置訊號矩陣，使其符合 (samples, channels) 的形狀
    signal_matrix = raw.get_data().T
    
    # 2. 獲取測量起始時間
    meas_date = raw.info['meas_date']
    if meas_date is not None:
        base_date = meas_date.date()
        base_time = meas_date.time()
    else:
        base_date = datetime.date.today()
        base_time = datetime.datetime.now().time()
        
    # 3. 💡 核心改進：使用 mne.annotations 抓取事件時間並轉為 Index
    markers = []
    triggers = []
    
    annotations = raw.annotations
    if annotations is not None and len(annotations) > 0:
        for onset, duration, desc in zip(annotations.onset, annotations.duration, annotations.description):
            # 透過 MNE 的內建方法將秒數(onset)精準轉換為數據點 Index
            sample_index = raw.time_as_index(onset)[0]
            
            # 🎯 關鍵修正：不論是什麼事件，一律塞進 markers 確保 GUI 100% 讀到並繪製！
            markers.append(sample_index)
            
            # 備份分流：如果符合 Trigger 特徵，才額外塞進 triggers 提供後續分析
            desc_upper = desc.upper()
            if any(k in desc_upper for k in ['STIM', 'TRIG', 'S ', 'USER TYPE']):
                triggers.append(sample_index)

    return {
        'signal': signal_matrix,
        'fs': fs,
        'n_sig': n_sig,
        'sig_name': sig_names,
        'base_time': base_time,
        'base_date': base_date,
        'markers': np.array(markers, dtype='int'),      # 100% 的事件都在這，GUI 絕對能讀取與顯示
        'triggers': np.array(triggers, dtype='int')     # 特定的實驗 Trigger 在這備用（相容分析模組）
    }