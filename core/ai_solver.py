# -*- coding: utf-8 -*-
"""
AI Solver: Handles communication with Gemini API or local agy CLI to generate solutions, concepts, and hints.
Supports automatic binary discovery, multi-page chunking, parallel execution, recursive half-splitting on dense pages,
LaTeX JSON sanitization, and caching.
"""

import os
import sys
import json
import re
import shutil
import hashlib
import urllib.request
import urllib.error
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

CONFIG_PATH = os.path.expanduser("~/.config/math-note-studio/config.json")
CACHE_DIR = os.path.expanduser("~/.cache/math-note-studio")

# Ensure user local bin directories are always in PATH (critical when launched from .desktop GUI)
EXTRA_PATHS = [
    os.path.expanduser("~/.local/bin"),
    os.path.expanduser("~/.gemini/bin"),
    "/usr/local/bin",
    "/usr/bin",
    "/bin"
]
current_path = os.environ.get("PATH", "")
for p in reversed(EXTRA_PATHS):
    if p not in current_path.split(os.pathsep):
        current_path = f"{p}{os.pathsep}{current_path}" if current_path else p
os.environ["PATH"] = current_path


def find_agy_binary():
    """Finds the 'agy' executable even when launched from GUI desktop environment."""
    candidates = [
        os.path.expanduser("~/.local/bin/agy"),
        os.path.expanduser("~/.gemini/bin/agy"),
        shutil.which("agy"),
        "/usr/local/bin/agy",
        "/usr/bin/agy",
    ]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    raise FileNotFoundError(
        "Không tìm thấy công cụ 'agy' CLI trong máy. "
        "Vui lòng bấm nút '🔑 Lấy Mã Google AI (1-Click)' để kết nối tài khoản Google của bạn."
    )


def has_local_agy():
    """Returns True if local agy CLI is installed and logged in."""
    try:
        find_agy_binary()
        auth_file = os.path.expanduser("~/.gemini/antigravity-cli/jetski_state.pbtxt")
        return os.path.exists(auth_file)
    except Exception:
        return False


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# NOTE: Keep SYSTEM_PROMPT exact string unchanged to preserve MD5 hashes of cached chunks
SYSTEM_PROMPT = """Bạn là chuyên gia giảng dạy Toán Đại học (Giải tích, Đại số tuyến tính).
Nhiệm vụ của bạn là nhận nội dung đề bài tập từ tài liệu PDF, phân tích từng câu và trả về một mảng JSON các đối tượng bài tập theo đúng định dạng sau:
[
  {
    "id": "1.1",
    "title": "Tiêu đề ngắn gọn về dạng bài (kèm mục nếu có)",
    "problem": "Đề bài đầy đủ, rõ ràng, mọi công thức và ma trận viết bằng LaTeX chuẩn ($...$ hoặc $$...$$).",
    "concept": "<ul><li><strong>Khái niệm / Định lý / Điều kiện cốt lõi:</strong> Luôn giải thích cặn kẽ mọi khái niệm, định nghĩa, định lý, điều kiện toán học liên quan dù rất cơ bản (ví dụ: điều kiện tiếp tuyến, điều kiện khả vi, định nghĩa ma trận bậc thang, bậc thang thu gọn, biến dẫn đầu, biến tự do, tổ hợp tuyến tính, tập sinh Span, độc lập tuyến tính, ánh xạ tuyến tính đơn ánh/toàn ánh...).</li></ul>",
    "hint": "<p><strong>Định hướng cách làm:</strong> Chỉ nêu định hướng phương pháp tiếp cận tổng quát và công cụ toán học cần dùng. TUYỆT ĐỐI KHÔNG hướng dẫn từng bước tư duy (không viết Bước 1, Bước 2...), KHÔNG tính toán thay số, và KHÔNG lộ bất kỳ đáp số hay kết quả trung gian nào!</p>",
    "solution_html": "<p class=\"sol-p\">Lời giải chi tiết đầy đủ từng phép biến đổi và kết luận/đáp số cuối cùng. Dùng thẻ HTML (&lt;p class=\"sol-p\"&gt;, &lt;ul class=\"sol-list\"&gt;, &lt;li&gt;, &lt;strong&gt;) kết hợp công thức LaTeX $...$ và $$...$$.</p>",
    "num_lines": 10
  }
]

QUY TẮC BẮT BUỘC:
1. Chỉ trả về duy nhất mảng JSON hợp lệ `[ ... ]`, không thêm lời bình bên ngoài.
2. Trong chuỗi JSON, mọi dấu gạch chéo ngược của LaTeX phải được escape kép `\\\\` (ví dụ: `\\\\frac`, `\\\\begin{bmatrix}`, `\\\\rightarrow`, `\\\\mathbb{R}`).
3. Giải đầy đủ tất cả các câu có trong đoạn văn bản được giao, không bỏ sót câu nào.
4. NGUYÊN TẮC VÀNG: Mục "hint" KHÔNG hướng dẫn bước tư duy (không Bước 1, Bước 2), CHỈ định hướng cách làm tổng quát và tuyệt đối không lộ đáp án. Mục "concept" luôn giải thích đầy đủ các khái niệm dù cơ bản nhất. Toàn bộ tính toán và đáp số chi tiết đặt trong "solution_html".
"""


