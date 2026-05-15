"""
Teacher Availability Service
=============================
Combines two data sources to answer "Is teacher X available at time Y?":

  1. Base schedule  → routine_slots table (from uploaded PDF)
  2. Overrides      → teacher_availability table (teacher/admin added exceptions)

Override types:
  'unavailable' → teacher has class in routine but WON'T be there
                  (students should be notified, class may be cancelled)
  'busy'        → teacher has no class but is NOT in their office room
                  (students shouldn't come to room expecting to find them)
"""

import logging
from datetime import date, time, datetime
from typing import Optional

from app.core.supabase import supabase_admin

logger = logging.getLogger("yourDIU.availability")

DAY_NAMES = {
    0: "Monday", 1: "Tuesday", 2: "Wednesday",
    3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_to_day_name(d: date) -> str:
    return DAY_NAMES[d.weekday()]


def _times_overlap(start1: str, end1: str, start2: str, end2: str) -> bool:
    """Check if two time ranges overlap."""
    def to_min(t: str) -> int:
        h, m = t.split(":")
        return int(h) * 60 + int(m)
    s1, e1 = to_min(start1), to_min(end1)
    s2, e2 = to_min(start2), to_min(end2)
    return s1 < e2 and s2 < e1


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def get_teacher_schedule(
    teacher_initials: str,
    routine_id: Optional[str] = None,
) -> list[dict]:
    """
    Get the full base schedule for a teacher from the routine.
    If routine_id is None, uses the active routine.
    """
    query = (
        supabase_admin.table("routine_slots")
        .select("*, routines!inner(is_active, department)")
        .eq("teacher_initials", teacher_initials)
    )
    if routine_id:
        query = query.eq("routine_id", routine_id)
    else:
        query = query.eq("routines.is_active", True)

    resp = query.execute()
    return resp.data or []


def get_teacher_overrides(
    teacher_id: str,
    target_date: date,
) -> list[dict]:
    """Get all availability overrides for a teacher on a specific date."""
    resp = (
        supabase_admin.table("teacher_availability")
        .select("*")
        .eq("teacher_id", teacher_id)
        .eq("date", target_date.isoformat())
        .execute()
    )
    return resp.data or []


def check_teacher_availability(
    teacher_initials: str,
    teacher_id: str,
    target_date: date,
    query_start: str,   # "10:00"
    query_end: str,     # "11:30"
) -> dict:
    """
    Check if a teacher is available at a given date + time range.

    Returns a dict with:
      available: bool
      status: 'available' | 'in_class' | 'unavailable' | 'busy'
      class_info: dict (if they have class at that time)
      override: dict (if they have an override for that time)
      message: human-readable string
    """
    day_name = _date_to_day_name(target_date)

    # ── Step 1: Check base schedule ─────────────────────────────────────────
    schedule = get_teacher_schedule(teacher_initials)
    class_at_time = None

    for slot in schedule:
        if slot["day"] == day_name and _times_overlap(
            query_start, query_end, slot["time_start"][:5], slot["time_end"][:5]
        ):
            class_at_time = slot
            break

    # ── Step 2: Check overrides ─────────────────────────────────────────────
    overrides = get_teacher_overrides(teacher_id, target_date)
    override_at_time = None

    for ov in overrides:
        if _times_overlap(
            query_start, query_end, ov["time_start"][:5], ov["time_end"][:5]
        ):
            override_at_time = ov
            break

    # ── Step 3: Determine final status ──────────────────────────────────────
    if override_at_time:
        status = override_at_time["status"]   # 'unavailable' or 'busy'
        note   = override_at_time.get("public_note") or (
            "Not available at this time" if status == "unavailable"
            else "Busy — not in office"
        )
        return {
            "available":  False,
            "status":     status,
            "class_info": class_at_time,
            "override":   override_at_time,
            "message":    note,
        }

    if class_at_time:
        return {
            "available":  False,
            "status":     "in_class",
            "class_info": class_at_time,
            "override":   None,
            "message":    (
                f"Teaching {class_at_time['course_code']} "
                f"(Batch {class_at_time['batch']}, Section {class_at_time['section']}) "
                f"in Room {class_at_time['room']}"
            ),
        }

    return {
        "available":  True,
        "status":     "available",
        "class_info": None,
        "override":   None,
        "message":    "Available",
    }


def get_teacher_free_slots(
    teacher_initials: str,
    teacher_id: str,
    target_date: date,
) -> list[dict]:
    """
    Return all time slots in the day where the teacher is free.
    Used for answering "When is Sir X free today/tomorrow?"
    """
    from app.services.routine.parser import TIME_SLOTS

    day_name = _date_to_day_name(target_date)
    schedule = get_teacher_schedule(teacher_initials)
    overrides = get_teacher_overrides(teacher_id, target_date)

    free_slots = []
    for start, end in TIME_SLOTS:
        result = check_teacher_availability(
            teacher_initials, teacher_id, target_date, start, end
        )
        if result["available"]:
            free_slots.append({"time_start": start, "time_end": end})

    return free_slots


def get_teacher_day_summary(
    teacher_initials: str,
    teacher_id: str,
    target_date: date,
) -> dict:
    """
    Full day summary for a teacher: all slots, status of each.
    Used in the AI assistant's context when students ask about a teacher.
    """
    from app.services.routine.parser import TIME_SLOTS

    slots_summary = []
    for start, end in TIME_SLOTS:
        result = check_teacher_availability(
            teacher_initials, teacher_id, target_date, start, end
        )
        slots_summary.append({
            "time":    f"{start}-{end}",
            "status":  result["status"],
            "message": result["message"],
        })

    free_count = sum(1 for s in slots_summary if s["status"] == "available")

    return {
        "date":        target_date.isoformat(),
        "day":         _date_to_day_name(target_date),
        "teacher":     teacher_initials,
        "slots":       slots_summary,
        "free_count":  free_count,
        "busy_count":  len(TIME_SLOTS) - free_count,
    }


def format_availability_for_ai(summary: dict, teacher_name: str = "") -> str:
    """Format teacher day summary as natural language for the AI assistant context."""
    name   = teacher_name or summary["teacher"]
    day    = summary["day"]
    date_s = summary["date"]

    lines = [f"{name} — Schedule for {day} ({date_s}):\n"]
    for slot in summary["slots"]:
        icon = "✓ Free" if slot["status"] == "available" else "✗ Busy"
        lines.append(f"  {slot['time']}: {icon} — {slot['message']}")

    lines.append(
        f"\nFree slots: {summary['free_count']} / {len(summary['slots'])}"
    )
    return "\n".join(lines)
