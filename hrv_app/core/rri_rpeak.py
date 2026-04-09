"""
R-peak detection and RRI analysis using a 5-method pipeline.

Ported from MATLAB RRIa_auto_2021.m / RRIb_auto_2021.m (HSKNA lab).
All magic numbers converted to time-based (seconds) so any sample rate is supported.

Pipeline overview:
    1. Template calibration (rri_calibrate) -- build R-wave template and
       morphological reference values from a clean segment of the signal.
    2. R-peak detection (rri_detect) -- 5 cascaded filters:
       Method 1: findpeaks (all local maxima)
       Method 2: distance-correlation template matching
       Methods 3/4/5: morphological feature filtering (DP, slope, amplitude)
    3. Two-round outlier rejection on RR intervals.
    4. HRV metric computation (SDNN, RMSSD, optionally frequency/nonlinear).

Dependencies: numpy, scipy
Optional:     hrv_app.core.vollmer_hrv  (for frequency-domain / nonlinear HRV)

Author: Rewritten from MATLAB by Claude (Anthropic)
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, Optional

import numpy as np
from numpy.typing import NDArray
from scipy.signal import butter, filtfilt, find_peaks
from scipy.spatial.distance import cdist

# ---------------------------------------------------------------------------
# Optional import for extended HRV metrics
# ---------------------------------------------------------------------------
try:
    from hrv_app.core import vollmer_hrv as vh

    HAS_VH = True
except ImportError:
    HAS_VH = False


# ===================================================================
# Distance Correlation
# ===================================================================

def distcorr(x: NDArray, y: NDArray) -> float:
    """Szekely distance correlation between two 1-D arrays.

    Reference
    ---------
    Szekely, Rizzo & Bakirov (2007).  Wikipedia: Distance Correlation.
    Original MATLAB implementation by Shen Liu (2013).

    Parameters
    ----------
    x, y : array_like, 1-D
        Input vectors of equal length.

    Returns
    -------
    dcor : float
        Distance correlation in [0, 1].
    """
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()

    if x.shape[0] != y.shape[0]:
        raise ValueError("Inputs must have the same number of elements")

    # Delete rows where either x or y is NaN
    valid = ~(np.isnan(x) | np.isnan(y))
    x = x[valid]
    y = y[valid]

    n = x.shape[0]
    if n < 2:
        return 0.0

    # Reshape for cdist: (N, 1)
    X = x.reshape(-1, 1)
    Y = y.reshape(-1, 1)

    # Pairwise distance matrices
    a = cdist(X, X, metric="euclidean")  # (n, n)
    b = cdist(Y, Y, metric="euclidean")

    # Double-centering for matrix a
    a_col_mean = a.mean(axis=0, keepdims=True)  # (1, n)
    a_row_mean = a.mean(axis=1, keepdims=True)  # (n, 1)
    a_grand = a.mean()
    A = a - a_col_mean - a_row_mean + a_grand

    # Double-centering for matrix b
    b_col_mean = b.mean(axis=0, keepdims=True)
    b_row_mean = b.mean(axis=1, keepdims=True)
    b_grand = b.mean()
    B = b - b_col_mean - b_row_mean + b_grand

    # Squared sample distance covariance and variances
    n2 = n * n
    dcov = (A * B).sum() / n2
    dvarx = (A * A).sum() / n2
    dvary = (B * B).sum() / n2

    denom = np.sqrt(dvarx * dvary)
    if denom == 0.0:
        return 0.0

    dcor = np.sqrt(dcov / denom)
    return float(dcor)


# ===================================================================
# Internal helpers
# ===================================================================

def _lowpass_filter(signal: NDArray, fs: float, cutoff: float = 50.0,
                    order: int = 4) -> NDArray:
    """Zero-phase Butterworth lowpass filter."""
    nyq = fs / 2.0
    if cutoff >= nyq:
        warnings.warn(
            f"Cutoff {cutoff} Hz >= Nyquist {nyq} Hz; skipping lowpass filter."
        )
        return signal.copy()
    b, a = butter(order, cutoff / nyq, btype="low")
    return filtfilt(b, a, signal)


def _take_last_km_minutes(signal: NDArray, fs: float, km: float) -> NDArray:
    """Return the last *km* minutes of a signal."""
    total_samples = len(signal)
    total_minutes = (total_samples - 1) / fs / 60.0
    if km >= total_minutes:
        return signal.copy()
    start = int((total_samples - 1) * (total_minutes - km) / total_minutes) + 1
    return signal[start:].copy()


def _preprocess(signal: NDArray, fs: float, km: float,
                cutoff: float = 50.0) -> tuple[NDArray, float]:
    """Shared preprocessing: lowpass -> last km min -> DC removal -> normalize.

    Returns
    -------
    nx1 : normalized signal (max abs = 1)
    norm_factor : the normalization divisor (max(abs(x1)))
    """
    sig = _lowpass_filter(signal, fs, cutoff=cutoff)
    sig = _take_last_km_minutes(sig, fs, km)
    sig = sig - sig.mean()  # DC removal
    norm_factor = np.max(np.abs(sig))
    if norm_factor == 0:
        norm_factor = 1.0
    nx1 = sig / norm_factor
    return nx1, norm_factor


def _find_valley(segment: NDArray):
    """Find the deepest valley in *segment* by inverting and finding peaks.

    Returns
    -------
    rc : 0-based index of the valley (largest inverted peak), or -1 if none.
    """
    inverted = -1.0 * segment
    peaks, _ = find_peaks(inverted)
    if len(peaks) == 0:
        return -1
    best = peaks[np.argmax(inverted[peaks])]
    return int(best)


# ===================================================================
# Time-based constants (derived from original 2500 Hz magic numbers)
# ===================================================================

# Template search region
_START_TIME_S = 6.1804      # range1 = 15451 @ 2500 Hz
_SPAN_TIME_S = 7.02         # 17550 samples @ 2500 Hz  (range1 to range1+17549)

# Template window (asymmetric around peak)
_PRE_PEAK_S = 0.06          # area  = 150 @ 2500 Hz
_POST_PEAK_S = 0.0296        # area2 = 74  @ 2500 Hz

# Candidate lookback windows (seconds)
_LOOKBACK_CANDIDATES_S = [
    0.0296, 0.0356, 0.0396, 0.0596, 0.0796,
    0.0996, 0.1196, 0.1396, 0.1596, 0.1796,
]

# Minimum peak position for detection (avoids edge artifacts)
_MIN_PEAK_TIME_S = 0.18     # 450 samples @ 2500 Hz

# RRI outlier rejection (round 2 std threshold, in seconds)
_STD_THRESHOLD_S = 0.012    # 30 samples / 2500 Hz


# ===================================================================
# Calibration (RRIa)
# ===================================================================

def rri_calibrate(
    signal: NDArray,
    fs: float = 2500.0,
    km: float = 5.0,
    n_peaks: int = 3,
    sim_thresh: float = 0.95,
) -> Dict[str, Any]:
    """Build an R-wave template and morphological reference values.

    This corresponds to RRIa_auto_2021.m.

    Parameters
    ----------
    signal : 1-D array
        Raw ECG signal (single channel).
    fs : float
        Sampling rate in Hz.
    km : float
        Use the last *km* minutes of the recording.
    n_peaks : int
        Number of template peaks to extract (default 3).
    sim_thresh : float
        Distance-correlation threshold for template validation (default 0.95).

    Returns
    -------
    dict with keys:
        template     : (n_peaks, window_len) array of normalized waveforms
        w            : chosen lookback window size (samples)
        M            : mean DP distance (samples)
        slope_upper  : upper slope bound (Ms + 30*MsD)
        slope_lower  : lower slope bound (Ms - 30*MsD)
        MVA          : mean peak-valley amplitude difference
        norm_factor  : normalization divisor used during preprocessing
        similarity_ok: True if template peaks converged
        lowpoint_ok  : True if a lookback window passed the valley test
    """
    # -- Convert time constants to sample counts --
    pre_peak = int(_PRE_PEAK_S * fs)      # e.g. 150 @ 2500 Hz
    post_peak = int(_POST_PEAK_S * fs)    # e.g. 74  @ 2500 Hz
    window_len = pre_peak + post_peak + 1 # e.g. 225 @ 2500 Hz
    start_idx = int(_START_TIME_S * fs)   # e.g. 15451 @ 2500 Hz
    span = int(_SPAN_TIME_S * fs)         # e.g. 17550 @ 2500 Hz
    ww = [int(t * fs) for t in _LOOKBACK_CANDIDATES_S]

    # -- Preprocessing --
    nx1, norm_factor = _preprocess(signal, fs, km)

    # -- Pad signal end so template extraction near edges doesn't fail --
    nx1 = np.concatenate([nx1, np.zeros(pre_peak)])

    # -- Find top n_peaks in the calibration region --
    region = nx1[start_idx: start_idx + span]
    all_peaks, _ = find_peaks(region)
    if len(all_peaks) == 0:
        raise ValueError("No peaks found in calibration region")

    pks = region[all_peaks].copy()  # peak amplitudes (mutable copy)
    locs = all_peaks.copy()          # 0-based indices within region

    # Pick the n_peaks largest
    ra_pos = np.zeros(n_peaks, dtype=int)   # absolute position in nx1
    ra_amp = np.zeros(n_peaks, dtype=float)
    for n in range(n_peaks):
        if len(pks) == 0:
            break
        idx = np.argmax(pks)
        ra_pos[n] = locs[idx] + start_idx  # convert to global index
        ra_amp[n] = pks[idx]
        pks[idx] = 0.0  # mask out this peak

    # -- Template validation (compare peaks 2,3 against peak 1) --
    def _extract_template(peak_pos: int, peak_amp: float) -> NDArray:
        """Extract and normalize a template window around a peak."""
        lo = peak_pos - pre_peak
        hi = peak_pos + post_peak + 1
        seg = nx1[lo:hi]
        return seg / peak_amp

    def _compute_similarities(ra_pos, ra_amp):
        ref = _extract_template(ra_pos[0], ra_amp[0])
        sst = np.zeros(n_peaks - 1)
        for j in range(1, n_peaks):
            cand = _extract_template(ra_pos[j], ra_amp[j])
            sst[j - 1] = distcorr(ref, cand)
        return sst

    sst = _compute_similarities(ra_pos, ra_amp)

    for ttt in range(1, 7):  # up to 6 iterations (1..6)
        dissimilar = np.where(sst < sim_thresh)[0]  # indices into sst (0-based)
        if len(dissimilar) == 0:
            break  # all similar -- done

        if ttt < 6:
            if len(dissimilar) == 1:
                # One dissimilar peak -- replace it with next largest from pool
                peak_idx_in_ra = dissimilar[0] + 1  # +1 because sst[0] compares peak 2 vs 1
                if len(pks) == 0 or np.max(pks) <= 0:
                    break
                idx = np.argmax(pks)
                ra_pos[peak_idx_in_ra] = locs[idx] + start_idx
                ra_amp[peak_idx_in_ra] = pks[idx]
                pks[idx] = 0.0
            elif len(dissimilar) >= 2:
                # Both dissimilar -- replace peak 1 (reference) with next largest
                if len(pks) == 0 or np.max(pks) <= 0:
                    break
                idx = np.argmax(pks)
                ra_pos[0] = locs[idx] + start_idx
                ra_amp[0] = pks[idx]
                pks[idx] = 0.0
        else:
            # Iteration 6: force-copy a similar peak to replace the dissimilar one
            dissimilar_last = np.where(sst < sim_thresh)[0]
            if len(dissimilar_last) > 0:
                bad_idx = dissimilar_last[-1] + 1  # which ra entry to overwrite
                # Determine the good partner to copy from
                if bad_idx == 2:
                    # peak 3 is bad -> copy from peak 2
                    ra_pos[2] = ra_pos[1]
                    ra_amp[2] = ra_amp[1]
                else:
                    # peak 2 is bad -> copy from peak 3
                    ra_pos[1] = ra_pos[2]
                    ra_amp[1] = ra_amp[2]

        # Recompute similarities with updated peaks
        sst = _compute_similarities(ra_pos, ra_amp)

    # -- Check final similarity --
    sst = _compute_similarities(ra_pos, ra_amp)
    similarity_ok = bool(np.all(sst >= sim_thresh))

    if not similarity_ok:
        # Template building failed -- return partial result
        return {
            "template": None,
            "w": None,
            "M": None,
            "slope_upper": None,
            "slope_lower": None,
            "MVA": None,
            "norm_factor": norm_factor,
            "similarity_ok": False,
            "lowpoint_ok": False,
        }

    # -- Build template matrix --
    ref_template = _extract_template(ra_pos[0], ra_amp[0])
    template = np.zeros((n_peaks, window_len))
    template[0] = ref_template
    for j in range(1, n_peaks):
        template[j] = _extract_template(ra_pos[j], ra_amp[j])

    # -- Pre-screen all peaks with loose threshold (0.80) for lookback test --
    all_pks_idx, _ = find_peaks(nx1)
    valid_mask = all_pks_idx > pre_peak
    all_pks_idx = all_pks_idx[valid_mask]
    all_pks_amp = nx1[all_pks_idx]

    q_pass = np.zeros(len(all_pks_idx), dtype=bool)
    for f, (pk_pos, pk_amp) in enumerate(zip(all_pks_idx, all_pks_amp)):
        if pk_amp == 0:
            continue
        cand = _extract_template(pk_pos, pk_amp)
        if distcorr(ref_template, cand) >= 0.80:
            q_pass[f] = True

    k = all_pks_idx[q_pass]  # positions of loosely-matched peaks

    # -- Test 10 candidate lookback windows --
    ratior = np.zeros(len(ww))
    for r, w in enumerate(ww):
        sta_locs = ra_pos - w  # start positions for standard peaks
        # Compute valley for each standard peak (for reference -- used later)
        rc_std = np.zeros(n_peaks, dtype=int)
        for n_idx in range(n_peaks):
            s = sta_locs[n_idx]
            if s < 0:
                rc_std[n_idx] = -1
                continue
            seg = nx1[s: s + w + 1]
            rc_std[n_idx] = _find_valley(seg)

        # Test on all loosely-matched peaks
        k_valid = k[k >= start_idx]  # only peaks in the valid region (>= range)
        pre_k = k_valid - w
        trc = np.zeros(len(pre_k), dtype=int)
        for n_idx, pk_start in enumerate(pre_k):
            if pk_start < 0:
                trc[n_idx] = -1
                continue
            seg = nx1[pk_start: pk_start + w + 1]
            trc[n_idx] = _find_valley(seg)

        n_total = len(trc)
        n_found = np.sum(trc > -1)
        ratior[r] = n_found / n_total if n_total > 0 else 0.0

    # -- Choose best lookback window --
    passing = np.where(ratior >= sim_thresh)[0]
    lowpoint_ok = True
    if len(passing) > 0:
        w_chosen = ww[passing[0]]  # smallest passing w
    else:
        w_chosen = ww[-1]  # default to largest
        lowpoint_ok = False

    # -- Compute morphological reference values with chosen w --
    sta_locs = ra_pos - w_chosen
    # Filter out standard peaks where lookback goes before signal start
    valid_sta = sta_locs >= 0
    sta_locs_valid = sta_locs[valid_sta]
    ra_pos_valid = ra_pos[valid_sta]
    ra_amp_valid = ra_amp[valid_sta]

    rc_final = np.zeros(len(sta_locs_valid), dtype=int)
    for n_idx, s in enumerate(sta_locs_valid):
        seg = nx1[s: s + w_chosen + 1]
        v = _find_valley(seg)
        rc_final[n_idx] = v if v >= 0 else 1  # default to 1 if no valley found

    # Valley positions (absolute): sta_loc + rc
    v_L = ra_pos_valid - (w_chosen - rc_final)
    # Amplitude differences
    v_A = ra_amp_valid - nx1[v_L]
    # DP distances
    dp = w_chosen + 1 - rc_final
    # Slopes
    slopes = v_A / dp

    M = float(np.mean(dp))
    Ms = float(np.mean(slopes))
    MsD = float(np.std(slopes, ddof=0))  # MATLAB std uses N-1 by default for vectors
    # But the original code doesn't specify -- numpy default ddof=0. MATLAB std
    # uses N-1 for vectors. For consistency with MATLAB:
    if len(slopes) > 1:
        MsD = float(np.std(slopes, ddof=1))

    MVA = float(np.mean(v_A))

    slope_upper = Ms + 30 * MsD
    slope_lower = Ms - 30 * MsD

    return {
        "template": template,
        "w": w_chosen,
        "M": M,
        "slope_upper": slope_upper,
        "slope_lower": slope_lower,
        "MVA": MVA,
        "norm_factor": norm_factor,
        "similarity_ok": similarity_ok,
        "lowpoint_ok": lowpoint_ok,
    }


# ===================================================================
# Detection (RRIb)
# ===================================================================

def rri_detect(
    signal: NDArray,
    calibration: Dict[str, Any],
    fs: float = 2500.0,
    km: float = 5.0,
    corr_thresh: float = 0.90,
    rri_floor_s: float = 0.4,
    rri_ceil_s: float = 4.0,
) -> Dict[str, Any]:
    """Detect R-peaks using the 5-method pipeline and compute RRI / HRV.

    This corresponds to RRIb_auto_2021.m.

    Parameters
    ----------
    signal : 1-D array
        Raw ECG signal (single channel).
    calibration : dict
        Output of ``rri_calibrate()``.
    fs : float
        Sampling rate in Hz.
    km : float
        Use the last *km* minutes of the recording.
    corr_thresh : float
        Distance-correlation threshold for Method 2 (default 0.90).
    rri_floor_s : float
        Minimum physiological RR interval in seconds (default 0.4 s = 150 bpm).
    rri_ceil_s : float
        Maximum physiological RR interval in seconds (default 4.0 s = 15 bpm).

    Returns
    -------
    dict with keys:
        r_peak_indices : 0-based indices into the preprocessed signal
        rr_intervals   : all RR intervals in seconds (before outlier rejection)
        rr_clean       : clean RR intervals in seconds (after outlier rejection)
        sdnn           : SDNN in ms
        rmssd          : RMSSD in ms
        hr             : mean heart rate in bpm (from clean RR)
    """
    if not calibration.get("similarity_ok", False):
        raise ValueError("Calibration failed (similarity_ok=False); cannot detect.")

    # -- Unpack calibration --
    template = calibration["template"]  # (n_peaks, window_len)
    ref_template = template[0]           # reference waveform
    w = calibration["w"]                 # lookback window (samples)
    M = calibration["M"]
    slope_upper = calibration["slope_upper"]
    slope_lower = calibration["slope_lower"]
    MVA = calibration["MVA"]
    norm_factor = calibration["norm_factor"]

    # -- Convert time constants to sample counts --
    pre_peak = int(_PRE_PEAK_S * fs)
    post_peak = int(_POST_PEAK_S * fs)
    min_peak_pos = int(_MIN_PEAK_TIME_S * fs)  # e.g. 450 @ 2500 Hz

    # -- Preprocessing (same filter, but normalize by calibration norm_factor) --
    sig = _lowpass_filter(signal, fs, cutoff=50.0)
    sig = _take_last_km_minutes(sig, fs, km)
    sig = sig - sig.mean()
    nx1 = sig / norm_factor

    # Pad end with zeros (for template extraction near the end)
    nx1 = np.concatenate([nx1, np.zeros(pre_peak)])

    # ---------------------------------------------------------------
    # Method 1: find all local maxima
    # ---------------------------------------------------------------
    all_peak_idx, _ = find_peaks(nx1)
    # Exclude peaks too close to the start (within pre_peak of signal start)
    all_peak_idx = all_peak_idx[all_peak_idx > pre_peak]

    # ---------------------------------------------------------------
    # Method 2: template matching via distance correlation
    # ---------------------------------------------------------------
    method2_pass = []
    for pk in all_peak_idx:
        pk_amp = nx1[pk]
        if pk_amp == 0:
            continue
        lo = pk - pre_peak
        hi = pk + post_peak + 1
        seg = nx1[lo:hi] / pk_amp
        corr = distcorr(ref_template, seg)
        if corr >= corr_thresh:
            method2_pass.append(pk)

    method2_pass = np.array(method2_pass, dtype=int)

    # Exclude peaks at position < min_peak_pos (edge artifact guard)
    method2_pass = method2_pass[method2_pass >= min_peak_pos]

    if len(method2_pass) == 0:
        return {
            "r_peak_indices": np.array([], dtype=int),
            "rr_intervals": np.array([]),
            "rr_clean": np.array([]),
            "sdnn": 0.0,
            "rmssd": 0.0,
            "hr": 0.0,
        }

    # ---------------------------------------------------------------
    # Methods 3/4/5: morphological feature filtering
    # ---------------------------------------------------------------
    # Look back w samples from each candidate to find valley
    pre_k = method2_pass - w  # start of lookback segment

    trc = np.zeros(len(method2_pass), dtype=int)
    for i, pk_start in enumerate(pre_k):
        if pk_start < 0:
            trc[i] = -1
            continue
        seg = nx1[pk_start: pk_start + w + 1]
        trc[i] = _find_valley(seg)

    # Keep only peaks where a valley was found
    found_mask = trc > -1
    trc2 = trc[found_mask]
    pre_k2 = pre_k[found_mask]
    floc = pre_k2 + w  # R-peak positions (should equal method2_pass[found_mask])

    # Valley absolute positions
    tv_L = pre_k2 + trc2
    # Peak-valley amplitude differences
    tv_A = nx1[floc] - nx1[tv_L]
    # DP: distance from valley to peak in samples
    dp = (w + 1) - trc2
    # Slopes
    tS = tv_A / dp

    # Combined filter (all three conditions must pass simultaneously)
    cond_dp = (dp >= 0.5 * M) & (dp <= 9.5 * M)
    cond_slope = (tS >= 0.8 * slope_lower) & (tS <= 1.2 * slope_upper)
    cond_amp = (tv_A >= 0.5 * MVA) & (tv_A <= 19.5 * MVA)
    all_pass = cond_dp & cond_slope & cond_amp

    # Final accepted R-peak positions
    r_peaks = floc[all_pass]

    if len(r_peaks) < 2:
        return {
            "r_peak_indices": r_peaks,
            "rr_intervals": np.array([]),
            "rr_clean": np.array([]),
            "sdnn": 0.0,
            "rmssd": 0.0,
            "hr": 0.0,
        }

    # ---------------------------------------------------------------
    # RR interval computation
    # ---------------------------------------------------------------
    # The MATLAB code: B = -([0 KK2'] - [KK2' 0]); RRI = B(2:end-1)
    # This computes differences between consecutive R-peak positions.
    rri_samples = np.diff(r_peaks).astype(float)

    # ---------------------------------------------------------------
    # Two-round outlier rejection
    # ---------------------------------------------------------------
    rri_floor_samples = rri_floor_s * fs   # e.g. 1000 @ 2500 Hz
    rri_ceil_samples = rri_ceil_s * fs     # e.g. 10000 @ 2500 Hz

    # Round 1: hard physiological thresholds
    mask1 = (rri_samples > rri_floor_samples) & (rri_samples < rri_ceil_samples)
    rri_r1 = rri_samples[mask1]

    if len(rri_r1) < 2:
        rri_clean_s = rri_r1 / fs
        sdnn = float(np.std(rri_clean_s, ddof=1) * 1000) if len(rri_clean_s) > 1 else 0.0
        rmssd = 0.0
        hr = float(60.0 / np.mean(rri_clean_s)) if len(rri_clean_s) > 0 else 0.0
        return {
            "r_peak_indices": r_peaks,
            "rr_intervals": rri_samples / fs,
            "rr_clean": rri_clean_s,
            "sdnn": sdnn,
            "rmssd": rmssd,
            "hr": hr,
        }

    # Round 2: statistical thresholds combined with hard thresholds
    mean_rri = np.mean(rri_r1)
    std_rri = np.std(rri_r1, ddof=1)  # MATLAB std uses N-1 (ddof=1)

    # Threshold selection based on std magnitude (in seconds)
    if std_rri / fs > _STD_THRESHOLD_S:
        # High variability: use tighter bounds (mean +/- 3*std)
        tg1 = mean_rri - 3 * std_rri
        tg2 = mean_rri + 3 * std_rri
    else:
        # Low variability: use wider bounds (mean +/- 10*std)
        tg1 = mean_rri - 10 * std_rri
        tg2 = mean_rri + 10 * std_rri

    # Apply BOTH statistical AND hard thresholds
    mask2 = (
        (rri_samples > tg1) & (rri_samples < tg2) &
        (rri_samples > rri_floor_samples) & (rri_samples < rri_ceil_samples)
    )
    rri_clean = rri_samples[mask2]

    # ---------------------------------------------------------------
    # HRV metrics
    # ---------------------------------------------------------------
    rri_clean_s = rri_clean / fs  # convert to seconds

    if len(rri_clean_s) > 1:
        sdnn = float(np.std(rri_clean_s, ddof=1) * 1000)  # ms
        diffs = np.diff(rri_clean_s)
        rmssd = float(np.sqrt(np.mean(diffs ** 2)) * 1000)  # ms
    else:
        sdnn = 0.0
        rmssd = 0.0

    hr = float(60.0 / np.mean(rri_clean_s)) if len(rri_clean_s) > 0 else 0.0

    return {
        "r_peak_indices": r_peaks,
        "rr_intervals": rri_samples / fs,
        "rr_clean": rri_clean_s,
        "sdnn": sdnn,
        "rmssd": rmssd,
        "hr": hr,
    }


# ===================================================================
# Top-level convenience function
# ===================================================================

def analyze_rri(
    ecg_signal: NDArray,
    fs: float = 2500.0,
    km: float = 5.0,
    corr_thresh: float = 0.90,
    rri_floor_s: float = 0.4,
    rri_ceil_s: float = 4.0,
) -> Dict[str, Any]:
    """End-to-end R-peak detection and HRV analysis.

    Calls ``rri_calibrate`` then ``rri_detect`` and optionally computes
    frequency-domain and nonlinear HRV metrics via ``vollmer_hrv``.

    Parameters
    ----------
    ecg_signal : 1-D array
        Raw ECG signal (single channel).
    fs : float
        Sampling rate in Hz.
    km : float
        Use the last *km* minutes of the recording.
    corr_thresh : float
        Distance-correlation threshold for Method 2.
    rri_floor_s, rri_ceil_s : float
        Hard RR interval bounds in seconds.

    Returns
    -------
    dict with keys:
        metrics      : dict of HRV metrics
        r_peaks      : 0-based R-peak indices (into preprocessed signal)
        rr_intervals : clean RR intervals in seconds
        rr_times     : cumulative sum of clean RR intervals (seconds)
        calibration  : full calibration dict (for debugging)
    """
    ecg_signal = np.asarray(ecg_signal, dtype=float).ravel()

    # Step 1: calibrate
    calibration = rri_calibrate(ecg_signal, fs=fs, km=km)

    if not calibration["similarity_ok"]:
        warnings.warn("Calibration failed: template similarity not achieved.")
        return {
            "metrics": {},
            "r_peaks": np.array([], dtype=int),
            "rr_intervals": np.array([]),
            "rr_times": np.array([]),
            "calibration": calibration,
        }

    # Step 2: detect
    detection = rri_detect(
        ecg_signal, calibration, fs=fs, km=km,
        corr_thresh=corr_thresh,
        rri_floor_s=rri_floor_s, rri_ceil_s=rri_ceil_s,
    )

    r_peaks = detection["r_peak_indices"]
    rr_clean = detection["rr_clean"]
    sdnn = detection["sdnn"]
    rmssd = detection["rmssd"]
    hr = detection["hr"]

    # Cumulative RR times
    rr_times = np.cumsum(rr_clean) if len(rr_clean) > 0 else np.array([])

    # Step 3: build metrics dict
    metrics: Dict[str, Any] = {
        "HR_mean": hr,
        "HRV_SDNN": sdnn,
        "HRV_RMSSD": rmssd,
    }

    # Extended HRV metrics (frequency-domain, nonlinear) if available
    if HAS_VH and len(rr_clean) >= 5:
        try:
            rr_ms = rr_clean * 1000  # vollmer_hrv typically expects ms

            # Frequency domain
            lf, hf, lf_hf, lfnu, hfnu = vh.freq_domain(rr_ms)
            metrics["HRV_LF"] = lf
            metrics["HRV_HF"] = hf
            metrics["HRV_LF_HF"] = lf_hf
            metrics["LFnu"] = lfnu
            metrics["HFnu"] = hfnu

            # Nonlinear: DFA alpha1
            alpha1 = vh.dfa_alpha1(rr_ms)
            metrics["HRV_DFA_alpha1"] = alpha1
        except Exception as e:
            warnings.warn(f"Extended HRV computation failed: {e}")

    return {
        "metrics": metrics,
        "r_peaks": r_peaks,
        "rr_intervals": rr_clean,
        "rr_times": rr_times,
        "calibration": calibration,
    }


# ===================================================================
# CLI entry point (for quick testing)
# ===================================================================

if __name__ == "__main__":
    import sys

    print("rri_rpeak module loaded successfully.")
    print(f"  distcorr available: True")
    print(f"  vollmer_hrv available: {HAS_VH}")
    print(f"  numpy {np.__version__}")

    # Quick self-test of distcorr
    rng = np.random.default_rng(42)
    x_test = rng.standard_normal(100)
    y_test = x_test + 0.1 * rng.standard_normal(100)
    dc = distcorr(x_test, y_test)
    print(f"  distcorr self-test (correlated): {dc:.4f} (expect ~0.95+)")

    y_indep = rng.standard_normal(100)
    dc2 = distcorr(x_test, y_indep)
    print(f"  distcorr self-test (independent): {dc2:.4f} (expect ~0.1-0.3)")
