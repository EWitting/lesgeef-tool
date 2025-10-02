# Pre-Assigned Teachers, "Geen Les" & Past Lessons Implementation

## Overview
Updated the constraint solver in `schedule_lessons()` to:
1. Respect and fix teacher assignments that are already specified in the imported planning Excel file
2. Skip lessons marked as "Geen les" (no lesson) and keep them empty
3. Skip lessons in the past and preserve their existing state

## Problem
Previously, the constraint solver had three issues:
1. When importing a planning file that already had teachers assigned to specific lessons, it would ignore these pre-assignments and potentially reassign different teachers
2. When importing lessons marked as "Geen les" (no lesson), the solver would still try to assign teachers to these cancelled lessons
3. When running the scheduler on a planning with past lessons, it would overwrite or change the existing teacher assignments for lessons that already occurred

## Solution

### Pre-Assigned Teachers
The constraint solver now:
1. **Detects pre-assigned teachers** by checking if `les.lesgevers` is populated when importing
2. **Fixes these assignments** using hard constraints (`model.Add(var == 1)`)
3. **Allows pre-assigned teachers** even if they marked "Nee" in the availability form
4. **Excludes them from penalties** since they are mandatory assignments
5. **Uses fuzzy matching** (Levenshtein distance) to match teacher names robustly

### "Geen Les" (No Lesson)
The constraint solver now:
1. **Detects cancelled lessons** by checking if `les.gaat_door == False` in the imported planning
2. **Skips these lessons** completely - no assignment variables created
3. **Keeps them empty** in the output (no teachers assigned)
4. **Excludes them from all constraints** including min/max teachers, experience requirements, etc.
5. **Excludes them from workload calculations** when computing baseline lesson counts

### Past Lessons
The constraint solver now:
1. **Detects past lessons** by comparing `les.datum < date.today()`
2. **Skips these lessons** completely - no assignment variables created
3. **Preserves existing state** in the output (keeps current teachers or empty status)
4. **Excludes them from all constraints** to avoid affecting optimization for future lessons
5. **Excludes them from workload calculations** for baseline and distribution
6. **Excludes them from report** "Niet Ingevulde Lessen" section

## Technical Details

### Changes in `_make_model()` (lines 70-96)

**"Geen Les" Detection:**
```python
geen_les_indices = set()
for index_les, les in enumerate(lessen):
    if not les.gaat_door:
        geen_les_indices.add(index_les)
        print(f"Les {les.datetime()} gaat niet door (overgeslagen in scheduler)")
```

These indices are then used throughout the function to skip cancelled lessons in all loops and constraints.

**Pre-assignment Detection with Fuzzy Matching:**
```python
pre_assigned = set()
for index_les, les in enumerate(lessen):
    if les.lesgevers:  # Check if teachers already assigned
        for lesgever in les.lesgevers:
            # Match by name using fuzzy matching (same as importer.py)
            distances = [distance(lesgever.naam, lg.naam) for lg in lesgevers]
            min_distance = min(distances) if distances else float('inf')
            
            if min_distance < 3:  # Threshold for accepting match
                index_lesgever = distances.index(min_distance)
                pre_assigned.add((index_lesgever, index_les))
```

The fuzzy matching uses the same `distance()` function from `importer.py` which:
- Calculates Levenshtein edit distance
- Tries full name match, first name only, and first name reversed
- Has a threshold of < 3 for accepting matches
- Handles cases where only first name is used in the Excel file

**Hard Constraint for Pre-assignments:**
```python
if is_available or is_pre_assigned:
    var = model.NewBoolVar(f"assignment_{index_lesgever}_{index_les}")
    # ... add to data structures ...
    
    if is_pre_assigned:
        model.Add(var == 1)  # MUST be assigned
```

### Soft Constraint Adjustments

1. **Lesgever Bonus** (lines 108-114): Pre-assigned teachers excluded from bonus since they're mandatory
2. **Misschien Penalty** (lines 116-121): Pre-assigned teachers excluded since their availability is irrelevant
3. **Ervaring Constraint** (lines 124-144): If a lesson already has an experienced pre-assigned teacher, the constraint is satisfied

### Soft Constraints Still Applied
- **Multiple lessons per week penalty**: Still applies to prevent scheduling pre-assigned teachers for even more lessons
- **Workload distribution penalty**: Pre-assigned teachers count towards their total workload

## Data Flow

