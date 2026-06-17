import os
import sys
import threading
# 确保项目根目录在 sys.path 中（支持直接运行此文件或从 main.py 导入）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFileDialog, QTextEdit, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from extractors.pdf_parser import parse_invoice
from extractors.image_parser import extract_amount_from_image


class OcrSignals(QObject):
    """信号中转：后台线程通过此对象发送信号到主线程"""
    amount_found = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal()


def _run_ocr_in_thread(img_path, signals):
    """在后台线程中执行OCR，通过 signals 回传结果"""
    try:
        amount = extract_amount_from_image(img_path)
        if amount:
            signals.amount_found.emit(amount)
        signals.finished.emit()
    except Exception as e:
        signals.error_occurred.emit(str(e))

class DropZone(QFrame):
    fileDropped = pyqtSignal(str)

    def __init__(self, title, file_exts, parent=None):
        super().__init__(parent)
        self.file_exts = file_exts
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #aaa;
                border-radius: 5px;
                background-color: #f9f9f9;
            }
            QLabel {
                border: none;
                background-color: transparent;
            }
        """)
        
        layout = QVBoxLayout()
        self.label = QLabel(title)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.setLayout(layout)
        
        self.file_path = None
        self.title_text = title

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1:
                path = urls[0].toLocalFile()
                ext = os.path.splitext(path)[1].lower()
                if ext in self.file_exts:
                    event.acceptProposedAction()
                    self.setStyleSheet("""
                        QFrame {
                            border: 2px dashed #4CAF50;
                            border-radius: 5px;
                            background-color: #e8f5e9;
                        }
                    """)
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #aaa;
                border-radius: 5px;
                background-color: #f9f9f9;
            }
        """)

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("""
            QFrame {
                border: 2px solid #4CAF50;
                border-radius: 5px;
                background-color: #f9f9f9;
            }
        """)
        path = event.mimeData().urls()[0].toLocalFile()
        self.file_path = path
        filename = os.path.basename(path)
        self.label.setText(f"{self.title_text}\n\n已选择:\n{filename}")
        self.fileDropped.emit(path)

    def reset(self):
        self.file_path = None
        self.label.setText(self.title_text)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #aaa;
                border-radius: 5px;
                background-color: #f9f9f9;
            }
        """)


class MainWindow(QWidget):
    def __init__(self, process_callback):
        super().__init__()
        self.process_callback = process_callback
        self.initUI()

    def initUI(self):
        self.setWindowTitle("发票整理与重命名助手")
        self.resize(700, 500)
        
        main_layout = QVBoxLayout()

        # 拖放区域 (左右)
        drop_layout = QHBoxLayout()
        
        self.pdf_zone = DropZone("拖入发票\n(PDF格式)", ['.pdf'])
        self.img_zone = DropZone("拖入订单截图\n(JPG, PNG等)", ['.jpg', '.jpeg', '.png', '.bmp'])
        
        self.pdf_zone.setMinimumHeight(200)
        self.img_zone.setMinimumHeight(200)

        self.pdf_zone.fileDropped.connect(self.on_pdf_dropped)
        self.img_zone.fileDropped.connect(self.on_img_dropped)

        drop_layout.addWidget(self.pdf_zone)
        drop_layout.addWidget(self.img_zone)
        
        main_layout.addLayout(drop_layout)

        # 输出文件夹选择
        folder_layout = QHBoxLayout()
        self.folder_btn = QPushButton("选择输出文件夹")
        self.folder_btn.clicked.connect(self.select_folder)
        self.folder_label = QLabel("未选择文件夹")
        self.target_folder = ""
        
        folder_layout.addWidget(self.folder_btn)
        folder_layout.addWidget(self.folder_label, stretch=1)
        
        main_layout.addLayout(folder_layout)

        # 开始按钮
        self.process_btn = QPushButton("开始处理")
        self.process_btn.setMinimumHeight(40)
        self.process_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.process_btn.clicked.connect(self.start_processing)
        main_layout.addWidget(self.process_btn)

        # 日志输出
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        main_layout.addWidget(self.log_area)

        self.setLayout(main_layout)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if folder:
            self.target_folder = folder
            self.folder_label.setText(folder)
            self.append_log(f"已选择输出文件夹: {folder}")

    def append_log(self, text):
        self.log_area.append(text)
        
    def on_pdf_dropped(self, pdf_path):
        self.append_log(f"已拖入发票，正在获取信息...")
        try:
            invoice_data = parse_invoice(pdf_path)
            
            date = invoice_data.get('date', '未知')
            amount = invoice_data.get('total_amount', '未知')
            name = invoice_data.get('item_name', '未知')
            inv_num = invoice_data.get('invoice_number', '未知')
            
            filename = os.path.basename(pdf_path)
            preview_text = (
                f"{self.pdf_zone.title_text}\n\n"
                f"文件名: {filename}\n"
                f"----------------\n"
                f"品名: {name}\n"
                f"金额: ￥{amount}\n"
                f"日期: {date}\n"
                f"号码: {inv_num}"
            )
            self.pdf_zone.label.setText(preview_text)
            self.append_log(f"解析成功：[{name}] | ￥{amount} | {date}")
            # 保存发票数据供后续比对用
            self.invoice_data = invoice_data
        except Exception as e:
            self.append_log(f"解析发票预览失败: {e}")
            self.pdf_zone.label.setText(f"{self.pdf_zone.title_text}\n\n[解析失败]\n{os.path.basename(pdf_path)}")

    def on_img_dropped(self, img_path):
        """图片拖入后：显示文件名，并启动后台OCR预览"""
        filename = os.path.basename(img_path)
        self.img_zone.label.setText(
            f"{self.img_zone.title_text}\n\n已选择:\n{filename}\n\n正在识别金额..."
        )
        self.append_log(f"已拖入截图: {filename}，正在后台识别...")
        # 启动后台线程识别金额（用 threading.Thread，简单可靠）
        self.img_signals = OcrSignals()
        self.img_signals.amount_found.connect(self.on_img_preview_amount)
        self.img_signals.finished.connect(lambda: None)  # 预览完成无需额外操作
        t = threading.Thread(target=_run_ocr_in_thread, args=(img_path, self.img_signals), daemon=True)
        t.start()

    def start_processing(self):
        pdf_path = self.pdf_zone.file_path
        img_path = self.img_zone.file_path

        if not pdf_path:
            QMessageBox.warning(self, "提示", "请先拖入发票 PDF。")
            return
            
        if not self.target_folder:
            QMessageBox.warning(self, "提示", "请先选择输出文件夹。")
            return

        self.process_btn.setEnabled(False)
        self.append_log("开始处理...")
        
        # 如果有图片，先在后台启动图片OCR线程
        if img_path:
            if hasattr(self, 'preview_amount') and self.preview_amount:
                # 拖入时已识别过，直接复用
                self.append_log(f"复用预览金额: ￥{self.preview_amount}")
                self.execute_main_process(pdf_path, img_path, self.preview_amount)
                self.preview_amount = None  # 用完清掉
            else:
                self.append_log("正在后台处理订单截图...")
                self.start_image_ocr(img_path)
        else:
            # 没有图片，直接执行主流程
            self.execute_main_process(pdf_path, img_path)
    
    def start_image_ocr(self, img_path):
        """启动后台线程处理图片OCR"""
        self.ocr_signals = OcrSignals()
        self.ocr_signals.amount_found.connect(self.on_amount_found)
        self.ocr_signals.finished.connect(self.on_image_ocr_finished)
        self.ocr_signals.error_occurred.connect(self.on_image_ocr_error)
        
        t = threading.Thread(target=_run_ocr_in_thread, args=(img_path, self.ocr_signals), daemon=True)
        t.start()
        
        # 保存当前状态供后续使用
        self.current_pdf_path = self.pdf_zone.file_path
        self.current_img_path = img_path
        self.extracted_amount = None
    
    def on_amount_found(self, amount):
        """后台线程：找到金额"""
        self.extracted_amount = amount
        self.append_log(f"识别到截图实付款金额: ￥{amount}")
    
    def on_img_preview_amount(self, amount):
        """图片拖入后的预览OCR回传"""
        filename = os.path.basename(self.img_zone.file_path) if self.img_zone.file_path else ""
        self.img_zone.label.setText(
            f"{self.img_zone.title_text}\n\n"
            f"文件: {filename}\n"
            f"----------------\n"
            f"实付款: ￥{amount}"
        )
        self.append_log(f"截图金额识别完成: ￥{amount}")
        # 保存供 start_processing 复用
        self.preview_amount = amount
    
    def on_image_ocr_error(self, error_msg):
        """后台线程：出错"""
        self.append_log(f"图片处理出错: {error_msg}")
    
    def on_image_ocr_finished(self):
        """后台线程：完成，继续主流程"""
        self.execute_main_process(self.current_pdf_path, self.current_img_path, self.extracted_amount)
    
    def execute_main_process(self, pdf_path, img_path, pre_extracted_amount=None):
        """执行主流程（调用process_callback）"""
        try:
            # 调用主逻辑，但传入已经提取的金额（避免重复OCR）
            self.process_callback(pdf_path, img_path, self.target_folder, self, pre_extracted_amount)
        except Exception as e:
            self.append_log(f"错误: {str(e)}")
            QMessageBox.critical(self, "处理失败", str(e))
        finally:
            self.process_btn.setEnabled(True)

    def reset_ui(self):
        self.pdf_zone.reset()
        self.img_zone.reset()
