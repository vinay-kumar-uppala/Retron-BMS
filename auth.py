import tkinter as tk
from tkinter import simpledialog, messagebox

# Predefined password for demonstration
VALID_PASSWORD = 'mypassword'

def authenticate():
    # Create a new window for authentication
    auth_window = tk.Toplevel(root)
    auth_window.title('Authentication')
    
    # Create a label and entry for the password
    tk.Label(auth_window, text='Enter password:').pack(padx=20, pady=10)
    password_entry = tk.Entry(auth_window, show='*')
    password_entry.pack(padx=20, pady=10)
    
    def check_password():
        entered_password = password_entry.get()
        if entered_password == VALID_PASSWORD:
            auth_window.destroy()
            show_settings_page()
        else:
            messagebox.showerror('Error', 'Invalid password')
    
    # Create an OK button
    tk.Button(auth_window, text='OK', command=check_password).pack(pady=10)

def show_settings_page():
    settings_window = tk.Toplevel(root)
    settings_window.title('Settings')
    
    # Add your settings page widgets here
    tk.Label(settings_window, text='Settings Page').pack(padx=20, pady=20)

def open_settings():
    authenticate()

root = tk.Tk()
root.title('Main Window')

# Button to open the settings page
tk.Button(root, text='Open Settings', command=open_settings).pack(pady=20)

root.mainloop()
