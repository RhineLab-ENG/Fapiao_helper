import cv2
import numpy as np
import re
from rapidocr_onnxruntime import RapidOCR

def extract_amount_from_image(img_path):
    try:
        # 使用 cv2 + numpy 读取中文路径
        image = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return None

        ocr = RapidOCR()
        result, _ = ocr(image)
        if not result or not isinstance(result, list):
            return None
        
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
            return None

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
            return None

        # 3. 排序取出"最右边"的那个块
        same_line_blocks.sort(key=lambda b: b['x_max'], reverse=True)
        rightmost_text = same_line_blocks[0]['text'].replace(' ', '')

        # 4. 只尝试从最右侧的黑字/数字中提取金额
        # 注意: 淘宝使用特殊字体，OCR可能会把 99.90 认成别的东西
        # 但我们严格只读最右侧，如果正则匹配不上，就返回 None，避免读到左侧的 "共减 22.21"
        match = re.search(r'\d+\.\d{1,2}', rightmost_text)
        if match:
            return match.group(0)

        # 兜底：如果右侧因为字体被识别成了乱码（没拿到金额），我们返回 None 以满足“只在成功识别时比较”的条件
        return None
    except Exception as e:
        print(f"Image parse error: {e}")
        return None