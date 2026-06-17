import sys
from PyQt6.QtWidgets import QApplication, QMessageBox
from ui.main_window import MainWindow
from extractors.pdf_parser import parse_invoice
from processors.file_manager import process_files
from processors.excel_logger import log_to_excel
from extractors.image_parser import extract_amount_from_image

def process_callback(pdf_path, img_path, target_folder, ui_window, pre_extracted_amount=None):
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

        # 2. 如果提供了截图，进行金额比对
        if img_path:
            if pre_extracted_amount:
                # 使用后台线程已提取的金额
                img_amount = pre_extracted_amount
            else:
                # 现场提取金额（如果没有后台预处理）
                ui_window.append_log("正在解析订单截图以核对金额...")
                img_amount = extract_amount_from_image(img_path)
                if img_amount:
                    ui_window.append_log(f"识别到截图实付款金额: ￥{img_amount}")
            if img_amount:
                pdf_amount = invoice_data.get('total_amount', '')
                try:
                    pdf_v = float(pdf_amount)
                    img_v = float(img_amount)
                    if abs(pdf_v - img_v) > 0.01:
                        reply = QMessageBox.warning(
                            ui_window,
                            "金额不符",
                            f"注意：发票总金额 ({pdf_v:.2f}) 与订单截图实付款 ({img_v:.2f}) 不一致！\n确认要继续处理吗？",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                            QMessageBox.StandardButton.No
                        )
                        if reply == QMessageBox.StandardButton.No:
                            ui_window.append_log("操作已取消。")
                            return
                except ValueError:
                    pass
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

        QMessageBox.information(ui_window, "成功", "处理完成！")
        ui_window.append_log("处理完成！\n" + "-"*40)
        
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
