"""Persistence module for Carbon Coach using SQLite.

Maintains multi-session activity logs, budget configurations, and campus groups.
Ensures history outlives individual sessions and enables 6-month rolling budget calculations.
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from carbon_coach.factors import DEFAULT_MONTHLY_BUDGET_KG, DEFAULT_SIX_MONTH_BUDGET_KG

from contextlib import contextmanager

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "carbon_coach.db")


@contextmanager
def get_db(db_path: Optional[str] = None):
    """Context manager for SQLite connection that guarantees closing on exit."""
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Initializes SQLite tables for activities, budgets, and campus groups."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'default_user',
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                details TEXT NOT NULL,
                kg_co2e REAL NOT NULL,
                metadata_json TEXT
            );
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_activities_user_time 
            ON activities (user_id, timestamp);
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                user_id TEXT PRIMARY KEY,
                monthly_kg REAL NOT NULL DEFAULT 150.0,
                six_month_kg REAL NOT NULL DEFAULT 900.0,
                updated_at TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campus_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_type TEXT NOT NULL,
                group_name TEXT NOT NULL,
                UNIQUE(user_id, group_type)
            );
        """)


def save_activity(
    category: str,
    details: str,
    kg_co2e: float,
    user_id: str = "default_user",
    timestamp: Optional[datetime] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Persists a single carbon activity record.

    Returns the inserted record dict with ID.
    """
    init_db(db_path)
    ts = (timestamp or datetime.now()).isoformat()
    meta_str = json.dumps(metadata or {})
    kg_val = round(float(kg_co2e), 4)

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO activities (user_id, timestamp, category, details, kg_co2e, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, ts, category.strip().lower(), details.strip(), kg_val, meta_str),
        )
        record_id = cursor.lastrowid

    return {
        "id": record_id,
        "user_id": user_id,
        "timestamp": ts,
        "category": category.strip().lower(),
        "details": details.strip(),
        "kg_co2e": kg_val,
        "metadata": metadata or {},
    }


def _get_period_date_ranges(period: str, ref_time: Optional[datetime] = None) -> Tuple[datetime, datetime, datetime, datetime]:
    """Calculates (current_start, current_end, prev_start, prev_end) for a given period."""
    now = ref_time or datetime.now()
    p = period.lower().strip()

    if p == "today":
        curr_start = datetime(now.year, now.month, now.day, 0, 0, 0)
        curr_end = now
        prev_start = curr_start - timedelta(days=1)
        prev_end = datetime(now.year, now.month, now.day, 0, 0, 0) - timedelta(microseconds=1)
    elif p in ("week", "this_week"):
        curr_start = now - timedelta(days=7)
        curr_end = now
        prev_start = now - timedelta(days=14)
        prev_end = curr_start
    elif p in ("month", "this_month"):
        curr_start = datetime(now.year, now.month, 1, 0, 0, 0)
        curr_end = now
        # previous month
        if now.month == 1:
            prev_start = datetime(now.year - 1, 12, 1, 0, 0, 0)
        else:
            prev_start = datetime(now.year, now.month - 1, 1, 0, 0, 0)
        prev_end = curr_start - timedelta(microseconds=1)
    elif p in ("six_months", "6_months", "last_6_months"):
        curr_start = now - timedelta(days=180)
        curr_end = now
        prev_start = now - timedelta(days=360)
        prev_end = curr_start
    elif p == "all":
        curr_start = datetime(2000, 1, 1, 0, 0, 0)
        curr_end = now
        prev_start = curr_start
        prev_end = curr_start
    else:
        # Default fallback to 30 days
        curr_start = now - timedelta(days=30)
        curr_end = now
        prev_start = now - timedelta(days=60)
        prev_end = curr_start

    return curr_start, curr_end, prev_start, prev_end


def get_activities_for_range(
    start_time: datetime,
    end_time: datetime,
    user_id: str = "default_user",
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves all activities between start_time and end_time for user_id."""
    init_db(db_path)
    start_str = start_time.isoformat()
    end_str = end_time.isoformat()

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, timestamp, category, details, kg_co2e, metadata_json
            FROM activities
            WHERE user_id = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp DESC
            """,
            (user_id, start_str, end_str),
        )
        rows = cursor.fetchall()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "user_id": r["user_id"],
            "timestamp": r["timestamp"],
            "category": r["category"],
            "details": r["details"],
            "kg_co2e": round(float(r["kg_co2e"]), 4),
            "metadata": json.loads(r["metadata_json"] or "{}"),
        })
    return results


def get_all_activities(
    user_id: str = "default_user",
    limit: int = 100,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves the most recent activities for user_id."""
    init_db(db_path)
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, timestamp, category, details, kg_co2e, metadata_json
            FROM activities
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = cursor.fetchall()

    return [
        {
            "id": r["id"],
            "user_id": r["user_id"],
            "timestamp": r["timestamp"],
            "category": r["category"],
            "details": r["details"],
            "kg_co2e": round(float(r["kg_co2e"]), 4),
            "metadata": json.loads(r["metadata_json"] or "{}"),
        }
        for r in rows
    ]


def get_summary_data(
    period: str,
    user_id: str = "default_user",
    ref_time: Optional[datetime] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Computes total kg CO2e, category breakdown, and trend vs previous period."""
    curr_start, curr_end, prev_start, prev_end = _get_period_date_ranges(period, ref_time)
    current_activities = get_activities_for_range(curr_start, curr_end, user_id, db_path)
    prev_activities = get_activities_for_range(prev_start, prev_end, user_id, db_path)

    total_kg = sum(a["kg_co2e"] for a in current_activities)
    prev_total_kg = sum(a["kg_co2e"] for a in prev_activities)

    # Category breakdown
    cat_breakdown: Dict[str, Dict[str, Any]] = {}
    for a in current_activities:
        cat = a["category"]
        if cat not in cat_breakdown:
            cat_breakdown[cat] = {"kg_co2e": 0.0, "count": 0, "percentage": 0.0}
        cat_breakdown[cat]["kg_co2e"] += a["kg_co2e"]
        cat_breakdown[cat]["count"] += 1

    for cat, data in cat_breakdown.items():
        data["kg_co2e"] = round(data["kg_co2e"], 3)
        if total_kg > 0:
            data["percentage"] = round((data["kg_co2e"] / total_kg) * 100, 1)

    diff_kg = round(total_kg - prev_total_kg, 3)
    if prev_total_kg > 0:
        percent_change = round(((total_kg - prev_total_kg) / prev_total_kg) * 100, 1)
    else:
        percent_change = 0.0 if total_kg == 0 else 100.0

    if diff_kg > 0.001:
        direction = "increased"
    elif diff_kg < -0.001:
        direction = "decreased"
    else:
        direction = "unchanged"

    return {
        "period": period,
        "total_kg_co2e": round(total_kg, 3),
        "activity_count": len(current_activities),
        "category_breakdown": cat_breakdown,
        "trend": {
            "previous_period_kg": round(prev_total_kg, 3),
            "diff_kg": diff_kg,
            "percent_change": percent_change,
            "direction": direction,
        },
        "start_time": curr_start.isoformat(),
        "end_time": curr_end.isoformat(),
    }


def set_user_budget(
    monthly_kg: float,
    six_month_kg: float,
    user_id: str = "default_user",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Updates user budget thresholds."""
    init_db(db_path)
    m_val = round(float(monthly_kg), 2)
    s_val = round(float(six_month_kg), 2)
    now_str = datetime.now().isoformat()

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO budgets (user_id, monthly_kg, six_month_kg, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                monthly_kg = excluded.monthly_kg,
                six_month_kg = excluded.six_month_kg,
                updated_at = excluded.updated_at
            """,
            (user_id, m_val, s_val, now_str),
        )

    return {
        "user_id": user_id,
        "monthly_kg": m_val,
        "six_month_kg": s_val,
        "updated_at": now_str,
    }


def get_user_budget(user_id: str = "default_user", db_path: Optional[str] = None) -> Dict[str, float]:
    """Retrieves current budget thresholds for user_id, defaulting to spec constants."""
    init_db(db_path)
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT monthly_kg, six_month_kg FROM budgets WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()

    if row:
        return {
            "monthly_kg": float(row["monthly_kg"]),
            "six_month_kg": float(row["six_month_kg"]),
        }
    return {
        "monthly_kg": DEFAULT_MONTHLY_BUDGET_KG,
        "six_month_kg": DEFAULT_SIX_MONTH_BUDGET_KG,
    }


def get_budget_status(
    user_id: str = "default_user",
    ref_time: Optional[datetime] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluates both the current calendar month and rolling 6 months against budgets.

    Status thresholds:
    - < 80%: ok
    - 80% to 100%: warning
    - > 100%: exceeded
    """
    budgets = get_user_budget(user_id, db_path)
    m_budget = budgets["monthly_kg"]
    s_budget = budgets["six_month_kg"]

    now = ref_time or datetime.now()

    # Window 1: Calendar Month (1st of month to now)
    month_start = datetime(now.year, now.month, 1, 0, 0, 0)
    month_activities = get_activities_for_range(month_start, now, user_id, db_path)
    month_used = round(sum(a["kg_co2e"] for a in month_activities), 3)

    month_percent = round((month_used / m_budget) * 100, 1) if m_budget > 0 else 0.0
    if month_percent > 100.0:
        m_status = "exceeded"
        m_remaining = 0.0
        m_excess = round(month_used - m_budget, 3)
    elif month_percent >= 80.0:
        m_status = "warning"
        m_remaining = round(max(0.0, m_budget - month_used), 3)
        m_excess = 0.0
    else:
        m_status = "ok"
        m_remaining = round(max(0.0, m_budget - month_used), 3)
        m_excess = 0.0

    # Window 2: Rolling 6 months (180 days to now)
    six_start = now - timedelta(days=180)
    six_activities = get_activities_for_range(six_start, now, user_id, db_path)
    six_used = round(sum(a["kg_co2e"] for a in six_activities), 3)

    six_percent = round((six_used / s_budget) * 100, 1) if s_budget > 0 else 0.0
    if six_percent > 100.0:
        s_status = "exceeded"
        s_remaining = 0.0
        s_excess = round(six_used - s_budget, 3)
    elif six_percent >= 80.0:
        s_status = "warning"
        s_remaining = round(max(0.0, s_budget - six_used), 3)
        s_excess = 0.0
    else:
        s_status = "ok"
        s_remaining = round(max(0.0, s_budget - six_used), 3)
        s_excess = 0.0

    # Overall summary status
    if m_status == "exceeded" or s_status == "exceeded":
        overall = "exceeded"
    elif m_status == "warning" or s_status == "warning":
        overall = "warning"
    else:
        overall = "ok"

    return {
        "status": overall,
        "monthly": {
            "used_kg": month_used,
            "budget_kg": m_budget,
            "remaining_kg": m_remaining,
            "excess_kg": m_excess,
            "percent_used": month_percent,
            "status": m_status,
        },
        "six_months": {
            "used_kg": six_used,
            "budget_kg": s_budget,
            "remaining_kg": s_remaining,
            "excess_kg": s_excess,
            "percent_used": six_percent,
            "status": s_status,
        },
    }


def get_highest_emitting_category(
    user_id: str = "default_user",
    period: str = "month",
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Identifies the category contributing the highest kg CO2e in the given period."""
    summary = get_summary_data(period, user_id=user_id, db_path=db_path)
    breakdown = summary.get("category_breakdown", {})
    if not breakdown:
        return None

    sorted_cats = sorted(breakdown.items(), key=lambda item: item[1]["kg_co2e"], reverse=True)
    top_cat, top_data = sorted_cats[0]
    return {
        "category": top_cat,
        "kg_co2e": top_data["kg_co2e"],
        "percentage": top_data["percentage"],
        "count": top_data["count"],
        "total_period_kg": summary["total_kg_co2e"],
    }


def record_user_group(
    user_id: str,
    group_type: str,
    group_name: str,
    db_path: Optional[str] = None,
) -> None:
    """Assigns a user to a campus group (hostel, department, etc.)."""
    init_db(db_path)
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO campus_groups (user_id, group_type, group_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, group_type) DO UPDATE SET
                group_name = excluded.group_name
            """,
            (user_id, group_type.strip().lower(), group_name.strip()),
        )


def get_leaderboard_data(
    group_type: str,
    period: str = "month",
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Calculates average emissions per member for groups of group_type."""
    init_db(db_path)
    curr_start, curr_end, _, _ = _get_period_date_ranges(period)
    start_str = curr_start.isoformat()
    end_str = curr_end.isoformat()
    gt = group_type.strip().lower()

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT cg.group_name, 
                   COUNT(DISTINCT cg.user_id) as member_count,
                   COALESCE(SUM(a.kg_co2e), 0.0) as total_kg
            FROM campus_groups cg
            LEFT JOIN activities a 
                   ON cg.user_id = a.user_id 
                  AND a.timestamp >= ? 
                  AND a.timestamp <= ?
            WHERE cg.group_type = ?
            GROUP BY cg.group_name
            ORDER BY (COALESCE(SUM(a.kg_co2e), 0.0) / COUNT(DISTINCT cg.user_id)) ASC
            """,
            (start_str, end_str, gt),
        )
        rows = cursor.fetchall()

    leaderboard = []
    for rank, r in enumerate(rows, 1):
        members = max(1, r["member_count"])
        total = round(float(r["total_kg"]), 3)
        avg = round(total / members, 3)
        leaderboard.append({
            "rank": rank,
            "group_name": r["group_name"],
            "group_type": gt,
            "member_count": members,
            "total_kg": total,
            "avg_kg_per_person": avg,
        })
    return leaderboard
