# F:\M143020071\HRC_D\HRV-project-main\hrv_app\templates\template_data_Eng.py

TEMPLATES = {
    "sdnn_low": {
        "label": "Low SDNN",
        "analysis": (
            "Based on the analysis: Your SDNN is slightly lower than the standard value, "
            "indicating potential stress or physical discomfort. Please be mindful of cardiovascular risks. "
            "Frequency domain data shows active sympathetic activity throughout the baseline and stress phases."
        ),
        "recommendation": (
            "Increased physical exercise is recommended to improve HRV. "
            "If you experience chest tightness or pain during exercise, please consult a cardiologist."
        ),
    },
    "arrhythmia": {
        "label": "Arrhythmia",
        "analysis": "Detection results indicate arrhythmia. Standard HRV metrics may not be applicable.",
        "recommendation": "Please consult a cardiologist if you experience palpitations or dizziness.",
    },
    "noise": {
        "label": "Noise Interference",
        "analysis": (
            "Based on the combined values above, the following information can be obtained: "
            "This examination requires a quiet and steady state for accurate judgment. Your results show "
            "significant noise, possibly caused by speaking, movement, etc., "
            "making the data uninterpretable."
        ),
        "recommendation": "Unable to interpret due to noise.",
    },
    "normal": {
        "label": "Normal",
        "analysis": (
            "Based on the combined values above, the following information can be obtained: "
            "In the time-domain analysis, your SDNN is above the standard value, indicating a relatively lower cardiovascular risk. "
            "In the frequency-domain analysis, your data shows that the parasympathetic nervous system was more active during the baseline period; "
            "the parasympathetic nervous system was active during the stress period; and sympathetic activity decreased during the recovery period. "
            "Your overall autonomic nervous system has returned to a state of parasympathetic dominance."
        ),
        "recommendation": (
            "After evaluation, your Heart Rate Variability (HRV) is higher than the standard value, and your cardiovascular risk is relatively low. "
            "It is recommended to exercise more to maintain your Heart Rate Variability."
        ),
    },
}

CONDITION_ORDER = ["sdnn_low", "arrhythmia", "noise", "normal"]

def get_dropdown_labels():
    return [TEMPLATES[key]["label"] for key in CONDITION_ORDER]

def get_template(condition_key):
    return TEMPLATES[condition_key]

def get_key_by_index(index):
    return CONDITION_ORDER[index]