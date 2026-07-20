#!/usr/bin/env python3
"""Generate NeuralForge Complete Platform Guide PDF — v2."""

from fpdf import FPDF
import copy

OUTPUT = "/home/definitelynotme/Desktop/ai-panel/docs/NeuralForge_Complete_Guide.pdf"
FONT_DIR = "/usr/share/fonts/truetype/dejavu/"

# Colors
C_COVER_BG = (15, 23, 42)  # #0f172a
C_DARK = (20, 25, 45)
C_ACCENT = (0, 120, 215)
C_ACCENT2 = (0, 180, 160)
C_LIGHT_BG = (240, 242, 245)
C_WHITE = (255, 255, 255)
C_TEXT = (40, 40, 50)
C_MUTED = (120, 120, 140)
C_SECTION_BG = (20, 25, 45)
C_CODE_BG = (35, 38, 52)
C_INFO_BLUE = (0, 120, 215)
C_INFO_GREEN = (0, 160, 100)
C_INFO_AMBER = (200, 150, 0)

# ─── All real API endpoints ──────────────────────────────────────────────

REAL_ENDPOINTS = {
    "System & Actions": [
        ("GET",    "/",                              "Web UI (HTML)"),
        ("GET",    "/api/health",                    "Health check with alerts"),
        ("GET",    "/api/status",                    "All module statuses"),
        ("GET",    "/api/storage",                   "Disk usage by category"),
        ("POST",   "/api/restart",                   "Restart NeuralForge server"),
        ("POST",   "/api/actions/stop-all-heavy",    "Stop all heavy GPU services"),
        ("POST",   "/api/actions/start-basics",      "Start Ollama + Qdrant + WebUI"),
        ("POST",   "/api/actions/free-vram",         "Unload all Ollama models"),
    ],
    "Module Lifecycle": [
        ("POST",   "/api/module/{filename}/start",   "Start a module"),
        ("POST",   "/api/module/{filename}/stop",    "Stop a module"),
        ("GET",    "/api/module/{filename}/log",     "Last 50 log lines"),
        ("POST",   "/api/cleanup/{module_file}",     "Clean module storage"),
    ],
    "Secrets": [
        ("GET",    "/api/secrets",                   "List stored API keys"),
        ("POST",   "/api/secrets",                   "Save / update API key"),
    ],
    "Telegram Bot": [
        ("GET",    "/api/telegram",                  "Bot config + session list"),
        ("GET",    "/api/telegram/session/{id}",     "Single session details"),
        ("DELETE", "/api/telegram/session/{id}",     "Delete a session"),
        ("POST",   "/api/telegram/config",           "Update bot config"),
        ("POST",   "/api/telegram/personas",         "Create custom persona"),
        ("PUT",    "/api/telegram/personas/{id}",    "Update persona"),
        ("DELETE", "/api/telegram/personas/{id}",    "Delete persona"),
        ("POST",   "/api/telegram/start",            "Start bot"),
        ("POST",   "/api/telegram/stop",             "Stop bot"),
        ("DELETE", "/api/telegram/sessions",         "Clear all sessions"),
        ("DELETE", "/api/telegram/messages",         "Clear message history"),
    ],
    "Agents": [
        ("GET",    "/api/agents",                    "Roles, tools, models, status"),
        ("POST",   "/api/agents/run",                "Run solo agent task"),
        ("POST",   "/api/agents/upload",             "Upload file for agent"),
        ("GET",    "/api/agents/pdf/{filename}",     "Serve agent-generated PDF"),
        ("POST",   "/api/agents/run-team",           "Run team chain"),
        ("POST",   "/api/agents/run-orchestrator",   "Run AI orchestrator"),
        ("GET",    "/api/agents/status",             "Running agents status"),
        ("POST",   "/api/agents/stop",               "Stop running agent"),
        ("GET",    "/api/agents/history",            "List past tasks"),
        ("GET",    "/api/agents/history/{filename}", "Read history file"),
        ("DELETE", "/api/agents/history/{filename}", "Delete history file"),
        ("DELETE", "/api/agents/history",            "Clear all history"),
    ],
    "RAG": [
        ("GET",    "/api/rag/status",                "Collections + stats"),
        ("POST",   "/api/rag/index",                 "Index directory into Qdrant"),
        ("POST",   "/api/rag/upload-and-index",      "Upload file & index"),
        ("DELETE", "/api/rag/collection/{name}",     "Delete collection"),
        ("POST",   "/api/rag/chat",                  "RAG-augmented chat"),
    ],
    "LoRA Fine-Tuning": [
        ("GET",    "/api/finetune",                  "Models, status, datasets"),
        ("POST",   "/api/finetune/start",            "Start training run"),
        ("POST",   "/api/finetune/stop",             "Stop training"),
        ("POST",   "/api/finetune/upload-dataset",   "Upload JSONL dataset"),
    ],
    "SMM — Profiles": [
        ("GET",    "/api/smm/profiles",              "List social profiles"),
        ("GET",    "/api/smm/profiles/{id}",         "Single profile details"),
        ("POST",   "/api/smm/profiles",              "Create profile"),
        ("PUT",    "/api/smm/profiles/{id}",         "Update profile"),
        ("DELETE", "/api/smm/profiles/{id}",         "Delete profile"),
    ],
    "SMM — Content": [
        ("POST",   "/api/smm/generate",              "Generate post text"),
        ("POST",   "/api/smm/generate-image-prompt", "Generate image prompt"),
        ("POST",   "/api/smm/generate-image",        "Generate post image"),
        ("POST",   "/api/smm/regen-post",            "Regenerate existing post"),
        ("POST",   "/api/smm/batch-generate",        "Batch generate posts"),
        ("GET",    "/api/smm/batch-status",          "Batch job status"),
        ("POST",   "/api/smm/publish",               "Publish to platform"),
    ],
    "SMM — Queue & Calendar": [
        ("GET",    "/api/smm/queue",                 "Content queue list"),
        ("POST",   "/api/smm/queue",                 "Add to queue"),
        ("PUT",    "/api/smm/queue/{id}",            "Update queue item"),
        ("DELETE", "/api/smm/queue/{id}",            "Remove from queue"),
        ("GET",    "/api/smm/calendar",              "Calendar view data"),
        ("GET",    "/api/smm/events",                "Scheduled events"),
    ],
    "SMM — Trends & Analytics": [
        ("POST",   "/api/smm/trends/scan",           "Scan trend sources"),
        ("GET",    "/api/smm/trends/history",        "Trend scan history"),
        ("GET",    "/api/smm/trends/by-id",          "Trend by ID"),
        ("GET",    "/api/smm/trends/latest",         "Latest trends"),
        ("GET",    "/api/smm/analytics",             "Analytics overview"),
        ("GET",    "/api/smm/analytics/post/{id}",   "Per-post analytics"),
        ("GET",    "/api/smm/token-health",          "Token health status"),
        ("POST",   "/api/smm/token-refresh",         "Refresh expired token"),
    ],
    "SMM — Storage & Search": [
        ("GET",    "/api/smm/storage",               "SMM storage usage"),
        ("POST",   "/api/smm/cleanup",               "Clean SMM data"),
        ("POST",   "/api/smm/github-search",         "Search GitHub repos"),
        ("GET",    "/api/smm/image/{filename}",      "Serve generated image"),
    ],
    "WebSocket": [
        ("WS",     "/ws",                            "Real-time events stream"),
    ],
}


class NeuralForgePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=22)
        self.add_font("DejaVu", "", FONT_DIR + "DejaVuSans.ttf")
        self.add_font("DejaVu", "B", FONT_DIR + "DejaVuSans-Bold.ttf")
        self.add_font("DejaVu", "I", FONT_DIR + "DejaVuSans-Oblique.ttf")
        self.add_font("DejaVu", "BI", FONT_DIR + "DejaVuSans-BoldOblique.ttf")
        self.add_font("DejaVuMono", "", FONT_DIR + "DejaVuSansMono.ttf")
        self.add_font("DejaVuMono", "B", FONT_DIR + "DejaVuSansMono-Bold.ttf")
        self.toc_entries = []
        self.is_cover = False
        self.is_toc = False

    def header(self):
        if self.page_no() <= 2 or self.is_cover or self.is_toc:
            return
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*C_MUTED)
        self.cell(95, 8, "NeuralForge \u2014 Complete Platform Guide", align="L")
        self.cell(95, 8, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*C_ACCENT)
        self.set_line_width(0.3)
        self.line(10, 18, 200, 18)
        self.ln(4)

    def footer(self):
        if self.page_no() <= 2 or self.is_cover or self.is_toc:
            return
        self.set_y(-15)
        self.set_draw_color(200, 200, 210)
        self.set_line_width(0.2)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*C_MUTED)
        self.cell(0, 10, "NeuralForge v1.0  |  Self-hosted AI Command Center  |  localhost:9000", align="C")

    def section_header(self, number, title):
        if self.get_y() > 250:
            self.add_page()
        link = self.add_link()
        self.set_link(link, y=self.get_y(), page=self.page_no())
        self.toc_entries.append((number, title, self.page_no(), link))

        self.ln(3)
        y = self.get_y()
        self.set_fill_color(*C_SECTION_BG)
        self.rect(10, y, 190, 13, "F")
        self.set_fill_color(*C_ACCENT)
        self.rect(10, y, 3, 13, "F")
        self.set_xy(16, y + 1.5)
        self.set_font("DejaVu", "B", 13)
        self.set_text_color(*C_WHITE)
        self.cell(0, 10, f"{number}. {title}")
        self.set_xy(10, y + 15)
        self.ln(1)

    def sub_header(self, text):
        if self.get_y() > 262:
            self.add_page()
        self.ln(2)
        self.set_font("DejaVu", "B", 10.5)
        self.set_text_color(*C_ACCENT)
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*C_ACCENT2)
        self.set_line_width(0.4)
        self.line(10, self.get_y(), 75, self.get_y())
        self.ln(2)

    def body_text(self, text):
        self.set_font("DejaVu", "", 9)
        self.set_text_color(*C_TEXT)
        self.multi_cell(0, 5, text)
        self.ln(1)

    def bullet(self, text, indent=15):
        self.set_x(indent)
        self.set_font("DejaVu", "", 8.5)
        self.set_text_color(*C_TEXT)
        self.cell(4, 5, "\u2022")
        self.multi_cell(0, 5, text)
        self.ln(0.3)

    def bullet_bold_val(self, bold_part, rest, indent=15):
        self.set_x(indent)
        self.set_font("DejaVu", "B", 8.5)
        self.set_text_color(*C_TEXT)
        self.cell(self.get_string_width(bold_part) + 1.5, 5, bold_part)
        self.set_font("DejaVu", "", 8.5)
        self.multi_cell(0, 5, rest)
        self.ln(0.3)

    def code_block(self, text):
        self.ln(1)
        lines = text.split("\n")
        h = len(lines) * 4.2 + 5
        if self.get_y() + h > 270:
            self.add_page()
        y_start = self.get_y()
        self.set_fill_color(*C_CODE_BG)
        self.rect(12, y_start, 186, h, "F")
        # rounded accent strip
        self.set_fill_color(*C_ACCENT)
        self.rect(12, y_start, 2, h, "F")
        self.set_xy(17, y_start + 2.5)
        self.set_font("DejaVuMono", "", 7.5)
        self.set_text_color(200, 210, 230)
        for line in lines:
            self.cell(0, 4.2, line, new_x="LMARGIN", new_y="NEXT")
            self.set_x(17)
        self.set_xy(10, y_start + h + 1)
        self.ln(1)

    def info_box(self, text, color=C_INFO_BLUE):
        self.ln(1)
        y = self.get_y()
        # Measure height needed
        self.set_font("DejaVu", "I", 8.5)
        # Calculate how many lines
        nlines = max(1, len(text) // 85 + 1)
        box_h = max(10, nlines * 4.5 + 5)
        if y + box_h > 270:
            self.add_page()
            y = self.get_y()
        # Left accent bar
        self.set_fill_color(*color)
        self.rect(12, y, 3, box_h, "F")
        # Background
        bg = (min(255, 225 + color[0] // 20), min(255, 225 + color[1] // 20), min(255, 225 + color[2] // 20))
        self.set_fill_color(*bg)
        self.rect(15, y, 183, box_h, "F")
        self.set_xy(19, y + 2)
        self.set_font("DejaVu", "I", 8.5)
        self.set_text_color(*C_TEXT)
        self.multi_cell(175, 4.5, text)
        self.set_xy(10, y + box_h + 1)
        self.ln(1)

    def table_header(self, cols):
        """cols = [(label, width), ...]"""
        if self.get_y() > 255:
            self.add_page()
        self.set_font("DejaVu", "B", 7.5)
        self.set_fill_color(*C_SECTION_BG)
        self.set_text_color(*C_WHITE)
        for label, w in cols:
            if w == 0:
                self.cell(0, 6.5, " " + label, fill=True, new_x="LMARGIN", new_y="NEXT")
            else:
                self.cell(w, 6.5, " " + label, fill=True)

    def table_row(self, values, widths, row_idx=0):
        if self.get_y() > 270:
            self.add_page()
        bg = C_LIGHT_BG if row_idx % 2 == 0 else C_WHITE
        self.set_fill_color(*bg)
        self.set_font("DejaVu", "", 7.5)
        self.set_text_color(*C_TEXT)
        for j, (val, w) in enumerate(zip(values, widths)):
            if w == 0:
                self.cell(0, 5.5, " " + val, fill=True, new_x="LMARGIN", new_y="NEXT")
            else:
                self.cell(w, 5.5, " " + val, fill=True)


def build_cover(pdf):
    pdf.is_cover = True
    pdf.add_page()
    # Full dark background
    pdf.set_fill_color(*C_COVER_BG)
    pdf.rect(0, 0, 210, 297, "F")

    # Top accent line
    pdf.set_fill_color(*C_ACCENT)
    pdf.rect(0, 75, 210, 2.5, "F")

    # Subtle secondary line
    pdf.set_fill_color(*C_ACCENT2)
    pdf.rect(20, 85, 60, 0.8, "F")

    # Title
    pdf.set_y(100)
    pdf.set_font("DejaVu", "B", 36)
    pdf.set_text_color(*C_WHITE)
    pdf.cell(0, 18, "NeuralForge", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(3)
    pdf.set_font("DejaVu", "B", 16)
    pdf.set_text_color(180, 195, 220)
    pdf.cell(0, 10, "Complete Platform Guide", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("DejaVu", "I", 12)
    pdf.set_text_color(*C_ACCENT2)
    pdf.cell(0, 10, "Self-hosted AI Command Center", align="C", new_x="LMARGIN", new_y="NEXT")

    # Bottom accent
    pdf.set_fill_color(*C_ACCENT)
    pdf.rect(0, 175, 210, 1, "F")

    # Stats box
    pdf.ln(6)
    box_y = 185
    pdf.set_fill_color(30, 35, 55)
    pdf.rect(25, box_y, 160, 50, "F")
    pdf.set_fill_color(*C_ACCENT)
    pdf.rect(25, box_y, 160, 1.5, "F")

    stats = [
        ("11", "Services"),
        ("69", "APIs"),
        ("6", "Tabs"),
        ("24", "MCP Tools"),
        ("30+", "Models"),
    ]
    x_start = 30
    col_w = 30
    for i, (val, label) in enumerate(stats):
        x = x_start + i * col_w
        pdf.set_xy(x, box_y + 10)
        pdf.set_font("DejaVu", "B", 20)
        pdf.set_text_color(*C_ACCENT)
        pdf.cell(col_w, 10, val, align="C")
        pdf.set_xy(x, box_y + 22)
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(160, 165, 185)
        pdf.cell(col_w, 6, label, align="C")

    # Bottom info
    pdf.set_y(250)
    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(130, 135, 155)
    pdf.cell(0, 8, "localhost:9000", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 8)
    pdf.cell(0, 6, "Version 1.0  |  March 2026", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.is_cover = False


def build_toc(pdf, page_map=None):
    """Build TOC page. If page_map provided, use real page numbers."""
    pdf.is_toc = True
    pdf.add_page()
    pdf.ln(5)
    y = pdf.get_y()
    pdf.set_fill_color(*C_SECTION_BG)
    pdf.rect(10, y, 190, 13, "F")
    pdf.set_fill_color(*C_ACCENT)
    pdf.rect(10, y, 3, 13, "F")
    pdf.set_xy(16, y + 1.5)
    pdf.set_font("DejaVu", "B", 13)
    pdf.set_text_color(*C_WHITE)
    pdf.cell(0, 10, "Table of Contents")
    pdf.set_xy(10, y + 17)
    pdf.ln(4)

    toc_items = [
        ("1",  "Overview & Architecture"),
        ("2",  "Dashboard"),
        ("3",  "Module System"),
        ("4",  "AI Model Stack"),
        ("5",  "AI Agents"),
        ("6",  "RAG (Retrieval-Augmented Generation)"),
        ("7",  "Telegram AI Bot"),
        ("8",  "LoRA Fine-Tuning"),
        ("9",  "Generation Pipeline"),
        ("10", "SMM AI Department"),
        ("11", "MCP Server"),
        ("12", "Installation & Startup"),
        ("13", "API Reference (69 Endpoints)"),
        ("14", "Hardware Requirements"),
    ]
    for num, title in toc_items:
        page_str = ""
        if page_map and num in page_map:
            page_str = str(page_map[num])

        pdf.set_font("DejaVu", "B", 10)
        pdf.set_text_color(*C_ACCENT)
        pdf.cell(10, 8, num + ".")
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(*C_TEXT)
        title_w = pdf.get_string_width(title)
        pdf.cell(title_w + 2, 8, title)

        # Dots leader
        if page_str:
            page_w = pdf.get_string_width(page_str)
            remaining = 190 - 10 - title_w - 2 - page_w - 2
            pdf.set_font("DejaVu", "", 8)
            pdf.set_text_color(*C_MUTED)
            dot_w = pdf.get_string_width(" . ")
            n_dots = max(0, int(remaining / dot_w))
            pdf.cell(remaining, 8, " ." * n_dots)
            pdf.set_font("DejaVu", "B", 10)
            pdf.set_text_color(*C_TEXT)
            pdf.cell(page_w + 2, 8, page_str, new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.cell(0, 8, "", new_x="LMARGIN", new_y="NEXT")

    pdf.is_toc = False


def sec_overview(pdf):
    pdf.add_page()
    pdf.section_header("1", "Overview & Architecture")
    pdf.body_text(
        "NeuralForge is a self-hosted AI command center accessible at localhost:9000. "
        "It consolidates 11 services behind a unified web interface, exposing 69 API endpoints "
        "for full programmatic control. The platform is organized into 6 primary tabs: "
        "Dashboard, Agents, RAG, Telegram, LoRA, and SMM."
    )
    pdf.body_text(
        "It runs entirely on your hardware with no cloud dependencies, giving you complete "
        "control over your AI infrastructure, data privacy, and operational costs. Every "
        "component communicates over localhost, and the web UI provides real-time monitoring "
        "of all running services."
    )

    pdf.sub_header("Architecture Diagram")
    pdf.code_block(
        "                    +---------------------------+\n"
        "                    |    NeuralForge Web UI      |\n"
        "                    |      localhost:9000         |\n"
        "                    +-------------+---------------+\n"
        "                                  |\n"
        "                    +-------------+---------------+\n"
        "                    |     FastAPI Backend         |\n"
        "                    |   69 REST + 1 WS Endpoint   |\n"
        "                    +--+------+------+------+---+-+\n"
        "                       |      |      |      |   |\n"
        "              +--------+  +---+--+ +-+----+ | +-+-------+\n"
        "              | Ollama |  |Comfy | |Wan2GP| | |Qdrant   |\n"
        "              | :11434 |  |UI    | |:7860 | | |:6333    |\n"
        "              +--------+  |:8188 | +------+ | +---------+\n"
        "                          +------+          |\n"
        "                    +----------+  +---------+---------+\n"
        "                    |Hunyuan3D |  | Audio Stack       |\n"
        "                    |:7870     |  | ACE-Step  :7880   |\n"
        "                    +----------+  | Qwen3-TTS :7890   |\n"
        "                                  | Whisper   :7895   |\n"
        "                                  +-------------------+"
    )

    pdf.sub_header("Core Principles")
    pdf.bullet("Fully local: all processing on your GPU/CPU, zero cloud API calls required")
    pdf.bullet("Unified control: single web interface to manage all 11 AI services")
    pdf.bullet("Smart VRAM management: exclusive GPU groups prevent out-of-memory crashes")
    pdf.bullet("Extensible: YAML module system, full REST API, MCP integration for Claude Code")
    pdf.bullet("Resilient: systemd-managed, auto-restart on failure, health monitoring")

    pdf.sub_header("Six Platform Tabs")
    tabs = [
        ("Dashboard", "Real-time hardware monitoring, service lifecycle, health alerts, GPU/RAM/Disk metrics"),
        ("Agents", "13 AI roles with 9 tools, solo/team/orchestrator modes, file upload, history"),
        ("RAG", "Document indexing with ONNX GPU embeddings (1800 docs/s), multi-collection semantic search"),
        ("Telegram", "AI auto-responder from your account, 14 personas, voice clone, vision analysis"),
        ("LoRA", "Fine-tune LLMs with Unsloth, 16 base models, live training monitor, JSONL datasets"),
        ("SMM", "Social media management: trend scanning, post generation, 7-platform publishing, analytics"),
    ]
    for name, desc in tabs:
        pdf.bullet_bold_val(name + ":", " " + desc)


def sec_dashboard(pdf):
    pdf.add_page()
    pdf.section_header("2", "Dashboard")
    pdf.body_text(
        "The Dashboard is the operational nerve center of NeuralForge. It provides real-time "
        "hardware telemetry, service lifecycle management, and health alerting at a glance. "
        "All data refreshes automatically via WebSocket connection."
    )

    pdf.sub_header("Live Metrics")
    pdf.bullet("GPU: VRAM usage, temperature, fan speed, power draw (nvidia-smi real-time)")
    pdf.bullet("RAM: total / used / available / swap usage")
    pdf.bullet("CPU: per-core utilization, load averages")
    pdf.bullet("Disk: mount points, free space, usage percentage per partition")

    pdf.sub_header("Service Management")
    pdf.body_text(
        "Each of the 11 modules can be started and stopped individually from the UI. Services "
        "marked as heavy_gpu belong to an exclusive GPU group \u2014 starting one automatically "
        "stops others in the same group to prevent VRAM exhaustion. Service types include "
        "systemd units, direct processes, and Docker containers."
    )

    pdf.sub_header("Monitoring Widgets")
    pdf.bullet("Ollama Models \u2014 currently loaded models, parameter count, quantization level")
    pdf.bullet("GPU Processes \u2014 per-process VRAM consumption with PID and command")
    pdf.bullet("Qdrant Collections \u2014 vector count, embedding dimension, health status")
    pdf.bullet("Storage Overview \u2014 disk usage breakdown by category (models, logs, data, cache)")

    pdf.sub_header("Health Alert Thresholds")
    thresholds = [
        ("GPU Temperature", "> 85\u00b0C", "CRITICAL", "> 75\u00b0C", "WARNING"),
        ("VRAM Usage", "> 95%", "CRITICAL", "> 85%", "WARNING"),
        ("RAM Available", "< 2 GB", "CRITICAL", "< 5 GB", "WARNING"),
        ("Disk Free", "< 10 GB", "CRITICAL", "< 50 GB", "WARNING"),
    ]
    cols = [("Metric", 35), ("Critical When", 35), ("Level", 25), ("Warning When", 35), ("Level", 0)]
    pdf.table_header(cols)
    ws = [35, 35, 25, 35, 0]
    for i, row in enumerate(thresholds):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.sub_header("Quick Actions")
    pdf.bullet_bold_val("Start Basics:", " Launch Ollama + Qdrant + Open WebUI in one click")
    pdf.bullet_bold_val("Stop Heavy:", " Shut down all heavy_gpu services to free VRAM instantly")
    pdf.bullet_bold_val("Free VRAM:", " Unload all Ollama models from GPU memory without stopping the service")

    pdf.sub_header("API Keys Management")
    pdf.body_text(
        "API keys and tokens are stored in secrets.json and managed through the Dashboard UI. "
        "Keys are masked in the interface and can be added, edited, or removed without touching "
        "config files. Supported keys include: Telegram API hash, Twitter OAuth tokens, "
        "LinkedIn, Facebook, Instagram, Threads, and Bluesky credentials."
    )


def sec_modules(pdf):
    pdf.add_page()
    pdf.section_header("3", "Module System")
    pdf.body_text(
        "NeuralForge uses a YAML-based module system for declaring, configuring, and managing services. "
        "Each module specifies its type (systemd, process, or docker), port, VRAM requirements, "
        "health check URL, and GPU group membership."
    )

    pdf.sub_header("Module Registry (11 Services)")
    modules = [
        ("Ollama",     "systemd", "11434", "\u2014",       "\u2014",       "LLM inference engine (30+ models)"),
        ("ComfyUI",    "process", "8188",  "8\u201322 GB", "heavy_gpu", "Image generation (FLUX Klein)"),
        ("Wan2GP",     "process", "7860",  "12\u201324 GB","heavy_gpu", "Video generation (Wan 2.2)"),
        ("Hunyuan3D",  "process", "7870",  "13\u201320 GB","heavy_gpu", "3D model generation"),
        ("ACE-Step",   "process", "7880",  "4\u20136 GB",  "\u2014",       "AI music generation"),
        ("Qwen3-TTS",  "process", "7890",  "4\u20135 GB",  "\u2014",       "Text-to-speech / voice clone"),
        ("Whisper",    "process", "7895",  "2\u201310 GB", "\u2014",       "Speech-to-text (99 languages)"),
        ("Qdrant",     "docker",  "6333",  "\u2014",       "\u2014",       "Vector database for RAG"),
        ("Open WebUI", "docker",  "8080",  "\u2014",       "\u2014",       "Chat interface for Ollama"),
        ("Perplexica", "docker",  "3000",  "\u2014",       "\u2014",       "AI-powered web search"),
        ("SearXNG",    "docker",  "8888",  "\u2014",       "\u2014",       "Meta search engine"),
    ]
    cols = [("Service", 26), ("Type", 18), ("Port", 13), ("VRAM", 22), ("Group", 22), ("Description", 0)]
    pdf.table_header(cols)
    ws = [26, 18, 13, 22, 22, 0]
    for i, row in enumerate(modules):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.info_box("Services in the same heavy_gpu group are mutually exclusive. Starting ComfyUI will auto-stop Wan2GP and Hunyuan3D to free VRAM.")

    pdf.sub_header("Example Module YAML")
    pdf.code_block(
        'comfyui:\n'
        '  name: "ComfyUI"\n'
        '  type: process\n'
        '  port: 8188\n'
        '  vram_min: 8\n'
        '  vram_max: 22\n'
        '  group: heavy_gpu\n'
        '  start_cmd: "python main.py --listen 0.0.0.0 --port 8188"\n'
        '  workdir: "/opt/ComfyUI"\n'
        '  health_check: "http://localhost:8188/system_stats"'
    )

    pdf.sub_header("Module Lifecycle")
    pdf.body_text(
        "Modules transition through states: stopped -> starting -> running -> stopping -> stopped. "
        "Health checks poll the configured URL every 5 seconds. If a process crashes, the status "
        "automatically updates. Logs are captured to /tmp/ai-panel-logs/{module}.log and the last "
        "50 lines are available via the API."
    )


def sec_models(pdf):
    pdf.add_page()
    pdf.section_header("4", "AI Model Stack")
    pdf.body_text(
        "NeuralForge manages 30+ AI models across six categories. All LLMs are served through Ollama, "
        "while specialized models (vision, audio, generation) run as dedicated services."
    )

    pdf.sub_header("Large Language Models (via Ollama)")
    llms = [
        ("Nemotron 3 Nano 30B",  "19 GB",  "~25 tok/s", "NVIDIA reasoning, 1M context window"),
        ("Qwen 3.5 35B-A3B",    "3.5 GB", "112 tok/s",  "MoE architecture, fast general purpose"),
        ("Qwen 3.5 27B",        "17 GB",  "~30 tok/s",  "Main workhorse, excellent multilingual"),
        ("Qwen 3.5 9B",         "6.6 GB", "~60 tok/s",  "Lightweight, good for quick tasks"),
        ("Gemma 3 27B",         "17 GB",  "~28 tok/s",  "Google, 140 languages, multimodal"),
        ("DeepSeek-R1 32B",     "20 GB",  "~22 tok/s",  "Chain-of-thought reasoning"),
        ("DeepSeek-R1 14B",     "9 GB",   "~45 tok/s",  "Lightweight reasoning model"),
        ("Phi-4 Reasoning 14B", "9 GB",   "~40 tok/s",  "Microsoft, math & logic specialist"),
        ("Qwen 2.5 Coder 32B",  "20 GB",  "~24 tok/s",  "Code gen, 92.7% HumanEval"),
        ("Mistral Small 24B",   "15 GB",  "~35 tok/s",  "Fast, balanced quality/speed"),
        ("Phi 4 14B",           "9 GB",   "~42 tok/s",  "Compact general purpose"),
        ("Command R 35B",       "21 GB",  "~20 tok/s",  "Cohere, optimized for RAG"),
        ("Llama 3.1 70B",       "42 GB",  "~8 tok/s",   "Max quality, requires CPU offload"),
    ]
    cols = [("Model", 48), ("VRAM", 18), ("Speed", 22), ("Use Case", 0)]
    pdf.table_header(cols)
    ws = [48, 18, 22, 0]
    for i, row in enumerate(llms):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.sub_header("Vision Models")
    vis = [
        ("MiniCPM-V 8B",     "5.5 GB", "Telegram bot photo analysis, auto VRAM swap"),
        ("Qwen3-VL 8B",      "5.5 GB", "Agent tool analyze_image, video understanding"),
    ]
    cols = [("Model", 48), ("VRAM", 18), ("Use Case", 0)]
    pdf.table_header(cols)
    ws = [48, 18, 0]
    for i, row in enumerate(vis):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.sub_header("Embedding Models")
    emb = [
        ("bge-m3 (ONNX GPU)", "~1 GB", "1800 docs/s", "RAG indexing, 180x faster than Ollama"),
    ]
    cols = [("Model", 48), ("VRAM", 18), ("Throughput", 22), ("Notes", 0)]
    pdf.table_header(cols)
    ws = [48, 18, 22, 0]
    for i, row in enumerate(emb):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.sub_header("Audio Models")
    aud = [
        ("Whisper (large-v3)", "2\u201310 GB", "Speech-to-text, 99 languages"),
        ("Qwen3-TTS",         "4\u20135 GB",  "Text-to-speech, voice clone from 3s sample"),
        ("ACE-Step",           "4\u20136 GB",  "AI music generation from text prompts"),
    ]
    cols = [("Model", 48), ("VRAM", 22), ("Description", 0)]
    pdf.table_header(cols)
    ws = [48, 22, 0]
    for i, row in enumerate(aud):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.sub_header("Generation Models")
    gen = [
        ("FLUX Klein",    "8\u201322 GB",  "ComfyUI", "Fast image gen, SDXL-quality"),
        ("Wan 2.2",       "12\u201324 GB", "Wan2GP",  "Video from text/image prompts"),
        ("Hunyuan3D v2",  "13\u201320 GB", "Service", "3D model generation"),
    ]
    cols = [("Model", 40), ("VRAM", 22), ("Engine", 22), ("Notes", 0)]
    pdf.table_header(cols)
    ws = [40, 22, 22, 0]
    for i, row in enumerate(gen):
        pdf.table_row(row, ws, i)


def sec_agents(pdf):
    pdf.add_page()
    pdf.section_header("5", "AI Agents")
    pdf.body_text(
        "The Agent system provides specialized AI roles that can work solo, in sequential teams, "
        "or under an AI orchestrator. Each agent has a defined persona, configurable tool access, "
        "and produces structured output. Agents are powered by the universal.py engine and support "
        "file uploads, PDF generation, and persistent task history."
    )

    pdf.sub_header("13 Agent Roles")
    roles = [
        ("Researcher",       "Deep web research, source validation",  "qwen3.5:35b-a3b"),
        ("Programmer",       "Code generation, review, debugging",    "qwen2.5-coder:32b"),
        ("Data Analyst",     "CSV/JSON analysis, visualization",      "qwen3.5:27b"),
        ("Content Manager",  "Writes texts, articles, blog posts",    "qwen3.5:27b"),
        ("Summarizer",       "Text condensation, key point extract",  "qwen3.5:9b"),
        ("Critic-Editor",    "Fact checking, quality improvement",    "qwen3.5:27b"),
        ("Translator",       "RU, EN, ET, DE, FR, ES + 5 more",      "qwen3.5:27b"),
        ("Email Assistant",  "Professional email drafting",           "qwen3.5:9b"),
        ("Tester",           "Test case generation, bug finding",     "qwen2.5-coder:32b"),
        ("Trade Analyst",    "Market and financial analysis",         "qwen3.5:27b"),
        ("Tutor",            "Educational step-by-step guides",       "qwen3.5:27b"),
        ("Security Auditor", "Vulnerability assessment, code audit",  "qwen2.5-coder:32b"),
        ("Custom Agent",     "Full customization of role + tools",    "user choice"),
    ]
    cols = [("Role", 32), ("Description", 62), ("Default Model", 0)]
    pdf.table_header(cols)
    ws = [32, 62, 0]
    for i, row in enumerate(roles):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.sub_header("9 Agent Tools")
    tools = [
        ("web_search",     "Search the web via SearXNG / Perplexica"),
        ("read_url",       "Fetch and parse any web page content"),
        ("run_python",     "Execute Python code in sandboxed environment"),
        ("read_file",      "Read local files on the server"),
        ("write_file",     "Write / create files on the server"),
        ("analyze_file",   "Deep analysis of documents (CSV, JSON, etc.)"),
        ("analyze_image",  "Vision model image understanding"),
        ("rag_search",     "Search RAG knowledge base collections"),
        ("deep_scrape",    "Multi-page website scraping with depth control"),
    ]
    cols = [("Tool ID", 30), ("Description", 0)]
    pdf.table_header(cols)
    ws = [30, 0]
    for i, row in enumerate(tools):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.sub_header("3 Execution Modes")
    pdf.bullet_bold_val("Solo:", " Single agent runs with access to all enabled tools. Good for focused tasks.")
    pdf.bullet_bold_val("Team:", " Sequential chain \u2014 each agent receives the prior agent's output as context. "
                        "Example: Researcher -> Writer -> Critic produces researched, polished content.")
    pdf.bullet_bold_val("Orchestrator:", " AI meta-agent auto-selects agents and tools based on the task. "
                        "Retries if quality score < 7/10. Fully autonomous multi-step workflows.")

    pdf.sub_header("15 Team Presets")
    presets = [
        "Research & Write", "Code Review Pipeline", "Full Article Workflow",
        "Data Report", "Security Audit", "Translation Chain",
        "Email Draft & Review", "Test Generation", "Market Analysis",
        "Tutorial Creation", "Code + Test + Review", "Summarize & Translate",
        "Content + SEO", "Deep Research", "Custom Chain",
    ]
    half = (len(presets) + 1) // 2
    for i in range(half):
        pdf.set_font("DejaVu", "", 8.5)
        pdf.set_text_color(*C_TEXT)
        pdf.set_x(15)
        pdf.cell(4, 5, "\u2022")
        pdf.cell(80, 5, presets[i])
        if i + half < len(presets):
            pdf.cell(4, 5, "\u2022")
            pdf.cell(80, 5, presets[i + half])
        pdf.ln(5)


def sec_rag(pdf):
    pdf.add_page()
    pdf.section_header("6", "RAG (Retrieval-Augmented Generation)")
    pdf.body_text(
        "The RAG module enables knowledge-augmented conversations by indexing your documents "
        "into a Qdrant vector database and retrieving relevant context at query time. It uses "
        "ONNX-accelerated GPU embeddings for indexing throughput that makes large-scale document "
        "processing practical."
    )

    pdf.sub_header("Embedding Performance Comparison")
    perf = [
        ("bge-m3 ONNX GPU",  "1,800 docs/sec", "~1 GB",   "Default, production-grade"),
        ("Ollama nomic-embed","10 docs/sec",    "~2 GB",   "Slow, not recommended"),
        ("CPU-only bge-m3",   "50 docs/sec",    "0 GPU",   "Fallback when GPU busy"),
    ]
    cols = [("Engine", 42), ("Throughput", 32), ("VRAM", 20), ("Notes", 0)]
    pdf.table_header(cols)
    ws = [42, 32, 20, 0]
    for i, row in enumerate(perf):
        pdf.table_row(row, ws, i)
    pdf.ln(2)
    pdf.info_box("ONNX GPU embedding is 180x faster than Ollama-based embedding. Indexing 10,000 documents takes ~5.5 seconds vs ~17 minutes.")

    pdf.sub_header("Supported Document Formats")
    fmts = [
        ("PDF",  ".pdf",  "Text extraction with page number tracking"),
        ("Text", ".txt",  "Plain text, line-based chunking"),
        ("Markdown", ".md", "Markdown with header-aware splitting"),
        ("Word", ".docx", "Microsoft Word document extraction"),
        ("CSV",  ".csv",  "Tabular data, row-level chunking"),
        ("HTML", ".html", "Web page content extraction, tag stripping"),
    ]
    cols = [("Format", 25), ("Extension", 20), ("Processing", 0)]
    pdf.table_header(cols)
    ws = [25, 20, 0]
    for i, row in enumerate(fmts):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.sub_header("Key Features")
    pdf.bullet("Multi-collection search \u2014 query across multiple knowledge bases simultaneously")
    pdf.bullet("Chat with citations \u2014 responses include source document references with page numbers")
    pdf.bullet("Upload & Index \u2014 drag-and-drop file upload with instant indexing")
    pdf.bullet("Directory indexing \u2014 recursively index entire folders")
    pdf.bullet("Collection management \u2014 create, browse, and delete collections from the UI")
    pdf.bullet("Export to Markdown \u2014 export conversation with sources for archiving")
    pdf.bullet("Embedding cache \u2014 avoid re-embedding unchanged documents")

    pdf.sub_header("RAG Chat API Example")
    pdf.code_block(
        'curl -X POST http://localhost:9000/api/rag/chat \\\n'
        '  -H "Content-Type: application/json" \\\n'
        '  -d \'{\n'
        '    "query": "What are the requirements for residency?",\n'
        '    "collection": "estonian_laws",\n'
        '    "model": "qwen3.5:27b",\n'
        '    "language": "english"\n'
        '  }\''
    )

    pdf.sub_header("Architecture Details")
    pdf.body_text(
        "Documents are split into chunks (default 512 tokens with 50-token overlap), "
        "embedded using bge-m3, and stored in Qdrant with metadata (source file, page number, "
        "chunk index). At query time, the user question is embedded and the top-K most similar "
        "chunks are retrieved (default K=5). These chunks are injected into the LLM prompt as "
        "context, and the model generates an answer with citations."
    )


def sec_telegram(pdf):
    pdf.add_page()
    pdf.section_header("7", "Telegram AI Bot")
    pdf.body_text(
        "The Telegram module turns your Telegram account into an AI-powered conversational agent "
        "using Telethon (User API). It responds from your own account with configurable personas, "
        "supporting text, voice messages (with voice cloning), and photo analysis."
    )

    pdf.sub_header("14 Built-in Personas")
    personas = [
        ("#1",  "Philosopher",        "Existential sage mixing Nietzsche with memes"),
        ("#2",  "Street Philosopher", "Street-smart guy with unexpectedly deep thoughts"),
        ("#3",  "IT Demon",           "Perceives reality as code, people as processes"),
        ("#4",  "Granny from 2077",   "Caring grandma from a cyberpunk future"),
        ("#5",  "Noir Detective",     "Hard-boiled 40s detective in modern reality"),
        ("#6",  "Nerd Pirate",        "Pirate sailing the internet seeking knowledge"),
        ("#7",  "Cat Overlord",       "Arrogant cat, considers humans as servants"),
        ("#8",  "Conspiracy Nut",     "Sees absurd conspiracies everywhere (+ voice mode)"),
        ("#9",  "Budget Shakespeare", "Pompous theatrical language about mundane things"),
        ("#10", "Polite Zombie",      "Craves brains but discusses it with manners"),
        ("#11", "Corporate Bot",      "Parody manager: everything is KPIs and synergy"),
        ("#12", "Meme Capybara",      "Maximum zen and chill (attaches capybara photos)"),
        ("#13", "Crypto Maniac",      "Deranged crypto investor, emotional rollercoaster"),
        ("#14", "Custom Character",   "User-defined personality and system prompt"),
    ]
    cols = [("N", 8), ("Persona", 32), ("Style / Description", 0)]
    pdf.table_header(cols)
    ws = [8, 32, 0]
    for i, row in enumerate(personas):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.sub_header("Voice Clone Pipeline")
    pdf.code_block(
        "Incoming voice msg\n"
        "   |-> ffmpeg (decode OGG to WAV)\n"
        "   |-> Whisper STT (speech to text, auto language detect)\n"
        "   |-> LLM (generate response in active persona's style)\n"
        "   |-> Qwen3-TTS (clone sender's voice from 3-second sample)\n"
        "   |-> ffmpeg (encode WAV to OGG Opus)\n"
        "   |-> Send voice reply in cloned voice"
    )

    pdf.sub_header("Vision Pipeline")
    pdf.code_block(
        "Incoming photo\n"
        "   |-> Auto-unload current Ollama models (free VRAM)\n"
        "   |-> Load MiniCPM-V 8B (vision model)\n"
        "   |-> Analyze image + generate response in persona style\n"
        "   |-> Unload vision model, restore previous model\n"
        "   |-> Send text reply"
    )

    pdf.sub_header("Features")
    pdf.bullet("Automatic language detection \u2014 responds in the sender's language")
    pdf.bullet("5-message conversation memory per chat for contextual replies")
    pdf.bullet("Cooldown system (30s default) to prevent spam and rate limiting")
    pdf.bullet("Session logging for debugging, review, and conversation export")
    pdf.bullet("CRUD for custom personas via panel UI \u2014 create unlimited characters")
    pdf.bullet("Per-persona voice reply toggle \u2014 some personas voice-only by default")
    pdf.bullet("Capybara mode \u2014 attaches random capybara photo to every reply")


def sec_lora(pdf):
    pdf.add_page()
    pdf.section_header("8", "LoRA Fine-Tuning")
    pdf.body_text(
        "The LoRA tab provides a web interface for fine-tuning language models using Unsloth, "
        "which delivers 2x training speed and 60% less memory usage compared to standard "
        "PyTorch training. Adapters can be exported and used directly with Ollama."
    )

    pdf.sub_header("16 Supported Base Models")
    lora_models = [
        ("unsloth/Nemotron-Mini-4B-Instruct", "4B",  "~5 GB",  "~15 min/epoch"),
        ("unsloth/Llama-3.1-8B-Instruct",     "8B",  "~8 GB",  "~25 min/epoch"),
        ("unsloth/Llama-3.2-3B-Instruct",     "3B",  "~4 GB",  "~10 min/epoch"),
        ("unsloth/Llama-3.2-1B-Instruct",     "1B",  "~2 GB",  "~5 min/epoch"),
        ("unsloth/Qwen2.5-7B-Instruct",       "7B",  "~7 GB",  "~20 min/epoch"),
        ("unsloth/Qwen2.5-32B-Instruct",      "32B", "~22 GB", "~90 min/epoch"),
        ("unsloth/gemma-2-9b-it",             "9B",  "~9 GB",  "~28 min/epoch"),
        ("unsloth/gemma-2-2b-it",             "2B",  "~3 GB",  "~8 min/epoch"),
        ("unsloth/Mistral-7B-Instruct-v0.3",  "7B",  "~7 GB",  "~20 min/epoch"),
        ("unsloth/Phi-3.5-mini-instruct",     "3.8B","~5 GB",  "~12 min/epoch"),
        ("unsloth/Phi-4",                     "14B", "~12 GB", "~45 min/epoch"),
        ("unsloth/DeepSeek-R1-Distill-Qwen-7B","7B", "~7 GB",  "~22 min/epoch"),
        ("unsloth/DeepSeek-R1-Distill-Qwen-14B","14B","~12 GB","~48 min/epoch"),
        ("unsloth/Llama-3.3-70B-Instruct",    "70B", "~22 GB", "~180 min (4bit)"),
        ("unsloth/SmolLM2-1.7B-Instruct",     "1.7B","~2.5 GB","~7 min/epoch"),
        ("unsloth/Llama-3.1-8B",              "8B",  "~8 GB",  "~25 min/epoch"),
    ]
    cols = [("Model", 72), ("Params", 12), ("VRAM", 16), ("Train Time*", 0)]
    pdf.table_header(cols)
    ws = [72, 12, 16, 0]
    for i, row in enumerate(lora_models):
        pdf.table_row(row, ws, i)

    pdf.ln(2)
    pdf.info_box("* Training times are approximate for 1000-sample datasets on RTX 3090. Actual time depends on dataset size, sequence length, and batch size.", C_INFO_AMBER)

    pdf.sub_header("Training Parameters")
    pdf.bullet_bold_val("Rank (r):", " LoRA rank dimension (4\u2013128, default 16)")
    pdf.bullet_bold_val("Alpha:", " Scaling factor (8\u2013256, default 32)")
    pdf.bullet_bold_val("Epochs:", " Training iterations (1\u201350)")
    pdf.bullet_bold_val("Batch Size:", " Samples per gradient step")
    pdf.bullet_bold_val("Learning Rate:", " Optimizer step size (e.g. 2e-4)")
    pdf.bullet_bold_val("Max Seq Length:", " Context window for training samples (512\u201332768)")

    pdf.sub_header("Workflow")
    pdf.body_text(
        "1. Select base model from the 16 available options.\n"
        "2. Upload training data in JSONL format (instruction/input/output fields).\n"
        "3. Configure training hyperparameters.\n"
        "4. Start training \u2014 output streams live to the UI.\n"
        "5. Monitor loss curves in real-time.\n"
        "6. Stop early if convergence reached.\n"
        "7. Export LoRA adapter for use with Ollama."
    )

    pdf.sub_header("Dataset Format")
    pdf.body_text("Training data must be in JSONL format with the following structure:")
    pdf.code_block(
        '{"instruction": "Translate to French", "input": "Hello", "output": "Bonjour"}\n'
        '{"instruction": "Summarize", "input": "Long text...", "output": "Summary..."}\n'
        '{"instruction": "Fix the bug", "input": "def f(x):\\n  return x+", "output": "def f(x):\\n  return x + 1"}'
    )

    pdf.sub_header("Output & Export")
    pdf.body_text(
        "After training completes, the LoRA adapter is saved to the output directory. "
        "You can merge it with the base model and create an Ollama-compatible GGUF file. "
        "The adapter typically adds only 50-200 MB on top of the base model, making it "
        "efficient to store multiple fine-tuned variants."
    )
    pdf.info_box("LoRA adapters are small (50-200 MB) and can be swapped without reloading the full base model. Train multiple adapters for different tasks.")


def sec_generation(pdf):
    pdf.add_page()
    pdf.section_header("9", "Generation Pipeline")
    pdf.body_text(
        "NeuralForge provides an integrated pipeline for generating images, videos, and 3D models. "
        "The system automatically manages VRAM between pipeline stages, stopping one heavy service "
        "before starting the next."
    )

    pdf.sub_header("Pipeline Stages")
    stages = [
        ("1. Image", "ComfyUI + FLUX Klein", "8\u201322 GB", "Text-to-image, various styles"),
        ("2. Video", "Wan2GP + Wan 2.2",     "12\u201324 GB", "Image-to-video or text-to-video"),
        ("3. 3D",    "Hunyuan3D v2",         "13\u201320 GB", "Image-to-3D mesh generation"),
    ]
    cols = [("Step", 22), ("Engine", 40), ("VRAM", 22), ("Description", 0)]
    pdf.table_header(cols)
    ws = [22, 40, 22, 0]
    for i, row in enumerate(stages):
        pdf.table_row(row, ws, i)

    pdf.ln(2)
    pdf.info_box("Full pipeline runs sequentially on a single GPU. Each stage auto-stops the previous heavy_gpu service before starting.")

    pdf.sub_header("Automation Level")
    pdf.body_text(
        "The pipeline is fully automated: provide a text prompt and it generates an image, "
        "animates it into a video, then creates a 3D model. Each stage can also be run "
        "independently via API calls."
    )

    pdf.sub_header("5 Built-in Examples")
    examples = [
        ("Robot", "Futuristic humanoid robot in a neon-lit cityscape"),
        ("Dragon", "Fantasy dragon with detailed iridescent scales"),
        ("Car", "Concept sports car with aerodynamic design"),
        ("Cat", "Photorealistic Persian cat portrait in studio lighting"),
        ("Sword", "Ornate fantasy sword with glowing rune engravings"),
    ]
    for name, desc in examples:
        pdf.bullet_bold_val(name + ":", " " + desc)

    pdf.sub_header("API Usage Example")
    pdf.code_block(
        'curl -X POST http://localhost:9000/api/smm/generate-image \\\n'
        '  -H "Content-Type: application/json" \\\n'
        '  -d \'{"prompt": "a futuristic robot in a neon city"}\''
    )


def sec_smm(pdf):
    pdf.add_page()
    pdf.section_header("10", "SMM AI Department")
    pdf.body_text(
        "The SMM module is a complete AI-powered social media management system. It covers the "
        "full content lifecycle: trend discovery, AI-generated posts with images, scheduling, "
        "multi-platform publishing, and engagement analytics. The system supports brand profiles "
        "with custom voice, tone, and target audience settings."
    )

    pdf.sub_header("Workflow Overview")
    pdf.code_block(
        "Trend Scanning (6 sources)\n"
        "   |-> Topic Selection\n"
        "   |-> AI Post Generation (2-pass: research + brand voice)\n"
        "   |-> Image Generation (FLUX Klein via ComfyUI)\n"
        "   |-> Content Queue (edit, schedule, reorder)\n"
        "   |-> Multi-Platform Publish (7 platforms)\n"
        "   |-> Analytics Dashboard (engagement tracking)"
    )

    pdf.sub_header("7 Supported Platforms")
    platforms = [
        ("Telegram",  "Bot API",   "Text + image, channel/group posting"),
        ("Twitter/X", "OAuth 2.0", "Tweet + media, thread support"),
        ("LinkedIn",  "OAuth 2.0", "Article + image, company pages"),
        ("Facebook",  "Graph API", "Post + image, page publishing"),
        ("Instagram", "Graph API", "Image + caption, carousel support"),
        ("Threads",   "Graph API", "Text + image posting"),
        ("Bluesky",   "AT Proto",  "Text + image, alt text support"),
    ]
    cols = [("Platform", 25), ("Auth", 22), ("Capabilities", 0)]
    pdf.table_header(cols)
    ws = [25, 22, 0]
    for i, row in enumerate(platforms):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.sub_header("Key Features")
    pdf.bullet("6 trend sources: Google Trends, Reddit, HackerNews, GitHub Trending, arXiv, custom RSS")
    pdf.bullet("2-pass post generation: first draft with research context, then polish with brand voice")
    pdf.bullet("AI image generation: auto-generate visuals matching post content via FLUX Klein")
    pdf.bullet("Batch generation: create multiple posts in one operation for content calendaring")
    pdf.bullet("Content queue with drag-and-drop reordering and scheduled auto-publishing")
    pdf.bullet("Calendar view: visual timeline of scheduled and published content")
    pdf.bullet("Token health monitoring: track expiration and validity of all platform tokens")
    pdf.bullet("Per-post analytics: engagement metrics, reach, and click tracking")
    pdf.bullet("GitHub repository search: find trending repos for tech content")
    pdf.bullet("Profile management: multiple brand profiles with independent settings")

    pdf.sub_header("Content Generation Workflow")
    pdf.body_text(
        "Post generation uses a 2-pass approach: First, the AI researches the topic using "
        "trend data, web search results, and profile context to create a draft. Then, a second "
        "pass applies the brand's voice, tone, and formatting rules to produce the final post. "
        "Each post can be customized for the target platform (different length, hashtags, format)."
    )

    pdf.sub_header("Auto-Scheduler")
    pdf.body_text(
        "The content queue supports scheduled publishing with configurable time slots. "
        "The calendar view shows a visual timeline of past, scheduled, and draft posts. "
        "Posts can be rescheduled via drag-and-drop. The auto-scheduler distributes "
        "batch-generated content across optimal posting times."
    )

    pdf.sub_header("API Usage Example")
    pdf.code_block(
        'curl -X POST http://localhost:9000/api/smm/generate \\\n'
        '  -H "Content-Type: application/json" \\\n'
        '  -d \'{\n'
        '    "profile_id": "neural_overlord",\n'
        '    "topic": "Latest advances in local LLMs",\n'
        '    "platforms": ["telegram", "twitter", "linkedin"]\n'
        '  }\''
    )


def sec_mcp(pdf):
    pdf.add_page()
    pdf.section_header("11", "MCP Server")
    pdf.body_text(
        "NeuralForge exposes 24 tools via the Model Context Protocol (MCP) for integration "
        "with Claude Code, Claude Desktop, and other MCP-compatible clients. The MCP server "
        "communicates with NeuralForge via its REST API."
    )

    pdf.sub_header("All 24 MCP Tools")
    mcp_tools = [
        ("get_system_status",    "Hardware metrics: GPU, RAM, CPU, disk, services"),
        ("start_service",        "Start a specific NeuralForge service by name"),
        ("stop_service",         "Stop a specific NeuralForge service by name"),
        ("rag_search",           "Semantic search across RAG collections"),
        ("rag_list_collections", "List all Qdrant vector collections"),
        ("rag_index_file",       "Index a single file into a collection"),
        ("rag_index_directory",  "Recursively index a directory"),
        ("ask_rag",              "Full RAG chat: retrieve + generate answer"),
        ("get_storage_info",     "Disk usage breakdown by service"),
        ("cleanup_storage",      "Clean logs/cache for a service"),
        ("finetune_status",      "Current LoRA training status and progress"),
        ("finetune_start",       "Start a LoRA fine-tuning run"),
        ("finetune_stop",        "Stop running LoRA training"),
        ("run_pipeline",         "Trigger image/video/3D generation pipeline"),
        ("run_backup",           "Create platform backup archive"),
        ("get_gpu_processes",    "List GPU processes with VRAM usage"),
        ("ollama_loaded_models", "Currently loaded Ollama models"),
        ("convert_audio",        "Convert audio between formats"),
        ("run_agent",            "Run a solo agent task"),
        ("run_agent_team",       "Run a team chain of agents"),
        ("run_orchestrator",     "Run the AI orchestrator"),
        ("stop_all_and_free_vram","Stop heavy services + unload models"),
        ("generate_image",       "Generate image via ComfyUI + FLUX"),
        ("check_health",         "Health check with alert status"),
    ]
    cols = [("Tool", 48), ("Description", 0)]
    pdf.table_header(cols)
    ws = [48, 0]
    for i, row in enumerate(mcp_tools):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.sub_header("MCP Configuration")
    pdf.body_text("Add to your Claude Code .mcp.json or claude_desktop_config.json:")
    pdf.code_block(
        '{\n'
        '  "mcpServers": {\n'
        '    "neuralforge": {\n'
        '      "command": "python",\n'
        '      "args": ["mcp_server.py"],\n'
        '      "cwd": "/home/user/ai-panel"\n'
        '    }\n'
        '  }\n'
        '}'
    )
    pdf.info_box("MCP tools allow Claude Code to directly control your NeuralForge instance: start services, run agents, search RAG, and more.")

    pdf.sub_header("MCP Resource")
    pdf.body_text(
        "In addition to tools, the MCP server exposes a status://system resource that provides "
        "a read-only snapshot of the entire system state including all service statuses, GPU "
        "metrics, loaded models, and active tasks. MCP clients can subscribe to this resource "
        "for real-time system awareness."
    )

    pdf.sub_header("Usage Example with Claude Code")
    pdf.body_text(
        "Once configured, you can ask Claude Code to interact with NeuralForge directly:"
    )
    pdf.code_block(
        '> "Start Ollama and check what models are loaded"\n'
        '  -> Claude calls: start_service("ollama")\n'
        '  -> Claude calls: ollama_loaded_models()\n'
        '  -> Returns list of loaded models with VRAM usage\n'
        '\n'
        '> "Index my project docs into RAG and ask about the API"\n'
        '  -> Claude calls: rag_index_directory("/path/to/docs")\n'
        '  -> Claude calls: ask_rag("How does the API work?")\n'
        '  -> Returns answer with source citations'
    )


def sec_installation(pdf):
    pdf.add_page()
    pdf.section_header("12", "Installation & Startup")

    pdf.sub_header("Prerequisites")
    pdf.bullet("Ubuntu 22.04+ or compatible Linux distribution")
    pdf.bullet("NVIDIA GPU with 12+ GB VRAM (24 GB recommended)")
    pdf.bullet("Python 3.10+ with pip and venv")
    pdf.bullet("Docker and Docker Compose v2")
    pdf.bullet("NVIDIA Container Toolkit (for GPU access in Docker containers)")
    pdf.bullet("ffmpeg (for audio processing)")

    pdf.sub_header("Install Process")
    pdf.code_block(
        "git clone https://github.com/user/neuralforge.git\n"
        "cd neuralforge\n"
        "chmod +x install.sh\n"
        "./install.sh"
    )
    pdf.body_text(
        "The installer: 1) Installs system dependencies (Python packages, ffmpeg). "
        "2) Downloads service binaries and Docker images. 3) Patches paths for your environment. "
        "4) Generates configuration files. 5) Sets up systemd user service for auto-start."
    )

    pdf.sub_header("systemd User Service")
    pdf.code_block(
        "[Unit]\n"
        "Description=NeuralForge AI Platform\n"
        "After=network.target docker.service\n\n"
        "[Service]\n"
        "Type=simple\n"
        "WorkingDirectory=/home/user/ai-panel\n"
        "ExecStart=/usr/bin/python3 server.py\n"
        "Restart=always\n"
        "RestartSec=5\n\n"
        "[Install]\n"
        "WantedBy=default.target"
    )

    pdf.sub_header("Server Management")
    pdf.body_text("Control commands:")
    pdf.code_block(
        "# Start\n"
        "systemctl --user start ai-panel\n\n"
        "# Stop\n"
        "systemctl --user stop ai-panel\n\n"
        "# Restart (from API - preferred)\n"
        "curl -X POST http://localhost:9000/api/restart\n\n"
        "# View logs\n"
        "journalctl --user -u ai-panel -f"
    )
    pdf.info_box("Always prefer POST /api/restart over killing the server process. The API restart preserves state and performs clean shutdown.", C_INFO_AMBER)


def sec_api(pdf):
    pdf.add_page()
    pdf.section_header("13", "API Reference (69 Endpoints)")
    pdf.body_text(
        "NeuralForge exposes 69 REST API endpoints + 1 WebSocket at localhost:9000. All endpoints "
        "accept and return JSON. Below is the complete list organized by category, extracted "
        "directly from server.py and smm/routes.py."
    )

    for category, eps in REAL_ENDPOINTS.items():
        pdf.sub_header(category)
        cols = [("Method", 15), ("Endpoint", 78), ("Description", 0)]
        pdf.table_header(cols)

        pdf.set_font("DejaVuMono", "", 7)
        for i, (method, path, desc) in enumerate(eps):
            if pdf.get_y() > 268:
                pdf.add_page()
            bg = C_LIGHT_BG if i % 2 == 0 else C_WHITE
            pdf.set_fill_color(*bg)

            # Color-coded method
            if method == "GET":
                pdf.set_text_color(0, 150, 80)
            elif method == "POST":
                pdf.set_text_color(0, 100, 200)
            elif method == "DELETE":
                pdf.set_text_color(200, 50, 50)
            elif method == "PUT":
                pdf.set_text_color(200, 150, 0)
            elif method == "WS":
                pdf.set_text_color(140, 80, 200)
            pdf.set_font("DejaVuMono", "B", 7)
            pdf.cell(15, 5, " " + method, fill=True)

            pdf.set_text_color(*C_TEXT)
            pdf.set_font("DejaVuMono", "", 7)
            pdf.cell(78, 5, " " + path, fill=True)
            pdf.set_font("DejaVu", "", 7)
            pdf.cell(0, 5, " " + desc, fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)


def sec_requirements(pdf):
    pdf.add_page()
    pdf.section_header("14", "Hardware Requirements")

    pdf.sub_header("Hardware Specifications")
    cols = [("Component", 35), ("Minimum", 45), ("Recommended", 45), ("Tested On", 0)]
    pdf.table_header(cols)
    reqs = [
        ("GPU VRAM",  "12 GB",       "24 GB",           "RTX 3090 24GB"),
        ("RAM",       "16 GB",       "64+ GB",          "128 GB DDR4 ECC"),
        ("Disk",      "50 GB free",  "200+ GB SSD",     "2 TB NVMe RAID"),
        ("CPU",       "4+ cores",    "8+ cores",        "Threadripper PRO"),
        ("Network",   "Localhost",   "Gigabit",         "10 GbE"),
    ]
    ws = [35, 45, 45, 0]
    for i, row in enumerate(reqs):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.sub_header("Software Requirements")
    pdf.bullet_bold_val("OS:", " Ubuntu 22.04+ (tested on Ubuntu 24.04)")
    pdf.bullet_bold_val("Python:", " 3.10+ (3.12 recommended)")
    pdf.bullet_bold_val("Docker:", " 20.10+ with Docker Compose v2")
    pdf.bullet_bold_val("NVIDIA Driver:", " 535+ with CUDA 12.x")
    pdf.bullet_bold_val("NVIDIA Container Toolkit:", " Required for GPU access in Docker")
    pdf.bullet_bold_val("ffmpeg:", " Required for audio processing (voice clone, STT)")

    pdf.ln(2)
    pdf.sub_header("VRAM Usage Patterns")
    pdf.body_text(
        "Not all services run simultaneously. The heavy_gpu group ensures only one large service "
        "uses the GPU at a time. Typical usage patterns on a 24 GB GPU:"
    )
    patterns = [
        ("Chat + RAG",           "Ollama (4\u201316 GB) + Qdrant",       "8\u201318 GB"),
        ("Image Generation",     "ComfyUI + FLUX Klein",               "8\u201322 GB"),
        ("Video Generation",     "Wan2GP + Wan 2.2",                   "12\u201324 GB"),
        ("3D Generation",        "Hunyuan3D v2",                       "13\u201320 GB"),
        ("Telegram Bot (full)",  "Ollama + Whisper + TTS + Vision",    "12\u201318 GB"),
        ("LoRA Training",        "Unsloth + base model",               "5\u201322 GB"),
        ("Agent Workflow",       "Ollama + tools",                     "6\u201320 GB"),
    ]
    cols = [("Workload", 42), ("Services Used", 65), ("VRAM", 0)]
    pdf.table_header(cols)
    ws = [42, 65, 0]
    for i, row in enumerate(patterns):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.info_box("A 24 GB GPU (RTX 3090/4090) can run most features. 12 GB GPUs work with smaller models (9B) and careful VRAM management. The heavy_gpu mutex system prevents OOM crashes automatically.")

    pdf.sub_header("Port Allocation")
    ports = [
        ("9000",  "NeuralForge",  "Main web UI and API server"),
        ("11434", "Ollama",       "LLM inference API"),
        ("8188",  "ComfyUI",      "Image generation interface"),
        ("7860",  "Wan2GP",       "Video generation"),
        ("7870",  "Hunyuan3D",    "3D model generation"),
        ("7880",  "ACE-Step",     "Music generation"),
        ("7890",  "Qwen3-TTS",   "Text-to-speech / voice clone"),
        ("7895",  "Whisper",      "Speech-to-text"),
        ("6333",  "Qdrant",       "Vector database"),
        ("8080",  "Open WebUI",   "Chat interface"),
        ("3000",  "Perplexica",   "AI search"),
        ("8888",  "SearXNG",      "Meta search engine"),
    ]
    cols = [("Port", 16), ("Service", 30), ("Description", 0)]
    pdf.table_header(cols)
    ws = [16, 30, 0]
    for i, row in enumerate(ports):
        pdf.table_row(row, ws, i)

    pdf.ln(3)
    pdf.sub_header("Disk Space Breakdown")
    pdf.body_text("Approximate disk usage by component:")
    disk = [
        ("Ollama models",         "5-80 GB",   "Depends on model count and sizes"),
        ("ComfyUI + checkpoints", "10-30 GB",  "FLUX Klein checkpoint + VAE"),
        ("Wan2GP model",          "15-25 GB",  "Wan 2.2 video model weights"),
        ("Hunyuan3D model",       "10-20 GB",  "3D generation weights"),
        ("Docker images",         "5-10 GB",   "Qdrant, WebUI, Perplexica, SearXNG"),
        ("Python environments",   "3-8 GB",    "Virtual environments + packages"),
        ("User data",             "Variable",  "RAG collections, LoRA datasets, logs"),
    ]
    cols = [("Component", 45), ("Size", 22), ("Notes", 0)]
    pdf.table_header(cols)
    ws = [45, 22, 0]
    for i, row in enumerate(disk):
        pdf.table_row(row, ws, i)


def build_all_sections(pdf):
    """Build all content sections."""
    sec_overview(pdf)
    sec_dashboard(pdf)
    sec_modules(pdf)
    sec_models(pdf)
    sec_agents(pdf)
    sec_rag(pdf)
    sec_telegram(pdf)
    sec_lora(pdf)
    sec_generation(pdf)
    sec_smm(pdf)
    sec_mcp(pdf)
    sec_installation(pdf)
    sec_api(pdf)
    sec_requirements(pdf)


def main():
    # --- Pass 1: Build the document to discover page numbers ---
    pdf1 = NeuralForgePDF()
    pdf1.set_title("NeuralForge \u2014 Complete Platform Guide")
    pdf1.set_author("NeuralForge")
    build_cover(pdf1)
    build_toc(pdf1)  # placeholder TOC
    build_all_sections(pdf1)

    # Collect page numbers for each section
    page_map = {}
    for num, title, page, link in pdf1.toc_entries:
        page_map[num] = page

    # --- Pass 2: Rebuild with real TOC page numbers ---
    pdf = NeuralForgePDF()
    pdf.set_title("NeuralForge \u2014 Complete Platform Guide")
    pdf.set_author("NeuralForge")
    pdf.set_subject("Self-hosted AI Command Center Documentation")

    build_cover(pdf)
    build_toc(pdf, page_map)
    build_all_sections(pdf)

    pdf.output(OUTPUT)
    print(f"PDF generated: {OUTPUT}")
    print(f"Pages: {pdf.pages_count}")


if __name__ == "__main__":
    main()
