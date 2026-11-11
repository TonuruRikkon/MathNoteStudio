# -*- coding: utf-8 -*-
"""
PDF Builder: Generates HTML templates with MathJax SVG and converts to vector PDF via Chrome Headless.
"""

import os
import sys
import shutil
import subprocess
import time
from pathlib import Path

BASE_DIR = getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
MATHJAX_LOCAL_PATH = os.path.join(ASSETS_DIR, "mathjax_svg.js")


def find_browser_binary():
    """Finds Chrome, Chromium, or Microsoft Edge across Linux, Windows, and macOS."""
    candidates = [
        shutil.which("google-chrome-stable"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("msedge"),
        shutil.which("chrome"),
        # Windows standard paths (Chrome & built-in Microsoft Edge)
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        # macOS paths
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    raise FileNotFoundError(
        "Không tìm thấy trình duyệt Google Chrome hoặc Microsoft Edge để xuất PDF."
    )


class PDFBuilder:
    @staticmethod
    def build_solution_html(cards_data, doc_title, subtitle=""):
        mathjax_src = Path(MATHJAX_LOCAL_PATH).as_uri() if os.path.exists(MATHJAX_LOCAL_PATH) else "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"
        
        cards_html = []
        for c in cards_data:
            cid = c.get("id", "")
            title = c.get("title", "")
            prob = c.get("problem", "")
            sol = c.get("solution_html", "")
            img_b64 = c.get("image", "")
            
            img_tag = f'<div class="img-container"><img src="{img_b64}" alt="Hình minh họa Bài {cid}"></div>' if img_b64 else ""
            
            card = f"""
<div class="card">
  <div class="card-header">
    <span class="card-badge">Bài {cid}</span>
    <span class="card-title-text">{title}</span>
  </div>
  <div class="problem-box">
    <div class="problem-label">Đề bài:</div>
    <div>{prob}</div>
  </div>
  {img_tag}
  <div class="solution-box">
    <div class="solution-label">✓ Lời giải chi tiết:</div>
    {sol}
  </div>
</div>
"""
            cards_html.append(card)

        html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>{doc_title} - Lời Giải Chi Tiết</title>
<script>
window.MathJax = {{
  tex: {{
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
  }},
  options: {{ enableAssistiveMml: false }},
  svg: {{ fontCache: 'local' }}
}};
</script>
<script src="{mathjax_src}"></script>
<style>
  @page {{
    size: A4 portrait;
    margin: 14mm 14mm 14mm 14mm;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Liberation Sans", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    background: #ffffff;
    margin: 0;
    padding: 0;
    line-height: 1.6;
    font-size: 10.5pt;
  }}
  .doc-header {{
    text-align: center;
    border-bottom: 2.5px solid #1e40af;
    padding-bottom: 14px;
    margin-bottom: 22px;
  }}
  .doc-univ {{
    font-size: 10pt;
    font-weight: 700;
    color: #475569;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 4px;
  }}
  .doc-title {{
    font-size: 18pt;
    font-weight: 800;
    color: #1e3a8a;
    margin: 0 0 6px 0;
  }}
  .doc-subtitle {{
    font-size: 10.5pt;
    color: #047857;
    font-weight: 600;
    margin: 0;
  }}
  .card {{
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 14px 18px 16px 18px;
    margin-bottom: 20px;
    background: #ffffff;
    page-break-inside: avoid;
    break-inside: avoid;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
  }}
  .card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1.5px solid #e2e8f0;
    padding-bottom: 8px;
    margin-bottom: 10px;
  }}
  .card-badge {{
    background: #1e40af;
    color: #ffffff;
    font-weight: 700;
    font-size: 10.5pt;
    padding: 3px 10px;
    border-radius: 4px;
  }}
  .card-title-text {{
    font-size: 11.5pt;
    font-weight: 700;
    color: #1e293b;
  }}
  .problem-box {{
    background: #f8fafc;
    border-left: 3.5px solid #3b82f6;
    padding: 10px 14px;
    border-radius: 4px;
    margin-bottom: 12px;
    font-size: 10.5pt;
    color: #0f172a;
  }}
  .problem-label {{
    font-weight: 700;
    color: #1d4ed8;
    margin-bottom: 4px;
    text-transform: uppercase;
    font-size: 9pt;
  }}
  .img-container {{
    text-align: center;
    margin: 12px 0;
  }}
  .img-container img {{
    max-height: 180px;
    max-width: 90%;
    border-radius: 6px;
    border: 1px solid #e2e8f0;
  }}
  .solution-box {{
    padding-top: 4px;
    font-size: 10.5pt;
  }}
  .solution-label {{
    font-weight: 700;
    color: #047857;
    margin-bottom: 6px;
    font-size: 10pt;
  }}
  .sol-p {{ margin: 5px 0; }}
  .sol-list {{ margin: 4px 0 6px 20px; padding: 0; }}
  .sol-list li {{ margin-bottom: 4px; }}
  strong {{ color: #0f172a; }}
</style>
</head>
<body>
<div class="doc-header">
  <div class="doc-univ">Tài liệu học tập & Giảng dạy • Bộ môn Toán</div>
  <h1 class="doc-title">{doc_title}</h1>
  <p class="doc-subtitle">{subtitle if subtitle else "Hướng dẫn giải chi tiết toàn bộ bài tập • Định dạng Vector LaTeX"}</p>
</div>
{"\n".join(cards_html)}
</body>
</html>"""
        return html

    @staticmethod
    def build_note_html(cards_data, doc_title, line_height=27, line_style="dashed", default_lines=10, include_hints=True):
        mathjax_src = Path(MATHJAX_LOCAL_PATH).as_uri() if os.path.exists(MATHJAX_LOCAL_PATH) else "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"
        border_style = f"1.2px {line_style} #cbd5e1"

        cards_html = []
        for c in cards_data:
            cid = c.get("id", "")
            title = c.get("title", "")
            prob = c.get("problem", "")
            concept = c.get("concept", "")
            hint = c.get("hint", "")
            n_lines = c.get("num_lines", default_lines)
            img_b64 = c.get("image", "")

            img_tag = f'<div class="img-container"><img src="{img_b64}" alt="Hình minh họa Bài {cid}"></div>' if img_b64 else ""
            lines_divs = '\n'.join([f'    <div class="dotted-line" style="height: {line_height}px; border-bottom: {border_style};"></div>'] * n_lines)

            # Conditional hint container
            hint_html = ""
            if include_hints and (concept or hint):
                hint_html = f"""
  <div class="hint-container">
    <div class="hint-title">💡 Khái niệm then chốt & Định hướng cách làm:</div>
    {concept}
    {hint}
  </div>
"""

            card = f"""
<div class="card">
  <div class="card-header">
    <span class="badge">Câu {cid}</span>
    <span class="card-title-text">{title}</span>
  </div>
  <div class="problem-content">{prob}</div>
  {img_tag}
  {hint_html}
  <div class="work-section">
    <div class="work-header">
      <span>✍️ Bài làm & Ghi chú (Dành cho Bảng vẽ):</span>
      <span>{n_lines} dòng kẻ</span>
    </div>
{lines_divs}
  </div>
</div>
"""
            cards_html.append(card)

        html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>{doc_title} - Vở Ghi Chú Bảng Vẽ</title>
<script>
window.MathJax = {{
  tex: {{
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
  }},
  options: {{ enableAssistiveMml: false }},
  svg: {{ fontCache: 'local' }}
}};
</script>
<script src="{mathjax_src}"></script>
<style>
  @page {{
    size: A4 portrait;
    margin: 12mm 12mm 12mm 12mm;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Liberation Sans", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    background: #ffffff;
    margin: 0;
    padding: 0;
    line-height: 1.55;
    font-size: 11pt;
  }}
  .doc-header {{
    border-bottom: 2px solid #2563eb;
    padding-bottom: 12px;
    margin-bottom: 18px;
  }}
  .header-top {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }}
  .title-group {{ flex: 1; }}
  .doc-title {{
    font-size: 17pt;
    font-weight: 800;
    color: #1e3a8a;
    margin: 0 0 4px 0;
  }}
  .doc-subtitle {{
    font-size: 10pt;
    color: #475569;
    margin: 0;
  }}
  .student-box {{
    border: 1px dashed #94a3b8;
    background: #f8fafc;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 9.5pt;
    color: #334155;
    min-width: 250px;
  }}
  .student-row {{ margin: 3px 0; }}
  .card {{
    border: 1.2px solid #cbd5e1;
    border-radius: 8px;
    padding: 12px 16px 14px 16px;
    margin-bottom: 18px;
    background: #ffffff;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  .card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    border-bottom: 1px solid #f1f5f9;
    padding-bottom: 6px;
  }}
  .badge {{
    background: #2563eb;
    color: #ffffff;
    font-weight: 700;
    font-size: 10.5pt;
    padding: 3px 9px;
    border-radius: 4px;
  }}
  .card-title-text {{
    font-size: 11pt;
    font-weight: 700;
    color: #0f172a;
  }}
  .problem-content {{
    font-size: 11pt;
    color: #0f172a;
    margin-bottom: 10px;
    line-height: 1.6;
  }}
  .hint-container {{
    background: #f0fdfa;
    border-left: 3.5px solid #0d9488;
    border-top: 1px solid #ccfbf1;
    border-right: 1px solid #ccfbf1;
    border-bottom: 1px solid #ccfbf1;
    padding: 8px 12px;
    border-radius: 5px;
    margin-bottom: 12px;
    font-size: 10pt;
    color: #134e4a;
  }}
  .hint-title {{
    font-weight: 700;
    color: #0f766e;
    margin-bottom: 4px;
    font-size: 10pt;
  }}
  .hint-container ul {{
    margin: 2px 0 2px 18px;
    padding: 0;
  }}
  .hint-container li {{
    margin-bottom: 3px;
    line-height: 1.45;
  }}
  .work-section {{ margin-top: 8px; }}
  .work-header {{
    font-size: 9pt;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 2px;
    display: flex;
    justify-content: space-between;
  }}
  .img-container {{
    text-align: center;
    margin: 8px 0;
  }}
  .img-container img {{
    max-height: 160px;
    max-width: 85%;
    border-radius: 4px;
    border: 1px solid #e2e8f0;
  }}
</style>
</head>
<body>
<div class="doc-header">
  <div class="header-top">
    <div class="title-group">
      <h1 class="doc-title">{doc_title}</h1>
      <p class="doc-subtitle">Phiếu Bài Tập & Ghi Chú Trực Tiếp (Bản chuyên dụng cho Bảng Vẽ - Drawing Tablet)</p>
    </div>
    <div class="student-box">
      <div class="student-row"><strong>Họ và tên:</strong> ........................................</div>
      <div class="student-row"><strong>Lớp/Khóa:</strong> ....................................</div>
      <div class="student-row"><strong>Ngày học:</strong> ..... / ..... / 2026</div>
    </div>
  </div>
</div>
{"\n".join(cards_html)}
</body>
</html>"""
        return html

    @staticmethod
    def render_pdf_from_html(html_path, pdf_path, timeout=180):
        """Compiles HTML to PDF via Chrome / Edge Headless (Cross-platform: Linux, Windows, macOS)."""
        browser_bin = find_browser_binary()
        html_uri = Path(os.path.abspath(html_path)).as_uri()
        cmd = [
            browser_bin,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--allow-file-access-from-files",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=35000",
            f"--print-to-pdf={os.path.abspath(pdf_path)}",
            html_uri
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if os.path.exists(pdf_path):
            return True, os.path.getsize(pdf_path)
        else:
            return False, res.stderr
