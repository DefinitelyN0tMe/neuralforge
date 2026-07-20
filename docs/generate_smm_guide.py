#!/usr/bin/env python3
"""Generate SMM AI Department Complete Technical Guide PDF."""

from fpdf import FPDF
from datetime import datetime

OUTPUT = "/home/definitelynotme/Desktop/ai-panel/docs/SMM_AI_Department_Guide.pdf"
FONT_DIR = "/usr/share/fonts/truetype/dejavu/"

# Colors
C_DARK = (15, 23, 42)        # #0f172a
C_ACCENT = (59, 130, 246)    # blue-500
C_ACCENT2 = (16, 185, 129)   # emerald-500
C_LIGHT_BG = (241, 245, 249) # slate-100
C_WHITE = (255, 255, 255)
C_TEXT = (30, 41, 59)         # slate-800
C_MUTED = (100, 116, 139)    # slate-500
C_SECTION_BG = (30, 41, 59)
C_ROW_ALT = (248, 250, 252)  # slate-50
C_ROW_EVEN = (255, 255, 255)
C_TABLE_HEAD = (30, 58, 138)
C_ORANGE = (234, 88, 12)
C_PURPLE = (139, 92, 246)


class SmmGuidePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=22)
        self.add_font("DejaVu", "", FONT_DIR + "DejaVuSans.ttf")
        self.add_font("DejaVu", "B", FONT_DIR + "DejaVuSans-Bold.ttf")
        self.add_font("DejaVu", "I", FONT_DIR + "DejaVuSans-Oblique.ttf")
        self.add_font("DejaVu", "BI", FONT_DIR + "DejaVuSans-BoldOblique.ttf")
        self.add_font("Mono", "", FONT_DIR + "DejaVuSansMono.ttf")
        self.add_font("Mono", "B", FONT_DIR + "DejaVuSansMono-Bold.ttf")
        self.toc_entries = []
        self.is_cover = False

    def header(self):
        if self.page_no() <= 2 or self.is_cover:
            return
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*C_MUTED)
        self.set_y(8)
        self.cell(95, 6, "SMM AI Department Guide | NeuralForge", align="L")
        self.cell(95, 6, f"Page {self.page_no()}", align="R")
        self.ln(2)
        self.set_draw_color(*C_ACCENT)
        self.set_line_width(0.4)
        self.line(10, 16, 200, 16)
        self.set_y(20)

    def footer(self):
        if self.page_no() <= 1 or self.is_cover:
            return
        self.set_y(-12)
        self.set_draw_color(200, 205, 215)
        self.set_line_width(0.2)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*C_MUTED)
        self.cell(0, 8, "NeuralForge Platform  |  Self-hosted AI Control Center  |  localhost:9000", align="C")

    def section_title(self, number, title):
        """Dark banner section header."""
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
        self.set_xy(16, y + 2)
        self.set_font("DejaVu", "B", 13)
        self.set_text_color(*C_WHITE)
        self.cell(0, 9, f"{number}. {title}")
        self.set_xy(10, y + 15)
        self.ln(2)

    def sub_title(self, text):
        self.ln(2)
        self.set_font("DejaVu", "B", 10.5)
        self.set_text_color(*C_ACCENT)
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*C_ACCENT2)
        self.set_line_width(0.4)
        self.line(10, self.get_y(), 75, self.get_y())
        self.ln(2)

    def sub_sub_title(self, text):
        self.ln(1)
        self.set_font("DejaVu", "B", 9.5)
        self.set_text_color(*C_ORANGE)
        self.cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body(self, text):
        self.set_font("DejaVu", "", 9)
        self.set_text_color(*C_TEXT)
        self.multi_cell(0, 5, text)
        self.ln(1)

    def bullet(self, text, indent=14):
        self.set_x(indent)
        self.set_font("DejaVu", "", 9)
        self.set_text_color(*C_TEXT)
        w = self.get_string_width(text) + 10
        self.cell(4, 5, "\u2022")
        self.multi_cell(176, 5, text)
        self.ln(0.5)

    def bullet_bold(self, bold, rest, indent=14):
        self.set_x(indent)
        self.set_font("DejaVu", "B", 9)
        self.set_text_color(*C_TEXT)
        bw = self.get_string_width(bold) + 1
        self.cell(bw, 5, bold)
        self.set_font("DejaVu", "", 9)
        self.multi_cell(176 - bw, 5, rest)
        self.ln(0.5)

    def code(self, text):
        self.ln(1)
        lines = text.split("\n")
        h = len(lines) * 4.2 + 5
        if self.get_y() + h > 270:
            self.add_page()
        y0 = self.get_y()
        self.set_fill_color(30, 35, 50)
        self.rect(12, y0, 186, h, "F")
        self.set_xy(15, y0 + 2.5)
        self.set_font("Mono", "", 7.5)
        self.set_text_color(200, 215, 240)
        for line in lines:
            self.cell(0, 4.2, line, new_x="LMARGIN", new_y="NEXT")
            self.set_x(15)
        self.set_xy(10, y0 + h + 2)
        self.ln(1)

    def info_box(self, text, color=None):
        if color is None:
            color = C_ACCENT
        self.ln(1)
        y = self.get_y()
        h = max(11, len(text) // 80 * 5 + 11)
        if y + h > 272:
            self.add_page()
            y = self.get_y()
        self.set_fill_color(*color)
        self.rect(12, y, 3, h, "F")
        bg = (min(255, 220 + color[0]//15), min(255, 230 + color[1]//15), min(255, 235 + color[2]//15))
        self.set_fill_color(*bg)
        self.rect(15, y, 183, h, "F")
        self.set_xy(18, y + 2)
        self.set_font("DejaVu", "I", 8.5)
        self.set_text_color(*C_TEXT)
        self.multi_cell(175, 4.5, text)
        self.set_xy(10, y + h + 2)
        self.ln(1)

    def table(self, headers, rows, col_widths=None):
        """Alternating-row table with proper widths."""
        if col_widths is None:
            total = 186
            col_widths = [total // len(headers)] * len(headers)
            # Adjust last column to fill
            col_widths[-1] = total - sum(col_widths[:-1])

        if self.get_y() + 8 + len(rows) * 6 > 272:
            self.add_page()

        # Header row
        self.set_fill_color(*C_TABLE_HEAD)
        self.set_font("DejaVu", "B", 8)
        self.set_text_color(*C_WHITE)
        x0 = 12
        y0 = self.get_y()
        for i, h in enumerate(headers):
            self.set_xy(x0, y0)
            self.cell(col_widths[i], 7, f" {h}", fill=True)
            x0 += col_widths[i]
        self.ln(7)

        # Data rows
        self.set_font("DejaVu", "", 7.5)
        for ri, row in enumerate(rows):
            if self.get_y() > 270:
                self.add_page()
            if ri % 2 == 0:
                self.set_fill_color(*C_ROW_ALT)
            else:
                self.set_fill_color(*C_ROW_EVEN)
            x0 = 12
            y0 = self.get_y()
            max_h = 6
            for ci, val in enumerate(row):
                self.set_xy(x0, y0)
                self.set_text_color(*C_TEXT)
                # Truncate if too long
                txt = str(val)
                self.cell(col_widths[ci], 6, f" {txt}", fill=True)
                x0 += col_widths[ci]
            self.ln(6)
        self.ln(2)


def build_cover(pdf):
    pdf.is_cover = True
    pdf.add_page()
    # Full dark background
    pdf.set_fill_color(*C_DARK)
    pdf.rect(0, 0, 210, 297, "F")

    # Decorative accent lines
    pdf.set_draw_color(*C_ACCENT)
    pdf.set_line_width(1.5)
    pdf.line(20, 50, 190, 50)
    pdf.set_draw_color(*C_ACCENT2)
    pdf.set_line_width(0.8)
    pdf.line(20, 53, 140, 53)

    # Title block
    pdf.set_xy(20, 65)
    pdf.set_font("DejaVu", "B", 32)
    pdf.set_text_color(*C_WHITE)
    pdf.cell(0, 18, "SMM AI Department")
    pdf.set_xy(20, 88)
    pdf.set_font("DejaVu", "", 16)
    pdf.set_text_color(*C_ACCENT)
    pdf.cell(0, 10, "Complete Technical Guide")
    pdf.set_xy(20, 103)
    pdf.set_font("DejaVu", "B", 13)
    pdf.set_text_color(*C_ACCENT2)
    pdf.cell(0, 10, "NeuralForge Platform")

    # Stats boxes
    stats = [
        ("7", "Platforms"),
        ("6", "Sources"),
        ("8", "Niches"),
        ("22", "API Endpoints"),
    ]
    box_w = 40
    gap = 3
    start_x = 20
    y_box = 130

    for i, (num, label) in enumerate(stats):
        x = start_x + i * (box_w + gap)
        # Box background
        pdf.set_fill_color(30, 41, 70)
        pdf.rect(x, y_box, box_w, 30, "F")
        # Top accent bar
        pdf.set_fill_color(*C_ACCENT)
        pdf.rect(x, y_box, box_w, 2, "F")
        # Number
        pdf.set_xy(x, y_box + 5)
        pdf.set_font("DejaVu", "B", 22)
        pdf.set_text_color(*C_WHITE)
        pdf.cell(box_w, 12, num, align="C")
        # Label
        pdf.set_xy(x, y_box + 18)
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(*C_MUTED)
        pdf.cell(box_w, 8, label, align="C")

    # Description block
    pdf.set_xy(20, 180)
    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(148, 163, 184)  # slate-400
    pdf.multi_cell(170, 6,
        "Automated social media management powered by local LLMs.\n"
        "Multi-source trend scanning, AI content generation, multi-platform publishing,\n"
        "analytics tracking, and batch scheduling for 7 platforms."
    )

    # Bottom info
    pdf.set_draw_color(*C_ACCENT)
    pdf.set_line_width(0.5)
    pdf.line(20, 220, 190, 220)

    pdf.set_xy(20, 228)
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(*C_MUTED)
    pdf.cell(85, 6, f"Version 2.0  |  {datetime.now().strftime('%B %Y')}")
    pdf.cell(85, 6, "Self-hosted  |  Ollama + FastAPI", align="R")

    pdf.set_xy(20, 238)
    pdf.set_font("Mono", "", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 6, "Tech: Python 3.12 | FastAPI | SQLite WAL | Ollama | ComfyUI | SearXNG")

    pdf.is_cover = False


def build_toc(pdf):
    """Replaced by build_toc_v2."""
    pass


def build_section_1(pdf):
    """System Architecture."""
    pdf.section_title("1", "System Architecture")
    pdf.body(
        "The SMM AI Department is a self-contained module within the NeuralForge platform. "
        "It provides end-to-end social media management: from trend discovery through AI content "
        "generation to multi-platform publishing and analytics tracking. The module is implemented "
        "as a FastAPI APIRouter mounted on the main NeuralForge server at localhost:9000."
    )
    pdf.sub_title("Core Components")
    pdf.bullet_bold("FastAPI Router: ", "All SMM endpoints under /api/smm/* prefix, mounted via APIRouter. "
                    "22 endpoints organized into 8 functional groups.")
    pdf.bullet_bold("SQLite Database: ", "WAL-mode DB (smm_data.db) for queue, trends, analytics. "
                    "Thread-local connections via threading.local() for safe concurrent access.")
    pdf.bullet_bold("JSON Profile Store: ", "Per-profile JSON files in smm_profiles/ directory. "
                    "Profiles contain sensitive API tokens and are kept out of the database by design.")
    pdf.bullet_bold("Ollama LLM Backend: ", "Local inference via Ollama API at localhost:11434. "
                    "Default model: qwen3.5:9b for generation, qwen3.5:27b for trend analysis.")
    pdf.bullet_bold("ComfyUI Integration: ", "Image generation through ComfyUI workflows at localhost:8188. "
                    "Output directory: /home/user/Desktop/ComfyUI/output/")
    pdf.bullet_bold("SearXNG: ", "Self-hosted meta-search engine at localhost:8888. "
                    "Used for web trend discovery across Google, Bing, and DuckDuckGo.")

    pdf.sub_title("Data Directories")
    pdf.table(
        ["Directory", "Purpose", "Storage Type"],
        [
            ["smm_profiles/", "Profile configurations with API credentials", "JSON files"],
            ["smm_trends/", "Trend scan debug logs, publish logs", "JSON files"],
            ["smm_trends/_publish_logs/", "Per-publish event logs for audit trail", "JSON files"],
            ["smm_queue/", "Legacy queue storage (migrated to SQLite)", "JSON (deprecated)"],
            ["smm_images/", "Generated post images and variants", "PNG/JPG files"],
            ["smm_data.db", "Main database: queue, trends, analytics", "SQLite WAL"],
        ],
        col_widths=[35, 95, 56]
    )

    pdf.sub_title("Request Flow")
    pdf.body(
        "The complete lifecycle of a social media post follows these stages:"
    )
    pdf.bullet("1. Profile creation via wizard (4-step UI flow: basics, platforms, schedule, style)")
    pdf.bullet("2. Trend scan: multi-source aggregation with intelligent niche routing (6 source types)")
    pdf.bullet("3. Scoring: composite score from source type, engagement, freshness, keyword density")
    pdf.bullet("4. Content generation: LLM creates platform-specific posts from scored trend data")
    pdf.bullet("5. Image generation: optional ComfyUI workflow with LLM-generated prompts")
    pdf.bullet("6. Queue management: draft -> approved -> scheduled -> published lifecycle")
    pdf.bullet("7. Preview & editing: per-platform preview with inline editing and character limits")
    pdf.bullet("8. Publishing: simultaneous dispatch to all connected platforms with rate limiting")
    pdf.bullet("9. Analytics: periodic collection of engagement metrics (likes, comments, views, shares)")
    pdf.bullet("10. Cleanup: automated purge of old published items and analytics data")

    pdf.sub_title("Module Dependencies")
    pdf.body(
        "The SMM module registers its dependencies via register_dependencies() at startup. "
        "This function receives load_modules_fn, start_module_fn, and stop_module_fn from the main "
        "server, initializes the SQLite database, and performs a one-time migration of any existing "
        "JSON queue/trend files into SQLite."
    )

    pdf.info_box(
        "Architecture note: Profiles are stored as JSON files (not in SQLite) because they contain "
        "sensitive API tokens. The _smm_strip_credentials() function masks all tokens before sending "
        "profile data to the frontend. Database migration from JSON to SQLite happens automatically "
        "on first startup if the queue table is empty and JSON files exist."
    )


def build_section_2(pdf):
    """API Endpoints Reference."""
    pdf.section_title("2", "API Endpoints Reference")
    pdf.body(
        "All endpoints are prefixed with /api/smm/ and served by the FastAPI router. "
        "22 endpoints organized into 8 functional groups."
    )

    # Profiles
    pdf.sub_title("Profile Management (5 endpoints)")
    pdf.table(
        ["Method", "Endpoint", "Description"],
        [
            ["GET", "/api/smm/profiles", "List all profiles (credentials stripped)"],
            ["GET", "/api/smm/profiles/{profile_id}", "Get single profile by ID"],
            ["POST", "/api/smm/profiles", "Create new profile (wizard step 1)"],
            ["PUT", "/api/smm/profiles/{profile_id}", "Update profile (merges platforms safely)"],
            ["DELETE", "/api/smm/profiles/{profile_id}", "Delete profile and its JSON file"],
        ],
        col_widths=[18, 70, 98]
    )

    # Trends
    pdf.sub_title("Trend Scanning (4 endpoints)")
    pdf.table(
        ["Method", "Endpoint", "Description"],
        [
            ["POST", "/api/smm/trends/scan", "Start async trend scan for profile"],
            ["GET", "/api/smm/trends/history", "List trend reports (id + timestamp)"],
            ["GET", "/api/smm/trends/by-id", "Get specific trend report by ID"],
            ["GET", "/api/smm/trends/latest", "Get latest trend report for profile"],
        ],
        col_widths=[18, 70, 98]
    )

    # Content Generation
    pdf.sub_title("Content Generation (4 endpoints)")
    pdf.table(
        ["Method", "Endpoint", "Description"],
        [
            ["POST", "/api/smm/generate", "Generate platform-specific posts from topic"],
            ["POST", "/api/smm/generate-image-prompt", "Generate image prompt from post text"],
            ["POST", "/api/smm/generate-image", "Generate image via ComfyUI workflow"],
            ["POST", "/api/smm/regen-post", "Regenerate single platform post"],
        ],
        col_widths=[18, 70, 98]
    )

    # Queue & Publishing
    pdf.sub_title("Queue, Publishing & Scheduling (7 endpoints)")
    pdf.table(
        ["Method", "Endpoint", "Description"],
        [
            ["GET", "/api/smm/queue", "List queue items for profile"],
            ["POST", "/api/smm/queue", "Add item to queue"],
            ["PUT", "/api/smm/queue/{item_id}", "Update queue item"],
            ["DELETE", "/api/smm/queue/{item_id}", "Delete queue item"],
            ["POST", "/api/smm/publish", "Publish queue item to platforms"],
            ["POST", "/api/smm/batch-generate", "Batch generate posts for N days"],
            ["GET", "/api/smm/batch-status", "Check batch generation progress"],
        ],
        col_widths=[18, 70, 98]
    )

    # Calendar, Events, Analytics, etc
    pdf.sub_title("Calendar, Analytics & System (7 endpoints)")
    pdf.table(
        ["Method", "Endpoint", "Description"],
        [
            ["GET", "/api/smm/calendar", "Queue items grouped by date for calendar"],
            ["GET", "/api/smm/events", "Recent publish events from logs"],
            ["GET", "/api/smm/analytics", "Analytics summary for profile"],
            ["GET", "/api/smm/analytics/post/{queue_id}", "Per-post analytics metrics"],
            ["GET", "/api/smm/token-health", "Check token expiry for all platforms"],
            ["POST", "/api/smm/token-refresh", "Refresh expired platform tokens"],
            ["GET", "/api/smm/storage", "Storage usage statistics"],
        ],
        col_widths=[18, 70, 98]
    )

    pdf.sub_title("Utility Endpoints (2 endpoints)")
    pdf.table(
        ["Method", "Endpoint", "Description"],
        [
            ["GET", "/api/smm/image/{filename}", "Serve generated image file"],
            ["POST", "/api/smm/cleanup", "Delete published items older than N days"],
            ["POST", "/api/smm/github-search", "Search GitHub repos by query"],
        ],
        col_widths=[18, 70, 98]
    )


def build_section_3(pdf):
    """Database Schema."""
    pdf.section_title("3", "Database Schema")
    pdf.body(
        "SQLite database (smm_data.db) with WAL journal mode for concurrent reads. "
        "Thread-local connections via threading.local(). Three tables with strategic indexing."
    )

    pdf.sub_title("Table: queue")
    pdf.body("Stores all content queue items across their lifecycle (draft -> approved -> published).")
    pdf.table(
        ["Column", "Type", "Default", "Description"],
        [
            ["id", "TEXT PK", "-", "Unique slug-based ID (from profile name)"],
            ["profile_id", "TEXT NOT NULL", "-", "FK to profile JSON file"],
            ["topic_title", "TEXT", "''", "Topic/headline for the post"],
            ["posts", "TEXT", "'{}'", "JSON: {platform: post_text} map"],
            ["image", "TEXT", "NULL", "Filename of generated image"],
            ["image_variants", "TEXT", "'{}'", "JSON: per-platform image variants"],
            ["status", "TEXT", "'draft'", "draft | approved | published"],
            ["scheduled_time", "TEXT", "NULL", "ISO datetime for auto-publish"],
            ["publish_results", "TEXT", "'{}'", "JSON: per-platform publish results"],
            ["created", "TEXT NOT NULL", "-", "ISO creation timestamp"],
            ["updated", "TEXT NOT NULL", "-", "ISO last-update timestamp"],
        ],
        col_widths=[32, 30, 20, 104]
    )
    pdf.body("Indexes: idx_queue_profile (profile_id), idx_queue_status (status)")

    pdf.sub_title("Table: trends")
    pdf.body("Stores LLM-analyzed trend reports from multi-source scans.")
    pdf.table(
        ["Column", "Type", "Default", "Description"],
        [
            ["id", "INTEGER PK", "AUTO", "Auto-increment primary key"],
            ["profile_id", "TEXT NOT NULL", "-", "Profile that ran the scan"],
            ["timestamp", "TEXT NOT NULL", "-", "When the scan was performed"],
            ["report", "TEXT NOT NULL", "-", "Full JSON trend report from LLM"],
            ["created", "TEXT NOT NULL", "-", "Row creation timestamp"],
        ],
        col_widths=[32, 30, 20, 104]
    )
    pdf.body("Index: idx_trends_profile (profile_id)")

    pdf.sub_title("Table: analytics")
    pdf.body("Hourly snapshots of engagement metrics per published post per platform.")
    pdf.table(
        ["Column", "Type", "Default", "Description"],
        [
            ["id", "INTEGER PK", "AUTO", "Auto-increment primary key"],
            ["queue_id", "TEXT NOT NULL", "-", "FK to queue item"],
            ["profile_id", "TEXT NOT NULL", "-", "Profile owner"],
            ["platform", "TEXT NOT NULL", "-", "Platform name (telegram, twitter, etc)"],
            ["post_id", "TEXT NOT NULL", "-", "Platform-specific post ID"],
            ["likes", "INTEGER", "0", "Like/reaction count"],
            ["comments", "INTEGER", "0", "Comment/reply count"],
            ["views", "INTEGER", "0", "View/impression count"],
            ["shares", "INTEGER", "0", "Share/repost count"],
            ["collected_at", "TEXT NOT NULL", "-", "Hour-rounded collection time"],
        ],
        col_widths=[32, 30, 20, 104]
    )
    pdf.body("Indexes: idx_analytics_queue (queue_id), idx_analytics_profile (profile_id)")
    pdf.info_box(
        "Deduplication: analytics_save() checks for existing entry in the same hour. "
        "If found, it UPDATEs instead of INSERTing, preventing metric duplication on re-scans."
    )


def build_section_4(pdf):
    """Profile Management & Wizard."""
    pdf.section_title("4", "Profile Management & Wizard")
    pdf.body(
        "Profiles are the central configuration unit. Each profile defines a brand identity, "
        "connected platforms, posting style, and schedule. Profiles are stored as JSON files in "
        "smm_profiles/ directory to keep sensitive API tokens out of the database."
    )

    pdf.sub_title("Profile Wizard (4-Step UI Flow)")
    pdf.body("The frontend wizard guides users through complete profile setup:")

    pdf.sub_sub_title("Step 1: Basics")
    pdf.bullet_bold("name: ", "Brand/project name (used to generate slug ID)")
    pdf.bullet_bold("niche: ", "Comma-separated keywords (e.g., 'AI, machine learning, devops')")
    pdf.bullet_bold("tone: ", "Content style: professional, casual, humorous, educational")
    pdf.bullet_bold("language: ", "ru, en, or ru+en for bilingual content")

    pdf.sub_sub_title("Step 2: Platforms")
    pdf.body(
        "Connect up to 7 platforms with their API credentials. Each platform has its own "
        "configuration fields (bot_token, channel, api_key, etc). The UI shows connection "
        "status with green/red indicators."
    )

    pdf.sub_sub_title("Step 3: Schedule")
    pdf.bullet_bold("posting_schedule: ", "Per-day time slots for auto-publishing")
    pdf.body("The scheduler checks queue_get_scheduled() for approved items with past scheduled_time and auto-publishes them.")

    pdf.sub_sub_title("Step 4: Style")
    pdf.bullet_bold("visual_style: ", "Image generation preset: tech-dark, minimalist, vibrant, corporate")
    pdf.bullet_bold("hashtags: ", "Default hashtags added to all posts")
    pdf.bullet_bold("competitors: ", "Up to 3 competitor accounts for trend comparison")

    pdf.sub_title("Profile JSON Structure")
    pdf.code(
        '{\n'
        '  "id": "neural-blog",\n'
        '  "name": "Neural Blog",\n'
        '  "niche": "AI, machine learning, LLM, devops",\n'
        '  "tone": "professional",\n'
        '  "language": "ru",\n'
        '  "hashtags": ["#AI", "#ML", "#devops"],\n'
        '  "competitors": ["@techblog"],\n'
        '  "visual_style": "tech-dark",\n'
        '  "platforms": {\n'
        '    "telegram": {"enabled": true, "bot_token": "...", "channel": "@mychan"},\n'
        '    "twitter": {"enabled": true, "api_key": "..."},\n'
        '    "linkedin": {"enabled": true, "access_token": "..."}\n'
        '  },\n'
        '  "posting_schedule": {"mon": ["10:00", "18:00"], "wed": ["12:00"]}\n'
        '}'
    )

    pdf.sub_title("Credential Security: _smm_strip_credentials()")
    pdf.body(
        "Every API response that includes profile data passes through _smm_strip_credentials(). "
        "This function deep-copies the profile via JSON serialization and replaces all sensitive "
        "fields with '***' mask. The frontend never receives real tokens."
    )
    pdf.body("Masked fields: bot_token, webhook, api_key, api_secret, access_token, access_secret, "
             "page_token, person_urn, account_id, user_id")
    pdf.body("A boolean 'connected' flag is set to True if any credential was present, allowing "
             "the UI to show connection status without exposing secrets.")
    pdf.info_box(
        "PUT /api/smm/profiles/{id} handles credential merging: if a field value is '***', "
        "the server skips it and keeps the existing token. This prevents UI save operations "
        "from wiping out real credentials."
    )


def build_section_5(pdf):
    """Trend Scanning & Scoring Algorithm."""
    pdf.section_title("5", "Trend Scanning & Scoring")
    pdf.body(
        "The trend scanner aggregates content from 6 source types, scores each result using "
        "a multi-factor algorithm, then sends the top 35 results to a local LLM for analysis "
        "and topic extraction."
    )

    pdf.sub_title("Data Sources (6 Types)")
    pdf.table(
        ["Source Type", "Data Fetched", "Engagement Metric"],
        [
            ["google_trends", "Trending searches via RSS feed", "Search volume (relative)"],
            ["reddit", "Hot posts from niche subreddits", "Upvotes + comments"],
            ["hackernews", "Top/new stories from HN API", "Points + comments"],
            ["rss", "RSS/Atom feed entries", "N/A (content-based)"],
            ["github", "Trending repos + topic search", "Stars + forks*3"],
            ["searxng", "Meta-search web results", "Traffic estimates"],
        ],
        col_widths=[32, 82, 72]
    )

    pdf.sub_title("Scoring Algorithm")
    pdf.body("Each collected result gets a composite score from 4 signal categories:")

    pdf.sub_sub_title("1. Source Type Boost (base credibility)")
    pdf.table(
        ["Source", "Points", "Reasoning"],
        [
            ["google_trends", "+15", "Highest: reflects real search demand"],
            ["reddit", "+12", "Community-validated viral content"],
            ["hackernews", "+10", "Tech-specific quality signal"],
            ["rss", "+8", "Curated editorial content"],
            ["github", "+6", "Code/project relevance"],
            ["searxng/web", "+0", "Base level, no inherent boost"],
        ],
        col_widths=[40, 20, 126]
    )

    pdf.sub_sub_title("2. Engagement Boost (virality signal)")
    pdf.table(
        ["Engagement Level", "Points", "Threshold"],
        [
            [">500", "+25", "Viral content (high upvotes, stars, etc)"],
            [">100", "+15", "Popular content"],
            [">30", "+8", "Moderate engagement"],
            [">0", "+3", "Minimal but non-zero engagement"],
        ],
        col_widths=[40, 20, 126]
    )

    pdf.sub_sub_title("3. Freshness & Relevance")
    pdf.table(
        ["Signal", "Points", "Condition"],
        [
            ["Published today", "+20", "freshness == 'day'"],
            ["Keyword in title", "+5", "Each profile keyword found in title"],
            ["Current year mentioned", "+8", "Year string found in content"],
            ["Old content penalty", "-15", "Previous year or older found"],
        ],
        col_widths=[40, 20, 126]
    )

    pdf.sub_sub_title("4. Language Filters (hard penalties)")
    pdf.table(
        ["Filter", "Points", "Condition"],
        [
            ["CJK characters in title", "-100", "For ru/en profiles, removes CJK results"],
            ["CJK domain for en profiles", "-100", "zhihu, baidu, csdn, bilibili domains"],
        ],
        col_widths=[45, 20, 121]
    )

    pdf.info_box(
        "After scoring, results are sorted by _score descending. The top 35 are sent to the LLM "
        "(Ollama) as a structured prompt for analysis. The LLM returns a JSON report with topic "
        "suggestions, trend summaries, and content angles."
    )

    pdf.sub_title("Source Implementation Details")

    pdf.sub_sub_title("Reddit Source (_smm_src_reddit)")
    pdf.body(
        "Two-strategy approach for maximum reliability:"
    )
    pdf.bullet_bold("Strategy 1 - SearXNG: ", "Search 'reddit {keyword}' via SearXNG meta-search. "
                    "Filters for reddit.com/r/ URLs, excludes wiki pages. Up to 4 keywords, 12 results each.")
    pdf.bullet_bold("Strategy 2 - RSS Fallback: ", "Direct RSS feeds from subreddit /hot/.rss endpoints. "
                    "Up to 3 subreddits, 8 entries each. 1-second delay between requests for rate limiting.")
    pdf.body("Cyrillic keywords are auto-translated to English for Reddit searches (e.g., "
             "'restoran' -> 'restaurant', 'fitnes' -> 'fitness').")

    pdf.sub_sub_title("HackerNews Source (_smm_src_hackernews)")
    pdf.body(
        "Uses HN Algolia API (hn.algolia.com/api/v1/search) with points>15 filter. "
        "Searches up to 4 keywords, 12 hits per keyword. Engagement = points + comments."
    )

    pdf.sub_sub_title("GitHub Sources")
    pdf.body(
        "Two GitHub data paths: trending page scraping and API search. "
        "The trending scraper parses github.com/trending HTML for repo links (up to 25 repos). "
        "The API search uses POST /api/smm/github-search with keyword-based queries. "
        "Auto-categorizes repos into 7 categories: Agent, Image Gen, RAG, Tool, Dataset, LLM, Chat."
    )

    pdf.sub_sub_title("Google Trends Source")
    pdf.body(
        "Fetches Google Trends RSS feed for real-time trending searches. "
        "Provides the highest source type boost (+15) due to reflecting actual search demand."
    )


def build_section_6(pdf):
    """Niche Routing Engine."""
    pdf.section_title("6", "Niche Routing Engine")
    pdf.body(
        "SMM_NICHE_ROUTES maps 8 predefined niches to their optimal data sources and subreddit lists. "
        "The routing function _smm_route_niche() scores each route against the profile's niche keywords "
        "and selects the best match. If no match is found, a generic fallback (searxng + reddit) is used."
    )

    pdf.sub_title("Niche: tech")
    pdf.bullet_bold("Keywords: ", "ai, ml, devops, programming, software, open source, llm, developer, "
                    "kubernetes, docker, linux, python, api, agent, rag, lora, fine-tun, comfyui, stable diffusion")
    pdf.bullet_bold("Sources: ", "github_trending_ai, hackernews, reddit, github_trending, rss, searxng")
    pdf.bullet_bold("Subreddits: ", "MachineLearning, selfhosted, devops, LocalLLaMA, opensource, programming, StableDiffusion")
    pdf.bullet_bold("RSS: ", "hnrss.org/newest?points=50, techcrunch.com/feed/")

    pdf.sub_title("Niche: crypto")
    pdf.bullet_bold("Keywords: ", "crypto, defi, web3, blockchain, bitcoin, ethereum, nft, "
                    "kriypto, bitkoin, blokchejn, token (+ Cyrillic variants)")
    pdf.bullet_bold("Sources: ", "reddit, rss, searxng")
    pdf.bullet_bold("Subreddits: ", "cryptocurrency, defi, ethereum, CryptoMarkets, Bitcoin")
    pdf.bullet_bold("RSS: ", "coindesk.com/arc/outboundfeeds/rss/")

    pdf.sub_title("Niche: food")
    pdf.bullet_bold("Keywords: ", "restaurant, food, cooking, chef, recipe, cafe (+ Cyrillic: restoran, eda, retsept, kafe, kulinar)")
    pdf.bullet_bold("Sources: ", "reddit, rss, searxng")
    pdf.bullet_bold("Subreddits: ", "food, Cooking, FoodPorn, AskCulinary, MealPrepSunday")
    pdf.bullet_bold("Site filters: ", "tripadvisor.com, wolt.com, bolt.eu/food")

    pdf.sub_title("Niche: fitness")
    pdf.bullet_bold("Keywords: ", "fitness, workout, health, gym, sport, running (+ Cyrillic)")
    pdf.bullet_bold("Sources: ", "reddit, google_trends, searxng")
    pdf.bullet_bold("Subreddits: ", "fitness, nutrition, bodyweightfitness, running, GYM")

    pdf.sub_title("Niche: business")
    pdf.bullet_bold("Keywords: ", "saas, b2b, startup, marketing, product, growth, venture, investment")
    pdf.bullet_bold("Sources: ", "hackernews, reddit, rss, searxng")
    pdf.bullet_bold("Subreddits: ", "SaaS, startups, Entrepreneur, marketing, smallbusiness")
    pdf.bullet_bold("RSS: ", "hnrss.org/newest?points=30&q=startup")

    pdf.sub_title("Niche: art")
    pdf.bullet_bold("Keywords: ", "art, design, comfyui, stable diffusion, flux, generative, midjourney, illustration")
    pdf.bullet_bold("Sources: ", "reddit, github_trending, searxng")
    pdf.bullet_bold("Subreddits: ", "StableDiffusion, comfyui, AIArt, generative, DigitalArt")

    pdf.sub_title("Niche: gaming")
    pdf.bullet_bold("Keywords: ", "game, gaming, esport, steam, unity, unreal, gamedev")
    pdf.bullet_bold("Sources: ", "reddit, rss, searxng")
    pdf.bullet_bold("Subreddits: ", "gaming, Games, pcgaming, indiegaming, gamedev")

    pdf.sub_title("Niche: education")
    pdf.bullet_bold("Keywords: ", "education, course, learn, tutorial, university, school, student")
    pdf.bullet_bold("Sources: ", "reddit, searxng, google_trends")
    pdf.bullet_bold("Subreddits: ", "learnprogramming, education, OnlineCourses")

    pdf.info_box(
        "Geo-routing: _smm_detect_locations() scans niche keywords for city/country names "
        "and auto-adds geographic subreddits (e.g., r/tallinn, r/berlin). Cyrillic names are "
        "transliterated (e.g., Moskva -> moscow, Sankt-Peterburg -> stpetersburg)."
    )


def build_section_7(pdf):
    """Platform Formats & Hashtag Manager."""
    pdf.section_title("7", "Platform Formats & Hashtag Manager")
    pdf.body(
        "SMM_PLATFORM_FORMATS defines the content constraints for each supported platform. "
        "These constraints are enforced during content generation (via LLM prompt) and post-generation "
        "(via trimming functions)."
    )

    pdf.sub_title("Platform Format Specifications")
    pdf.table(
        ["Platform", "Max Chars", "Max Tags", "Content Style"],
        [
            ["Telegram", "4096", "5", "Markdown, structured, emoji headings, source links"],
            ["Twitter", "280", "3", "Hook + key insight, 2-3 tags, provocative, no links in text"],
            ["LinkedIn", "3000", "5", "Professional tone, 3-5 paragraphs, expert position, CTA"],
            ["Instagram", "2200", "28", "Emotional storytelling, emoji-rich, 20-28 tags at end"],
            ["Facebook", "2000", "5", "Conversational, audience questions, engagement bait"],
            ["Threads", "500", "5", "Short opinion, conversational, 3-5 tags"],
            ["Discord", "2000", "0", "Casual community style, embed-friendly, NO hashtags"],
        ],
        col_widths=[28, 22, 20, 116]
    )

    pdf.sub_title("Hashtag Manager: _smm_trim_hashtags()")
    pdf.body(
        "After LLM generation, each post passes through the hashtag trimmer. The function ensures "
        "platform limits are respected:"
    )
    pdf.bullet("If max_hashtags == 0 (Discord): all #hashtags are stripped from the text")
    pdf.bullet("If hashtag count <= limit: text passes through unchanged")
    pdf.bullet("If hashtag count > limit: excess hashtags are removed from end of text")

    pdf.code(
        "def _smm_trim_hashtags(text: str, platform: str) -> str:\n"
        "    max_tags = SMM_PLATFORM_FORMATS.get(platform, {}).get('max_hashtags', 30)\n"
        "    if max_tags == 0:\n"
        "        return ' '.join(w for w in text.split() if not w.startswith('#'))\n"
        "    words = text.split()\n"
        "    hashtags = [w for w in words if w.startswith('#')]\n"
        "    if len(hashtags) <= max_tags:\n"
        "        return text\n"
        "    excess = set(hashtags[max_tags:])\n"
        "    return ' '.join(w for w in words if w not in excess)"
    )

    pdf.sub_title("LLM Prompt Integration")
    pdf.body(
        "Platform formats are injected into the LLM generation prompt dynamically. For each enabled "
        "platform, a format string is built:\n"
        "  '- telegram: up to 4096 chars. Markdown, structured, emoji headings...'\n"
        "  '- twitter: up to 280 chars. Hook + key insight...'\n"
        "The LLM is instructed to generate a JSON object with platform-keyed content that respects "
        "each platform's character limits and style guidelines."
    )


def build_section_8(pdf):
    """Content Generation Pipeline."""
    pdf.section_title("8", "Content Generation Pipeline")
    pdf.body(
        "The /api/smm/generate endpoint creates platform-specific posts from a topic. "
        "It accepts a topic title, optional article text, profile ID, list of target platforms, "
        "and LLM model name."
    )

    pdf.sub_title("Generation Flow")
    pdf.bullet("1. Load profile to get tone, language, hashtags, and enabled platforms")
    pdf.bullet("2. If article URL provided: scrape article text via _smm_scrape_url()")
    pdf.bullet("3. Build platform format instructions from SMM_PLATFORM_FORMATS")
    pdf.bullet("4. Construct LLM prompt with: topic, article context, profile tone/language, platform rules")
    pdf.bullet("5. Call Ollama API via _smm_call_ollama() with model and temperature settings")
    pdf.bullet("6. Parse JSON response via _smm_parse_json_obj() (3-stage fallback parser)")
    pdf.bullet("7. Trim hashtags per platform via _smm_trim_hashtags()")
    pdf.bullet("8. Return {platform: post_text} map")

    pdf.sub_title("LLM Call Configuration")
    pdf.table(
        ["Parameter", "Default", "Description"],
        [
            ["model", "qwen3.5:9b", "Ollama model name"],
            ["num_predict", "8000", "Max tokens to generate"],
            ["temperature", "0.7", "Creativity vs consistency"],
            ["think", "True", "Enable thinking/reasoning mode"],
            ["timeout", "360s", "Request timeout with 1 retry"],
        ],
        col_widths=[35, 30, 121]
    )

    pdf.sub_title("JSON Response Parser (_smm_parse_json_obj)")
    pdf.body("Three-stage fallback strategy for robust LLM output parsing:")
    pdf.bullet_bold("Stage 1: ", "Direct json.loads() on full response text")
    pdf.bullet_bold("Stage 2: ", "Find last complete {...} block by scanning braces from end of string")
    pdf.bullet_bold("Stage 3: ", "Fix truncated JSON: close unclosed quotes and braces, then parse")

    pdf.sub_title("Post Regeneration")
    pdf.body(
        "POST /api/smm/regen-post regenerates a single platform's post within an existing queue item. "
        "Takes queue_id, platform, and optional custom_prompt. Re-runs the LLM with the original topic "
        "context but allows the user to provide specific instructions for the regeneration."
    )


def build_section_9(pdf):
    """Publishing & Publish Preview."""
    pdf.section_title("9", "Publishing & Publish Preview")
    pdf.body(
        "The publishing system handles multi-platform dispatch with platform-specific APIs, "
        "image handling, and error tracking per platform."
    )

    pdf.sub_title("Publish Flow (POST /api/smm/publish)")
    pdf.bullet("1. Load queue item and profile with credentials")
    pdf.bullet("2. For Instagram/Threads: pre-upload images to Imgur (Meta requires public URLs)")
    pdf.bullet("3. Rate-limit: 2-second delay between platform dispatches")
    pdf.bullet("4. Per platform: fetch credentials, trim hashtags, send via platform API")
    pdf.bullet("5. Collect results: {platform: {ok, message, post_id}}")
    pdf.bullet("6. Save publish log to smm_trends/_publish_logs/ as JSON")
    pdf.bullet("7. Update queue item status to 'published' with publish_results")

    pdf.sub_title("Platform API Integrations")
    pdf.table(
        ["Platform", "API Used", "Image Support"],
        [
            ["Telegram", "Bot API: sendMessage / sendPhoto", "Direct file upload"],
            ["Discord", "Webhook URL: POST with embeds", "Direct file upload"],
            ["Twitter/X", "OAuth 1.0a: POST /2/tweets", "Media upload endpoint"],
            ["LinkedIn", "OAuth 2.0: ugcPosts API", "Image via asset upload"],
            ["Instagram", "Graph API: media + publish", "Imgur public URL required"],
            ["Threads", "Graph API: media + publish", "Imgur public URL required"],
            ["Facebook", "Page API: /feed or /photos", "Direct URL or upload"],
        ],
        col_widths=[28, 72, 86]
    )

    pdf.sub_title("Publish Preview Modal")
    pdf.body(
        "Before publishing, the UI shows a preview modal displaying each platform's post in its "
        "rendered format. Users can:\n"
        "- Review generated text for each platform side-by-side\n"
        "- See the attached image (or per-platform image variants)\n"
        "- Toggle individual platforms on/off for selective publishing\n"
        "- Edit post text inline before confirming publish\n"
        "- View character count vs platform limit with color-coded warnings"
    )

    pdf.sub_title("Image Variant System")
    pdf.body(
        "Each queue item can have platform-specific image variants stored in image_variants JSON field. "
        "The _get_platform_image() function checks for a variant first, falling back to the base image. "
        "This allows generating square images for Instagram and landscape for Twitter from the same source."
    )

    pdf.sub_title("Platform-Specific Publishing Details")

    pdf.sub_sub_title("Telegram Publishing")
    pdf.body(
        "Uses Bot API with sendMessage (text-only) or sendPhoto (with image). "
        "Supports Markdown parse_mode for formatted text. The bot_token and channel ID "
        "are read from profile config. Direct file upload for images."
    )

    pdf.sub_sub_title("Instagram & Threads Publishing")
    pdf.body(
        "Meta Graph API requires images to be accessible via public URL. The system "
        "pre-uploads images to Imgur before publishing. Separate uploads per platform to avoid "
        "Meta caching issues. 1-second delay between Imgur uploads for rate limiting. "
        "Two-step publish: first create media container, then publish it."
    )

    pdf.sub_sub_title("Discord Publishing")
    pdf.body(
        "Uses webhook URLs (no bot token required). Sends content as embed-formatted "
        "messages. Direct file upload for images. No hashtags (max_hashtags=0, all # stripped)."
    )

    pdf.sub_sub_title("Error Handling & Rate Limiting")
    pdf.body(
        "2-second delay between platform dispatches to avoid triggering rate limits. "
        "Each platform result includes ok/fail status and error message. Failed platforms "
        "are logged in the event log for debugging. Publish results are saved to the queue item "
        "for status tracking."
    )


def build_section_10(pdf):
    """Batch Generation & Calendar."""
    pdf.section_title("10", "Batch Generation & Calendar")

    pdf.sub_title("Batch Generation (POST /api/smm/batch-generate)")
    pdf.body(
        "Generates posts for multiple days at once. Runs as a background thread to avoid "
        "blocking the API. Maximum 14 days per batch."
    )
    pdf.table(
        ["Parameter", "Type", "Default", "Description"],
        [
            ["profile_id", "string", "required", "Profile to generate for"],
            ["days", "integer", "7", "Number of days (max 14)"],
            ["model", "string", "qwen3.5:9b", "Ollama model name"],
            ["platforms", "list", "required", "Target platforms list"],
            ["generate_images", "boolean", "false", "Also generate images via ComfyUI"],
        ],
        col_widths=[32, 22, 26, 106]
    )
    pdf.body(
        "Progress is tracked via _smm_batch_status dict and polled by GET /api/smm/batch-status. "
        "Status transitions: idle -> running (with progress message) -> done | error."
    )

    pdf.sub_title("Calendar View (GET /api/smm/calendar)")
    pdf.body(
        "Returns queue items grouped by date for the calendar UI component. "
        "Defaults to current week (Monday-Sunday) if no date range is specified."
    )
    pdf.code(
        "GET /api/smm/calendar?profile_id=neural-blog&date_from=2026-03-23&date_to=2026-03-29\n"
        "\n"
        "Response: {\n"
        '  "ok": true,\n'
        '  "days": {\n'
        '    "2026-03-24": [\n'
        '      {"id": "post-1", "topic_title": "AI Agents...", "status": "approved",\n'
        '       "platforms": ["telegram", "twitter"], "scheduled_time": "2026-03-24T10:00"}\n'
        "    ]\n"
        "  }\n"
        "}"
    )
    pdf.body(
        "Each calendar entry includes: id, truncated topic_title (50 chars), status, "
        "list of target platforms, scheduled_time, and image filename. The frontend renders "
        "this as a weekly grid with drag-and-drop rescheduling."
    )

    pdf.sub_title("Auto-Scheduler")
    pdf.body(
        "The auto-scheduler is a background task that periodically calls queue_get_scheduled(). "
        "It queries for items with status='approved' and scheduled_time in the past, then "
        "triggers automatic publishing. This enables the 'set and forget' workflow where users "
        "batch-generate a week of content and let the system publish on schedule."
    )


def build_section_11(pdf):
    """Analytics & Event Log."""
    pdf.section_title("11", "Analytics & Event Log")

    pdf.sub_title("Analytics System")
    pdf.body(
        "Post-publish analytics tracking collects engagement metrics from each platform. "
        "Metrics are stored as hourly snapshots in the analytics table, enabling time-series analysis."
    )
    pdf.bullet_bold("GET /api/smm/analytics: ", "Aggregate summary for a profile (total likes, comments, views, shares, by-platform breakdown, top 5 posts)")
    pdf.bullet_bold("GET /api/smm/analytics/post/{queue_id}: ", "Per-post latest metrics across all platforms")
    pdf.bullet_bold("analytics_save(): ", "Upsert pattern - updates existing hour entry or inserts new one")
    pdf.bullet_bold("analytics_cleanup_old(30): ", "Purges analytics data older than 30 days")

    pdf.sub_title("Analytics Summary Response")
    pdf.code(
        "{\n"
        '  "total_posts": 42,\n'
        '  "total_likes": 1580,\n'
        '  "total_comments": 234,\n'
        '  "total_views": 28500,\n'
        '  "total_shares": 89,\n'
        '  "by_platform": {\n'
        '    "telegram": {"likes": 800, "comments": 120, "views": 15000, "shares": 45},\n'
        '    "twitter": {"likes": 400, "comments": 80, "views": 8000, "shares": 30}\n'
        "  },\n"
        '  "top_posts": [\n'
        '    {"id": "post-1", "topic": "AI Agents Revolution", "likes": 150, "comments": 30, "views": 5200}\n'
        "  ]\n"
        "}"
    )

    pdf.sub_title("Event Log (GET /api/smm/events)")
    pdf.body(
        "The event log tracks all publish operations. Each publish action writes a JSON log file "
        "to smm_trends/_publish_logs/. The /api/smm/events endpoint reads these logs and returns "
        "a summarized view."
    )
    pdf.bullet("Each event includes: timestamp, topic title, success count, failure count, list of failed platforms")
    pdf.bullet("Events are sorted by file modification time (newest first)")
    pdf.bullet("Optional profile_id filter to show events for a specific profile")
    pdf.bullet("Default limit: 20 most recent events")

    pdf.code(
        "GET /api/smm/events?profile_id=neural-blog&limit=10\n"
        "\n"
        "Response: {\n"
        '  "events": [\n'
        '    {"timestamp": "2026-03-25T14:30:00", "topic": "GPT-5 Release Analysis",\n'
        '     "ok": 5, "fail": 1, "failed": ["instagram"], "total": 6}\n'
        "  ]\n"
        "}"
    )
    pdf.info_box(
        "Failure tracking enables automatic retry logic and helps identify platforms with "
        "expired tokens or misconfigured credentials."
    )


def build_section_12(pdf):
    """Token Health & Security."""
    pdf.section_title("12", "Token Health & Security")

    pdf.sub_title("Token Health Check (GET /api/smm/token-health)")
    pdf.body(
        "Checks token expiry status for all platforms of a profile. Returns per-platform health "
        "status including days until expiry and whether a refresh is needed."
    )
    pdf.bullet("Reads token_expires_at from each platform config")
    pdf.bullet("Calculates days remaining and flags tokens expiring within 7 days")
    pdf.bullet("Returns health map: {platform: {status, days_remaining, refreshable}}")

    pdf.sub_title("Token Refresh (POST /api/smm/token-refresh)")
    pdf.body("Supports automatic token refresh for platforms with refresh token flows:")

    pdf.sub_sub_title("Threads Token Refresh")
    pdf.bullet("Uses Meta Graph API: /refresh_access_token endpoint")
    pdf.bullet("Extends long-lived token by 60 days")
    pdf.bullet("Automatically updates token and expiry in profile JSON")

    pdf.sub_sub_title("LinkedIn Token Refresh")
    pdf.bullet("Uses OAuth 2.0 refresh_token grant")
    pdf.bullet("Requires client_id and client_secret in profile config")
    pdf.bullet("Updates access_token, refresh_token, and expiry timestamp")

    pdf.sub_title("Credential Security Model")
    pdf.body("Multi-layer security approach for API credentials:")
    pdf.bullet_bold("Storage isolation: ", "Credentials in JSON files, not in SQLite database")
    pdf.bullet_bold("API stripping: ", "_smm_strip_credentials() masks all tokens with '***' in responses")
    pdf.bullet_bold("Merge protection: ", "PUT endpoint skips '***' values to preserve real tokens")
    pdf.bullet_bold("Path sanitization: ", "_smm_safe_id() prevents directory traversal via regex filter")
    pdf.bullet_bold("Input validation: ", "Profile IDs cleaned with [a-z0-9-_] pattern only")

    pdf.sub_title("Cleanup & Maintenance")
    pdf.table(
        ["Operation", "Endpoint", "Default", "Description"],
        [
            ["Queue cleanup", "POST /api/smm/cleanup", "14 days", "Delete published items older than N days"],
            ["Analytics cleanup", "analytics_cleanup_old()", "30 days", "Purge old analytics snapshots"],
            ["Storage check", "GET /api/smm/storage", "-", "Report disk usage for images, DB, profiles"],
        ],
        col_widths=[32, 50, 22, 82]
    )


def build_section_13(pdf):
    """Image Generation Pipeline."""
    pdf.section_title("13", "Image Generation Pipeline")
    pdf.body(
        "The image pipeline uses ComfyUI for AI image generation. Two-step process: "
        "first generate a prompt from post text via LLM, then execute ComfyUI workflow."
    )

    pdf.sub_title("Step 1: Image Prompt Generation")
    pdf.body(
        "POST /api/smm/generate-image-prompt takes the post text and generates a detailed "
        "image generation prompt via Ollama. The LLM is instructed to create a visual description "
        "suitable for Stable Diffusion / Flux models."
    )

    pdf.sub_title("Step 2: ComfyUI Execution")
    pdf.body(
        "POST /api/smm/generate-image sends the prompt to ComfyUI at localhost:8188. "
        "The workflow generates the image and saves it to the ComfyUI output directory. "
        "The server copies the result to smm_images/ and links it to the queue item."
    )

    pdf.sub_title("Image Serving")
    pdf.body(
        "GET /api/smm/image/{filename} serves generated images directly via FastAPI FileResponse. "
        "Images are served from the smm_images/ directory."
    )

    pdf.sub_title("Visual Style Presets")
    pdf.body(
        "The profile's visual_style setting influences image prompt generation. Available presets "
        "include: tech-dark (dark backgrounds, neon accents), minimalist (clean, whitespace), "
        "vibrant (colorful, high contrast), and corporate (professional, muted tones)."
    )

    pdf.info_box(
        "Image variants: Each platform can have a custom-sized variant (square for Instagram, "
        "landscape for Twitter/LinkedIn). Variants are stored in the queue item's image_variants field "
        "and served via the same /api/smm/image/ endpoint."
    )

    pdf.sub_title("GitHub Repository Categories")
    pdf.body(
        "The GitHub search module auto-categorizes discovered repositories into 7 categories "
        "based on description and topic keywords. This helps trend analysis focus on relevant projects."
    )
    pdf.table(
        ["Category", "Detection Keywords"],
        [
            ["Agent", "agent, autonomous, crew, swarm, orchestrat, agentic"],
            ["Image Gen", "stable diffusion, comfyui, flux, image gen, diffusion, sdxl"],
            ["RAG", "rag, retrieval, vector, embedding, knowledge base"],
            ["Tool", "tool, cli, sdk, framework, library, api"],
            ["Dataset", "dataset, benchmark, eval, leaderboard"],
            ["LLM", "llm, language model, transformer, fine-tun, lora, inference"],
            ["Chat", "chat, assistant, copilot, companion"],
        ],
        col_widths=[30, 156]
    )


def build_section_14(pdf):
    """Quick Reference Card."""
    pdf.section_title("14", "Quick Reference")

    pdf.sub_title("Common Workflows")

    pdf.sub_sub_title("Create Profile and First Post")
    pdf.code(
        "# 1. Create profile\n"
        "POST /api/smm/profiles\n"
        '  {"name": "My Blog", "niche": "AI, tech", "tone": "professional",\n'
        '   "language": "en", "platforms": {"telegram": {"enabled": true, "bot_token": "..."}}}\n'
        "\n"
        "# 2. Scan trends\n"
        "POST /api/smm/trends/scan\n"
        '  {"profile_id": "my-blog", "model": "qwen3.5:27b"}\n'
        "\n"
        "# 3. Generate posts from topic\n"
        "POST /api/smm/generate\n"
        '  {"profile_id": "my-blog", "topic": "AI Agents in 2026",\n'
        '   "platforms": ["telegram", "twitter"], "model": "qwen3.5:9b"}\n'
        "\n"
        "# 4. Publish\n"
        "POST /api/smm/publish\n"
        '  {"queue_id": "post-id", "profile_id": "my-blog",\n'
        '   "platforms": ["telegram", "twitter"]}'
    )

    pdf.sub_sub_title("Batch Schedule a Week of Content")
    pdf.code(
        "# Generate 7 days of posts with images\n"
        "POST /api/smm/batch-generate\n"
        '  {"profile_id": "my-blog", "days": 7,\n'
        '   "platforms": ["telegram", "twitter", "linkedin"],\n'
        '   "generate_images": true, "model": "qwen3.5:9b"}\n'
        "\n"
        "# Check progress\n"
        "GET /api/smm/batch-status\n"
        "\n"
        "# View calendar\n"
        "GET /api/smm/calendar?profile_id=my-blog"
    )

    pdf.sub_title("Status Lifecycle")
    pdf.table(
        ["Status", "Meaning", "Transition"],
        [
            ["draft", "Newly generated, not reviewed", "User approves -> approved"],
            ["approved", "Reviewed and ready", "Scheduler or manual -> published"],
            ["published", "Successfully sent to platforms", "Cleanup after 14 days"],
        ],
        col_widths=[30, 70, 86]
    )

    pdf.sub_title("Key Internal Functions")
    pdf.table(
        ["Function", "Purpose"],
        [
            ["_smm_safe_id()", "Sanitize profile/queue IDs (regex: [a-z0-9-_])"],
            ["_smm_slugify()", "Convert name to URL-safe slug"],
            ["_smm_unique_id()", "Generate unique slug, append UUID if collision"],
            ["_smm_strip_credentials()", "Deep-copy profile, mask all tokens with '***'"],
            ["_smm_trim_hashtags()", "Enforce per-platform hashtag limits"],
            ["_smm_route_niche()", "Score niche keywords against 8 route definitions"],
            ["_smm_detect_locations()", "Find city/country names for geo-subreddit routing"],
            ["_smm_call_ollama()", "Send prompt to Ollama with retry and response cleaning"],
            ["_smm_parse_json_obj()", "3-stage JSON parser for LLM output"],
            ["_smm_scrape_url()", "Extract article text from URL (strip HTML tags)"],
            ["_has_cjk()", "Detect CJK characters for language filtering"],
        ],
        col_widths=[48, 138]
    )

    pdf.sub_title("Environment Requirements")
    pdf.table(
        ["Service", "URL", "Required For"],
        [
            ["NeuralForge Server", "localhost:9000", "Main API server (FastAPI + Uvicorn)"],
            ["Ollama", "localhost:11434", "LLM inference (trend analysis + content gen)"],
            ["ComfyUI", "localhost:8188", "Image generation workflows"],
            ["SearXNG", "localhost:8888", "Meta-search for trend discovery"],
        ],
        col_widths=[38, 46, 102]
    )

    pdf.info_box(
        "Important: Never kill the NeuralForge server process directly. Use POST /api/restart "
        "endpoint or curl to trigger a graceful restart."
    )


def main():
    pdf = SmmGuidePDF()

    # Cover page
    build_cover(pdf)

    # Table of Contents - rebuild with section 14
    build_toc_v2(pdf)

    # Sections
    build_section_1(pdf)
    build_section_2(pdf)
    build_section_3(pdf)
    build_section_4(pdf)
    build_section_5(pdf)
    build_section_6(pdf)
    build_section_7(pdf)
    build_section_8(pdf)
    build_section_9(pdf)
    build_section_10(pdf)
    build_section_11(pdf)
    build_section_12(pdf)
    build_section_13(pdf)
    build_section_14(pdf)

    pdf.output(OUTPUT)
    print(f"Generated: {OUTPUT}")
    print(f"Pages: {pdf.pages_count}")


def build_toc_v2(pdf):
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 18)
    pdf.set_text_color(*C_SECTION_BG)
    pdf.cell(0, 12, "Table of Contents", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*C_ACCENT)
    pdf.set_line_width(0.6)
    pdf.line(10, pdf.get_y(), 80, pdf.get_y())
    pdf.ln(6)

    toc_items = [
        ("1", "System Architecture"),
        ("2", "API Endpoints Reference"),
        ("3", "Database Schema"),
        ("4", "Profile Management & Wizard"),
        ("5", "Trend Scanning & Scoring"),
        ("6", "Niche Routing Engine"),
        ("7", "Platform Formats & Hashtag Manager"),
        ("8", "Content Generation Pipeline"),
        ("9", "Publishing & Publish Preview"),
        ("10", "Batch Generation & Calendar"),
        ("11", "Analytics & Event Log"),
        ("12", "Token Health & Security"),
        ("13", "Image Generation Pipeline"),
        ("14", "Quick Reference"),
    ]
    for num, title in toc_items:
        pdf.set_font("DejaVu", "B", 10)
        pdf.set_text_color(*C_ACCENT)
        pdf.cell(12, 8, num + ".")
        pdf.set_font("DejaVu", "", 10)
        pdf.set_text_color(*C_TEXT)
        pdf.cell(150, 8, title)
        pdf.ln(8)
        # Dotted line
        pdf.set_draw_color(200, 205, 215)
        pdf.set_line_width(0.1)
        y = pdf.get_y() - 4
        for x in range(25, 195, 3):
            pdf.line(x, y, x + 1, y)
    pdf.ln(4)


if __name__ == "__main__":
    main()
