import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import calendar
from datetime import datetime
import json
import os

class RecipeCard:
    def __init__(self, name, ingredients, instructions):
        self.name = name
        self.ingredients = ingredients
        self.instructions = instructions

    def to_dict(self):
        return {
            'name': self.name,
            'ingredients': self.ingredients,
            'instructions': self.instructions
        }

    @staticmethod
    def from_dict(data):
        return RecipeCard(data['name'], data['ingredients'], data['instructions'])

    def __str__(self):
        return self.name

class MealPlannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Monthly Meal Planner")

        self.recipes = []
        self.meal_plan = {}  # format: {(year, month, day): {'Breakfast': recipe, ...}}

        self.current_year = datetime.now().year
        self.current_month = datetime.now().month

        self.load_data()
        self.create_widgets()
        self.render_calendar()

    def create_widgets(self):
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill='x')

        ttk.Button(control_frame, text="Recipe Book", command=self.open_recipe_book).pack(side='left')
        ttk.Button(control_frame, text="Previous Month", command=self.prev_month).pack(side='left')
        ttk.Button(control_frame, text="Next Month", command=self.next_month).pack(side='left')
        ttk.Button(control_frame, text="Search Recipes", command=self.search_recipes).pack(side='left')
        ttk.Button(control_frame, text="Copy Meals", command=self.copy_meals_window).pack(side='left')

        self.calendar_frame = ttk.Frame(self.root)
        self.calendar_frame.pack(fill='both', expand=True)

    def render_calendar(self):
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

        month_days = calendar.monthcalendar(self.current_year, self.current_month)
        ttk.Label(self.calendar_frame, text=f"{calendar.month_name[self.current_month]} {self.current_year}", font=("Arial", 16)).grid(row=0, column=0, columnspan=7)

        for idx, day in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            ttk.Label(self.calendar_frame, text=day, borderwidth=1, relief="solid").grid(row=1, column=idx, sticky="nsew")

        today = datetime.now()

        for r, week in enumerate(month_days, start=2):
            for c, day in enumerate(week):
                if day == 0:
                    ttk.Label(self.calendar_frame, text="", borderwidth=1, relief="solid").grid(row=r, column=c, sticky="nsew")
                else:
                    is_today = (day == today.day and self.current_month == today.month and self.current_year == today.year)
                    style = {'background': 'lightblue'} if is_today else {}
                    btn = tk.Button(self.calendar_frame, text=str(day), command=lambda d=day: self.edit_day(d), **style)
                    btn.grid(row=r, column=c, sticky="nsew")

    def edit_day(self, day):
        date_key = (self.current_year, self.current_month, day)
        if date_key not in self.meal_plan:
            self.meal_plan[date_key] = {'Breakfast': None, 'Lunch': None, 'Dinner': None}

        win = tk.Toplevel(self.root)
        win.title(f"Meal Plan for {day} {calendar.month_name[self.current_month]} {self.current_year}")

        for idx, meal in enumerate(['Breakfast', 'Lunch', 'Dinner']):
            ttk.Label(win, text=meal).grid(row=idx, column=0)
            selected = tk.StringVar(value=str(self.meal_plan[date_key][meal]) if self.meal_plan[date_key][meal] else "None")

            option = ttk.Combobox(win, textvariable=selected, values=[str(r) for r in self.recipes] + ["None"])
            option.grid(row=idx, column=1)

            def make_save(meal_name, var):
                return lambda: self.save_meal_selection(date_key, meal_name, var.get())

            def make_view(var, meal_name):
                return lambda: self.view_recipe_by_name(var.get(), meal_name)

            ttk.Button(win, text="Save", command=make_save(meal, selected)).grid(row=idx, column=2)
            ttk.Button(win, text="View", command=make_view(selected, meal)).grid(row=idx, column=3)

    def save_meal_selection(self, date_key, meal_name, recipe_name):
        for recipe in self.recipes:
            if str(recipe) == recipe_name:
                self.meal_plan[date_key][meal_name] = recipe
                break
        else:
            self.meal_plan[date_key][meal_name] = None
        self.save_data()

    def view_recipe_by_name(self, name, meal_name):
        for recipe in self.recipes:
            if str(recipe) == name:
                details = f"Name: {recipe.name}\n\nIngredients:\n" + ", ".join(recipe.ingredients) + f"\n\nInstructions:\n{recipe.instructions}"
                messagebox.showinfo(f"{meal_name} Recipe", details)
                break

    def copy_meals_window(self):
        win = tk.Toplevel(self.root)
        win.title("Copy Meals Between Dates")

        ttk.Label(win, text="Source Date (YYYY-MM-DD):").grid(row=0, column=0)
        source_entry = ttk.Entry(win)
        source_entry.grid(row=0, column=1)

        ttk.Label(win, text="Target Date (YYYY-MM-DD):").grid(row=1, column=0)
        target_entry = ttk.Entry(win)
        target_entry.grid(row=1, column=1)

        def perform_copy():
            try:
                src = tuple(map(int, source_entry.get().split('-')))
                tgt = tuple(map(int, target_entry.get().split('-')))

                if src not in self.meal_plan:
                    messagebox.showerror("Error", "No meals planned on source date")
                    return

                self.meal_plan[tgt] = self.meal_plan[src].copy()
                self.save_data()
                messagebox.showinfo("Success", f"Meals copied from {src} to {tgt}")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Invalid date or failed to copy: {e}")

        ttk.Button(win, text="Copy", command=perform_copy).grid(row=2, column=0, columnspan=2)

    def open_recipe_book(self):
        win = tk.Toplevel(self.root)
        win.title("Recipe Book")

        listbox = tk.Listbox(win)
        listbox.pack(fill='both', expand=True)
        for recipe in self.recipes:
            listbox.insert(tk.END, recipe.name)

        def view():
            selected = listbox.curselection()
            if selected:
                recipe = self.recipes[selected[0]]
                details = f"Name: {recipe.name}\n\nIngredients:\n" + ", ".join(recipe.ingredients) + f"\n\nInstructions:\n{recipe.instructions}"
                messagebox.showinfo("Recipe Details", details)

        def edit():
            selected = listbox.curselection()
            if not selected:
                return
            recipe = self.recipes[selected[0]]
            edit_win = tk.Toplevel(win)
            edit_win.title("Edit Recipe")

            ttk.Label(edit_win, text="Name:").pack()
            name_entry = ttk.Entry(edit_win)
            name_entry.insert(0, recipe.name)
            name_entry.pack()

            ttk.Label(edit_win, text="Ingredients (comma separated):").pack()
            ingredients_entry = ttk.Entry(edit_win)
            ingredients_entry.insert(0, ", ".join(recipe.ingredients))
            ingredients_entry.pack()

            ttk.Label(edit_win, text="Instructions:").pack()
            instructions_text = tk.Text(edit_win, height=5, width=40)
            instructions_text.insert("1.0", recipe.instructions)
            instructions_text.pack()

            def save_changes():
                recipe.name = name_entry.get()
                recipe.ingredients = [i.strip() for i in ingredients_entry.get().split(',') if i.strip()]
                recipe.instructions = instructions_text.get("1.0", tk.END).strip()
                self.save_data()
                listbox.delete(selected[0])
                listbox.insert(selected[0], recipe.name)
                edit_win.destroy()

            ttk.Button(edit_win, text="Save Changes", command=save_changes).pack()

        def delete():
            selected = listbox.curselection()
            if selected:
                if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this recipe?"):
                    del self.recipes[selected[0]]
                    listbox.delete(selected[0])
                    self.save_data()

        def add():
            self.add_recipe()
            listbox.delete(0, tk.END)
            for recipe in self.recipes:
                listbox.insert(tk.END, recipe.name)

        ttk.Button(win, text="View", command=view).pack(side='left')
        ttk.Button(win, text="Edit", command=edit).pack(side='left')
        ttk.Button(win, text="Delete", command=delete).pack(side='left')
        ttk.Button(win, text="Add New", command=add).pack(side='left')

    def add_recipe(self):
        win = tk.Toplevel(self.root)
        win.title("Add Recipe")

        ttk.Label(win, text="Name:").pack()
        name_entry = ttk.Entry(win)
        name_entry.pack()

        ttk.Label(win, text="Ingredients (comma separated):").pack()
        ingredients_entry = ttk.Entry(win)
        ingredients_entry.pack()

        ttk.Label(win, text="Instructions:").pack()
        instructions_text = tk.Text(win, height=5, width=40)
        instructions_text.pack()

        def save():
            name = name_entry.get()
            ingredients = [i.strip() for i in ingredients_entry.get().split(',') if i.strip()]
            instructions = instructions_text.get("1.0", tk.END).strip()
            if name:
                self.recipes.append(RecipeCard(name, ingredients, instructions))
                self.save_data()
                win.destroy()
            else:
                messagebox.showerror("Error", "Name is required")

        ttk.Button(win, text="Save Recipe", command=save).pack()

    def search_recipes(self):
        query = simpledialog.askstring("Search Recipes", "Enter recipe name or ingredient:")
        if not query:
            return

        results = []
        for recipe in self.recipes:
            if query.lower() in recipe.name.lower() or any(query.lower() in ing.lower() for ing in recipe.ingredients):
                results.append(recipe)

        if results:
            win = tk.Toplevel(self.root)
            win.title("Search Results")
            for idx, recipe in enumerate(results):
                ttk.Label(win, text=recipe.name).grid(row=idx, column=0)
                ttk.Button(win, text="View", command=lambda r=recipe: messagebox.showinfo("Recipe", f"Name: {r.name}\n\nIngredients:\n" + ", ".join(r.ingredients) + f"\n\nInstructions:\n{r.instructions}")).grid(row=idx, column=1)
        else:
            messagebox.showinfo("Search Results", "No matching recipes found.")

    def prev_month(self):
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self.render_calendar()

    def next_month(self):
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self.render_calendar()

    def save_data(self):
        data = {
            'recipes': [r.to_dict() for r in self.recipes],
            'meal_plan': {
                str(k): {meal: r.name if r else None for meal, r in v.items()}
                for k, v in self.meal_plan.items()
            }
        }
        with open("meal_data.json", "w") as f:
            json.dump(data, f)

    def load_data(self):
        if os.path.exists("meal_data.json"):
            with open("meal_data.json", "r") as f:
                data = json.load(f)
                self.recipes = [RecipeCard.from_dict(d) for d in data.get('recipes', [])]
                for k, v in data.get('meal_plan', {}).items():
                    y, m, d = eval(k)
                    self.meal_plan[(y, m, d)] = {
                        meal: next((r for r in self.recipes if r.name == r_name), None)
                        for meal, r_name in v.items()
                    }

def start():
    root = tk.Tk()
    app = MealPlannerApp(root)
    root.mainloop()