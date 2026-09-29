"""
SMM SQLite database for queue items and trend reports.
Profiles stay in JSON (contain sensitive API tokens).
"""

import sqlite3
import json
import threading
from pathlib import Path
from datetime import datetime

DB_PATH = Path("smm_data.db")
_local = threading.local()


def _get_conn():
    """Get thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


def init_db():
    """Create tables if not exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS queue (
            id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL,
            topic_title TEXT DEFAULT '',
            posts TEXT DEFAULT '{}',
            image TEXT,
            image_variants TEXT DEFAULT '{}',
            status TEXT DEFAULT 'draft',
            scheduled_time TEXT,
            publish_results TEXT DEFAULT '{}',
            created TEXT NOT NULL,
            updated TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            queue_id TEXT NOT NULL,
            profile_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            post_id TEXT NOT NULL,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            views INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            collected_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_analytics_queue ON analytics(queue_id);
        CREATE INDEX IF NOT EXISTS idx_analytics_profile ON analytics(profile_id);

        CREATE TABLE IF NOT EXISTS trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            report TEXT NOT NULL,
            created TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_queue_profile ON queue(profile_id);
        CREATE INDEX IF NOT EXISTS idx_queue_status ON queue(status);
        CREATE INDEX IF NOT EXISTS idx_trends_profile ON trends(profile_id);
    """)
    conn.commit()


# ─── Queue Operations ────────────────────────────────────────────

def queue_list(profile_id=""):
    """List queue items, optionally filtered by profile."""
    conn = _get_conn()
    if profile_id:
        rows = conn.execute(
            "SELECT * FROM queue WHERE profile_id=? ORDER BY created DESC", (profile_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM queue ORDER BY created DESC").fetchall()
    return [_row_to_queue_item(r) for r in rows]


def queue_get(item_id):
    """Get single queue item."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM queue WHERE id=?", (item_id,)).fetchone()
    return _row_to_queue_item(row) if row else None


def queue_add(item):
    """Add item to queue."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO queue (id, profile_id, topic_title, posts, image, image_variants,
           status, scheduled_time, publish_results, created, updated)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (item["id"], item["profile_id"], item.get("topic_title", ""),
         json.dumps(item.get("posts", {}), ensure_ascii=False),
         item.get("image"), json.dumps(item.get("image_variants", {}), ensure_ascii=False),
         item.get("status", "draft"), item.get("scheduled_time"),
         json.dumps(item.get("publish_results", {}), ensure_ascii=False),
         item.get("created", datetime.now().isoformat()),
         item.get("updated", datetime.now().isoformat()))
    )
    conn.commit()


def queue_update(item_id, updates):
    """Update queue item fields."""
    conn = _get_conn()
    item = queue_get(item_id)
    if not item:
        return False
    for key in ("posts", "status", "scheduled_time", "image", "topic_title",
                "image_variants", "publish_results"):
        if key in updates:
            item[key] = updates[key]
    item["updated"] = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """UPDATE queue SET topic_title=?, posts=?, image=?, image_variants=?,
           status=?, scheduled_time=?, publish_results=?, updated=?
           WHERE id=?""",
        (item.get("topic_title", ""),
         json.dumps(item.get("posts", {}), ensure_ascii=False),
         item.get("image"),
         json.dumps(item.get("image_variants", {}), ensure_ascii=False),
         item.get("status", "draft"),
         item.get("scheduled_time"),
         json.dumps(item.get("publish_results", {}), ensure_ascii=False),
         item["updated"], item_id)
    )
    conn.commit()
    return True


def queue_delete(item_id):
    """Delete queue item."""
    conn = _get_conn()
    conn.execute("DELETE FROM queue WHERE id=?", (item_id,))
    conn.commit()


def queue_get_scheduled():
    """Get approved items with scheduled_time in the past."""
    conn = _get_conn()
    now = datetime.now().isoformat()
    rows = conn.execute(
        "SELECT * FROM queue WHERE status='approved' AND scheduled_time IS NOT NULL AND scheduled_time<=?",
        (now,)
    ).fetchall()
    return [_row_to_queue_item(r) for r in rows]


def queue_cleanup_old(days=14):
    """Delete published items older than N days."""
    conn = _get_conn()
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    deleted = conn.execute(
        "DELETE FROM queue WHERE status='published' AND updated<?", (cutoff,)
    ).rowcount
    conn.commit()
    return deleted


def queue_count():
    """Count queue items."""
    conn = _get_conn()
    return conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0]


# ─── Trends Operations ──────────────────────────────────────────

def trends_save(profile_id, report):
    """Save trend report."""
    conn = _get_conn()
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO trends (profile_id, timestamp, report, created) VALUES (?, ?, ?, ?)",
        (profile_id, report.get("timestamp", now),
         json.dumps(report, ensure_ascii=False), now)
    )
    conn.commit()


def trends_latest(profile_id):
    """Get latest trend report for profile."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT report FROM trends WHERE profile_id=? ORDER BY id DESC LIMIT 1",
        (profile_id,)
    ).fetchone()
    if row:
        return json.loads(row[0])
    return None


def trends_count():
    """Count trend reports."""
    conn = _get_conn()
    return conn.execute("SELECT COUNT(*) FROM trends").fetchone()[0]


# ─── Helpers ─────────────────────────────────────────────────────

def _row_to_queue_item(row):
    """Convert SQLite Row to dict."""
    if not row:
        return None
    d = dict(row)
    for json_field in ("posts", "image_variants", "publish_results"):
        if d.get(json_field) and isinstance(d[json_field], str):
            try:
                d[json_field] = json.loads(d[json_field])
            except (json.JSONDecodeError, TypeError):
                d[json_field] = {}
    return d


