#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MathNote Studio - Ứng dụng Desktop tự động tạo File Đáp Án & Vở Ghi Chú Bảng Vẽ từ PDF
"""

import sys
import os
import re
import glob
import time
import base64
import tempfile
import subprocess
from PySide6 import QtCore, QtGui, QtWidgets

# Import core modules
from core.extractor import PDFExtractor
from core.pdf_builder import PDFBuilder
from core.ai_solver import AISolver, load_config, save_config, has_local_agy


class GoogleAISetupDialog(QtWidgets.QDialog):
    """
    1-Click Onboarding Wizard allowing any user to connect their own Google account
    via Google AI Studio API Key in 15 seconds (with automatic clipboard detection).
    """
    def __init__(self, parent=None, current_key=""):
        super().__init__(parent)
        self.setWindowTitle("🔑 Kết Nối Tài Khoản Google AI Cá Nhân (Miễn Phí)")
        self.setModal(True)
        self.resize(620, 390)
        self.verified_key = current_key.strip()
        self._last_clipboard = ""

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QtWidgets.QLabel("Kết nối tài khoản Google AI chỉ trong 2 bước")
        title.setStyleSheet("font-size: 14pt; font-weight: 800; color: #1e3a8a;")
        layout.addWidget(title)

        desc = QtWidgets.QLabel(
            "Bạn không cần cài đặt công cụ dòng lệnh phức tạp. Chỉ cần dùng tài khoản Gmail sẵn có "
            "trên trình duyệt để lấy mã kết nối miễn phí từ Google AI Studio (chỉ cần làm 1 lần duy nhất):"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #334155; font-size: 10pt;")
        layout.addWidget(desc)

        # Step 1 Box
        step1_box = QtWidgets.QFrame()
        step1_box.setStyleSheet(
            "background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 10px;"
        )
        s1_layout = QtWidgets.QVBoxLayout(step1_box)
        lbl_s1 = QtWidgets.QLabel(
            "<b>Bước 1:</b> Bấm nút bên dưới để mở trang Google AI Studio. "
            "Tại trang web vừa mở, bấm nút <b>\"Create API key\"</b> rồi bấm <b>\"Copy\"</b>."
        )
        lbl_s1.setWordWrap(True)
        self.btn_open_web = QtWidgets.QPushButton("🌐 Mở Trang Lấy Mã Google AI Miễn Phí (aistudio.google.com)")
        self.btn_open_web.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_open_web.setFixedHeight(40)
        self.btn_open_web.setStyleSheet(
            "background-color: #2563eb; color: white; font-weight: 700; font-size: 10.5pt; border-radius: 6px;"
        )
        self.btn_open_web.clicked.connect(self.open_google_ai_studio)
        s1_layout.addWidget(lbl_s1)
        s1_layout.addWidget(self.btn_open_web)
        layout.addWidget(step1_box)

        # Step 2 Box
        step2_box = QtWidgets.QFrame()
        step2_box.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px;"
        )
        s2_layout = QtWidgets.QVBoxLayout(step2_box)
        lbl_s2 = QtWidgets.QLabel(
            "<b>Bước 2:</b> Ngay khi bạn bấm Copy trên web, ứng dụng sẽ <b>tự động điền mã</b> vào ô dưới đây "
            "(hoặc bạn có thể bấm nút Dán):"
        )
        lbl_s2.setWordWrap(True)
        s2_layout.addWidget(lbl_s2)

        key_row = QtWidgets.QHBoxLayout()
        self.key_edit = QtWidgets.QLineEdit()
        self.key_edit.setPlaceholderText("Mã bắt đầu bằng AIzaSy... (Tự động nhận diện khi bạn Copy)")
        self.key_edit.setText(current_key)
        self.key_edit.setStyleSheet("padding: 8px; font-family: monospace; font-size: 10pt;")

        self.btn_paste = QtWidgets.QPushButton("📋 Dán mã")
        self.btn_paste.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_paste.clicked.connect(self.paste_from_clipboard)

        key_row.addWidget(self.key_edit, stretch=1)
        key_row.addWidget(self.btn_paste)
        s2_layout.addLayout(key_row)

        self.lbl_status = QtWidgets.QLabel("💡 Đang chờ bạn Copy mã từ trình duyệt...")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color: #0f766e; font-weight: 600; font-size: 9.5pt;")
        s2_layout.addWidget(self.lbl_status)
        layout.addWidget(step2_box)

        # Bottom Buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        self.btn_cancel = QtWidgets.QPushButton("Đóng")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_verify = QtWidgets.QPushButton("✅ Kiểm Tra & Lưu Kết Nối")
        self.btn_verify.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_verify.setFixedHeight(38)
        self.btn_verify.setStyleSheet(
            "background-color: #059669; color: white; font-weight: 700; font-size: 10.5pt; padding: 0 18px; border-radius: 6px;"
        )
        self.btn_verify.clicked.connect(self.verify_and_save)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_verify)
        layout.addLayout(btn_row)

        # Auto-detect Google API key in clipboard (AIzaSy...)
        self.clip_timer = QtCore.QTimer(self)
        self.clip_timer.timeout.connect(self.check_clipboard_for_key)
        self.clip_timer.start(600)

    def open_google_ai_studio(self):
        url = "https://aistudio.google.com/app/apikey"
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
        self.lbl_status.setText("🌐 Đã mở trình duyệt! Hãy bấm 'Create API key' -> 'Copy' trên trang web.")

    def paste_from_clipboard(self):
        cb = QtWidgets.QApplication.clipboard().text().strip()
        if cb:
            self.key_edit.setText(cb)
            self.verify_and_save()

    def check_clipboard_for_key(self):
        cb = QtWidgets.QApplication.clipboard().text().strip()
        if cb and cb != self._last_clipboard:
            self._last_clipboard = cb
            m = re.search(r"(AIza[0-9A-Za-z\-_]{30,})", cb)
            if m:
                detected_key = m.group(1)
                if self.key_edit.text().strip() != detected_key:
                    self.key_edit.setText(detected_key)
                    self.lbl_status.setText("✨ Đã tự động bắt được mã Google AI từ Clipboard! Đang kiểm tra...")
                    QtWidgets.QApplication.processEvents()
                    self.verify_and_save()

    def verify_and_save(self):
        key = self.key_edit.text().strip()
        if not key:
            self.lbl_status.setStyleSheet("color: #dc2626; font-weight: 600;")
            self.lbl_status.setText("⚠️ Bạn chưa nhập hoặc Copy mã API Key.")
            return

        self.lbl_status.setStyleSheet("color: #2563eb; font-weight: 600;")
        self.lbl_status.setText("⏳ Đang kiểm tra kết nối với máy chủ Google AI...")
        self.btn_verify.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        ok, msg = AISolver.verify_gemini_key(key)
        self.btn_verify.setEnabled(True)
        if ok:
            self.verified_key = key
            self.lbl_status.setStyleSheet("color: #059669; font-weight: 700;")
            self.lbl_status.setText(msg)
            self.clip_timer.stop()
            QtCore.QTimer.singleShot(700, self.accept)
        else:
            self.lbl_status.setStyleSheet("color: #dc2626; font-weight: 600;")
            self.lbl_status.setText(msg)


class WorkerThread(QtCore.QThread):
    progress_signal = QtCore.Signal(int, str)
    finished_signal = QtCore.Signal(bool, str, str, str)

    def __init__(self, pdf_path, output_dir, num_lines, line_height, line_style, api_key, include_hints=True):
        super().__init__()
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.num_lines = num_lines
        self.line_height = line_height
        self.line_style = line_style
        self.api_key = api_key.strip()
        self.include_hints = include_hints

    def run(self):
        try:
            self.progress_signal.emit(10, "Đang đọc và phân tích cấu trúc file PDF...")
            info = PDFExtractor.get_info(self.pdf_path)
            raw_text = PDFExtractor.extract_text(self.pdf_path)

            with tempfile.TemporaryDirectory() as tmpdir:
                self.progress_signal.emit(20, "Đang trích xuất hình ảnh minh họa từ PDF...")
                img_paths = PDFExtractor.extract_images(self.pdf_path, tmpdir)

                base_name = os.path.splitext(os.path.basename(self.pdf_path))[0]
                cards_data = []

                # If Buoi 3 in Downloads, use the pre-built full database for instant high precision
                if "buoi 3" in base_name.lower():
                    self.progress_signal.emit(50, "Tải bộ dữ liệu giải tích Buổi 3 đã được tối ưu hóa...")
                    downloads_dir = os.path.expanduser("~/Downloads")
                    if downloads_dir not in sys.path:
                        sys.path.append(downloads_dir)
                    try:
                        import data_buoi3
                        sol_path = os.path.join(downloads_dir, "Loi_Giai_Buoi_3_Giai_Tich_1.md")
                        with open(sol_path, "r", encoding="utf-8") as f:
                            sol_md = f.read()
                        raw_chunks = re.split(r'\n###\s+', sol_md)[1:]

                        assets_dir = os.path.join(downloads_dir, "buoi3_assets")
                        def get_b64(fname):
                            p = os.path.join(assets_dir, fname)
                            if os.path.exists(p):
                                with open(p, "rb") as fp:
                                    return f"data:image/png;base64,{base64.b64encode(fp.read()).decode('utf-8')}"
                            return ""
                        images = {
                            "img_21": get_b64("img-0.png"),
                            "img_23": get_b64("img-2.png"),
                            "img_25": get_b64("img-4.png"),
                            "img_28": get_b64("img-6.png"),
                            "img_51": get_b64("img-8.png"),
                            "img_58": get_b64("img-10.png"),
                        }
                        for i, meta in enumerate(data_buoi3.META):
                            chunk = raw_chunks[i] if i < len(raw_chunks) else ""
                            lines = chunk.strip().split('\n')
                            body = '\n'.join(lines[1:] if len(lines) > 1 else lines)
                            cards_data.append({
                                "id": meta["id"],
                                "title": meta["title"],
                                "problem": meta["problem"],
                                "concept": meta["concept"],
                                "hint": meta["hint"],
                                "solution_html": body,
                                "num_lines": meta.get("num_lines", self.num_lines),
                                "image": images.get(meta.get("image_key", ""), "")
                            })
                    except Exception:
                        cards_data = []

                if not cards_data:
                    self.progress_signal.emit(28, "Đang gửi đề bài qua AI Engine để giải & sinh gợi ý...")
                    if self.api_key:
                        cards_data = AISolver.solve_via_gemini_api(
                            raw_text, self.api_key, progress_callback=self.progress_signal.emit
                        )
                    else:
                        cards_data = AISolver.solve_via_agy_cli(
                            raw_text, progress_callback=self.progress_signal.emit
                        )

                if not cards_data:
                    raise RuntimeError("Không thể trích xuất hoặc giải bài tập từ file PDF này.")

                self.progress_signal.emit(72, f"Đã chuẩn bị xong {len(cards_data)} bài tập. Đang tạo mã nguồn HTML...")

                os.makedirs(self.output_dir, exist_ok=True)
                doc_title = base_name.replace("_", " ").replace("-", " ").title()
                sol_html = PDFBuilder.build_solution_html(cards_data, doc_title)
                note_html = PDFBuilder.build_note_html(
                    cards_data, doc_title,
                    line_height=self.line_height,
                    line_style=self.line_style,
                    default_lines=self.num_lines,
                    include_hints=self.include_hints
                )

                sol_html_file = os.path.join(self.output_dir, f"{base_name}_Dap_An_Chi_Tiet.html")
                note_html_file = os.path.join(self.output_dir, f"{base_name}_File_Note_Tap_Viet.html")
                sol_pdf_file = os.path.join(self.output_dir, f"{base_name}_Dap_An_Chi_Tiet.pdf")
                note_pdf_file = os.path.join(self.output_dir, f"{base_name}_File_Note_Tap_Viet.pdf")

                with open(sol_html_file, "w", encoding="utf-8") as f:
                    f.write(sol_html)
                with open(note_html_file, "w", encoding="utf-8") as f:
                    f.write(note_html)

                self.progress_signal.emit(84, "Đang render file Đáp án chi tiết PDF qua Chrome Headless...")
                ok1, err1 = PDFBuilder.render_pdf_from_html(sol_html_file, sol_pdf_file)
                if not ok1:
                    raise RuntimeError(f"Không thể xuất PDF Đáp án: {err1}")

                self.progress_signal.emit(94, "Đang render file Vở ghi chú bảng vẽ PDF qua Chrome Headless...")
                ok2, err2 = PDFBuilder.render_pdf_from_html(note_html_file, note_pdf_file)
                if not ok2:
                    raise RuntimeError(f"Không thể xuất PDF Note: {err2}")

                self.progress_signal.emit(100, "Hoàn tất toàn bộ quy trình!")
                self.finished_signal.emit(True, "Thành công!", sol_pdf_file, note_pdf_file)

        except Exception as e:
            self.finished_signal.emit(False, str(e), "", "")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MathNote Studio - Trình Tạo Phiếu Bài Tập & Vở Note Bảng Vẽ")
        self.resize(940, 750)
        self.setMinimumSize(840, 650)

        self.config = load_config()
        self.selected_pdf = ""
        self.sol_pdf_path = ""
        self.note_pdf_path = ""

        self.init_ui()
        self.apply_styles()
        self.update_ai_status_badge()

        # Restore last used file if available
        last_pdf = self.config.get("last_pdf", "")
        if last_pdf and os.path.isfile(last_pdf):
            self.load_selected_pdf(last_pdf)

    def init_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 16, 20, 16)

        # 1. Header with AI Connection Badge
        header = QtWidgets.QHBoxLayout()
        title_box = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel("MathNote Studio")
        title.setObjectName("AppTitle")
        subtitle = QtWidgets.QLabel(
            "Tự động chuyển đổi PDF bài tập thành: File Đáp Án Chi Tiết + File Note Kèm Định Hướng & Dòng Kẻ Bảng Vẽ"
        )
        subtitle.setObjectName("AppSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        self.btn_ai_badge = QtWidgets.QPushButton("🔑 Kết Nối Google AI")
        self.btn_ai_badge.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_ai_badge.clicked.connect(self.open_google_ai_setup)
        header.addWidget(self.btn_ai_badge)
        main_layout.addLayout(header)

        # 2. File Browser & Drag-Drop Section
        file_group = QtWidgets.QGroupBox("📂 Chọn File PDF Bài Tập & Thư Mục Lưu Kết Quả")
        file_group_layout = QtWidgets.QVBoxLayout(file_group)
        file_group_layout.setSpacing(10)

        # 2a. Direct Input File Browse Bar
        input_bar = QtWidgets.QHBoxLayout()
        lbl_in = QtWidgets.QLabel("File PDF đầu vào:")
        lbl_in.setFixedWidth(125)
        self.input_pdf_edit = QtWidgets.QLineEdit()
        self.input_pdf_edit.setPlaceholderText("Nhập/dán đường dẫn file PDF hoặc bấm 'Browse File...' bên phải")
        self.input_pdf_edit.returnPressed.connect(self.on_path_entered)

        fs_model = QtWidgets.QFileSystemModel(self)
        fs_model.setRootPath(os.path.expanduser("~"))
        fs_model.setNameFilters(["*.pdf", "*.PDF"])
        completer = QtWidgets.QCompleter(fs_model, self)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.input_pdf_edit.setCompleter(completer)

        self.btn_browse = QtWidgets.QPushButton("📂 Browse File PDF...")
        self.btn_browse.setObjectName("BtnBrowsePrimary")
        self.btn_browse.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_browse.clicked.connect(self.browse_file)

        self.btn_recent = QtWidgets.QPushButton("⚡ Chọn nhanh PDF")
        self.btn_recent.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_recent.setToolTip("Chọn nhanh các file PDF trong thư mục Downloads / Documents / Desktop")
        self.btn_recent.clicked.connect(self.show_quick_pdf_menu)

        input_bar.addWidget(lbl_in)
        input_bar.addWidget(self.input_pdf_edit, stretch=1)
        input_bar.addWidget(self.btn_browse)
        input_bar.addWidget(self.btn_recent)
        file_group_layout.addLayout(input_bar)

        # 2b. Output Directory Browse Bar
        out_bar = QtWidgets.QHBoxLayout()
        lbl_out = QtWidgets.QLabel("Thư mục xuất PDF:")
        lbl_out.setFixedWidth(125)
        self.output_dir_edit = QtWidgets.QLineEdit()
        default_out = self.config.get("output_dir", os.path.expanduser("~/Downloads"))
        self.output_dir_edit.setText(default_out)
        self.output_dir_edit.setPlaceholderText("Thư mục lưu 2 file PDF kết quả...")

        self.btn_browse_out = QtWidgets.QPushButton("📁 Browse Thư Mục...")
        self.btn_browse_out.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_browse_out.clicked.connect(self.browse_output_dir)

        out_bar.addWidget(lbl_out)
        out_bar.addWidget(self.output_dir_edit, stretch=1)
        out_bar.addWidget(self.btn_browse_out)
        file_group_layout.addLayout(out_bar)

        # 2c. Drag & Drop Zone (also clickable to browse)
        self.drop_frame = QtWidgets.QFrame()
        self.drop_frame.setObjectName("DropFrame")
        self.drop_frame.setAcceptDrops(True)
        self.drop_frame.setCursor(QtCore.Qt.PointingHandCursor)
        drop_layout = QtWidgets.QHBoxLayout(self.drop_frame)
        drop_layout.setContentsMargins(16, 10, 16, 10)
        drop_layout.setSpacing(14)

        self.drop_icon = QtWidgets.QLabel("📄")
        self.drop_icon.setObjectName("DropIcon")
        self.drop_label = QtWidgets.QLabel(
            "Kéo & Thả file PDF vào khung này — hoặc Click trực tiếp vào đây để mở cửa sổ Browse File"
        )
        self.drop_label.setObjectName("DropLabel")
        self.drop_label.setWordWrap(True)

        drop_layout.addWidget(self.drop_icon)
        drop_layout.addWidget(self.drop_label, stretch=1)
        file_group_layout.addWidget(self.drop_frame)

        main_layout.addWidget(file_group)

        # 3. Settings Grid
        settings_group = QtWidgets.QGroupBox("⚙️ Cài Đặt Tùy Chọn Bản Note & Tài Khoản Google AI")
        settings_layout = QtWidgets.QGridLayout(settings_group)
        settings_layout.setHorizontalSpacing(16)
        settings_layout.setVerticalSpacing(10)

        # Number of lines
        settings_layout.addWidget(QtWidgets.QLabel("Số dòng kẻ mỗi câu:"), 0, 0)
        self.spin_lines = QtWidgets.QSpinBox()
        self.spin_lines.setRange(6, 25)
        self.spin_lines.setValue(self.config.get("num_lines", 10))
        settings_layout.addWidget(self.spin_lines, 0, 1)

        # Line height
        settings_layout.addWidget(QtWidgets.QLabel("Khoảng cách dòng:"), 0, 2)
        self.combo_height = QtWidgets.QComboBox()
        self.combo_height.addItems([
            "26 px (Nhỏ gọn)",
            "28 px (Tiêu chuẩn bút stylus)",
            "32 px (Thoải mái)",
            "36 px (Chữ to)"
        ])
        self.combo_height.setCurrentIndex(1)
        settings_layout.addWidget(self.combo_height, 0, 3)

        # Line style
        settings_layout.addWidget(QtWidgets.QLabel("Kiểu dòng kẻ:"), 1, 0)
        self.combo_style = QtWidgets.QComboBox()
        self.combo_style.addItems(["Nét đứt (Dashed)", "Nét chấm (Dotted)", "Nét liền mờ (Solid)"])
        settings_layout.addWidget(self.combo_style, 1, 1)

        # Google AI Key + 1-Click Setup Button
        settings_layout.addWidget(QtWidgets.QLabel("Tài khoản Google AI:"), 1, 2)
        key_box = QtWidgets.QHBoxLayout()
        self.input_key = QtWidgets.QLineEdit()
        self.input_key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.input_key.setPlaceholderText("Bấm 'Lấy Mã 1-Click' bên cạnh (hoặc để trống nếu có agy)")
        self.input_key.setText(self.config.get("api_key", ""))
        self.input_key.textChanged.connect(self.update_ai_status_badge)

        self.btn_get_key = QtWidgets.QPushButton("🔑 Lấy Mã 1-Click")
        self.btn_get_key.setObjectName("BtnBrowsePrimary")
        self.btn_get_key.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_get_key.setToolTip("Lấy mã Google AI miễn phí bằng Gmail trên trình duyệt chỉ trong 15 giây")
        self.btn_get_key.clicked.connect(self.open_google_ai_setup)

        key_box.addWidget(self.input_key, stretch=1)
        key_box.addWidget(self.btn_get_key)
        settings_layout.addLayout(key_box, 1, 3)

        # Include hints option (Bật/Tắt gợi ý)
        settings_layout.addWidget(QtWidgets.QLabel("Gợi ý & Khái niệm:"), 2, 0)
        self.chk_include_hints = QtWidgets.QCheckBox(
            "Bật giải thích khái niệm & định hướng cách làm (Bỏ chọn để tắt gợi ý hoàn toàn)"
        )
        self.chk_include_hints.setChecked(self.config.get("include_hints", True))
        self.chk_include_hints.setCursor(QtCore.Qt.PointingHandCursor)
        settings_layout.addWidget(self.chk_include_hints, 2, 1, 1, 3)

        main_layout.addWidget(settings_group)

        # 4. Action Button & Progress
        action_layout = QtWidgets.QHBoxLayout()
        self.btn_process = QtWidgets.QPushButton("🚀 BẮT ĐẦU TỰ ĐỘNG XỬ LÝ & XUẤT 2 FILE PDF")
        self.btn_process.setObjectName("BtnProcess")
        self.btn_process.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_process.setFixedHeight(46)
        self.btn_process.setEnabled(False)
        self.btn_process.clicked.connect(self.start_processing)
        action_layout.addWidget(self.btn_process)
        main_layout.addLayout(action_layout)

        # Progress bar
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(18)
        main_layout.addWidget(self.progress_bar)

        # Status / Log
        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(105)
        self.log_view.setObjectName("LogView")
        self.log_view.setPlaceholderText("Trạng thái tiến trình sẽ hiển thị tại đây...")
        main_layout.addWidget(self.log_view)

        # 5. Output Actions
        self.output_group = QtWidgets.QGroupBox("📂 Kết Quả & Thao Tác Nhanh")
        out_layout = QtWidgets.QHBoxLayout(self.output_group)

        self.btn_open_sol = QtWidgets.QPushButton("📄 Mở File Đáp Án Chi Tiết")
        self.btn_open_sol.setEnabled(False)
        self.btn_open_sol.clicked.connect(lambda: self.open_file(self.sol_pdf_path))

        self.btn_open_note = QtWidgets.QPushButton("✍️ Mở File Note Bảng Vẽ")
        self.btn_open_note.setEnabled(False)
        self.btn_open_note.clicked.connect(lambda: self.open_file(self.note_pdf_path))

        self.btn_open_dir = QtWidgets.QPushButton("📁 Mở Thư Mục Chứa File")
        self.btn_open_dir.setEnabled(False)
        self.btn_open_dir.clicked.connect(self.open_output_dir)

        out_layout.addWidget(self.btn_open_sol)
        out_layout.addWidget(self.btn_open_note)
        out_layout.addWidget(self.btn_open_dir)
        main_layout.addWidget(self.output_group)

        # Support drag, drop, and click on drop_frame
        self.drop_frame.dragEnterEvent = self.dragEnterEvent
        self.drop_frame.dropEvent = self.dropEvent
        self.drop_frame.mousePressEvent = lambda event: self.browse_file()

    def update_ai_status_badge(self):
        has_key = bool(self.input_key.text().strip())
        if has_key:
            self.btn_ai_badge.setText("🟢 Đã kết nối: Google AI Key cá nhân")
            self.btn_ai_badge.setStyleSheet(
                "background-color: #ecfdf5; border: 1px solid #34d399; color: #065f46; font-weight: 700; padding: 6px 12px; border-radius: 6px;"
            )
        elif has_local_agy():
            self.btn_ai_badge.setText("🟢 Đã kết nối: Local AI (agy) • Bấm để dùng Key riêng")
            self.btn_ai_badge.setStyleSheet(
                "background-color: #f0f9ff; border: 1px solid #60a5fa; color: #1e40af; font-weight: 600; padding: 6px 12px; border-radius: 6px;"
            )
        else:
            self.btn_ai_badge.setText("🟠 Chưa kết nối Google AI — Bấm để kết nối (15 giây)")
            self.btn_ai_badge.setStyleSheet(
                "background-color: #fffbeb; border: 1.5px solid #f59e0b; color: #b45309; font-weight: 700; padding: 6px 12px; border-radius: 6px;"
            )

    def open_google_ai_setup(self):
        dlg = GoogleAISetupDialog(self, current_key=self.input_key.text().strip())
        if dlg.exec() == QtWidgets.QDialog.Accepted and dlg.verified_key:
            self.input_key.setText(dlg.verified_key)
            self.config["api_key"] = dlg.verified_key
            save_config(self.config)
            self.update_ai_status_badge()
            self.append_log("✅ Đã kết nối và lưu mã Google AI cá nhân thành công!")
            return True
        return False

    def dragEnterEvent(self, e: QtGui.QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QtGui.QDropEvent):
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith(".pdf"):
                self.load_selected_pdf(path)

    def on_path_entered(self):
        path = os.path.expanduser(self.input_pdf_edit.text().strip())
        if os.path.isfile(path) and path.lower().endswith(".pdf"):
            self.load_selected_pdf(path)
        else:
            QtWidgets.QMessageBox.warning(
                self, "Đường dẫn không hợp lệ",
                f"Không tìm thấy file PDF tại:\n{path}"
            )

    def browse_file(self):
        """Opens a rich File Browser dialog with sidebar shortcuts (Downloads, Documents, Desktop, Home)."""
        start_dir = os.path.expanduser("~/Downloads")
        if self.selected_pdf and os.path.exists(os.path.dirname(self.selected_pdf)):
            start_dir = os.path.dirname(self.selected_pdf)
        elif not os.path.exists(start_dir):
            start_dir = os.path.expanduser("~")

        dialog = QtWidgets.QFileDialog(self, "Chọn File PDF Bài Tập", start_dir)
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        dialog.setNameFilters(["Tài liệu PDF (*.pdf *.PDF)", "Tất cả các file (*)"])
        dialog.setViewMode(QtWidgets.QFileDialog.Detail)
        dialog.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)

        sidebar_urls = [
            QtCore.QUrl.fromLocalFile(os.path.expanduser("~")),
            QtCore.QUrl.fromLocalFile(os.path.expanduser("~/Downloads")),
            QtCore.QUrl.fromLocalFile(os.path.expanduser("~/Documents")),
            QtCore.QUrl.fromLocalFile(os.path.expanduser("~/Desktop")),
        ]
        dialog.setSidebarUrls([u for u in sidebar_urls if os.path.exists(u.toLocalFile())])
        dialog.resize(780, 520)

        if dialog.exec() == QtWidgets.QDialog.Accepted:
            selected = dialog.selectedFiles()
            if selected:
                self.load_selected_pdf(selected[0])

    def browse_output_dir(self):
        """Opens a directory browser dialog for selecting where to save generated PDFs."""
        start_dir = os.path.expanduser(self.output_dir_edit.text().strip() or "~/Downloads")
        if not os.path.exists(start_dir):
            start_dir = os.path.expanduser("~")

        dialog = QtWidgets.QFileDialog(self, "Chọn Thư Mục Lưu File PDF Kết Quả", start_dir)
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
        dialog.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)

        sidebar_urls = [
            QtCore.QUrl.fromLocalFile(os.path.expanduser("~")),
            QtCore.QUrl.fromLocalFile(os.path.expanduser("~/Downloads")),
            QtCore.QUrl.fromLocalFile(os.path.expanduser("~/Documents")),
            QtCore.QUrl.fromLocalFile(os.path.expanduser("~/Desktop")),
        ]
        dialog.setSidebarUrls([u for u in sidebar_urls if os.path.exists(u.toLocalFile())])
        dialog.resize(760, 500)

        if dialog.exec() == QtWidgets.QDialog.Accepted:
            selected = dialog.selectedFiles()
            if selected:
                self.output_dir_edit.setText(selected[0])
                self.append_log(f"Đã đổi thư mục xuất file sang: {selected[0]}")

    def show_quick_pdf_menu(self):
        """Displays a popup menu of recent PDF files in Downloads, Documents, and Desktop."""
        menu = QtWidgets.QMenu(self)
        search_dirs = [
            ("Downloads", os.path.expanduser("~/Downloads")),
            ("Documents", os.path.expanduser("~/Documents")),
            ("Desktop", os.path.expanduser("~/Desktop")),
        ]
        found_files = []
        for label, d in search_dirs:
            if os.path.isdir(d):
                for p in glob.glob(os.path.join(d, "*.pdf")) + glob.glob(os.path.join(d, "*.PDF")):
                    try:
                        mtime = os.path.getmtime(p)
                        found_files.append((mtime, label, p))
                    except Exception:
                        pass

        found_files.sort(key=lambda x: x[0], reverse=True)
        if not found_files:
            act = menu.addAction("(Không tìm thấy file PDF nào trong Downloads/Documents/Desktop)")
            act.setEnabled(False)
        else:
            for _, folder_name, full_path in found_files[:20]:
                fname = os.path.basename(full_path)
                size_kb = os.path.getsize(full_path) / 1024
                action = menu.addAction(f"📄 [{folder_name}] {fname}  ({size_kb:.0f} KB)")
                action.triggered.connect(lambda checked=False, p=full_path: self.load_selected_pdf(p))

        menu.exec(self.btn_recent.mapToGlobal(QtCore.QPoint(0, self.btn_recent.height())))

    def load_selected_pdf(self, path):
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(path):
            return
        self.selected_pdf = path
        self.input_pdf_edit.setText(path)
        self.output_dir_edit.setText(os.path.dirname(path))

        info = PDFExtractor.get_info(path)
        self.drop_label.setText(
            f"✓ Đã chọn: {info['filename']} ({info['pages']} trang • {info['size_kb']:.1f} KB)\n"
            f"Đường dẫn: {path}  (Click vào đây nếu muốn chọn file khác)"
        )
        self.drop_icon.setText("📑")
        self.btn_process.setEnabled(True)
        self.btn_open_dir.setEnabled(True)

        self.config["last_pdf"] = path
        save_config(self.config)
        self.append_log(f"Đã chọn file: {path} ({info['pages']} trang)")

    def append_log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.log_view.append(f"[{timestamp}] {msg}")
        self.log_view.moveCursor(QtGui.QTextCursor.End)

    def start_processing(self):
        typed_path = os.path.expanduser(self.input_pdf_edit.text().strip())
        if typed_path and os.path.isfile(typed_path) and typed_path != self.selected_pdf:
            self.load_selected_pdf(typed_path)

        if not self.selected_pdf or not os.path.isfile(self.selected_pdf):
            QtWidgets.QMessageBox.warning(self, "Chưa chọn file", "Vui lòng chọn một file PDF hợp lệ trước khi xử lý.")
            return

        # If user has neither API key nor local agy-cli, automatically launch the 1-Click Google AI Setup Wizard!
        if not self.input_key.text().strip() and not has_local_agy():
            if not self.open_google_ai_setup():
                return

        output_dir = os.path.expanduser(self.output_dir_edit.text().strip()) or os.path.dirname(self.selected_pdf)

        self.btn_process.setEnabled(False)
        self.btn_browse.setEnabled(False)
        self.btn_recent.setEnabled(False)
        self.btn_browse_out.setEnabled(False)
        self.btn_open_sol.setEnabled(False)
        self.btn_open_note.setEnabled(False)
        self.progress_bar.setValue(5)

        # Save config
        self.config["num_lines"] = self.spin_lines.value()
        self.config["api_key"] = self.input_key.text().strip()
        self.config["include_hints"] = self.chk_include_hints.isChecked()
        self.config["output_dir"] = output_dir
        self.config["last_pdf"] = self.selected_pdf
        save_config(self.config)

        # Determine line height
        height_map = [26, 28, 32, 36]
        line_height = height_map[self.combo_height.currentIndex()]

        # Determine line style
        style_map = ["dashed", "dotted", "solid"]
        line_style = style_map[self.combo_style.currentIndex()]

        self.worker = WorkerThread(
            pdf_path=self.selected_pdf,
            output_dir=output_dir,
            num_lines=self.spin_lines.value(),
            line_height=line_height,
            line_style=line_style,
            api_key=self.input_key.text(),
            include_hints=self.chk_include_hints.isChecked()
        )
        self.worker.progress_signal.connect(self.on_progress)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.append_log(msg)

    def on_finished(self, success, msg, sol_pdf, note_pdf):
        self.btn_process.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.btn_recent.setEnabled(True)
        self.btn_browse_out.setEnabled(True)
        if success:
            self.sol_pdf_path = sol_pdf
            self.note_pdf_path = note_pdf
            self.btn_open_sol.setEnabled(True)
            self.btn_open_note.setEnabled(True)
            self.btn_open_dir.setEnabled(True)
            self.append_log(f"🎉 Đã xuất thành công:\n  1. {sol_pdf}\n  2. {note_pdf}")
            QtWidgets.QMessageBox.information(
                self, "Hoàn tất!",
                f"Đã tạo thành công 2 file PDF chất lượng cao:\n\n1. {os.path.basename(sol_pdf)}\n2. {os.path.basename(note_pdf)}"
            )
        else:
            self.append_log(f"❌ Lỗi: {msg}")
            QtWidgets.QMessageBox.critical(self, "Lỗi xử lý", f"Đã xảy ra lỗi:\n{msg}")

    def open_file(self, path):
        if path and os.path.exists(path):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(os.path.abspath(path)))

    def open_output_dir(self):
        folder = os.path.expanduser(self.output_dir_edit.text().strip())
        if not folder or not os.path.isdir(folder):
            if self.selected_pdf:
                folder = os.path.dirname(self.selected_pdf)
        if folder and os.path.isdir(folder):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(os.path.abspath(folder)))

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8fafc;
            }
            #AppTitle {
                font-size: 19pt;
                font-weight: 800;
                color: #1e3a8a;
            }
            #AppSubtitle {
                font-size: 9.5pt;
                color: #64748b;
            }
            #DropFrame {
                background-color: #f0f9ff;
                border: 2px dashed #60a5fa;
                border-radius: 10px;
            }
            #DropFrame:hover {
                background-color: #ecfdf5;
                border-color: #10b981;
            }
            #DropIcon {
                font-size: 28pt;
            }
            #DropLabel {
                font-size: 10pt;
                color: #1e293b;
                font-weight: 600;
            }
            QGroupBox {
                font-weight: 700;
                color: #1e293b;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 14px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: #ffffff;
                color: #0f172a;
                font-size: 9.5pt;
            }
            QLineEdit:focus {
                border: 1.5px solid #2563eb;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 600;
                color: #1e293b;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }
            #BtnBrowsePrimary {
                background-color: #eff6ff;
                border: 1px solid #60a5fa;
                color: #1d4ed8;
                font-weight: 700;
            }
            #BtnBrowsePrimary:hover {
                background-color: #dbeafe;
                border-color: #2563eb;
            }
            #BtnProcess {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                font-size: 11pt;
                font-weight: 700;
                border-radius: 8px;
            }
            #BtnProcess:hover {
                background-color: #1d4ed8;
            }
            #BtnProcess:disabled {
                background-color: #94a3b8;
            }
            QProgressBar {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                text-align: center;
                background-color: #e2e8f0;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 5px;
            }
            #LogView {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-family: monospace;
                font-size: 9.5pt;
                color: #334155;
            }
        """)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