1. **Import Planning** (`import_planning()`): Reads Excel, creates `Les` objects with `lesgevers` populated from columns
2. **Import Availability** (`import_forms_datumprikker()`): Matches availability data with lessons via `match_lessen()`
3. **Schedule Lessons** (`schedule_lessons()`): Detects pre-assignments and fixes them in the constraint solver
4. **Export Planning** (`export_planning()`): Writes final schedule back to Excel

## Excel File Format

The planning Excel file has this structure:
```
| Seizoen | Week | Datum | Tijd | Lesgever1 | Lesgever2 | Lesgever3 | Info |
```

- If teacher names are already filled in the Lesgever columns, they will be treated as pre-assigned
- Pre-assigned teachers will be preserved even if they indicate "Nee" in the availability form
- The constraint solver will fill in remaining empty slots around the pre-assignments

## Edge Cases Handled

1. **"Geen les" in any teacher column**: Detected (case-insensitive) and lesson is skipped
2. **"Geen les" with pre-assigned teachers**: Should not happen (importer clears lesgevers), but if it does, the lesson is skipped
3. **Past lessons with no teachers**: Preserved as-is (not filled in by scheduler)
4. **Past lessons with teachers**: Preserved exactly (not modified)
5. **Today's lessons**: Treated as future lessons (date.today() is the cutoff, so today >= today)
6. **Name variations** (e.g., "Alice" vs "Alice Smith"): Fuzzy matching with Levenshtein distance handles partial names
7. **Pre-assigned teacher not in availability matrix**: Warning printed with best match distance
8. **Pre-assigned teacher marked "Nee"**: Allowed anyway (overrides availability)
9. **Lesson already has experienced teacher**: No penalty for missing experienced teacher
10. **Pre-assigned teacher exceeds max**: Still enforced (max constraint applies to everyone)
11. **Typos in names**: Small typos (distance < 3) are automatically matched with a warning message
12. **Empty weeks due to "Geen les" or past lessons**: Workload baseline calculation excludes both

## Usage Example

If your Excel planning has:
```
| ... | Datum      | Tijd         | Alice     | Bob       | Charlie | Info         |
| ... | 2025-10-01 | 17:00-20:00 | Alice     |           |         | PKursus      |
| ... | 2025-10-03 | 17:00-20:00 |           |           |         | Regular Les  |
| ... | 2025-10-05 | 17:00-20:00 | Geen les  |           |         | Robbie Games |
```

The constraint solver will:
- ✅ Keep Alice assigned to the October 1st lesson (fixed)
- ✅ Fill in teachers for October 3rd based on availability and constraints
- ✅ **Skip October 5th completely (no teachers assigned)**
- ✅ Potentially add Bob and/or Charlie to October 1st if needed to meet minimum requirements
- ✅ Print: `"Les 2025-10-05 17:00:00 gaat niet door (overgeslagen in scheduler)"`

## Testing

To test the implementation:

**Pre-assigned Teachers:**
1. Create a planning Excel file with some teachers already filled in
2. Run `main.py` with this planning
3. Check the console output for "Pre-assigned: [Teacher] aan [Date]" messages
4. Verify that the final exported planning maintains these pre-assignments
5. Verify that additional teachers are added optimally around these fixed assignments

**"Geen Les":**
1. Create a planning Excel file with "Geen les" in any teacher column for some lessons
2. Run `main.py` with this planning
3. Check the console output for "Les [Date] gaat niet door (overgeslagen in scheduler)" messages
4. Verify that the final exported planning keeps these lessons empty (no teachers assigned)
5. Verify that these lessons are not counted in workload statistics

## Benefits

- **Historical data preservation**: Past lessons remain untouched, preserving the actual teaching record
- **Accurate scheduling**: Only schedules future lessons, avoiding confusion about what actually happened
- **Cancelled lesson handling**: Properly skips lessons marked as "Geen les" without trying to assign teachers
- **Accurate workload**: Cancelled and past lessons don't affect workload distribution calculations
- **Partial manual scheduling**: Allows manual assignment of specific teachers to specific lessons
- **Constraint preservation**: Pre-assignments still respect hard constraints (e.g., max teachers)
- **Optimal filling**: Remaining slots are filled optimally by the solver
- **Special cases**: Can handle situations like "Alice must teach this lesson" while letting solver optimize the rest
- **Robust name matching**: Fuzzy matching handles typos, first names only, and name variations automatically
- **Consistent behavior**: Uses the same matching logic as the availability form importer
- **Flexible planning**: Supports mixed scenarios with pre-assigned, cancelled, past, and to-be-scheduled lessons
- **Clean reports**: "Niet Ingevulde Lessen" only shows future unfilled lessons, not past ones