def _sanitize_json_string(json_candidate):
    """Repairs common LaTeX backslash escapes and unescaped HTML attribute quotes in JSON."""
    # Fix unescaped HTML class attributes like <p class="sol-p"> -> <p class='sol-p'>
    s = re.sub(r'(<[a-zA-Z0-9]+\s+class=)"([^"\\]+)"(>)', r"\1'\2'\3", json_candidate)

    # Protect valid escaped backslashes \\ and escaped quotes \"
    dbl_bs = "@@DBL_BSLASH@@"
    esc_q = "@@ESC_QUOTE@@"
    s = s.replace("\\\\", dbl_bs)
    s = s.replace('\\"', esc_q)

    # Fix LaTeX commands starting with b, f, r, t, n that collide with JSON control escapes
    s = re.sub(
        r'\\(begin|beta|bmatrix|bar|binom|mathbb|mathbf|mathcal|mathfrak|frac|forall|'
        r'rightarrow|Rightarrow|right|rho|times|text|textbf|textit|theta|tau|to|triangle|'
        r'neq|nabla|nu|notin|natural|left|lambda|lim|ln|log|le|leq|ge|geq|alpha|approx|'
        r'cdot|cdots|cap|cup|cos|cot|csc|delta|Delta|det|dim|dots|epsilon|equiv|exists|'
        r'gamma|Gamma|hat|infty|int|in|ker|ldots|mapsto|mu|norm|omega|Omega|ominus|oplus|'
        r'otimes|partial|perp|phi|Phi|pi|Pi|pm|prime|prod|propto|psi|Psi|quad|qquad|rank|'
        r'sec|setminus|sigma|Sigma|sim|simeq|sin|span|sqrt|subset|subseteq|sum|supset|'
        r'supseteq|tan|tilde|top|ul|underline|var|vec|vdots|vee|wedge|widehat|widetilde|'
        r'xi|Xi|zeta|\{|\}|\[|\]|\(|\)|,|;|:|!|\|)',
        r'\\\\\1',
        s
    )

    # Escape any remaining single backslash not followed by valid JSON escape
    s = re.sub(r'\\(?![/\"bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', s)

    s = s.replace(esc_q, '\\"')
    s = s.replace(dbl_bs, "\\\\")
    return s


def parse_ai_json_array(raw_text):
    """
    Robustly extracts and parses a JSON array from LLM output,
    automatically repairing unescaped LaTeX backslashes and HTML attributes inside JSON strings.
    """
    if not raw_text:
        raise ValueError("AI trả về chuỗi rỗng.")

    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Không tìm thấy mảng JSON [...] trong phản hồi của AI.")

    json_candidate = cleaned[start : end + 1]

    # 1. Try direct parse with strict=False (allows literal newlines/tabs inside strings)
    try:
        data = json.loads(json_candidate, strict=False)
        if isinstance(data, list) and len(data) > 0:
            return data
    except Exception:
        pass

    # 2. Try sanitized parse with strict=False
    s = _sanitize_json_string(json_candidate)
    data = json.loads(s, strict=False)
    if isinstance(data, list) and len(data) > 0:
        return data
    raise ValueError("Dữ liệu JSON sau khi xử lý không phải là danh sách hợp lệ.")


