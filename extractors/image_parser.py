import cv2
import numpy as np
import re
from rapidocr_onnxruntime import RapidOCR

def extract_amount_from_image(img_path):
    """返回整数「分」，未识别到金额时返回 0"""
    try:
        # 使用 cv2 + numpy 读取中文路径
        image = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return 0

        ocr = RapidOCR()
        result, _ = ocr(image)
        if not result or not isinstance(result, list):
            return 0
        
        target_y_center = None
        
        # 1. 找到 "实付款" 的纵坐标中心
        for item in result:
            box, text, score = item
            if not isinstance(text, str):
                continue
            text_clean = text.replace(' ', '')
            if '实付款' in text_clean:
                y_coords = [p[1] for p in box]
                target_y_center = sum(y_coords) / 4.0
                break
        
        if target_y_center is None:
            return 0

        # 2. 找到同一水平线（y_center 相近）的所有块
        same_line_blocks = []
        for item in result:
            box, text, score = item
            if not isinstance(text, str):
                continue
            
            y_coords = [p[1] for p in box]
            y_center = sum(y_coords) / 4.0
            height = max(y_coords) - min(y_coords)

            if abs(y_center - target_y_center) < max(height, 20):
                x_max = max(p[0] for p in box)
                same_line_blocks.append({'x_max': x_max, 'text': text})

        if not same_line_blocks:
            return 0

        # 3. 排序取出"最右边"的那个块
        same_line_blocks.sort(key=lambda b: b['x_max'], reverse=True)
        rightmost_text = same_line_blocks[0]['text'].replace(' ', '')

        # 4. 只尝试从最右侧的黑字/数字中提取金额
        match = re.search(r'\d+\.\d{1,2}', rightmost_text)
        if match:
            yuan_str = match.group(0)
            # 转为整数「分」存储，避免浮点精度问题
            return int(round(float(yuan_str) * 100))

        # 未识别到金额
        return 0
    except Exception as e:
        print(f"Image parse error: {e}")
        return 0


def extract_amount_from_order_pdf(pdf_path):
    """从淘宝/天猫导出的订单详情 PDF 中提取「实付款」金额，返回整数「分」"""
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            text = "".join(page.extract_text() or "" for page in pdf.pages)
        
        # 匹配 "实付款  ￥35.98" 或 "实付款 ¥35.98"
        match = re.search(r'实付款\s*[¥￥]\s*(\d+\.?\d{0,2})', text)
        if match:
            yuan_str = match.group(1)
            return int(round(float(yuan_str) * 100))
        return 0
    except Exception as e:
        print(f"Order PDF parse error: {e}")
        return 0