def migrate_json_to_db(queue_dir, trends_dir):
    """One-time migration from JSON files to SQLite."""
    migrated_queue = 0
    migrated_trends = 0

    # Migrate queue
    queue_path = Path(queue_dir)
    if queue_path.exists():
        for f in queue_path.glob("*.json"):
            try:
                item = json.loads(f.read_text())
                if not queue_get(item.get("id", "")):
                    queue_add(item)
                    migrated_queue += 1
            except Exception:
                pass

    # Migrate trends (only report JSONs, not debug files)
    trends_path = Path(trends_dir)
    if trends_path.exists():
        for f in sorted(trends_path.glob("*.json")):
            if f.name.startswith("_"):
                continue
            try:
                report = json.loads(f.read_text())
                profile_id = report.get("profile_id", "")
                if profile_id:
                    trends_save(profile_id, report)
                    migrated_trends += 1
            except Exception:
                pass

    # Move the sources aside so the migration can never run again: re-importing
    # old "approved" items once made the scheduler republish months-old posts.
    for path in (queue_path, trends_path):
        if path.exists():
            done = path / "_migrated"
            done.mkdir(exist_ok=True)
            for f in path.glob("*.json"):
                if not f.name.startswith("_"):
                    f.rename(done / f.name)

    return migrated_queue, migrated_trends


# ─── Analytics Operations ────────────────────────────────────────

def analytics_save(queue_id, profile_id, platform, post_id, likes=0, comments=0, views=0, shares=0):
    """Save analytics metrics — update if same hour, insert if new hour."""
    conn = _get_conn()
    collected_at = datetime.now().strftime("%Y-%m-%d %H:00")
    # Check if entry exists for this hour
    existing = conn.execute(
        "SELECT id FROM analytics WHERE queue_id=? AND platform=? AND collected_at=?",
        (queue_id, platform, collected_at)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE analytics SET likes=?, comments=?, views=?, shares=? WHERE id=?",
            (likes, comments, views, shares, existing[0])
        )
    else:
        conn.execute(
            """INSERT INTO analytics (queue_id, profile_id, platform, post_id, likes, comments, views, shares, collected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (queue_id, profile_id, platform, post_id, likes, comments, views, shares, collected_at)
        )
    conn.commit()


def analytics_get_latest(queue_id):
    """Get latest metrics for all platforms of a queue item."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT platform, post_id, likes, comments, views, shares, collected_at
           FROM analytics WHERE queue_id=?
           AND id IN (SELECT MAX(id) FROM analytics WHERE queue_id=? GROUP BY platform)""",
        (queue_id, queue_id)
    ).fetchall()
    return {r[0]: {"post_id": r[1], "likes": r[2], "comments": r[3],
                    "views": r[4], "shares": r[5], "collected_at": r[6]} for r in rows}


def analytics_cleanup_old(days=30):
    """Delete analytics data older than N days."""
    conn = _get_conn()
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    deleted = conn.execute("DELETE FROM analytics WHERE collected_at<?", (cutoff,)).rowcount
    conn.commit()
    return deleted


def analytics_summary(profile_id):
    """Get aggregate analytics summary for a profile."""
    conn = _get_conn()
    # Latest metrics per post per platform (deduplicated)
    rows = conn.execute(
        """SELECT a.platform, a.likes, a.comments, a.views, a.shares, q.topic_title, a.queue_id
           FROM analytics a
           JOIN queue q ON a.queue_id = q.id
           WHERE a.profile_id=?
           AND a.id IN (SELECT MAX(id) FROM analytics WHERE profile_id=? GROUP BY queue_id, platform)""",
        (profile_id, profile_id)
    ).fetchall()

    total_likes = sum(r[1] for r in rows)
    total_comments = sum(r[2] for r in rows)
    total_views = sum(r[3] for r in rows)
    total_shares = sum(r[4] for r in rows)

    # Per platform
    by_platform = {}
    for r in rows:
        plat = r[0]
        if plat not in by_platform:
            by_platform[plat] = {"likes": 0, "comments": 0, "views": 0, "shares": 0}
        by_platform[plat]["likes"] += r[1]
        by_platform[plat]["comments"] += r[2]
        by_platform[plat]["views"] += r[3]
        by_platform[plat]["shares"] += r[4]

    # Top posts by engagement (likes + comments)
    post_scores = {}
    for r in rows:
        qid = r[6]
        if qid not in post_scores:
            post_scores[qid] = {"topic": r[5], "likes": 0, "comments": 0, "views": 0}
        post_scores[qid]["likes"] += r[1]
        post_scores[qid]["comments"] += r[2]
        post_scores[qid]["views"] += r[3]
    top_posts = sorted(post_scores.items(), key=lambda x: x[1]["likes"] + x[1]["comments"], reverse=True)[:5]

    return {
        "total_posts": len(set(r[6] for r in rows)),
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_views": total_views,
        "total_shares": total_shares,
        "by_platform": by_platform,
        "top_posts": [{"id": qid, "topic": d["topic"][:50], "likes": d["likes"],
                        "comments": d["comments"], "views": d["views"]}
                       for qid, d in top_posts],
    }


def trends_list(profile_id, limit=20):
    """List trend reports for profile (id + timestamp only)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, timestamp FROM trends WHERE profile_id=? ORDER BY id DESC LIMIT ?",
        (profile_id, limit)
    ).fetchall()
    return [{"id": r[0], "timestamp": r[1]} for r in rows]


def trends_get_by_id(trend_id):
    """Get specific trend report by ID."""
    conn = _get_conn()
    row = conn.execute("SELECT report FROM trends WHERE id=?", (trend_id,)).fetchone()
    if row:
        return json.loads(row[0])
    return None
