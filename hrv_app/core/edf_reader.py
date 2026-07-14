"""
Module for reading .edf format files using pyedflib.
"""
import datetime
import numpy as np
import pyedflib
from scipy import signal as scipy_signal

def read_edf_file(file_path, target_fs=10000):
    """
    Reads an .edf file, resamples all channels to 10000Hz, 
    and returns a standardized dictionary.
    """
    f = pyedflib.EdfReader(file_path)
    
    n_sig = f.signals_in_file
    sig_names = f.getSignalLabels()
    
    resampled_signals = []
    
    # Process each channel independently
    for i in range(n_sig):
        fs_orig = f.getSampleFrequency(i)
        sig_orig = f.readSignal(i)
        
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
    startdate = f.getStartdatetime()
    if startdate:
        base_date = startdate.date()
        base_time = startdate.time()
    else:
        base_date = datetime.date.today()
        base_time = datetime.datetime.now().time()
        
    # Extract Annotations (Markers)
    annotations = f.readAnnotations() # returns (onsets, durations, descriptions)
    markers = []
    if annotations and len(annotations[0]) > 0:
        onsets_seconds = annotations[0]
        markers = [int(onset * target_fs) for onset in onsets_seconds]
        
    f.close()
    
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