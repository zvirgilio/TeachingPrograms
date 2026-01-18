import pandas as pd
import tkinter as tk
import difflib
from tkinter import filedialog, ttk, messagebox

# Helper function to normalize text (remove punctuation, lower case)
def clean_text(text):
    if pd.isna(text): return ""
    # Lowercase and strip spaces
    text = str(text).lower().strip()
    # Remove hyphens/punctuation to match "Van-Dijk" with "Van Dijk"
    text = text.replace('-', ' ').replace('.', '')
    # Remove double spaces
    return " ".join(text.split())


class SurveyToCanvasApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Survey Data Loader")
        self.root.geometry("1080x500")

        self.grade_file_path = ""
        self.survey_file_path= ""
        self.has_grade_data=False
        self.has_survey_data=False
        self.STUDENT_ID_COLUMN = "SIS User ID"
        self.STUDENT_NAME_COLUMN = "Student"

        # create a button to trigger file diaglog
        # select canvas grade book
        self.grades_button = tk.Button(root, text = "Select Canvas Gradebook", command=self.get_gradebook)
        self.grades_button.grid(row=0, column=0, padx=10, pady=5)

        # select survey data
        self.survey_button = tk.Button(root, text = "Select Survey Data", command =self.get_survey_data)
        self.survey_button.grid(row=1, column=0, padx=10, pady=5)



        # status label
        self.grades_label = tk.Label(root, text = "No grades file selected")
        self.grades_label.grid(row=0, column=1, padx=10, pady=5)

        self.survey_label = tk.Label(root, text = "No survey file selected")
        self.survey_label.grid(row=1, column=1, padx=10, pady=5)


        # assignment selection menu
        # self.assignment_label = tk.Label(root, text="No Gradebook selected", fg="gray")
        # self.assignment_label.grid(row=0, column=2, padx=10, pady=20)
        self.assignment_dropdown = ttk.Combobox(root, width=20, state='disabled') #starts grayed out
        self.DEFAULT_ASSIGNMENT_MESSAGE= "Select an assignment"
        self.assignment_dropdown.grid(row=0, column=2, padx=10, pady=(5,0))

        # blank error label if no assignment was selected from dropdown
        self.assignment_dropdown_label = tk.Label(root, text="", fg="red")
        self.assignment_dropdown_label.grid(row=1, column=2, padx=10, pady=(0,5))

        self.first_name_dropdown = ttk.Combobox(root, width=15, state='disabled') 
        self.DEFAULT_FIRST_NAME_MESSAGE = "Select first name column"
        self.first_name_dropdown.grid(row=2, column = 0, padx=10, pady=5)

        self.last_name_dropdown = ttk.Combobox(root, width=15, state='disabled') 
        self.DEFAULT_LAST_NAME_MESSAGE = "Select last name column"
        self.last_name_dropdown.grid(row=2, column = 1, padx=10, pady=5)

        self.sid_dropdown = ttk.Combobox(root, width=15, state='disabled') 
        self.DEFAULT_SID_MESSAGE = "Select SID name column"
        self.sid_dropdown.grid(row=2, column = 2, padx=10, pady=5)

        # survey data label
        self.survey_data_label = tk.Label(root, text="", fg="red")
        self.survey_data_label.grid(row=3, column=2, padx=10, pady=5)


        # run button
        self.run_button = tk.Button(root, text="Input Survey Grades", command=self.input_survey_grades, state="disabled")
        self.run_button.grid(row=4, column=2, padx=10, pady=20)



    def get_gradebook(self):
        # open file selection dialog
        selected_path = filedialog.askopenfilename(
            # initialdir="/",
            title="Select Canvas Gradebook",
            filetypes = (("CSV files", "*.csv"), ("All files", "*.*")),
            )
        # make sure user made a selection (and didn't hit cancel)
        if selected_path:
            try:
                self.grade_file_path = selected_path
                self.grades_label.config(text = f"Selected: {selected_path.split('/')[-1]}", fg="white")

                self.gradebook_data = pd.read_csv(self.grade_file_path)
                # process data after this
                exclude = {self.gradebook_data['Student'][0], '(read only)'}
                first_row = self.gradebook_data.iloc[0]
                mask = (first_row.notna() & ~first_row.isin(exclude))
                self.assignments = self.gradebook_data.columns[mask].tolist()

                self.assignment_dropdown['values'] = self.assignments
                self.assignment_dropdown.set(self.DEFAULT_ASSIGNMENT_MESSAGE)
                self.assignment_dropdown['state'] = 'readonly'

                self.has_grade_data=True

                self.grades_button.config(text="Change Canvas Gradebook")
                # self.print_assignments()

            except Exception as e:
                self.grades_label.config(text="Error loading file", fg="red")
                self.has_grade_data=False
                print(f"Error: {e}")

            self.set_run_button_state()

    def get_survey_data(self):
        selected_path = filedialog.askopenfilename(
            title="Select Survey Data",
            filetypes= (("CSV files", "*.csv"), ("All files", "*.*")),
        )
        if selected_path:
            try:
                self.survey_file_path = selected_path
                self.survey_label.config(text = f"Selected: {selected_path.split('/')[-1]}", fg="white")
                self.survey_data = pd.read_csv(self.survey_file_path)
                # self.sid_submissions = set(self.survey_data['SID'].tolist())

                self.has_survey_data=True
                self.survey_button.config(text="Change Survey Data")
                # print(self.sid_submissions[:5])

                self.survey_cols = self.survey_data.columns.tolist()
                self.first_name_dropdown['values'] = self.survey_cols
                self.last_name_dropdown['values'] = self.survey_cols
                self.sid_dropdown['values'] = self.survey_cols

                self.first_name_dropdown.set(self.DEFAULT_FIRST_NAME_MESSAGE)
                self.last_name_dropdown.set(self.DEFAULT_LAST_NAME_MESSAGE)
                self.sid_dropdown.set(self.DEFAULT_SID_MESSAGE)

                self.first_name_dropdown['state'] = 'readonly'
                self.last_name_dropdown['state'] = 'readonly'
                self.sid_dropdown['state'] = 'readonly'
        
            except Exception as e:
                self.survey_label.config(text="Error loading file", fg="red")
                self.has_survey_data=False
                print(f"Error: {e}")


            self.set_run_button_state()

    # enables/disables the run button based on whether the files have been selected
    def set_run_button_state(self):
        if self.both_files_selected():
            self.run_button['state'] = 'normal'
        else:
            self.run_button['state'] = 'disabled'

    # checks if a grade csv and survey data csv have been selected and loaded properly
    def both_files_selected(self):
        return (self.has_grade_data and self.has_survey_data)


    def input_survey_grades(self):
        if self.get_dropdown_choice():
            current_assignment, first_name, last_name, sid_label = self.get_dropdown_choice()                    # get the assignment from the menu
            survey_points = self.gradebook_data[current_assignment][0]         # use Canvas' default max number of points
            self.gradebook_data[current_assignment] = 0                        # set all grades to 0

            # self.sid_submissions = set(self.survey_data[sid_label].tolist()) # not used now that process data is more complex

            self.process_data(current_assignment, first_name, last_name, sid_label, survey_points)

            # print(self.gradebook_data[self.current_assignment][:5])
            # self.gradebook_data.loc[self.gradebook_data[self.STUDENT_ID_COLUMN].isin(self.sid_submissions), current_assignment] = survey_points     # set the scores of all students whose SID is the survey data to full points
            # print(self.gradebook_data[current_assignment][:5])
            self.save_grade_data()


            
    def process_data(self, curr_assignment, first_name, last_name, sid_label, survey_points):
        self.gradebook_data[curr_assignment] = 0
        gradebook_copy = self.gradebook_data.copy() #copied version of the gradebook so we don't have to worry about editing it
        survey_copy = self.survey_data.copy()

        # clean all the data
        gradebook_copy['clean_sid'] = gradebook_copy[self.STUDENT_ID_COLUMN].apply(clean_text)
        gradebook_copy['last_parsed'] = gradebook_copy[self.STUDENT_NAME_COLUMN].str.split(',').str[0]
        gradebook_copy['first_parsed'] = gradebook_copy[self.STUDENT_NAME_COLUMN].str.split(',').str[1]

        # standardize all names to 'first last' all lower case, no hyphens or other symbols
        gradebook_copy['clean_name'] = (gradebook_copy['first_parsed'] + ' ' + gradebook_copy['last_parsed']).apply(clean_text)

        survey_copy['clean_sid'] = survey_copy[sid_label].apply(clean_text)
        survey_copy['clean_name'] = (survey_copy[first_name] + " " + survey_copy[last_name]).apply(clean_text)

        # track which rows have been used to match students in survey to students in gradebook
        survey_copy['matched_idx_in_gradebook'] = None
        survey_copy['match_method'] = None

        for idx, row in survey_copy.iterrows():
    
            match_found = None
            method = None
            
            # Try to match by SID first, if it is not empty
            if row['clean_sid'] != "":
                matches = gradebook_copy[gradebook_copy['clean_sid'] == row['clean_sid']]
                if not matches.empty:
                    match_found = matches.index[0]
                    method = "ID Match"


            # Look for exact name match, if ID didn't match
            if match_found is None:
                matches = gradebook_copy[gradebook_copy['clean_name'] == row['clean_name']]
                if not matches.empty:
                    match_found = matches.index[0]
                    method = "Exact Name"

            # Fuzzy Name Match (implement later with a suggestion feature
            # If still no match, try fuzzy matching
            '''
            if match_found is None:
                # Get list of all gradebook names
                possibilities = gradebook_copy['clean_name'].tolist()
                
                # specific cutoff: 0.6 is loose, 0.8 is strict. 
                # 'n=1' gets the single best match
                close_matches = difflib.get_close_matches(row['clean_name'], possibilities, n=1, cutoff=0.8)
                
                if close_matches:
                    # Find the index of the matched name in df1
                    best_match_name = close_matches[0]
                    match_found = gradebook_copy[gradebook_copy['clean_name'] == best_match_name].index[0]
                    method = f"Fuzzy Match ({best_match_name})"
            '''
            # --- Record Result ---
            if match_found is not None:
                survey_copy.at[idx, 'matched_idx_in_gradebook'] = match_found
                survey_copy.at[idx, 'match_method'] = method

        matched_indices = survey_copy['matched_idx_in_gradebook'].dropna().unique()
        self.gradebook_data.loc[matched_indices, curr_assignment] = survey_points

        # Extract unmatched rows for the user to see
        self.unmatched_df = self.survey_data.loc[survey_copy['matched_idx_in_gradebook'].isnull()]
        self.unmatched_df = self.unmatched_df.dropna(axis=0, how='all')
        if not self.unmatched_df.empty:
            print(self.unmatched_df.to_string())

    
                
    def save_grade_data(self):
        save_path = filedialog.asksaveasfilename(
            initialfile='Unititled.csv',
            defaultextension=".csv",
            # filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if save_path:
            self.gradebook_data.to_csv(save_path, index=False)
            print(f"File sucessfully saved at: {save_path}")
            self.finish_and_prompt() 

        else:
            print("Save cancelled by user")

    def reset_program(self):
        self.grade_file_path = ""
        self.survey_file_path= ""
        self.gradebook_data=None
        self.survey_data=None 
        self.assignments=None
        self.sid_submissions=None
        self.has_grade_data=False
        self.has_survey_data=False

        # reset the file selection buttons
        self.grades_button.config(text = "Select Canvas Gradebook")
        self.survey_button.config(text = "Select Survey Data")

        # reset status label
        self.grades_label.config(text = "No grades file selected")
        self.survey_label.config(text = "No survey file selected")

        # reset assignment selection dropdown and error label
        self.assignment_dropdown['state'] = 'disabled'
        self.assignment_dropdown.set("")
        self.assignment_dropdown_label.config(text="", fg="red")

        self.first_name_dropdown['state'] = 'disabled'
        self.last_name_dropdown['state'] = 'disabled'
        self.sid_dropdown['state'] = 'disabled'

        self.first_name_dropdown.set("")
        self.last_name_dropdown.set("")
        self.sid_dropdown.set("")

        self.survey_data_label.config(text="", fg='red')

        # reset run button
        self.run_button['state']="disabled"


    def finish_and_prompt(self):
        answer = messagebox.askyesno("Finished", "\n\n Would like to process another file?")

        if answer:
            self.reset_program()
        else:
            self.root.destroy()

    # returns the choice from the assignment dropdown menu, returns None if no choice has been made
    def get_dropdown_choice(self):
        if self.assignment_dropdown.get()== self.DEFAULT_ASSIGNMENT_MESSAGE:
            self.assignment_dropdown_label.config(text="Need to select an assignment")
            return None
        
        elif (self.first_name_dropdown.get()== self.DEFAULT_FIRST_NAME_MESSAGE or
                self.last_name_dropdown.get()== self.DEFAULT_LAST_NAME_MESSAGE or
                self.sid_dropdown.get()== self.DEFAULT_SID_MESSAGE):
            self.survey_data_label.config(text="Choose input for all data fields")
            return None
        
        else:
            self.assignment_dropdown_label.config(text="")
            self.survey_data_label.config(text="")
            # print(self.assignment_dropdown.get())
            assignment = self.assignment_dropdown.get()
            first_name = self.first_name_dropdown.get()
            last_name = self.last_name_dropdown.get()
            sid_label = self.sid_dropdown.get()
            return assignment, first_name, last_name, sid_label

    def print_assignments(self):
        print(self.assignments)

def main():
    root = tk.Tk()
    app = SurveyToCanvasApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()