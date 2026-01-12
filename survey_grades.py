import pandas as pd
import tkinter as tk
from tkinter import filedialog, ttk, messagebox


class SurveyToCanvasApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Survey Data Loader")
        self.root.geometry("700x350")

        self.grade_file_path = ""
        self.survey_file_path= ""
        self.has_grade_data=False
        self.has_survey_data=False
        self.STUDENT_ID_COLUMN = "SIS User ID"

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
        self.DEFAULT_DROPDOWN_MESSAGE= "Select an assignment"
        self.assignment_dropdown.grid(row=0, column=2, padx=10, pady=(5,0))

        # blank error label if no assignment was selected from dropdown
        self.assignment_dropdown_label = tk.Label(root, text="", fg="red")
        self.assignment_dropdown_label.grid(row=1, column=2, padx=10, pady=(0,5))

        # run button
        self.run_button = tk.Button(root, text="Input Survey Grades", command=self.input_survey_grades, state="disabled")
        self.run_button.grid(row=2, column=2, padx=10, pady=20)



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
                self.assignment_dropdown.set(self.DEFAULT_DROPDOWN_MESSAGE)
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
                self.sid_submissions = set(self.survey_data['SID'].tolist())

                self.has_survey_data=True
                self.survey_button.config(text="Change Survey Data")
                # print(self.sid_submissions[:5])
        
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
            current_assignment = self.get_dropdown_choice()                    # get the assignment from the menu
            survey_points = self.gradebook_data[current_assignment][0]         # use Canvas' default max number of points
            self.gradebook_data[current_assignment] = 0                        # set all grades to 0
            # print(self.gradebook_data[self.current_assignment][:5])
            self.gradebook_data.loc[self.gradebook_data[self.STUDENT_ID_COLUMN].isin(self.sid_submissions), current_assignment] = survey_points     # set the scores of all students whose SID is the survey data to full points
            # print(self.gradebook_data[current_assignment][:5])
            self.save_grade_data()
            

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
        self.assignment_dropdown_label.config(text="", fg="red")

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
        if self.assignment_dropdown.get()== self.DEFAULT_DROPDOWN_MESSAGE:
                self.assignment_dropdown_label.config(text="Need to select an assignment")
                return None
        else:
            self.assignment_dropdown_label.config(text="")
            # print(self.assignment_dropdown.get())
            return self.assignment_dropdown.get()

    def print_assignments(self):
        print(self.assignments)

def main():
    root = tk.Tk()
    app = SurveyToCanvasApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()