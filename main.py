import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from ui.main_window import MainWindow
from extractors.pdf_parser import parse_invoice
from processors.file_manager import process_files
from processors.excel_logger import log_to_excel, _read_data_rows
from extractors.image_parser import extract_amount_from_image, extract_amount_from_order_pdf
from openpyxl import load_workbook


def _cents_to_yuan(cents):
    """整数「分」→ 显示用「元」字符串，如 9990 → '99.90'"""
    if cents is None or cents == 0:
        return '0.00'
    return f"{cents / 100:.2f}"


def _check_buyer_consistency(target_folder, new_buyer, ui_window):
    """检查当前买方是否与已有记录一致，不一致则弹框确认"""
    excel_path = os.path.join(target_folder, "发票汇总.xlsx")
    if not os.path.exists(excel_path) or not new_buyer:
        return True  # 无历史记录或未识别到买方，放行
    try:
        wb = load_workbook(excel_path)
        ws = wb.active
        rows, _ = _read_data_rows(ws)
        wb.close()
        if not rows:
            return True
        # F 列（第5索引）为买方名称
        prev_buyer = rows[0][5] if len(rows[0]) > 5 else ''
        if prev_buyer and prev_buyer != new_buyer:
            reply = QMessageBox.warning(
                ui_window,
                "买方不一致",
                f"当前发票买方「{new_buyer}」与已有记录「{prev_buyer}」不一致！\n确认要继续处理吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                ui_window.append_log("操作已取消（买方不一致）。")
                return False
    except Exception as e:
        ui_window.append_log(f"买方检查失败: {e}", "red")
    return True


def process_callback(pdf_path, img_path, target_folder, ui_window, pre_extracted_amount=None, skip_amount_check=False):
    """
    处理流程：
    1. 解析 PDF
    2. 如果有图片，进行金额比对（使用预提取的金额或现场提取）
    3. 重命名并移动文件
    4. 记录到 Excel
    """
    try:
        # 1. 解析 PDF
        ui_window.append_log(f"正在解析发票: {pdf_path}")
        invoice_data = parse_invoice(pdf_path)
        ui_window.append_log(f"解析成功: {invoice_data}")

        # 多买方确认（默认关闭）
        if getattr(ui_window, 'buyer_checkbox', None) and ui_window.buyer_checkbox.isChecked():
            buyer = invoice_data.get('buyer_name', '')
            if not _check_buyer_consistency(target_folder, buyer, ui_window):
                ui_window.process_btn.setEnabled(True)
                return

        # 2. 如果提供了截图，进行金额比对
        if img_path and not skip_amount_check:
            if pre_extracted_amount:
                # 使用后台线程已提取的金额
                img_amount = pre_extracted_amount
            else:
                # 现场提取金额（如果没有后台预处理）
                ui_window.append_log("正在解析订单以核对金额...")
                if img_path.lower().endswith('.pdf'):
                    img_amount = extract_amount_from_order_pdf(img_path)
                else:
                    img_amount = extract_amount_from_image(img_path)
                if img_amount:
                    ui_window.append_log(f"识别到截图实付款金额: ￥{_cents_to_yuan(img_amount)}")
            if img_amount:
                pdf_amount = invoice_data.get('total_amount', 0)
                if pdf_amount != img_amount:
                    reply = QMessageBox.warning(
                        ui_window,
                        "金额不符",
                        f"注意：发票总金额 (￥{_cents_to_yuan(pdf_amount)}) 与订单实付款 (￥{_cents_to_yuan(img_amount)}) 不一致！\n确认要继续处理吗？",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.No:
                        ui_window.append_log("操作已取消。")
                        return
            else:
                ui_window.append_log("未能在截图中找到实付款及其金额。跳过比对。")

        # 3. 文件重命名和复制
        ui_window.append_log("正在复制且重命名文件...")
        result_files = process_files(pdf_path, img_path, target_folder, invoice_data)
        
        if 'pdf' in result_files:
            ui_window.append_log(f"=> 生成发票文件: {result_files['pdf']}")
        if 'image' in result_files:
            ui_window.append_log(f"=> 生成订单文件: {result_files['image']}")

        # 4. 记录到Excel
        ui_window.append_log("正在写入 Excel...")
        excel_path = log_to_excel(target_folder, invoice_data)
        ui_window.append_log(f"=> Excel 文件已更新: {excel_path}")

        # 5. 将源文件重命名加 USED_ 前缀，标记已处理
        for src_path in (pdf_path, img_path):
            if src_path and os.path.exists(src_path):
                try:
                    dir_name = os.path.dirname(src_path)
                    base_name = os.path.basename(src_path)
                    new_path = os.path.join(dir_name, f"USED_{base_name}")
                    os.rename(src_path, new_path)
                    ui_window.append_log(f"=> 已标记: {new_path}")
                except Exception as e:
                    ui_window.append_log(f"标记文件失败 ({src_path}): {e}")

        ui_window.set_status("✓ 处理完成", "green")
        ui_window.append_log("-" * 40)
        
        # 重置拖拽区
        ui_window.reset_ui()
        
    except Exception as e:
        raise e

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow(process_callback)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
