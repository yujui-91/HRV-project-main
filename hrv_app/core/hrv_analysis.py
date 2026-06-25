import numpy as np
from hrv_app.core import vollmer_hrv as vh


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
