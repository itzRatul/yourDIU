"""
Routine PDF Parser
==================
Parses CSE Class Routine PDFs from Daffodil International University.

PDF structure (from analysis):
  - Landscape orientation, multiple pages (one or two days per page)
  - Header: "Class Routine for CSE Program", version, effective date
  - Day header: "SATURDAY", "SUNDAY", etc.
  - Time slot headers: 08:30-10:00 | 10:00-11:30 | 11:30-01:00 | 01:00-02:30 | 02:30-04:00 | 04:00-05:30
  - Sub-columns per slot: Room | Course | Teacher
  - Course format: CSE315(66_E) or CSE225(RE_A(3_C))

Strategy:
  1. Extract tables page-by-page with pdfplumber
  2. Detect which day each table belongs to
  3. Map column positions to time slots
  4. Parse each row into structured RoutineSlot
  5. Fallback: Gemini Vision for pages where table extraction fails
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("yourDIU.routine_parser")

# ── Time slots ──────────────────────────────────────────────────────────────
TIME_SLOTS: list[tuple[str, str]] = [
    ("08:30", "10:00"),
    ("10:00", "11:30"),
    ("11:30", "13:00"),   # displayed as 01:00 in 12-hr format
    ("13:00", "14:30"),
    ("14:30", "16:00"),
    ("16:00", "17:30"),
]

# 12-hr display labels as they appear in the PDF header row
TIME_LABELS_12HR: list[str] = [
    "08:30-10:00",
    "10:00-11:30",
    "11:30-01:00",
    "01:00-02:30",
    "02:30-04:00",
    "04:00-05:30",
]

DAYS = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]

# Regex to parse: CSE315(66_E) | CSE225(RE_A(3_C)) | PHY101(71_B)
_COURSE_PATTERN = re.compile(
    r"^([A-Z]{2,4}\d{3}(?:\([A-Z]+\))?)"      # course code (may have suffix like (RE))
    r"\(([^)_]+)"                               # opening paren + batch
    r"(?:_([^)]+))?\)+$"                        # _section + closing parens
)

# Simpler fallback: just grab course code before first '('
_COURSE_CODE_ONLY = re.compile(r"^([A-Z]{2,4}\d{3}(?:\([A-Z]+\))?)")


@dataclass
class ParsedSlot:
    day:             str
    time_start:      str       # "08:30"
    time_end:        str       # "10:00"
    room:            str
    course_code:     str
    batch:           str       = ""
    section:         str       = ""
    teacher_initials: str      = ""
    raw_course_text: str       = ""


@dataclass
class ParsedRoutine:
    title:          str
    department:     str        = "CSE"
    version:        str        = ""
    semester:       str        = ""
    effective_from: str        = ""    # ISO date string
    slots:          list[ParsedSlot] = field(default_factory=list)
    parse_errors:   list[str]  = field(default_factory=list)


# ---------------------------------------------------------------------------
# Course code parsing
# ---------------------------------------------------------------------------

def _parse_course(raw: str) -> tuple[str, str, str]:
    """
    Parse raw course text like 'CSE315(66_E)' or 'CSE225(RE_A(3_C))'.
    Returns (course_code, batch, section).
    """
    raw = raw.strip()
    if not raw:
        return "", "", ""

    m = _COURSE_PATTERN.match(raw)
    if m:
        code    = m.group(1).strip()
        batch   = m.group(2).strip() if m.group(2) else ""
        section = m.group(3).strip() if m.group(3) else ""
        # Clean up nested parens in RE cases like "RE_A(3_C)" → batch="RE_A(3", section="C"
        return code, batch, section

    # Fallback: at least grab the course code
    m2 = _COURSE_CODE_ONLY.match(raw)
    if m2:
        return m2.group(1), "", ""

    return raw, "", ""


# ---------------------------------------------------------------------------
# pdfplumber-based parser
# ---------------------------------------------------------------------------

def _extract_meta(first_page_text: str) -> tuple[str, str, str, str]:
    """Extract title, version, semester, effective_from from header text."""
    version   = ""
    semester  = ""
    eff_from  = ""
    title     = "CSE Class Routine"

    ver_match = re.search(r"Version\s+(V[\d.]+)", first_page_text, re.IGNORECASE)
    if ver_match:
        version = ver_match.group(1)
        title   = f"CSE Class Routine {version}"

    # "Summer-2026", "Fall-2025", "Spring-2026"
    sem_match = re.search(r"(Summer|Fall|Spring|Winter)[-\s](\d{4})", first_page_text, re.IGNORECASE)
    if sem_match:
        semester = f"{sem_match.group(1)}-{sem_match.group(2)}"
        title    = f"{title} {semester}"

    # "Effective From: Saturday 16 May, 2026"
    eff_match = re.search(
        r"Effective From.*?(\d{1,2})\s+(\w+)[,\s]+(\d{4})", first_page_text, re.IGNORECASE
    )
    if eff_match:
        try:
            from datetime import datetime
            eff_from = datetime.strptime(
                f"{eff_match.group(1)} {eff_match.group(2)} {eff_match.group(3)}", "%d %B %Y"
            ).date().isoformat()
        except ValueError:
            pass

    return title, version, semester, eff_from


def _find_day_in_text(text: str) -> Optional[str]:
    """Return the day name if a day header is found in text."""
    upper = text.upper()
    for day in DAYS:
        if day.upper() in upper:
            return day
    return None


def _parse_table_rows(rows: list[list], day: str) -> list[ParsedSlot]:
    """
    Parse pdfplumber table rows for a given day.
    The table has 3 columns per time slot: Room | Course | Teacher
    Total: 6 slots × 3 cols = 18 data columns (plus possible row label column).
    """
    slots: list[ParsedSlot] = []

    if not rows or len(rows) < 2:
        return slots

    # Find the header row that contains time labels
    header_row_idx = None
    for i, row in enumerate(rows):
        row_text = " ".join(str(c or "") for c in row)
        if any(lbl in row_text for lbl in ["08:30", "10:00", "11:30"]):
            header_row_idx = i
            break

    if header_row_idx is None:
        return slots

    # Map column index → (slot_index, field_type: 0=room, 1=course, 2=teacher)
    header_row  = rows[header_row_idx]
    col_map: dict[int, tuple[int, str]] = {}
    slot_idx    = -1

    for col_i, cell in enumerate(header_row):
        cell_str = str(cell or "").strip()
        # A time label starts a new slot group
        if any(lbl in cell_str for lbl in ["08:30", "10:00", "11:30", "01:00", "02:30", "04:00"]):
            slot_idx += 1
            col_map[col_i] = (slot_idx, "room")
        elif cell_str.lower() in ("course", ""):
            if slot_idx >= 0:
                col_map[col_i] = (slot_idx, "course")
        elif cell_str.lower() in ("teacher",):
            if slot_idx >= 0:
                col_map[col_i] = (slot_idx, "teacher")

    # If header detection failed, fall back to assuming 3-column repeating pattern
    if not col_map:
        offset = 1 if str(rows[0][0] or "").strip().lower() in ("room", "") else 0
        for col_i in range(offset, len(header_row)):
            s_idx   = (col_i - offset) // 3
            f_type  = ["room", "course", "teacher"][(col_i - offset) % 3]
            col_map[col_i] = (s_idx, f_type)

    # Process data rows
    for row in rows[header_row_idx + 1:]:
        if not row:
            continue
        # Build per-slot buffer
        slot_data: dict[int, dict] = {}
        for col_i, cell in enumerate(row):
            if col_i not in col_map:
                continue
            s_idx, f_type = col_map[col_i]
            if s_idx not in slot_data:
                slot_data[s_idx] = {"room": "", "course": "", "teacher": ""}
            val = str(cell or "").strip()
            if val:
                slot_data[s_idx][f_type] = val

        for s_idx, data in slot_data.items():
            room    = data.get("room", "").strip()
            course  = data.get("course", "").strip()
            teacher = data.get("teacher", "").strip()

            # Skip empty or header-only rows
            if not room or not course:
                continue
            if course.lower() in ("course", "room", "teacher"):
                continue

            if s_idx >= len(TIME_SLOTS):
                continue

            code, batch, section = _parse_course(course)

            slots.append(ParsedSlot(
                day              = day,
                time_start       = TIME_SLOTS[s_idx][0],
                time_end         = TIME_SLOTS[s_idx][1],
                room             = room,
                course_code      = code,
                batch            = batch,
                section          = section,
                teacher_initials = teacher,
                raw_course_text  = course,
            ))

    return slots


def parse_routine_pdf(file_path: str | Path) -> ParsedRoutine:
    """
    Main entry point: parse a DIU routine PDF file.
    Returns a ParsedRoutine with all slots extracted.
    """
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber")

    file_path = Path(file_path)
    result    = ParsedRoutine(title="CSE Class Routine")

    try:
        with pdfplumber.open(file_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"

            # Extract metadata from full text
            result.title, result.version, result.semester, result.effective_from = (
                _extract_meta(full_text)
            )

            current_day: Optional[str] = None

            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text() or ""

                # Detect day change on this page
                day_found = _find_day_in_text(page_text)
                if day_found:
                    current_day = day_found

                if not current_day:
                    continue

                # Extract tables from this page
                tables = page.extract_tables(
                    table_settings={
                        "vertical_strategy":   "lines",
                        "horizontal_strategy": "lines",
                        "snap_tolerance":       5,
                        "join_tolerance":       3,
                    }
                )

                if not tables:
                    # Try text-based extraction as fallback
                    tables = page.extract_tables()

                for table in (tables or []):
                    # Check if this table block has a different day in its text
                    table_text = " ".join(
                        str(cell or "") for row in table for cell in row
                    )
                    day_in_table = _find_day_in_text(table_text)
                    active_day   = day_in_table or current_day

                    parsed = _parse_table_rows(table, active_day)
                    result.slots.extend(parsed)

                logger.debug("Page %d: day=%s, slots so far=%d", page_num, current_day, len(result.slots))

    except Exception as exc:
        msg = f"PDF parse error: {exc}"
        logger.error(msg)
        result.parse_errors.append(msg)

    logger.info(
        "Parsed routine '%s': %d slots, %d errors",
        result.title, len(result.slots), len(result.parse_errors),
    )
    return result


# ---------------------------------------------------------------------------
# Gemini Vision fallback (for pages where pdfplumber fails)
# ---------------------------------------------------------------------------

async def parse_page_with_gemini(image_bytes: bytes, day: str) -> list[ParsedSlot]:
    """
    Use Gemini Vision to extract routine slots from a page image.
    Called when pdfplumber returns 0 slots for a page.
    """
    try:
        import google.generativeai as genai
        from app.core.config import settings

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""
This is a class routine table for {day} at Daffodil International University.
Extract ALL class entries as JSON array. Each entry must have:
  "room": room code (e.g. "KT-201"),
  "course_code": course code (e.g. "CSE315"),
  "batch": batch number as string (e.g. "66"),
  "section": section letter (e.g. "E"),
  "teacher_initials": teacher code (e.g. "MAK"),
  "time_start": 24hr format (e.g. "08:30"),
  "time_end": 24hr format (e.g. "10:00")

Time slots: 08:30-10:00, 10:00-11:30, 11:30-13:00, 13:00-14:30, 14:30-16:00, 16:00-17:30
Return ONLY valid JSON array, no explanation.
"""
        import PIL.Image
        import io
        img      = PIL.Image.open(io.BytesIO(image_bytes))
        response = await model.generate_content_async([prompt, img])
        text     = response.text.strip()

        # Extract JSON from response
        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if not json_match:
            return []

        import json
        entries = json.loads(json_match.group())
        slots   = []
        for e in entries:
            slots.append(ParsedSlot(
                day              = day,
                time_start       = e.get("time_start", ""),
                time_end         = e.get("time_end", ""),
                room             = e.get("room", ""),
                course_code      = e.get("course_code", ""),
                batch            = str(e.get("batch", "")),
                section          = e.get("section", ""),
                teacher_initials = e.get("teacher_initials", ""),
                raw_course_text  = f"{e.get('course_code','')}({e.get('batch','')}_{e.get('section','')})",
            ))
        return slots

    except Exception as exc:
        logger.warning("Gemini Vision fallback failed: %s", exc)
        return []
