"""
Module for reading .abf format files using Neo.
"""
import datetime
import numpy as np
import neo

def read_abf_file(file_path):
    """
    Reads an .abf file using Neo,
    and returns a standardized dictionary matching the GUI pipeline.
    """
    # 1. 載入 ABF 檔案 (使用 Neo 的 AxonIO)
    reader = neo.io.AxonIO(filename=file_path)
    block = reader.read_block()
    
    # 取得第一個 segment (連續紀錄通常都在 block.segments[0])
    seg = block.segments[0]
    
    # 🛡️ 安全防呆 1：確保檔案內真的有類比訊號，避免後續取 [0] 時崩潰
    if not seg.analogsignals:
        raise ValueError(f"No analog signals found in the file: {file_path}")
    
    # 初始化收集訊號的容器 (ABF 有時會將不同通道存在不同的 AnalogSignal 物件中)
    signal_matrices = []
    sig_names = []
    
    # 遍歷提取類比訊號 (AnalogSignal)
    for anasig in seg.analogsignals:
        # 預設 .abf 標註的單位不可信
        signal_matrices.append(np.asarray(anasig.magnitude, dtype=float))
        
        # 獲取通道名稱 (與原本相同)
        names = anasig.array_annotations.get('channel_names')
        if names is not None:
            sig_names.extend([n.decode('utf-8') if isinstance(n, bytes) else str(n) for n in names])
        else:
            sig_names.extend([f"Ch{len(sig_names) + i + 1}" for i in range(anasig.shape[1])])

    # 水平合併所有的通道矩陣 => 確保形狀為 (samples, channels)
    # 🛡️ 安全防呆 2：捕捉因不同通道取樣點長度不一致而導致的合併失敗
    try:
        signal_matrix = np.hstack(signal_matrices) if signal_matrices else np.array([])
    except ValueError as e:
        raise ValueError("All channels must have the same length (number of samples) to be stacked.") from e
        
    n_sig = signal_matrix.shape[1] if signal_matrix.ndim > 1 else 0
    
    # 獲取取樣率 (從第一個類比訊號物件中提取)
    fs = float(seg.analogsignals[0].sampling_rate.rescale('Hz').magnitude)
    
    # 2. 獲取測量起始時間
    meas_datetime = block.rec_datetime
    if meas_datetime is not None:
        base_date = meas_datetime.date()
        base_time = meas_datetime.time()
    else:
        base_date = datetime.date.today()
        base_time = datetime.datetime.now().time()
        
    # 3. 💡 核心改進：抓取事件時間並轉為 Index
    markers = []
    triggers = []
    
    # 遍歷所有的事件標記 (Events)
    for ev in seg.events:
        # 取得事件的秒數 (確保單位轉換為秒)
        times_sec = ev.times.rescale('s').magnitude
        labels = ev.labels
        
        for t, desc in zip(times_sec, labels):
            # 處理部分標籤為 bytes 的情況
            desc_str = desc.decode('utf-8') if isinstance(desc, bytes) else str(desc)
            
            # 手動將秒數精準轉換為數據點 Index (時間 * 取樣率)
            sample_index = int(np.round(t * fs))
            
            # 🎯 關鍵修正：不論是什麼事件，一律塞進 markers 確保 GUI 100% 讀到並繪製！
            markers.append(sample_index)
            
            # 備份分流：如果符合 Trigger 特徵，才額外塞進 triggers 提供後續分析
            desc_upper = desc_str.upper()
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