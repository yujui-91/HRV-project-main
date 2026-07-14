"""
Module for reading .abf format files using pyabf.
"""
import datetime
import numpy as np
import pyabf
from scipy import signal as scipy_signal

def read_abf_file(file_path, target_fs=10000):
    """
    Reads an .abf file, resamples all channels to 10000Hz, 
    and returns a standardized dictionary.
    """
    abf = pyabf.ABF(file_path)
    
    fs_orig = abf.dataRate
    n_sig = abf.channelCount
    sig_names = abf.adcNames
    
    # abf.data is typically a 2D numpy array [channel, sample]
    sig_matrix_orig = abf.data
    
    resampled_signals = []
    
    # ABF usually has the same sampling rate for all channels, 
    # but we apply the same unified logic for consistency.
    for i in range(n_sig):
        sig_orig = sig_matrix_orig[i, :]
        
        if fs_orig != target_fs and fs_orig > 0:
            num_target_samples = int(len(sig_orig) * (target_fs / fs_orig))
            sig_resampled = scipy_signal.resample(sig_orig, num_target_samples)
        else:
            sig_resampled = sig_orig
            
        resampled_signals.append(sig_resampled)
        
    # Align lengths
    min_len = min(len(sig) for sig in resampled_signals)
    signal_matrix = np.column_stack([sig[:min_len] for sig in resampled_signals])
    
    # Extract Date/Time
    try:
        # pyabf parses the creation date into a datetime object
        abf_datetime = abf.abfDateTime
        base_date = abf_datetime.date()
        base_time = abf_datetime.time()
    except AttributeError:
        base_date = datetime.date.today()
        base_time = datetime.datetime.now().time()
        
    # Extract Tags (Markers)
    markers = []
    if hasattr(abf, 'tagTimesMin') and len(abf.tagTimesMin) > 0:
        # tagTimesMin is in minutes, convert to seconds then to target_fs samples
        markers = [int(t_min * 60 * target_fs) for t_min in abf.tagTimesMin]
        
    return {
        'signal': signal_matrix,
        'fs': target_fs,
        'n_sig': n_sig,
        'sig_name': sig_names,
        'base_time': base_time,
        'base_date': base_date,
        'markers': np.array(markers, dtype='int'),
        'triggers': np.array([], dtype='int')
    }