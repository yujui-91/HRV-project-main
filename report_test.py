"""Generate Chinese PDF reports for all condition templates."""
from hrv_app.core.report_generator import generate_report
from hrv_app.templates.template_data import TEMPLATES, CONDITION_ORDER

PATIENT_INFO = {
    'record_number': '100001',
    'name': '張三',
    'exam_time': '2016-08-30 12:54:42',
    'birth_date': '20021201',
}

HRV_RESULTS = {
    'metrics': {
        'HRV_SDNN': 139.23,
        'HRV_LF': 0.03,
        'HRV_HF': 0.04,
        'HRV_LF_HF': 0.90,
        'HRV_DFA_alpha1': 0.65,
        'LFnu': 42.9,
        'HFnu': 57.1,
    }
}


def run_test():
    for key in CONDITION_ORDER:
        tmpl = TEMPLATES[key]
        output_pdf = f"test_zh_{key}.pdf"
        print(f"[中文] {key} -> {output_pdf} ...")
        try:
            generate_report(
                output_pdf,
                PATIENT_INFO,
                HRV_RESULTS,
                tmpl['analysis'],
                tmpl['recommendation'],
            )
            print(f"  OK")
        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == "__main__":
    run_test()
