"""
Module for reading .acq format files using bioread.
"""
import datetime
import numpy as np
import bioread
from scipy import signal as scipy_signal

def read_acq_file(file_path, target_fs=10000):
    """
    Reads an .acq file, resamples all channels to 10000Hz, 
    and returns a standardized dictionary.
    """
    data = bioread.read_file(file_path)
    
    sig_names = []
    resampled_signals = []
    
    # 1. 處理通道升降頻
    for ch in data.channels:
        sig_names.append(ch.name)
        fs_orig = ch.samples_per_second
        sig_orig = ch.data
        
        # Resample 至目標採樣率
        if fs_orig != target_fs and fs_orig > 0:
            num_target_samples = int(len(sig_orig) * (target_fs / fs_orig))
            sig_resampled = scipy_signal.resample(sig_orig, num_target_samples)
        else:
            sig_resampled = sig_orig
            
        resampled_signals.append(sig_resampled)
    
    # 對齊長度
    min_len = min(len(sig) for sig in resampled_signals)
    signal_matrix = np.column_stack([sig[:min_len] for sig in resampled_signals])
    
    # 2. 修正後的 Event Markers 提取邏輯（加入第 0 秒過濾）
    markers = []
    triggers = []
    
    if data.event_markers:
        for m in data.event_markers:
            # 使用 time_index 屬性取得秒數
            time_sec = m.time_index 
            sample_index = int(time_sec * target_fs)
            
            # 🛑 關鍵修正：如果是第 0 秒（或 Index 為 0）的系統標記，直接跳過不記錄
            if sample_index == 0 or time_sec == 0:
                continue
            
            # 記錄至 markers 列表，確保 GUI 正常繪製其餘所有標記
            markers.append(sample_index)
            
            # 備份：如果是真正的實驗 Trigger，也塞入 triggers
            m_type = m.type.upper() if m.type else ""
            if 'USER TYPE' in m_type or 'TRIGGER' in m_type:
                triggers.append(sample_index)
    
    # 預設時間回退
    base_date = datetime.date.today()
    base_time = datetime.datetime.now().time()
    
    return {
        'signal': signal_matrix,
        'fs': target_fs,
        'n_sig': len(sig_names),
        'sig_name': sig_names,
        'base_time': base_time,
        'base_date': base_date,
        'markers': np.array(markers, dtype='int'),    # 已排除第 0 秒事件
        'triggers': np.array(triggers, dtype='int')   # 已排除第 0 秒事件
    }