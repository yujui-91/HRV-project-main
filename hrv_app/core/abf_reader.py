"""
Module for reading .abf format files using pyabf.
"""
import datetime
import numpy as np
import pyabf
from scipy import signal as scipy_signal

def read_abf_header(file_path, target_fs=10000):
    """
    Read only the header of an ABF file (fast, no signal data).
    Matches the behavior of read_tff_header[cite: 1].
    """
    # loadData=False 讓 pyabf 只解析標頭，不加載龐大的訊號數據，速度提升數百倍
    abf = pyabf.ABF(file_path, loadData=False)
    
    n_sig = abf.channelCount
    sig_names = abf.adcNames
    
    # 提取日期與時間
    try:
        abf_datetime = abf.abfDateTime
        base_date = abf_datetime.date()
        base_time = abf_datetime.time()
    except AttributeError:
        base_date = datetime.date.today()
        base_time = datetime.datetime.now().time()
        
    return {
        'fs': target_fs,        # 配合系統底層邏輯，統一回傳目標採樣率
        'n_sig': n_sig,
        'sig_name': sig_names,
        'base_time': base_time,
        'base_date': base_date,
    }

def read_abf_file(file_path, target_fs=10000):
    """
    Reads an .abf file, resamples all channels to 10000Hz, 
    and returns a standardized dictionary.
    """
    abf = pyabf.ABF(file_path)
    
    fs_orig = abf.dataRate
    n_sig = abf.channelCount
    sig_names = abf.adcNames
    
    # abf.data 原始形狀為 [channel, sample]
    sig_matrix_orig = abf.data
    
    resampled_signals = []
    
    # 針對所有通道進行重採樣一致性處理
    for i in range(n_sig):
        sig_orig = sig_matrix_orig[i, :]
        
        if fs_orig != target_fs and fs_orig > 0:
            num_target_samples = int(len(sig_orig) * (target_fs / fs_orig))
            sig_resampled = scipy_signal.resample(sig_orig, num_target_samples)
        else:
            sig_resampled = sig_orig
            
        resampled_signals.append(sig_resampled)
        
    # 對齊長度，避免傅立葉重採樣產生的點數浮點誤差
    min_len = min(len(sig) for sig in resampled_signals)
    signal_matrix = np.column_stack([sig[:min_len] for sig in resampled_signals])
    
    # 提取日期與時間
    try:
        abf_datetime = abf.abfDateTime
        base_date = abf_datetime.date()
        base_time = abf_datetime.time()
    except AttributeError:
        base_date = datetime.date.today()
        base_time = datetime.datetime.now().time()
        
    # 提取標記 (Markers)
    markers = []
    if hasattr(abf, 'tagTimesMin') and len(abf.tagTimesMin) > 0:
        # tagTimesMin 單位為分鐘，需轉換為秒，再依據 target_fs 換算成 Sample Index
        markers = [int(t_min * 60 * target_fs) for t_min in abf.tagTimesMin]
        
    return {
        'signal': signal_matrix,
        'fs': target_fs,
        'n_sig': n_sig,
        'sig_name': sig_names,
        'base_time': base_time,
        'base_date': base_date,
        'markers': np.array(markers, dtype='int'),
        'triggers': np.array([], dtype='int')  # 保持空陣列，確保對接架構不報錯
    }