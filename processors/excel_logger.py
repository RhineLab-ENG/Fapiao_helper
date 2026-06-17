import os
from openpyxl import Workbook, load_workbook

def log_to_excel(target_folder, invoice_data):
    """
    将提取到的发票数据写入 Excel 文件。
    如果存在则追加，不存在则新建。
    """
    excel_path = os.path.join(target_folder, "发票汇总.xlsx")
    
    date = invoice_data.get('date', '')
    amount = invoice_data.get('total_amount', '')
    item_name = invoice_data.get('item_name', '')
    invoice_number = invoice_data.get('invoice_number', '')

    row_data = [date, amount, item_name, invoice_number]

    if os.path.exists(excel_path):
        try:
            wb = load_workbook(excel_path)
            ws = wb.active
            ws.append(row_data)
            wb.save(excel_path)
        except Exception as e:
            raise ValueError(f"追加写入 Excel 失败 (请检查文件是否被占用): {e}")
    else:
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "发票记录"
            # 写入表头
            ws.append(["开票日期", "金额", "第一项品名", "发票号码"])
            # 写入数据
            ws.append(row_data)
            wb.save(excel_path)
        except Exception as e:
            raise ValueError(f"新建 Excel 失败: {e}")

    return excel_path
