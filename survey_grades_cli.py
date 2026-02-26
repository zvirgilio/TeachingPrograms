import argparse
import sys
import re
import difflib
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Shared helpers (copied from survey_grades.py)
# ---------------------------------------------------------------------------

def clean_text(text):
    """Normalize strings for matching (remove punctuation, lowercase)."""
    if pd.isna(text):
        return ""
    if str(text)[-2:] == ".0":
        text = str(text)[:-2]
    text = str(text).lower().strip()
    text = text.replace('-', ' ').replace('.', '')
    return " ".join(text.split())


def auto_detect_columns(columns):
    """
    Attempt to identify which survey CSV columns hold first name, last name,
    and student ID.

    Returns a dict:
        {
            'first_name': (col_name, confidence),
            'last_name':  (col_name, confidence),
            'sid':        (col_name, confidence),
        }
    where confidence is 'high', 'low', or None.
    """
    PATTERNS = {
        'first_name': ['firstname', 'first', 'givenname', 'given', 'fname'],
        'last_name':  ['lastname', 'last', 'surname', 'family', 'familyname', 'lname'],
        'sid':        ['sid', 'studentid', 'id', 'studentnumber', 'emplid', 'campusid'],
    }

    def normalize(s):
        return re.sub(r'[\s\-_\.]+', '', s.lower())

    result = {}
    for role, patterns in PATTERNS.items():
        best_col = None
        best_score = 0.0
        for col in columns:
            norm_col = normalize(col)
            for pat in patterns:
                score = difflib.SequenceMatcher(None, norm_col, pat).ratio()
                if norm_col == pat:
                    score = 1.0
                if score > best_score:
                    best_score = score
                    best_col = col

        if best_score >= 0.85:
            confidence = 'high'
        elif best_score >= 0.5:
            confidence = 'low'
        else:
            confidence = None
            best_col = None

        result[role] = (best_col, confidence)

    return result


def process_data(gradebook_df, survey_df, assignment_col, first_col, last_col, sid_col, points):
    """
    Match survey respondents to gradebook students and award points.

    Returns (updated_gradebook_df, unmatched_df).
    """
    STUDENT_ID_COLUMN = "SIS User ID"
    STUDENT_NAME_COLUMN = "Student"

    gradebook_df = gradebook_df.copy()
    gradebook_df.loc[1:, assignment_col] = 0  # preserve row 0 (Points Possible)

    gradebook_copy = gradebook_df.copy()
    survey_copy = survey_df.copy()

    gradebook_copy['clean_sid'] = gradebook_copy[STUDENT_ID_COLUMN].apply(clean_text)
    gradebook_copy['last_parsed'] = gradebook_copy[STUDENT_NAME_COLUMN].str.split(',').str[0]
    gradebook_copy['first_parsed'] = gradebook_copy[STUDENT_NAME_COLUMN].str.split(',').str[1]
    gradebook_copy['clean_name'] = (
        gradebook_copy['first_parsed'] + ' ' + gradebook_copy['last_parsed']
    ).apply(clean_text)

    survey_copy['clean_sid'] = survey_copy[sid_col].apply(clean_text)
    survey_copy['clean_name'] = (
        survey_copy[first_col].astype(str) + " " + survey_copy[last_col].astype(str)
    ).apply(clean_text)

    survey_copy['matched_idx_in_gradebook'] = None
    survey_copy['match_method'] = None

    for idx, row in survey_copy.iterrows():
        match_found = None
        method = None

        if row['clean_sid'] != "":
            matches = gradebook_copy[gradebook_copy['clean_sid'] == row['clean_sid']]
            if not matches.empty:
                match_found = matches.index[0]
                method = "ID Match"

        if match_found is None:
            matches = gradebook_copy[gradebook_copy['clean_name'] == row['clean_name']]
            if not matches.empty:
                match_found = matches.index[0]
                method = "Exact Name"

        if match_found is not None:
            survey_copy.at[idx, 'matched_idx_in_gradebook'] = match_found
            survey_copy.at[idx, 'match_method'] = method

    matched_indices = survey_copy['matched_idx_in_gradebook'].dropna().unique()
    gradebook_df.loc[matched_indices, assignment_col] = points

    unmatched_df = survey_df.loc[survey_copy['matched_idx_in_gradebook'].isnull()]
    unmatched_df = unmatched_df.dropna(axis=0, how='all')

    return gradebook_df, unmatched_df


# ---------------------------------------------------------------------------
# Interactive helpers
# ---------------------------------------------------------------------------

def prompt_file(prompt_text):
    """Prompt until the user provides a valid path to an existing CSV."""
    while True:
        raw = input(prompt_text).strip().strip('"').strip("'")
        path = Path(raw).expanduser()
        if not path.exists():
            print(f"  File not found: {path}")
        elif path.suffix.lower() != '.csv':
            print(f"  Expected a .csv file, got: {path.suffix}")
        else:
            return path


def prompt_choice(prompt_text, options):
    """Print a numbered list and return the zero-based index of the chosen item."""
    for i, opt in enumerate(options):
        print(f"  {i + 1}. {opt}")
    while True:
        raw = input(prompt_text).strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print(f"  Enter a number between 1 and {len(options)}.")


