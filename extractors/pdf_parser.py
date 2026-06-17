import pdfplumber
import re
import math

def parse_invoice(pdf_path):
    """
    解析发票 PDF，提取需要的字段
    返回字典: 
    {
        'invoice_number': '发票号码',
        'date': 'YYYYMMDD',
        'item_name': '第一项品名',
        'total_amount': '总金额'
    }
    """
    result = {
        'invoice_number': '',
        'date': '',
        'item_name': '',
        'total_amount': ''
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"
            
            # 1. 发票号码 (Invoice number)
            # 全电发票为20位，或者传统发票11位、10位等，也可能是跟在“发票号码：”后面的数字
            num_match = re.search(r"发票号码[:：]\s*(\d+)", text)
            if num_match:
                result['invoice_number'] = num_match.group(1)
            else:
                # 尝试其他常见格式
                num_match2 = re.search(r"No[:：]?\s*(\d{10,20})", text, re.IGNORECASE)
                if num_match2:
                    result['invoice_number'] = num_match2.group(1)

            # 2. 开票日期 (Date)
            date_match = re.search(r"开票日期[:：]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
            if date_match:
                year, month, day = date_match.groups()
                result['date'] = f"{year}{month.zfill(2)}{day.zfill(2)}"
            else:
                date_match2 = re.search(r"(\d{4})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{1,2})", text)
                if date_match2:
                    year, month, day = date_match2.groups()
                    result['date'] = f"{year}{month.zfill(2)}{day.zfill(2)}"

            # 3. 总金额 (Total amount) 价税合计
            amount_match = re.search(r"[价计（(]\s*小写\s*[)）]?\s*[¥￥]\s*([0-9.,]+)", text)
            if not amount_match:
                amount_match = re.search(r"小写[:：]?\s*[¥￥]\s*([0-9.,]+)", text)
            if not amount_match:
                amount_match = re.search(r"[价计（(]\s*小写\s*[)）]?\s*([0-9.,]+)", text)
            
            if amount_match:
                result['total_amount'] = amount_match.group(1).replace(',', '')

            # 4. 第一项品名 (First item name)
            # 通过全局文本直接使用正则匹配（能兼顾表格抽取错位的情况）
            name_match = re.search(r"\*[^\*]+\*[^\s]+", text)
            if name_match:
                clean_name = name_match.group(0).strip()
                result['item_name'] = clean_name[:15]
            
            # 如果上面正则没抓到，再尝试其他正则兜底方式
            if not result['item_name']:
                name_match = re.search(r"\*.*?\*.*?(?=\n|\s)", text)
                if name_match:
                    name_found = name_match.group(0).strip()
                    result['item_name'] = name_found[:15]

    except Exception as e:
        print(f"Error parsing PDF {pdf_path}: {e}")
        raise ValueError(f"解析发票失败: {e}")

    return result
