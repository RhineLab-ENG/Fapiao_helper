# 发票整理与重命名助手（Fapiao Helper）

一个基于 **PyQt6** 的桌面工具，用于批量整理电子发票：解析发票信息、核对订单金额、自动重命名文件并生成 Excel 汇总表。

## 功能特性

- 拖拽发票 PDF 自动提取：发票号码、开票日期、第一项品名、金额、买方/卖方名称
- 支持订单截图（JPG/PNG/BMP）OCR 金额识别（可开关）
- 支持淘宝导出的订单 PDF 金额提取（始终启用）
- 发票金额与订单实付款不一致时弹窗确认
- 自动复制并重命名发票与订单文件
- 自动生成/更新 `发票汇总.xlsx`，并维护底部合计行
- 处理完成后将源文件重命名为 `USED_原文件名`

## 运行环境

- Python 3.10+
- Windows（提供 `build.bat` 打包脚本）

安装依赖：

```bash
pip install -r requirements.txt
```

## 启动方式

```bash
python main.py
```

## 使用流程

1. 拖入左侧发票 PDF
2. 可选：拖入右侧订单截图或淘宝订单 PDF
3. 选择输出文件夹
4. 按需勾选：
   - **金额核对（OCR）**：仅影响图片 OCR；订单 PDF 不受影响
   - **多买方确认**：买方与已有记录不一致时提示确认
5. 点击“开始处理”

## 输出说明

### 1) 重命名文件

输出文件命名格式：

`<开票日期>-<金额>-<第一项品名>-发票/订单-<发票号码>.<扩展名>`

### 2) Excel 汇总

在输出目录生成/更新 `发票汇总.xlsx`，列如下：

- 开票日期
- 金额
- 第一项品名
- 发票号码
- 卖方名称
- 买方名称

底部自动生成汇总行：`合计 | 金额总和 | 共N张`

## 项目结构

```text
Fapiao_helper/
├─ main.py
├─ requirements.txt
├─ extractors/
│  ├─ pdf_parser.py
│  └─ image_parser.py
├─ processors/
│  ├─ file_manager.py
│  └─ excel_logger.py
└─ ui/
   └─ main_window.py
```

## 打包（Windows）

项目提供 `build.bat`，用于调用 PyInstaller 打包为单文件可执行程序：

```bat
build.bat
```