def confirm(prompt_text, default=True):
    """Yes/no prompt; returns bool."""
    hint = "[Y/n]" if default else "[y/N]"
    raw = input(f"{prompt_text} {hint}: ").strip().lower()
    if raw == "":
        return default
    return raw in ("y", "yes")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Grade a Canvas survey assignment from the command line."
    )
    parser.add_argument("--gradebook",  metavar="PATH", help="Path to Canvas gradebook CSV")
    parser.add_argument("--survey",     metavar="PATH", help="Path to survey response CSV")
    parser.add_argument("--assignment", metavar="NAME_OR_NUM",
                        help="Assignment name (or 1-based number from the list)")
    parser.add_argument("--output",     metavar="PATH",
                        help="Output CSV path (default: <gradebook-stem>_graded.csv)")
    return parser


def resolve_assignment(arg, assignments):
    """Match --assignment value to an assignment name or 1-based index."""
    if arg.isdigit():
        idx = int(arg) - 1
        if 0 <= idx < len(assignments):
            return assignments[idx]
        print(f"  Index {arg} out of range (1–{len(assignments)}).")
        return None
    # Try substring match
    matches = [a for a in assignments if arg.lower() in a.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"  '{arg}' matches multiple assignments:")
        for m in matches:
            print(f"    {m}")
        return None
    print(f"  No assignment matching '{arg}'.")
    return None


def resolve_survey_columns(detected, all_cols):
    """
    For each role, use high-confidence detections automatically;
    prompt for low-confidence or undetected columns.
    Returns (first_col, last_col, sid_col).
    """
    DISPLAY = {'first_name': 'First name', 'last_name': 'Last name', 'sid': 'Student ID'}
    resolved = {}

    for role in ('first_name', 'last_name', 'sid'):
        col, confidence = detected[role]
        display = DISPLAY[role]

        if confidence == 'high':
            print(f"  {display}: '{col}'  (auto-detected)")
            resolved[role] = col
        elif confidence == 'low':
            print(f"  {display}: '{col}'  (low confidence — please confirm)")
            print(f"  Available columns:")
            idx = prompt_choice(
                f"  Select column for {display} [Enter {all_cols.index(col) + 1} to keep '{col}']: ",
                all_cols,
            )
            resolved[role] = all_cols[idx]
        else:
            print(f"  {display}: could not auto-detect — please select:")
            idx = prompt_choice(f"  Select column for {display}: ", all_cols)
            resolved[role] = all_cols[idx]

    return resolved['first_name'], resolved['last_name'], resolved['sid']


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = build_parser().parse_args()

    # 1. Gradebook
    if args.gradebook:
        gradebook_path = Path(args.gradebook).expanduser()
    else:
        gradebook_path = prompt_file("Path to Canvas gradebook CSV: ")

    try:
        gradebook_df = pd.read_csv(gradebook_path)
    except Exception as e:
        print(f"Error reading gradebook: {e}")
        sys.exit(1)

    # 2. Filter to valid assignment columns (same logic as GUI)
    exclude = {gradebook_df['Student'][0], '(read only)'}
    first_row = gradebook_df.iloc[0]
    mask = first_row.notna() & ~first_row.isin(exclude)
    assignments = gradebook_df.columns[mask].tolist()
    print(f"\nFound {len(assignments)} assignment(s) in gradebook.")

    # 3. Select assignment
    if args.assignment:
        assignment_col = resolve_assignment(args.assignment, assignments)
        if assignment_col is None:
            print("Use --assignment with a valid name or number.")
            sys.exit(1)
        print(f"Assignment: {assignment_col}")
    elif len(assignments) == 1:
        assignment_col = assignments[0]
        print(f"Assignment: {assignment_col}  (only one found, auto-selected)")
    else:
        print("\nSelect assignment:")
        idx = prompt_choice("Enter number: ", assignments)
        assignment_col = assignments[idx]

    # 4. Survey
    if args.survey:
        survey_path = Path(args.survey).expanduser()
    else:
        survey_path = prompt_file("\nPath to survey response CSV: ")

    try:
        survey_df = pd.read_csv(survey_path)
    except Exception as e:
        print(f"Error reading survey: {e}")
        sys.exit(1)

    # 5. Auto-detect survey columns
    print("\nDetecting survey columns:")
    detected = auto_detect_columns(survey_df.columns.tolist())
    first_col, last_col, sid_col = resolve_survey_columns(detected, survey_df.columns.tolist())

    # 6. Confirm and run
    points = gradebook_df[assignment_col][0]
    print(f"\nReady to run:")
    print(f"  Assignment : {assignment_col} ({points} pts)")
    print(f"  First name : {first_col}")
    print(f"  Last name  : {last_col}")
    print(f"  Student ID : {sid_col}")

    if not confirm("\nProceed?"):
        print("Cancelled.")
        sys.exit(0)

    updated_df, unmatched_df = process_data(
        gradebook_df, survey_df, assignment_col,
        first_col, last_col, sid_col, points,
    )

    # 7. Report results
    total_students = len(gradebook_df) - 2  # subtract Points Possible + test student rows
    matched_count = total_students - len(unmatched_df)
    print(f"\nMatched  : {matched_count} students")
    print(f"Unmatched: {len(unmatched_df)} students")
    if not unmatched_df.empty:
        print("\nUnmatched survey respondents:")
        for _, row in unmatched_df.iterrows():
            first = str(row.get(first_col, '')).strip()
            last  = str(row.get(last_col,  '')).strip()
            sid   = str(row.get(sid_col,   '')).strip()
            print(f"  {first} {last}  (SID: {sid})")

    # 8. Save
    default_out = gradebook_path.stem + "_graded.csv"
    out_path = Path(args.output) if args.output else Path(default_out)
    updated_df.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
