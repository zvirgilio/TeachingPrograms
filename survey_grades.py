import pandas as pd
import tkinter as tk
import difflib
import re
from tkinter import filedialog, ttk, messagebox


# ---------------------------------------------------------------------------
# Shared helpers
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
    The returned gradebook_df has the assignment column updated in-place on a copy.
    """
    STUDENT_ID_COLUMN = "SIS User ID"
    STUDENT_NAME_COLUMN = "Student"

    gradebook_df = gradebook_df.copy()
    gradebook_df.loc[1:, assignment_col] = 0  # zero student rows only; preserve row 0 (Points Possible)

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
# GUI
# ---------------------------------------------------------------------------

class SurveyToCanvasApp:

    STUDENT_ID_COLUMN = "SIS User ID"
    STUDENT_NAME_COLUMN = "Student"

    def __init__(self, root):
        self.root = root
        self.root.title("Survey Grader")
        self.root.resizable(False, False)

        # State
        self.gradebook_df = None
        self.survey_df = None
        self.survey_cols = []
        self.assignments = []
        self.first_col = None
        self.last_col = None
        self.sid_col = None
        self.updated_gradebook_df = None

        # Build all frames up-front; show only frame_files initially
        self.frame_files = tk.Frame(root, padx=20, pady=20)
        self.frame_columns = tk.Frame(root, padx=20, pady=20)
        self.frame_run = tk.Frame(root, padx=20, pady=20)

        self._build_files_frame()
        self._build_columns_frame()
        self._build_run_frame()

        self.frame_files.pack(fill='both', expand=True)

    # ------------------------------------------------------------------
    # Frame builders
    # ------------------------------------------------------------------

    def _build_files_frame(self):
        f = self.frame_files

        tk.Button(f, text="Select Canvas Gradebook", width=24,
                  command=self.load_gradebook).grid(row=0, column=0, padx=10, pady=8, sticky='w')
        self.lbl_gradebook = tk.Label(f, text="No gradebook selected", fg="gray", anchor='w', width=50)
        self.lbl_gradebook.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        tk.Button(f, text="Select Survey Data", width=24,
                  command=self.load_survey).grid(row=1, column=0, padx=10, pady=8, sticky='w')
        self.lbl_survey = tk.Label(f, text="No survey file selected", fg="gray", anchor='w', width=50)
        self.lbl_survey.grid(row=1, column=1, padx=10, pady=8, sticky='w')

    def _build_columns_frame(self):
        f = self.frame_columns

        tk.Label(f, text="Confirm Survey Columns", font=("", 13, "bold")).grid(
            row=0, column=0, columnspan=3, pady=(0, 12))

        labels = ["First Name", "Last Name", "Student ID"]
        self.col_combos = {}
        self.col_conf_labels = {}

        for i, (role, display) in enumerate(
                zip(['first_name', 'last_name', 'sid'], labels)):
            tk.Label(f, text=display, anchor='e', width=12).grid(
                row=i + 1, column=0, padx=(0, 6), pady=6, sticky='e')

            cb = ttk.Combobox(f, width=30, state='readonly')
            cb.grid(row=i + 1, column=1, padx=6, pady=6)
            cb.bind("<<ComboboxSelected>>", lambda e: self._check_confirm_ready())
            self.col_combos[role] = cb

            lbl = tk.Label(f, text="", width=18, anchor='w')
            lbl.grid(row=i + 1, column=2, padx=6, pady=6, sticky='w')
            self.col_conf_labels[role] = lbl

        self.btn_confirm = tk.Button(f, text="Confirm Columns", state='disabled',
                                     command=self.confirm_columns)
        self.btn_confirm.grid(row=4, column=0, columnspan=3, pady=(12, 0))

    def _build_run_frame(self):
        f = self.frame_run

        # Assignment selection
        tk.Label(f, text="Assignment:", anchor='e', width=14).grid(
            row=0, column=0, padx=(0, 6), pady=8, sticky='e')
        self.assignment_cb = ttk.Combobox(f, width=40, state='readonly')
        self.assignment_cb.grid(row=0, column=1, columnspan=2, padx=6, pady=8, sticky='w')
        self.assignment_cb.bind("<<ComboboxSelected>>", lambda e: self._check_run_ready())

        self.btn_run = tk.Button(f, text="Run", width=14, state='disabled',
                                 command=self.run)
        self.btn_run.grid(row=1, column=0, columnspan=3, pady=(4, 16))

        # Results panel (hidden until after run); uses grid like the rest of frame_run
        self.frame_results = tk.Frame(f)
        self.frame_results.grid(row=2, column=0, columnspan=3, sticky='nsew', pady=(8, 0))
        self.frame_results.grid_remove()  # hidden initially

        tk.Label(self.frame_results, text="Results", font=("", 12, "bold")).pack(anchor='w')

        counts_row = tk.Frame(self.frame_results)
        counts_row.pack(anchor='w', pady=(4, 8))
        self.lbl_matched = tk.Label(counts_row, text="Matched: —", width=18, anchor='w')
        self.lbl_matched.pack(side='left')
        self.lbl_unmatched = tk.Label(counts_row, text="Unmatched: —", width=18, anchor='w')
        self.lbl_unmatched.pack(side='left')

        tk.Label(self.frame_results, text="Unmatched respondents:", anchor='w').pack(anchor='w')

        text_frame = tk.Frame(self.frame_results)
        text_frame.pack(fill='both', expand=True)
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side='right', fill='y')
        self.unmatched_text = tk.Text(text_frame, height=10, width=60,
                                      yscrollcommand=scrollbar.set, state='disabled',
                                      wrap='none')
        self.unmatched_text.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.unmatched_text.yview)

        btn_row = tk.Frame(self.frame_results)
        btn_row.pack(pady=(12, 0))
        self.btn_save = tk.Button(btn_row, text="Save Gradebook", width=16,
                                  command=self.save)
        self.btn_save.pack(side='left', padx=8)
        self.btn_reset = tk.Button(btn_row, text="Process Another", width=16,
                                   command=self.reset)
        self.btn_reset.pack(side='left', padx=8)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def load_gradebook(self):
        path = filedialog.askopenfilename(
            title="Select Canvas Gradebook",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.gradebook_df = pd.read_csv(path)
            exclude = {self.gradebook_df[self.STUDENT_NAME_COLUMN][0], '(read only)'}
            first_row = self.gradebook_df.iloc[0]
            mask = first_row.notna() & ~first_row.isin(exclude)
            self.assignments = self.gradebook_df.columns[mask].tolist()

            self.assignment_cb['values'] = self.assignments
            if len(self.assignments) == 1:
                self.assignment_cb.current(0)
                self._check_run_ready()

            self.lbl_gradebook.config(text="✓", fg='green')
        except Exception as e:
            self.lbl_gradebook.config(text="Error loading file", fg='red')
            self.gradebook_df = None
            messagebox.showerror("Error", f"Could not load gradebook:\n{e}")
            return

        self._maybe_show_columns_frame()

    def load_survey(self):
        path = filedialog.askopenfilename(
            title="Select Survey Data",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.survey_df = pd.read_csv(path)
            self.survey_cols = self.survey_df.columns.tolist()

            detected = auto_detect_columns(self.survey_cols)

            for role, cb in self.col_combos.items():
                cb['values'] = self.survey_cols
                col, confidence = detected[role]
                lbl = self.col_conf_labels[role]
                if confidence == 'high':
                    cb.set(col)
                    lbl.config(text="Auto-detected", fg='green')
                elif confidence == 'low':
                    cb.set(col)
                    lbl.config(text="Please confirm", fg='orange')
                else:
                    cb.set('')
                    lbl.config(text="Please select", fg='red')

            self._check_confirm_ready()

            self.lbl_survey.config(text="✓", fg='green')
        except Exception as e:
            self.lbl_survey.config(text="Error loading file", fg='red')
            self.survey_df = None
            messagebox.showerror("Error", f"Could not load survey:\n{e}")
            return

        self._maybe_show_columns_frame()

    def confirm_columns(self):
        self.first_col = self.col_combos['first_name'].get()
        self.last_col = self.col_combos['last_name'].get()
        self.sid_col = self.col_combos['sid'].get()

        self.frame_columns.pack_forget()
        self.frame_run.pack(fill='both', expand=True)

    def run(self):
        assignment_col = self.assignment_cb.get()
        if not assignment_col:
            return

        points = self.gradebook_df[assignment_col][0]

        try:
            updated_df, unmatched_df = process_data(
                self.gradebook_df, self.survey_df,
                assignment_col, self.first_col, self.last_col, self.sid_col,
                points,
            )
        except Exception as e:
            messagebox.showerror("Error", f"Processing failed:\n{e}")
            return

        self.updated_gradebook_df = updated_df

        # Header rows (points row + test student row) are not real students;
        # count matched as total gradebook rows minus 2 header rows minus unmatched
        total_students = len(self.gradebook_df) - 2
        matched_count = total_students - len(unmatched_df)

        self.lbl_matched.config(text=f"Matched: {matched_count}")
        self.lbl_unmatched.config(text=f"Unmatched: {len(unmatched_df)}")

        self.unmatched_text.config(state='normal')
        self.unmatched_text.delete('1.0', 'end')
        if unmatched_df.empty:
            self.unmatched_text.insert('end', "(none)")
        else:
            for _, row in unmatched_df.iterrows():
                first = str(row.get(self.first_col, '')).strip()
                last = str(row.get(self.last_col, '')).strip()
                sid = str(row.get(self.sid_col, '')).strip()
                self.unmatched_text.insert('end', f"{first} {last}  (SID: {sid})\n")
        self.unmatched_text.config(state='disabled')

        self.frame_results.grid()

    def save(self):
        path = filedialog.asksaveasfilename(
            initialfile='graded.csv',
            defaultextension=".csv",
        )
        if path:
            self.updated_gradebook_df.to_csv(path, index=False)

    def reset(self):
        self.gradebook_df = None
        self.survey_df = None
        self.survey_cols = []
        self.assignments = []
        self.first_col = None
        self.last_col = None
        self.sid_col = None
        self.updated_gradebook_df = None

        # Reset files frame
        self.lbl_gradebook.config(text="No gradebook selected", fg='gray')
        self.lbl_survey.config(text="No survey file selected", fg='gray')

        # Reset columns frame
        for role, cb in self.col_combos.items():
            cb.set('')
            cb['values'] = []
            self.col_conf_labels[role].config(text='', fg='black')
        self.btn_confirm.config(state='disabled')

        # Reset run frame
        self.assignment_cb.set('')
        self.assignment_cb['values'] = []
        self.btn_run.config(state='disabled')
        self.frame_results.grid_remove()
        self.unmatched_text.config(state='normal')
        self.unmatched_text.delete('1.0', 'end')
        self.unmatched_text.config(state='disabled')

        # Return to files frame
        self.frame_run.pack_forget()
        self.frame_columns.pack_forget()
        self.frame_files.pack(fill='both', expand=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _maybe_show_columns_frame(self):
        """Transition to the columns frame once both files are loaded."""
        if self.gradebook_df is not None and self.survey_df is not None:
            self.frame_files.pack_forget()
            self.frame_columns.pack(fill='both', expand=True)

    def _check_confirm_ready(self):
        all_selected = all(
            cb.get() for cb in self.col_combos.values()
        )
        self.btn_confirm.config(state='normal' if all_selected else 'disabled')

    def _check_run_ready(self):
        if self.assignment_cb.get():
            self.btn_run.config(state='normal')
        else:
            self.btn_run.config(state='disabled')


# ---------------------------------------------------------------------------

def main():
    root = tk.Tk()
    SurveyToCanvasApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
