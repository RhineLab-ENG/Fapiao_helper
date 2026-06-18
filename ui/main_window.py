import os
import sys
import threading
# 确保项目根目录在 sys.path 中（支持直接运行此文件或从 main.py 导入）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFileDialog, QTextEdit, QFrame, QMessageBox, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QTextCursor
from extractors.pdf_parser import parse_invoice
from extractors.image_parser import extract_amount_from_image, extract_amount_from_order_pdf


def _cents_to_yuan(cents):
    """整数「分」→ 显示用「元」字符串，如 9990 → '99.90'"""
    if cents is None or cents == 0:
        return '0.00'
    return f"{cents / 100:.2f}"


class OcrSignals(QObject):
    """信号中转：后台线程通过此对象发送信号到主线程"""
    amount_found = pyqtSignal(int)
    no_amount_found = pyqtSignal()
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal()


def _run_ocr_in_thread(img_path, signals):
    """在后台线程中执行OCR，通过 signals 回传结果"""
    try:
        amount = extract_amount_from_image(img_path)
        if amount:
            signals.amount_found.emit(amount)
        else:
            signals.no_amount_found.emit()
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
        self.img_zone = DropZone("拖入订单截图或淘宝导出的PDF\n(JPG, PNG, PDF等)", ['.jpg', '.jpeg', '.png', '.bmp', '.pdf'])
        
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
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.target_folder = ""
        
        folder_layout.addWidget(self.folder_btn)
        folder_layout.addWidget(self.folder_label, stretch=1)
        folder_layout.addWidget(self.status_label)
        
        main_layout.addLayout(folder_layout)

        # 金额核对开关
        self.ocr_checkbox = QCheckBox("金额核对（OCR）")
        self.ocr_checkbox.setChecked(False)
        self.ocr_checkbox.setToolTip("开启后，拖入截图将自动 OCR 识别实付款金额并与发票比对\n（PDF 订单始终自动提取，不受此开关影响）")
        main_layout.addWidget(self.ocr_checkbox)

        # 多买方确认开关
        self.buyer_checkbox = QCheckBox("多买方确认")
        self.buyer_checkbox.setChecked(False)
        self.buyer_checkbox.setToolTip("开启后，若当前买方与已有记录不同将弹框提示，防止放错发票")
        main_layout.addWidget(self.buyer_checkbox)

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

    def append_log(self, text, color=None):
        if color:
            escaped = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            self.log_area.moveCursor(QTextCursor.MoveOperation.End)
            self.log_area.insertHtml(f'<span style="color:{color};">{escaped}</span><br>')
        else:
            self.log_area.append(text)

    def set_status(self, text, color):
        """在文件夹选择行右侧显示状态文字（绿/红）"""
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.status_label.setText(text)
        
    def on_pdf_dropped(self, pdf_path):
        self.append_log(f"已拖入发票，正在获取信息...")
        try:
            invoice_data = parse_invoice(pdf_path)
            
            date = invoice_data.get('date', '未知')
            amount_cents = invoice_data.get('total_amount', 0)
            amount = _cents_to_yuan(amount_cents)
            name = invoice_data.get('item_name', '未知')
            inv_num = invoice_data.get('invoice_number', '未知')
            seller = invoice_data.get('seller_name', '未知')
            
            filename = os.path.basename(pdf_path)
            
            preview_text = (
                f"{self.pdf_zone.title_text}\n\n"
                f"文件名: {filename}\n"
                f"----------------\n"
                f"卖方: {seller}\n"
                f"品名: {name}\n"
                f"金额: ￥{amount}\n"
                f"日期: {date}\n"
                f"号码: {inv_num}"
            )
            self.pdf_zone.label.setText(preview_text)
            self.append_log(f"解析成功：[{seller}] | [{name}] | ￥{amount} | {date}")
            # 保存发票数据供后续比对用
            self.invoice_data = invoice_data
            
            # 金额为 0 → 可能不是有效发票（先更新GUI再弹框）
            if amount_cents == 0:
                self.append_log("警告: 未识别到有效金额，PDF 可能不是发票", "red")
                QMessageBox.warning(self, "无效发票", "PDF 可能不是发票，未识别到有效金额。")
        except Exception as e:
            self.append_log(f"解析发票预览失败: {e}", "red")
            self.pdf_zone.label.setText(f"{self.pdf_zone.title_text}\n\n[解析失败]\n{os.path.basename(pdf_path)}")

    def on_img_dropped(self, img_path):
        """PDF 始终提取金额；图片受 OCR 开关控制"""
        filename = os.path.basename(img_path)
        is_pdf = img_path.lower().endswith('.pdf')
        
        if is_pdf:
            # PDF 订单：直接提取，不计成本始终显示金额
            self.append_log(f"已拖入订单PDF: {filename}，正在提取金额...")
            amount = extract_amount_from_order_pdf(img_path)
            if amount:
                self.on_img_preview_amount(amount)
            else:
                self.on_img_preview_no_amount()
        elif self.ocr_checkbox.isChecked():
            # 图片：后台 OCR，结果显示金额
            self.img_zone.label.setText(
                f"{self.img_zone.title_text}\n\n已选择:\n{filename}\n\n正在识别金额..."
            )
            self.append_log(f"已拖入截图: {filename}，正在后台识别...")
            self.img_signals = OcrSignals()
            self.img_signals.amount_found.connect(self.on_img_preview_amount)
            self.img_signals.no_amount_found.connect(self.on_img_preview_no_amount)
            self.img_signals.finished.connect(lambda: None)
            t = threading.Thread(target=_run_ocr_in_thread, args=(img_path, self.img_signals), daemon=True)
            t.start()
        else:
            # OCR 关闭 + 图片：只显示文件名，不显示金额
            self.img_zone.label.setText(
                f"{self.img_zone.title_text}\n\n已选择:\n{filename}"
            )
            self.append_log(f"已拖入截图: {filename}（OCR已关闭）")

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
        self.status_label.setText("")
        self.append_log("开始处理...")
        
        # PDF 订单始终核对（不花时间），图片受 OCR 开关控制
        if img_path:
            is_pdf = img_path.lower().endswith('.pdf')
            if hasattr(self, 'preview_amount') and self.preview_amount:
                # 已有预览金额，直接复用
                self.append_log(f"复用预览金额: ￥{_cents_to_yuan(self.preview_amount)}")
                self.execute_main_process(pdf_path, img_path, self.preview_amount)
                self.preview_amount = None
            elif is_pdf:
                # PDF 订单：现场提取（兜底，正常已在 on_img_dropped 提取）
                self.append_log("正在提取订单PDF金额...")
                amount = extract_amount_from_order_pdf(img_path)
                if amount:
                    self.append_log(f"识别到实付款: ￥{_cents_to_yuan(amount)}")
                self.execute_main_process(pdf_path, img_path, amount)
            elif self.ocr_checkbox.isChecked():
                # 图片：后台 OCR
                self.append_log("正在后台处理订单...")
                self.start_image_ocr(img_path)
            else:
                # OCR 关闭 + 图片：跳过核对
                self.append_log("OCR已关闭，跳过金额核对。")
                self.execute_main_process(pdf_path, img_path, skip_amount_check=True)
        else:
            # 没有图片，直接执行主流程
            self.execute_main_process(pdf_path, img_path)
    
    def start_image_ocr(self, img_path):
        """启动后台线程处理图片OCR"""
        self.ocr_signals = OcrSignals()
        self.ocr_signals.amount_found.connect(self.on_amount_found)
        self.ocr_signals.no_amount_found.connect(self.on_process_no_amount)
        self.ocr_signals.finished.connect(self.on_image_ocr_finished)
        self.ocr_signals.error_occurred.connect(self.on_image_ocr_error)
        
        t = threading.Thread(target=_run_ocr_in_thread, args=(img_path, self.ocr_signals), daemon=True)
        t.start()
        
        # 保存当前状态供后续使用
        self.current_pdf_path = self.pdf_zone.file_path
        self.current_img_path = img_path
        self.extracted_amount = None
    
    def on_amount_found(self, amount):
        """后台线程：找到金额（amount 为整数「分」）"""
        self.extracted_amount = amount
        self.append_log(f"识别到截图实付款金额: ￥{_cents_to_yuan(amount)}")

    def on_process_no_amount(self):
        """后台线程：未找到金额（处理流程）"""
        self.append_log("截图金额识别失败：未找到实付款金额")
    
    def on_img_preview_amount(self, amount):
        """图片拖入后的预览OCR回传（amount 为整数「分」）"""
        filename = os.path.basename(self.img_zone.file_path) if self.img_zone.file_path else ""
        yuan = _cents_to_yuan(amount)
        self.img_zone.label.setText(
            f"{self.img_zone.title_text}\n\n"
            f"文件: {filename}\n"
            f"----------------\n"
            f"实付款: ￥{yuan}"
        )
        self.append_log(f"截图金额识别完成: ￥{yuan}")
        self.preview_amount = amount

    def on_img_preview_no_amount(self):
        """图片拖入后的预览OCR回传：识别失败"""
        filename = os.path.basename(self.img_zone.file_path) if self.img_zone.file_path else ""
        self.img_zone.label.setText(
            f"{self.img_zone.title_text}\n\n"
            f"文件: {filename}\n"
            f"----------------\n"
            f"[未识别到金额]"
        )
        self.append_log("截图金额识别失败：未找到实付款金额")
        self.preview_amount = None
    
    def on_image_ocr_error(self, error_msg):
        """后台线程：出错"""
        self.append_log(f"图片处理出错: {error_msg}", "red")
    
    def on_image_ocr_finished(self):
        """后台线程：完成，继续主流程"""
        self.execute_main_process(self.current_pdf_path, self.current_img_path, self.extracted_amount)
    
    def execute_main_process(self, pdf_path, img_path, pre_extracted_amount=None, skip_amount_check=False):
        """执行主流程（调用process_callback）"""
        try:
            # 调用主逻辑，但传入已经提取的金额（避免重复OCR）
            self.process_callback(pdf_path, img_path, self.target_folder, self, pre_extracted_amount, skip_amount_check)
        except Exception as e:
            self.set_status(f"✗ 处理失败: {e}", "red")
        finally:
            self.process_btn.setEnabled(True)

    def reset_ui(self):
        self.pdf_zone.reset()
        self.img_zone.reset()