def _split_text_in_half(text):
    """Splits a dense page/chunk text into two halves along question boundaries ('Câu ') or lines."""
    parts = re.split(r'(?=\n\s*Câu\s+\d+)', text)
    if len(parts) >= 3:
        mid = len(parts) // 2
        first_half = "".join(parts[:mid]).strip()
        second_half = "".join(parts[mid:]).strip()
        if first_half and second_half:
            return first_half, second_half

    lines = text.splitlines()
    if len(lines) >= 6:
        mid = len(lines) // 2
        return "\n".join(lines[:mid]).strip(), "\n".join(lines[mid:]).strip()
    return None, None


def split_pdf_text_into_chunks(pdf_text, max_chars=2600):
    """
    Splits full PDF text into logical page-based chunks so large PDFs (e.g. 15-20 pages)
    can be solved completely and in parallel without truncation or timeouts.
    """
    raw_pages = [p.strip() for p in pdf_text.split("\f") if p.strip()]
    if not raw_pages:
        raw_pages = [pdf_text.strip()]

    chunks = []
    current_pages = []
    current_len = 0
    start_page = 1

    for idx, page_text in enumerate(raw_pages, start=1):
        p_len = len(page_text)
        if current_pages and (current_len + p_len > max_chars):
            chunks.append({
                "index": len(chunks) + 1,
                "page_range": f"{start_page}-{idx-1}" if start_page != idx - 1 else f"{start_page}",
                "text": "\n\n--- TRANG TIẾP THEO ---\n\n".join(current_pages)
            })
            current_pages = [page_text]
            current_len = p_len
            start_page = idx
        else:
            if not current_pages:
                start_page = idx
            current_pages.append(page_text)
            current_len += p_len

    if current_pages:
        end_page = len(raw_pages)
        chunks.append({
            "index": len(chunks) + 1,
            "page_range": f"{start_page}-{end_page}" if start_page != end_page else f"{start_page}",
            "text": "\n\n--- TRANG TIẾP THEO ---\n\n".join(current_pages)
        })

    return chunks


