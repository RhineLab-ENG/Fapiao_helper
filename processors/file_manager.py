import os
import shutil

def format_filename(invoice_data, file_type):
    """
    格式化新文件名
    :param invoice_data: dict containing date, total_amount(分), item_name, invoice_number
    :param file_type: '发票' or '订单'
    :return: 格式化后的文件名，不包含扩展名
    """
    date = invoice_data.get('date', '未知日期')
    amount_cents = invoice_data.get('total_amount', 0)
    amount = f"{amount_cents / 100:.2f}"
    item_name = invoice_data.get('item_name', '未知品名')
    invoice_number = invoice_data.get('invoice_number', '未知号码')

    # <开票日期>-<金额>-<第一项品名的前几个字>-发票/订单-<发票号码>
    name = f"{date}-{amount}-{item_name}-{file_type}-{invoice_number}"
    
    # 去除Windows文件名不支持的字符
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '')
        
    return name

def process_files(pdf_path, image_path, target_folder, invoice_data):
    """
    复制并重命名文件到目标文件夹
    """
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

    results = {}

    # 1. 处理 PDF 发票
    if pdf_path and os.path.exists(pdf_path):
        ext = os.path.splitext(pdf_path)[1]
        new_pdf_name = format_filename(invoice_data, '发票') + ext
        new_pdf_path = os.path.join(target_folder, new_pdf_name)
        shutil.copy2(pdf_path, new_pdf_path)
        results['pdf'] = new_pdf_path

    # 2. 处理截图
    if image_path and os.path.exists(image_path):
        ext = os.path.splitext(image_path)[1]
        new_img_name = format_filename(invoice_data, '订单') + ext
        new_img_path = os.path.join(target_folder, new_img_name)
        shutil.copy2(image_path, new_img_path)
        results['image'] = new_img_path

    return results
