import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

def create_temp_row(parent, temp_logo_path, temp_label, temp_value, column_index):
    # Frame for each temperature entry
    row_frame = tk.Frame(parent, bg='white', padx=10, pady=10)
    row_frame.grid(row=0, column=column_index, padx=5, pady=5, sticky='nsew')

    # Load and display temperature logo
    temp_logo = ImageTk.PhotoImage(Image.open(temp_logo_path).resize((30, 30), Image.LANCZOS))
    temp_logo_label = tk.Label(row_frame, image=temp_logo, bg='white')
    temp_logo_label.image = temp_logo  # Keep a reference to avoid garbage collection
    temp_logo_label.grid(row=0, column=0, padx=5, pady=5)

    # Temperature label
    label = tk.Label(row_frame, text=temp_label, font=("Helvetica", 12), bg='white')
    label.grid(row=0, column=1, padx=5, pady=5)

    # Progress bar
    progress_bar = ttk.Progressbar(row_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
    progress_bar.grid(row=0, column=2, padx=5, pady=5)
    progress_bar['value'] = temp_value

    # Temperature value
    temp_value_label = tk.Label(row_frame, text=f"{temp_value}°", font=("Helvetica", 12), bg='white')
    temp_value_label.grid(row=0, column=3, padx=5, pady=5)

def create_dashboard_page(container):
    # Create container for metrics
    metrics_container = tk.Frame(container,  bg='#ecf0f1')
    metrics_container.grid(row=0, column=0, padx=20, pady=10, sticky='nsew')

    # Define headers and values
    headers = [
        ("Status", "IDLE"),
        ("Pack Voltage", "42.4V"),
        ("Current", "10A"),
        ("Capacity (AH)", "10Ah"),
        ("SOC", "45%"),
        ("SSR", "108"),
    ]

    # Configure grid columns to expand equally
    for i in range(len(headers)):
        metrics_container.grid_columnconfigure(i, weight=1)

    frames = {}
    for i, (header, value) in enumerate(headers):
        frame = tk.Frame(metrics_container, bg='white', padx=10, pady=10)
        frame.grid(row=0, column=i, sticky='nsew')
        
        label = tk.Label(frame, text=header, font=("Helvetica", 14, 'bold'), bg='green', fg='white')
        label.pack(fill='x')
        
        value_label = tk.Label(frame, text=value, font=("Helvetica", 14), bg='white', fg='black')
        value_label.pack(pady=5)

        frames[header] = (frame, value_label)

    # Create container for temperature readings
    temp_container = tk.Frame(container, bg='lightgray')
    temp_container.grid(row=1, column=0, padx=20, pady=10, sticky='nsew')

    # Example temperature readings
    temp_readings = [60, 55, 65, 70]  # Example data

    # Configure columns in temp_container to expand
    num_columns = len(temp_readings)
    for i in range(num_columns):
        temp_container.grid_columnconfigure(i, weight=1)

    # Create temperature rows and place them in columns
    for i, temp in enumerate(temp_readings):
        create_temp_row(temp_container, "temp-logo.png", f"Temp T{i+1}", temp, i)

def create_nav_bar(root, frames):
    # Implement navigation bar creation
    pass

def show_frame(frames, page_name):
    for frame_name, frame in frames.items():
        if frame_name == page_name:
            frame.tkraise()
        else:
            frame.lower()

def main():
    root = tk.Tk()
    root.title("Battery Management System")
    root.geometry("1920x1080")

    frames = {}

    create_nav_bar(root, frames)

    container = tk.Frame(root)
    container.pack(side="top", fill="both", expand=True)
    container.grid_rowconfigure(0, weight=1)
    container.grid_columnconfigure(0, weight=1)

    frames["DashboardPage"] = tk.Frame(container)
    frames["ConnectionPage"] = tk.Frame(container)
    frames["DataLoggingPage"] = tk.Frame(container)
    frames["GraphsPage"] = tk.Frame(container)
    frames["SettingsPage"] = tk.Frame(container)

    for frame in frames.values():
        frame.grid(row=0, column=0, sticky="nsew")

    create_dashboard_page(frames["DashboardPage"])
   
    show_frame(frames, "DashboardPage")
    root.mainloop()

if __name__ == "__main__":
    main()