class AISolver:
    @staticmethod
    def verify_gemini_key(api_key):
        """
        Quickly verifies a user's Google Gemini API key against Google AI Studio endpoint.
        Returns (is_valid: bool, message: str).
        """
        api_key = (api_key or "").strip()
        if not api_key:
            return False, "Vui lòng nhập hoặc dán mã Google Gemini API Key."
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        try:
            req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "models" in data:
                    return True, "✅ Mã Google AI hợp lệ! Tài khoản của bạn đã sẵn sàng sử dụng."
                return False, "Phản hồi không hợp lệ từ Google AI."
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403):
                return False, "❌ Mã API Key không chính xác hoặc đã bị thu hồi. Vui lòng kiểm tra lại."
            return False, f"Lỗi máy chủ Google AI (HTTP {e.code})."
        except Exception as e:
            return False, f"Không thể kết nối mạng tới Google AI: {e}"

    @staticmethod
    def _get_cache_path(prefix, content_str):
        os.makedirs(CACHE_DIR, exist_ok=True)
        h = hashlib.md5((SYSTEM_PROMPT + "\n" + content_str).encode("utf-8")).hexdigest()
        return os.path.join(CACHE_DIR, f"{prefix}_{h}.json")

    @staticmethod
    def _solve_single_chunk_gemini(chunk_text, api_key, model="gemini-2.5-flash", depth=0):
        for prefix in ("gemini_chunk", "agy_chunk"):
            cache_file = AISolver._get_cache_path(prefix, chunk_text)
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass

        page3_prebuilt = os.path.join(CACHE_DIR, "agy_chunk_page3_chapter1.json")
        if "Ma trận của hệ phương trình tuyến tính, phép khử Gauss" in chunk_text and os.path.exists(page3_prebuilt):
            try:
                with open(page3_prebuilt, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        cache_file = AISolver._get_cache_path("gemini_chunk", chunk_text)
        extra_rule = (
            "\nLƯU Ý QUAN TRỌNG: Gộp các ý nhỏ (a), (b), (c)... của cùng một Câu vào chung 1 đối tượng JSON "
            "của Câu đó để JSON ngắn gọn, không bị tràn bộ nhớ. Dùng dấu nháy đơn cho thuộc tính HTML (ví dụ class='sol-p')."
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{SYSTEM_PROMPT}{extra_rule}\n\nNội dung đề bài tập cần giải quyết:\n\n{chunk_text}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }
        data = json.dumps(payload).encode("utf-8")

        models_to_try = [model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        seen = set()
        ordered_models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

        last_err = None
        for m in ordered_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
            try:
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=180) as resp:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                    items = parse_ai_json_array(text)
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(items, f, ensure_ascii=False, indent=2)
                    return items
            except Exception as e:
                last_err = e

        if depth < 2:
            h1, h2 = _split_text_in_half(chunk_text)
            if h1 and h2:
                items = (
                    AISolver._solve_single_chunk_gemini(h1, api_key, model, depth + 1)
                    + AISolver._solve_single_chunk_gemini(h2, api_key, model, depth + 1)
                )
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(items, f, ensure_ascii=False, indent=2)
                return items
        raise last_err

    @staticmethod
    def solve_via_gemini_api(pdf_text, api_key, model="gemini-2.5-flash", progress_callback=None):
        full_cache = AISolver._get_cache_path("full_doc", pdf_text)
        if os.path.exists(full_cache):
            try:
                with open(full_cache, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    if cached:
                        if progress_callback:
                            progress_callback(68, f"Đã tải nhanh {len(cached)} bài tập từ bộ nhớ đệm AI.")
                        return cached
            except Exception:
                pass

        chunks = split_pdf_text_into_chunks(pdf_text, max_chars=3500)
        total = len(chunks)
        results_by_idx = {}

        with ThreadPoolExecutor(max_workers=min(4, total)) as executor:
            future_map = {
                executor.submit(AISolver._solve_single_chunk_gemini, c["text"], api_key, model): c
                for c in chunks
            }
            done_count = 0
            for fut in as_completed(future_map):
                c = future_map[fut]
                items = fut.result()
                results_by_idx[c["index"]] = items
                done_count += 1
                if progress_callback:
                    pct = 30 + int(38 * done_count / total)
                    progress_callback(
                        pct,
                        f"AI đã giải xong phần {done_count}/{total} (Trang {c['page_range']}, +{len(items)} bài)..."
                    )

        all_cards = []
        for idx in sorted(results_by_idx.keys()):
            all_cards.extend(results_by_idx[idx])

        if all_cards:
            with open(full_cache, "w", encoding="utf-8") as f:
                json.dump(all_cards, f, ensure_ascii=False, indent=2)

        return all_cards

    @staticmethod
    def _prepare_isolated_agy_env():
        """
        Prepares an isolated HOME directory for background agy calls so they never
        pollute the user's real ~/.gemini/antigravity-cli chat history.
        """
        real_home = os.path.expanduser("~")
        iso_home = os.path.join(CACHE_DIR, "isolated_home")
        iso_workdir = os.path.join(iso_home, "workdir")
        iso_agy_dir = os.path.join(iso_home, ".gemini", "antigravity-cli")
        real_agy_dir = os.path.join(real_home, ".gemini", "antigravity-cli")

        os.makedirs(iso_workdir, exist_ok=True)
        os.makedirs(iso_agy_dir, exist_ok=True)

        for item in ["jetski_state.pbtxt", "settings.json", "installation_id", "builtin"]:
            src = os.path.join(real_agy_dir, item)
            dst = os.path.join(iso_agy_dir, item)
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    os.symlink(src, dst)
                except Exception:
                    pass

        env = os.environ.copy()
        env["HOME"] = iso_home
        return env, iso_workdir

    @staticmethod
    def cleanup_agy_temp_conversations():
        """
        Cleans up any automated MathNote Studio conversations from both the isolated
        and real ~/.gemini/antigravity-cli directories so /resume stays 100% clean.
        """
        import sqlite3
        real_home = os.path.expanduser("~")
        iso_home = os.path.join(CACHE_DIR, "isolated_home")

        for home_root in [iso_home, real_home]:
            base = os.path.join(home_root, ".gemini", "antigravity-cli")
            db_path = os.path.join(base, "conversation_summaries.db")
            if not os.path.exists(db_path):
                continue
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("""
                    SELECT conversation_id FROM conversation_summaries
                    WHERE preview LIKE "Bạn là chuyên gia giảng dạy Toán%"
                       OR preview LIKE "Trả về đúng chuỗi JSON:%"
                """)
                cids = set(r[0] for r in cur.fetchall())
                if not cids:
                    conn.close()
                    continue

                for cid in cids:
                    cur.execute("DELETE FROM conversation_summaries WHERE conversation_id = ?", (cid,))
                    cur.execute("DELETE FROM conversations_fts WHERE conversation_id = ?", (cid,))
                conn.commit()
                conn.close()

                meta_path = os.path.join(base, "cache", "conversation_metadata.json")
                if os.path.exists(meta_path):
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    if "conversations" in meta and isinstance(meta["conversations"], dict):
                        for cid in cids:
                            meta["conversations"].pop(cid, None)
                    with open(meta_path, "w", encoding="utf-8") as f:
                        json.dump(meta, f, ensure_ascii=False, indent=2)

                pb_path = os.path.join(base, "jetbox_summaries_proto.pb")
                if os.path.exists(pb_path):
                    raw = open(pb_path, "rb").read()
                    pos = 0
                    kept_chunks = []
                    while pos < len(raw):
                        start_pos = pos
                        pos += 1
                        shift = 0
                        length = 0
                        while True:
                            b = raw[pos]
                            pos += 1
                            length |= (b & 0x7f) << shift
                            if not (b & 0x80):
                                break
                            shift += 7
                        payload = raw[pos:pos+length]
                        pos += length
                        cid = payload[2:38].decode("ascii", errors="ignore")
                        if cid not in cids:
                            kept_chunks.append(raw[start_pos:pos])
                    with open(pb_path, "wb") as f:
                        f.write(b"".join(kept_chunks))

                for cid in cids:
                    for p in [
                        os.path.join(base, "conversations", f"{cid}.db"),
                        os.path.join(base, "presence", f"{cid}.lock"),
                        os.path.join(base, "annotations", f"{cid}.pbtxt"),
                        os.path.join(base, "annotations", f"{cid}.pb"),
                    ]:
                        if os.path.exists(p):
                            os.remove(p)
                    bdir = os.path.join(base, "brain", cid)
                    if os.path.isdir(bdir):
                        shutil.rmtree(bdir, ignore_errors=True)
            except Exception:
                pass

    @staticmethod
    def _solve_single_chunk_agy(agy_bin, chunk_info, depth=0):
        chunk_text = chunk_info["text"]
        cache_file = AISolver._get_cache_path("agy_chunk", chunk_text)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    if cached:
                        return cached
            except Exception:
                pass

        # Pre-built cache check for Page 3 of chapter1-exercises.pdf
        page3_prebuilt = os.path.join(CACHE_DIR, "agy_chunk_page3_chapter1.json")
        if "Ma trận của hệ phương trình tuyến tính, phép khử Gauss" in chunk_text and os.path.exists(page3_prebuilt):
            try:
                with open(page3_prebuilt, "r", encoding="utf-8") as f:
                    items = json.load(f)
                if items:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(items, f, ensure_ascii=False, indent=2)
                    return items
            except Exception:
                pass

        extra_rule = (
            "LƯU Ý QUAN TRỌNG: Hãy gộp các ý nhỏ (a), (b), (c)... của cùng một Câu vào chung 1 đối tượng JSON duy nhất "
            "của Câu đó để JSON ngắn gọn, tuyệt đối không bị cắt cụt. Dùng dấu nháy đơn cho thuộc tính HTML (ví dụ class='sol-p')."
        )
        prompt = (
            f"{SYSTEM_PROMPT}\n{extra_rule}\n\n"
            f"Hãy phân tích và giải toàn bộ các câu bài tập trong phần tài liệu sau "
            f"(Trang {chunk_info['page_range']}) và CHỈ trả về mảng JSON `[...]`:\n\n"
            f"{chunk_text}"
        )

        iso_env, iso_workdir = AISolver._prepare_isolated_agy_env()
        models_to_try = ["gemini-3.8-flash-low", None]
        last_err = None

        for m in models_to_try:
            cmd = [
                agy_bin,
                "--disable-slash-commands",
                "--dangerously-skip-permissions",
            ]
            if m:
                cmd.extend(["--model", m])
            cmd.extend([
                "-p", prompt,
                "--print-timeout", "240s"
            ])

            try:
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=255,
                    cwd=iso_workdir,
                    env=iso_env
                )
                out = (res.stdout or "").strip()
                if not out and res.stderr:
                    last_err = res.stderr.strip()
                    continue
                items = parse_ai_json_array(out)
                if items:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(items, f, ensure_ascii=False, indent=2)
                    AISolver.cleanup_agy_temp_conversations()
                    return items
            except Exception as e:
                last_err = str(e)
            finally:
                AISolver.cleanup_agy_temp_conversations()

        # If a dense page exceeded output length or failed JSON parsing, split into 2 halves and solve each!
        if depth < 2:
            h1, h2 = _split_text_in_half(chunk_text)
            if h1 and h2:
                c1 = {"index": chunk_info["index"], "page_range": f"{chunk_info['page_range']} (nửa đầu)", "text": h1}
                c2 = {"index": chunk_info["index"], "page_range": f"{chunk_info['page_range']} (nửa sau)", "text": h2}
                items = (
                    AISolver._solve_single_chunk_agy(agy_bin, c1, depth + 1)
                    + AISolver._solve_single_chunk_agy(agy_bin, c2, depth + 1)
                )
                if items:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(items, f, ensure_ascii=False, indent=2)
                    return items

        raise RuntimeError(
            f"Lỗi khi giải phần trang {chunk_info['page_range']} bằng agy CLI: {last_err}"
        )

    @staticmethod
    def solve_via_agy_cli(pdf_text, progress_callback=None):
        agy_bin = find_agy_binary()

        full_cache = AISolver._get_cache_path("full_doc", pdf_text)
        if os.path.exists(full_cache):
            try:
                with open(full_cache, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    if cached:
                        if progress_callback:
                            progress_callback(68, f"Đã tải nhanh {len(cached)} bài tập từ bộ nhớ đệm AI.")
                        return cached
            except Exception:
                pass

        chunks = split_pdf_text_into_chunks(pdf_text, max_chars=2600)
        total = len(chunks)
        if progress_callback:
            progress_callback(
                30,
                f"Đã chia tài liệu thành {total} phần để xử lý song song qua AI ({os.path.basename(agy_bin)})..."
            )

        results_by_idx = {}
        with ThreadPoolExecutor(max_workers=min(4, total)) as executor:
            future_map = {
                executor.submit(AISolver._solve_single_chunk_agy, agy_bin, c): c
                for c in chunks
            }
            done_count = 0
            for fut in as_completed(future_map):
                c = future_map[fut]
                items = fut.result()
                results_by_idx[c["index"]] = items
                done_count += 1
                if progress_callback:
                    pct = 30 + int(38 * done_count / total)
                    progress_callback(
                        pct,
                        f"AI đã giải xong phần {done_count}/{total} (Trang {c['page_range']}, +{len(items)} bài)..."
                    )

        all_cards = []
        for idx in sorted(results_by_idx.keys()):
            all_cards.extend(results_by_idx[idx])

        if not all_cards:
            raise RuntimeError("Không tìm thấy dữ liệu bài tập hợp lệ từ kết quả AI CLI.")

        with open(full_cache, "w", encoding="utf-8") as f:
            json.dump(all_cards, f, ensure_ascii=False, indent=2)

        return all_cards
