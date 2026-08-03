import sys
import traceback

import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt

from PyQt6.QtWidgets import QApplication, QMessageBox
from hrv_app.gui.main_window import MainWindow


def _install_excepthook():
    """全域例外處理: 避免 slot 內未捕捉的例外讓 PyQt6 直接 abort()。

    PyQt6 對 Qt event loop 所呼叫的 slot 中、未被捕捉的 Python 例外，預設會
    終止整個行程 (Windows 上呈現為 Qt6Core.dll 例外碼 0xc0000409 / __fastfail)，
    且沒有任何 traceback 或錯誤對話框。安裝自訂 excepthook 後，例外會被印到終端機
    並以對話框呈現，事件迴圈得以繼續，方便日後除錯而非靜默崩潰。
    """
    def hook(exc_type, exc_value, exc_tb):
        sys.stderr.write(
            ''.join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        sys.stderr.flush()
        try:
            QMessageBox.critical(
                None, '未預期的錯誤',
                f'{exc_type.__name__}: {exc_value}\n\n(詳細追蹤已輸出至終端機)')
        except Exception:
            pass

    sys.excepthook = hook


def main():
    # Chinese font support
    plt.rcParams['font.sans-serif'] = [
        'Microsoft JhengHei', 'SimHei', 'sans-serif'
    ]
    plt.rcParams['axes.unicode_minus'] = False

    app = QApplication(sys.argv)
    _install_excepthook()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
