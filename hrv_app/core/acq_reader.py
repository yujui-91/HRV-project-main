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
    
    # Process each channel independently
    for ch in data.channels:
        sig_names.append(ch.name)
        fs_orig = ch.samples_per_second
        sig_orig = ch.data
        
        # Resample if original fs does not match target fs
        if fs_orig != target_fs and fs_orig > 0:
            num_target_samples = int(len(sig_orig) * (target_fs / fs_orig))
            sig_resampled = scipy_signal.resample(sig_orig, num_target_samples)
        else:
            sig_resampled = sig_orig
            
        resampled_signals.append(sig_resampled)
    
    # Align lengths to avoid dimension mismatch during stacking
    min_len = min(len(sig) for sig in resampled_signals)
    signal_matrix = np.column_stack([sig[:min_len] for sig in resampled_signals])
    
    # Extract Markers (Events)
    markers = []
    if data.event_markers:
        # Convert event time (seconds) to target_fs sample index
        markers = [int(m.time * target_fs) for m in data.event_markers]
    
    # Default datetime fallback if not available in format
    base_date = datetime.date.today()
    base_time = datetime.datetime.now().time()
    
    return {
        'signal': signal_matrix,
        'fs': target_fs,
        'n_sig': len(sig_names),
        'sig_name': sig_names,
        'base_time': base_time,
        'base_date': base_date,
        'markers': np.array(markers, dtype='int'),
        'triggers': np.array([], dtype='int') # Bioread doesn't strictly separate triggers from markers
    }