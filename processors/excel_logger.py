import os
from openpyxl import Workbook, load_workbook

HEADERS = ["开票日期", "金额", "第一项品名", "发票号码", "卖方名称", "买方名称"]
SUMMARY_MARKER = "合计"  # 汇总行 A 列标记


def _cents_to_yuan(cents):
    if cents == 0:
        return '0.00'
    return f"{cents / 100:.2f}"


def _read_data_rows(ws):
    """读取工作表中所有数据行（跳过表头和汇总行），返回 (rows, 金额合计_分)"""
    rows = []
    total_cents = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        # 跳过空行和汇总行
        if row[0] is None or str(row[0]).strip() == '' or str(row[0]) == SUMMARY_MARKER:
            continue
        rows.append(row)
        # B 列是金额（元字符串）
        try:
            total_cents += int(round(float(str(row[1])) * 100))
        except (ValueError, TypeError, IndexError):
            pass
    return rows, total_cents


def log_to_excel(target_folder, invoice_data):
    """
    将发票数据写入 Excel，末尾自动生成合计行。
    """
    excel_path = os.path.join(target_folder, "发票汇总.xlsx")
    
    date = invoice_data.get('date', '')
    amount_cents = invoice_data.get('total_amount', 0)
    amount = _cents_to_yuan(amount_cents)
    item_name = invoice_data.get('item_name', '')
    invoice_number = invoice_data.get('invoice_number', '')
    seller_name = invoice_data.get('seller_name', '')
    buyer_name = invoice_data.get('buyer_name', '')

    new_row = [date, amount, item_name, invoice_number, seller_name, buyer_name]

    if os.path.exists(excel_path):
        try:
            wb = load_workbook(excel_path)
            ws = wb.active
            # 读取现有数据行
            existing_rows, existing_total = _read_data_rows(ws)
            # 追加新行
            existing_rows.append(tuple(new_row))
            existing_total += amount_cents
            # 重写工作表
            ws.delete_rows(1, ws.max_row)
            ws.append(HEADERS)
            for r in existing_rows:
                ws.append(list(r))
            # 汇总行
            ws.append([SUMMARY_MARKER, _cents_to_yuan(existing_total), f"共{len(existing_rows)}张", "", "", ""])
            wb.save(excel_path)
        except Exception as e:
            raise ValueError(f"追加写入 Excel 失败 (请检查文件是否被占用): {e}")
    else:
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "发票记录"
            ws.append(HEADERS)
            ws.append(new_row)
            # 汇总行
            ws.append([SUMMARY_MARKER, amount, "共1张", "", "", ""])
            wb.save(excel_path)
        except Exception as e:
            raise ValueError(f"新建 Excel 失败: {e}")

    return excel_path
