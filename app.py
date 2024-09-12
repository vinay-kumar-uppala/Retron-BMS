import tkinter as tk
from tkinter.filedialog import askopenfile,askopenfilename,asksaveasfilename
from tkinter import ttk,filedialog, messagebox
import serial
import serial.tools.list_ports
from PIL import Image, ImageTk
from ttkthemes import ThemedTk
import pandas as pd
import random
import time,threading
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import re,math,datetime
import queue,os, sys
import json
import math

# Production File Configurations.
company_logo_path = os.path.join(sys._MEIPASS, 'company_logo.png')
cell_path = os.path.join(sys._MEIPASS, 'cell.png')
temp_path = os.path.join(sys._MEIPASS, 'temp-logo.png')
company_icon = os.path.join(sys._MEIPASS, 'icon.ico')

# AH Current Calculation Constants.
AH_meter = 0
Battery_AH = 6   #setting input
Percentage_SOC=0
stopFlag=False
last_AH = 0 

# Define a dictionary to map STATUS_CODE to corresponding actions
status_code_map = {
    "106": ("Over-Discharge", lambda: reset_AH_meter()),
    "108": ("Normal", lambda: None),
    "100": ("System Fault", lambda: None),
    "101": ("Temperature Fault", lambda: None),
    "102": ("Short-Circuit", lambda: None),
    "103": ("Overload", lambda: None),
    "107": ("Precharge", lambda: None),
    "104": ("Cell-Voltage fault", lambda: reset_AH_meter()),
    "105": ("Over-Charge", lambda: reset_AH_meter()),
}

def reset_AH_meter():
    global AH_meter, last_AH
    last_AH = AH_meter
    AH_meter = 0

# Serial Constants
ser=None
buffer = b''
start_reading = False
stop_ser_thread = False

null_sequence = b'\x00' * 128
settings_file = 'settings.json'
# Global variable to store the last plotted figure
last_plotted_figure = None
# Predefined password for demonstration purposes
VALID_PASSWORD = 'retronev'

def load_settings():
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            return json.load(f)
    return {}

# Save settings to file
def save_settings(settings):
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=4)

settings_data = load_settings()
num_v_values = settings_data.get("num_cells",1) if settings_data!=None else 8 #setting input      # Set the number of 'V' values expected
temp_max = settings_data.get("ts_upper",1) if settings_data!=None else 100 
cell_max = settings_data.get("cv_upper",1) if settings_data!=None else 4500.00
battery_volt_max = settings_data.get("bv_upper",1) if settings_data!=None else 4500.00 
battery_current_max = settings_data.get("bc_upper",1) if settings_data!=None else 20
IchOff = settings_data.get("IchOffset",1) if settings_data!=None else 0
IdchOff = settings_data.get("IdchOffset",1) if settings_data!=None else 0
# Define regular expression patterns for each value
patterns = {
    'VBAT': re.compile(r'VBAT:(\d+\.\d+)V'),
    'IBAT': re.compile(r'IBAT:(\d+\.\d+)A'),
    'STATUS': re.compile(r'(Charging|Discharging|Standby)'),
    'SSR': re.compile(r'SSR:(\d+)'),
    'STATUS_CODE': re.compile(r'STATUS:(\d+)'),
    # Updated regex patterns for temperatures to optionally match °C
    'T1': re.compile(r'T1:(\d+)(?:°C)?'),
    'T2': re.compile(r'T2:(\d+)(?:°C)?'),
    'T3': re.compile(r'T3:(\d+)(?:°C)?'),
    'T4': re.compile(r'T4:(\d+)(?:°C)?'),
    'TBMS': re.compile(r'TBMS:(\d+)(?:°C)?'),
}

serial_data = {
    'VBAT': '0',
    'IBAT': '0',
    'PACK_AH':'0',
    'STATUS': 'NA',
    'SSR': '0',
    'STATUS_CODE': '0',
    'SOC': '0',
    'TBMS': '0',
    'T1': '0',
    'T2': '0',
    'T3': '0',
    'T4': '0'
}
# Add 'V' patterns dynamically based on num_v_values
for i in range(1, num_v_values + 1):
    patterns[f'V{i}'] = re.compile(f'V{i}:(\d+)')
    serial_data[f'V{i}'] = 0

# Initialize variables
values = {key: None for key in patterns}

# Global variables
log_file_path = ""
logging_interval = 1  # Default to 1 second
logging_running = False
logged_data = []

def show_frame(frames, frame_name):
    frame = frames[frame_name]
    frame.tkraise()

def create_nav_bar(root, frames):
    global connection_status_label
    nav_bar = tk.Frame(root, bg="#444", height=40)
    nav_bar.pack(side="top", fill="x")

    # Connection status label
    connection_status_label = tk.Label(nav_bar, text="Disconnected", font=("Helvetica", 12, "bold"), fg='white', bg='red')
    connection_status_label.pack(side="left", padx=8, pady=3)

    button_style = {
        "font": ("Helvetica", 12, "bold"),
        "bg": "#444",
        "fg": "white",
        "activebackground": "#555",
        "activeforeground": "white",
        "bd": 0,
        "highlightthickness": 0,
        "relief": "flat",
        "width": 8,
        "padx": 8,
        "pady": 3  # Decreased padding to reduce the height of the buttons
    }

    buttons = [
        ("Settings", "SettingsPage", lambda: authenticate_and_show_settings_page(frames)),
        ("Data Log", "DataLoggingPage", lambda f="DataLoggingPage": show_frame(frames, f)),
        ("Dashboard", "DashboardPage", lambda f="DashboardPage": show_frame(frames, f)),
        ("Connection", "ConnectionPage", lambda f="ConnectionPage": show_frame(frames, f)),
    ]

    for (text, frame_name, command) in buttons:
        button = tk.Button(nav_bar, text=text, command=command, **button_style)
        button.pack(side="right", padx=5, pady=5)
        
def authenticate_and_show_settings_page(frames):
    def check_password():
        entered_password = password_entry.get()
        if entered_password == VALID_PASSWORD:
            auth_window.destroy()
            show_frame(frames, "SettingsPage")
        else:
            messagebox.showerror('Error', 'Invalid password')
            auth_window.destroy()

    auth_window = tk.Toplevel()
    auth_window.title('Authentication')

    tk.Label(auth_window, text='Enter password:').pack(padx=40, pady=50)
    password_entry = tk.Entry(auth_window, show='*')
    password_entry.pack(padx=20, pady=10)

    tk.Button(auth_window, text='OK', command=check_password).pack(pady=10)

def create_frames(root):
    # frames = {}
    names = ['VBAT', 'IBAT', 'STATUS', 'PACKAH', 'SOC', 'SSR']

    cell_voltages = [0, 0, 0, 0, 0, 0, 0, 0]  # Example data
    temp_readings = [0, 0, 0, 0]  # Example data for 5 sensors

    # # Load cell and temp logos
    cell_logo = ImageTk.PhotoImage(Image.open(cell_path).resize((30, 30), Image.LANCZOS))
    temp_logo = ImageTk.PhotoImage(Image.open(temp_path).resize((30, 30), Image.LANCZOS))

    container = tk.Frame(root, bg='#ecf0f1')
    container.pack(fill='both', expand=True, padx=20, pady=20)

    frames = {}

    # Header labels
    headers = [
        ("STATUS", "IDLE"),
        ("VBAT", "0V"),
        ("IBAT", "0A"),
        ("PACKAH", "0Ah"),
        ("SOC", "0%"),
        ("SSR", "0"),
    ]

    # Configure grid columns to expand equally
    for i in range(len(headers)):
        container.grid_columnconfigure(i, weight=1)

    for i, (header, value) in enumerate(headers):
        frame = tk.Frame(container, bg='white', padx=10, pady=10)  # Removed bd and relief
        frame.grid(row=0, column=i, sticky='nsew')
        
        label = tk.Label(frame, text=header, font=("Helvetica", 14, 'bold'),bg='green', fg='white')
        label.pack(fill='x')
        
        value_label = tk.Label(frame, text=value, font=("Helvetica", 14), bg='white',fg='black')
        value_label.pack(pady=5)

        frames[header] = (frame,value_label) # Store the frame and the value label for later updates

    # Temperature readings
    temp_readings = [0, 0, 0, 0, 0]  # Example data for 5 sensors
    temp_labels = ["Temp T1", "Temp T2", "Temp T3", "Temp T4", "Temp T5"]
    num_columns = len(temp_readings)


    for i, temp in enumerate(temp_readings):
        create_temp_row(container, temp_path, f"Temp T{i+1}", temp, i,frames)

    # Container for the three columns
    columns_container = tk.Frame(root, bg='#ecf0f1')
    columns_container.pack(fill='both', expand=True, padx=10, pady=10)
    
    # Column 1: Cell voltages
    cell_voltage_container = tk.Frame(columns_container, bg='#ecf0f1')
    cell_voltage_container.grid(row=0, column=0, sticky='nsew', padx=10)

    # Example data for cell voltages
    cell_voltages = [
        ("1", "0000"),
        ("2", "0000"),
        ("3", "0000"),
        ("4", "0000"),
        ("5", "0000"),
        ("6", "0000"),
        ("7", "0000"),
        ("8", "0000"),
        ("9", "0000"),
        ("10", "0000"),
        ("11", "0000"),
        ("12", "0000"),
        ("13", "0000"),
        ("14", "0000"),
        ("15", "0000"),
        ("16", "0000")
    ]

    for cell_number, voltage in cell_voltages:
        create_cell_voltage_row(cell_voltage_container, cell_number, voltage, frames)

    # Column 2: Graph display
    graph_container = tk.Frame(columns_container, bg='#ecf0f1')
    graph_container.grid(row=0, column=1, sticky='nsew', padx=10)
    create_graph(graph_container)

    # Column 3: Graph generation fields
    graph_generation_container = tk.Frame(columns_container, bg='#ecf0f1')
    graph_generation_container.grid(row=0, column=2, sticky='nsew', padx=10)
    create_graph_generation_fields(graph_generation_container,graph_container)

    # Configure grid columns to expand equally
    columns_container.grid_columnconfigure(0, weight=1)
    columns_container.grid_columnconfigure(1, weight=2)
    columns_container.grid_columnconfigure(2, weight=1)

    return frames

def browse_file_graph(entry, x_field_dropdown, y_field_dropdown):
    file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
    entry.delete(0, tk.END)
    entry.insert(0, file_path)

    # Load CSV and populate dropdowns
    if file_path:
        df = pd.read_csv(file_path)
        columns = list(df.columns)
        
        # Update dropdowns
        x_field_dropdown['values'] = columns
        y_field_dropdown['values'] = columns

def create_graph_generation_fields(parent, graph_container):
    fields_frame = tk.Frame(parent, bg='#ecf0f1', padx=10, pady=10)
    fields_frame.pack(fill='both', expand=True)

    # File path
    file_path_label = tk.Label(fields_frame, text="Choose File Path", font=("Helvetica", 12, 'bold'), bg='white')
    file_path_label.pack(pady=5, anchor='w')

    file_path_entry = tk.Entry(fields_frame, font=("Helvetica", 12))
    file_path_entry.pack(pady=5, fill='x')

    file_path_button = tk.Button(fields_frame, text="Browse", font=("Helvetica", 12, 'bold'),
                                 command=lambda: browse_file_graph(file_path_entry, x_field_dropdown, y_field_dropdown))
    file_path_button.pack(pady=5)

    # X-axis field
    x_field_label = tk.Label(fields_frame, text="X-Axis Field", font=("Helvetica", 12, 'bold'), bg='white')
    x_field_label.pack(pady=5, anchor='w')

    x_field_dropdown = ttk.Combobox(fields_frame, font=("Helvetica", 12))
    x_field_dropdown.pack(pady=5, fill='x')

    # Y-axis field
    y_field_label = tk.Label(fields_frame, text="Y-Axis Field", font=("Helvetica", 12, 'bold'), bg='white')
    y_field_label.pack(pady=5, anchor='w')

    y_field_dropdown = ttk.Combobox(fields_frame, font=("Helvetica", 12))
    y_field_dropdown.pack(pady=5, fill='x')

    # X-axis interval
    interval_label = tk.Label(fields_frame, text="X-Axis Interval", font=("Helvetica", 12, 'bold'), bg='white')
    interval_label.pack(pady=5, anchor='w')

    interval_entry = tk.Entry(fields_frame, font=("Helvetica", 12))
    interval_entry.pack(pady=5, fill='x')

    # No of samples
    samples_label = tk.Label(fields_frame, text="No of Samples", font=("Helvetica", 12, 'bold'), bg='white')
    samples_label.pack(pady=5, anchor='w')

    samples_entry = tk.Entry(fields_frame, font=("Helvetica", 12))
    samples_entry.pack(pady=5, fill='x')

    # Plot and Save buttons
    plot_button = tk.Button(fields_frame, text="Plot Graph", font=("Helvetica", 12, 'bold'),
                            command=lambda: plot_graph(graph_container, file_path_entry.get(), x_field_dropdown.get(), y_field_dropdown.get(), interval_entry.get(), samples_entry.get()))
    plot_button.pack(pady=10)

    save_button = tk.Button(fields_frame, text="Save Graph", font=("Helvetica", 12, 'bold'), command=save_graph)
    save_button.pack(pady=10)

def plot_graph(graph_container, file_path, x_field, y_field, interval, samples):
    # Read CSV file
    global last_plotted_figure
    df = pd.read_csv(file_path)
    
    if x_field and y_field:
        fig, ax = plt.subplots(figsize=(5, 4))  # Increase the figure size for better fitting

        sample_data = df[::int(interval)].head(int(samples))
        
        ax.plot(sample_data[x_field], sample_data[y_field], label=y_field)
        
        ax.set_title('Generated Graph')
        ax.set_xlabel(x_field)
        ax.set_ylabel(y_field)
        ax.tick_params(axis='x', rotation=90)  # Rotate x-axis labels verticall
        # Store the figure in the global variable
        last_plotted_figure = fig

    for widget in graph_container.winfo_children():
        widget.destroy()

    canvas = FigureCanvasTkAgg(fig, master=graph_container)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

def save_graph():
    global last_plotted_figure
    if last_plotted_figure:
        file_path = filedialog.asksaveasfilename(defaultextension=".png",
                                                 filetypes=[("PNG files", "*.png"),
                                                            ("PDF files", "*.pdf"),
                                                            ("All files", "*.*")])
        if file_path:
            last_plotted_figure.savefig(file_path)
            messagebox.showinfo("Save Graph", "Graph saved successfully!")
    else:
        messagebox.showwarning("Save Graph", "No graph available to save.")

def create_graph(parent):
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot([1, 2, 3, 4], [1, 4, 2, 3])  # Example data

    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

def create_cell_voltage_row(parent, cell_number, voltage, frames):
    row_frame = tk.Frame(parent, bg='white', padx=5, pady=5)
    row_frame.pack(fill='x', pady=5)

    # Cell number label
    cell_number_label = tk.Label(row_frame, text=str(cell_number), font=("Helvetica", 12, 'bold'), bg='green', fg='white')
    cell_number_label.pack(side=tk.LEFT, padx=5)

    # Progress bar
    progress_bar = ttk.Progressbar(row_frame, orient=tk.HORIZONTAL, length=200, mode='determinate', maximum=5000)
    progress_bar.pack(side=tk.LEFT, padx=5)
    progress_bar['value'] = voltage

    # Voltage value
    voltage_value_label = tk.Label(row_frame, text=f"{voltage} mV", font=("Helvetica", 12, 'bold'), bg='white')
    voltage_value_label.pack(side=tk.LEFT, padx=5)

    frames[f"V{cell_number}"] = (row_frame, voltage_value_label, progress_bar)


def create_temp_row(parent, temp_logo_path, temp_label, temp_value, column_index, frames):
    # Frame for each temperature entry
    row_frame = tk.Frame(parent, bg='white', padx=10, pady=10)
    row_frame.grid(row=1, column=column_index, padx=2, pady=2, sticky='nsew')

    # Load and display temperature logo
    temp_logo = ImageTk.PhotoImage(Image.open(temp_logo_path).resize((30, 30), Image.LANCZOS))
    temp_logo_label = tk.Label(row_frame, image=temp_logo, bg='white')
    temp_logo_label.image = temp_logo  # Keep a reference to avoid garbage collection
    temp_logo_label.grid(row=1, column=0, padx=2, pady=2)

    # Temperature label
    label = tk.Label(row_frame, text=temp_label, font=("Helvetica", 12,'bold'), bg='white')
    label.grid(row=1, column=1, padx=2, pady=2)

    # Progress bar
    progress_bar = ttk.Progressbar(row_frame, orient=tk.HORIZONTAL, length=100, mode='determinate', maximum=100)
    progress_bar.grid(row=1, column=2, padx=2, pady=2)
    progress_bar['value'] = temp_value

    # Temperature value
    temp_value_label = tk.Label(row_frame, text=f"{temp_value}°C", font=("Helvetica", 12), bg='white')
    temp_value_label.grid(row=1, column=3, padx=2, pady=2)

    frames[temp_label] = (row_frame, temp_value_label, progress_bar)


def create_dashboard_page(frame):
    global dashboardFrame
    frame.configure(bg="lightblue")
    # Dashboard frames
    dashboardFrame = create_frames(frame)
    
def connect():
    global ser,thread
    port = com_port.get()
    baud = baud_rate.get()
    try:
        ser = serial.Serial(port, baud)
        status_label.config(text="Serial Connected", bg="green")
        connection_status_label.config(text="Connected", fg='white', bg='green')
        data_queue = queue.Queue()
        thread = threading.Thread(target=read_serial_data, args=(dashboardFrame,ser, data_queue))
        thread.daemon = True  # Daemonize thread
        thread.start() 
    except Exception as e:
        status_label.config(text="Serial Not Connected", bg="red")
        print("error in serial connection : ",e)

def disconnect():
    global ser
    try:
        if ser.isOpen():
            ser.close()
            ser = None
            thread.join()
            print("serial is closed")
            status_label.config(text="Serial Disconnected", bg="red")
            connection_status_label.config(text="Disconnected", fg='red')
    except NameError:
        status_label.config(text="Serial Not Connected", bg="red")

def create_connection_page(frame):
    frame.configure(bg="white")
    global ser
    ser = None
    thread = None
    
    label = tk.Label(frame, text="Connection Page", bg="white", font=("Helvetica", 16))
    label.pack(side="top", fill="x", pady=10)

    content = tk.Frame(frame, bg="white")
    content.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    global com_port, baud_rate

    # Load the company logo
    logo_img = tk.PhotoImage(file=company_logo_path)  # Replace with your actual logo file path
    logo_label = tk.Label(content, image=logo_img, bg="white")
    logo_label.image = logo_img  # Keep a reference to avoid garbage collection
    logo_label.grid(row=0, column=0, columnspan=2, pady=10)

    tk.Label(content, text="Select a COM Port:", bg="white", font=("Helvetica", 14)).grid(row=1, column=0, pady=10, padx=10, sticky='w')
    com_port = ttk.Combobox(content, values=[port.device for port in serial.tools.list_ports.comports()])
    com_port.grid(row=1, column=1, pady=10, padx=10, sticky='e')

    tk.Label(content, text="Select Baud Rate:", bg="white", font=("Helvetica", 14)).grid(row=2, column=0, pady=10, padx=10, sticky='w')
    baud_rate = ttk.Combobox(content, values=["9600", "115200"])
    baud_rate.grid(row=2, column=1, pady=10, padx=10, sticky='e')
    baud_rate.set("9600")

    btn_style = {
        "font": ("Helvetica", 12, "bold"),
        "bg": "#444",
        "fg": "white",
        "activebackground": "#555",
        "activeforeground": "white",
        "bd": 0,
        "highlightthickness": 0,
        "relief": "flat",
        "width": 12,
        "padx": 10,
        "pady": 10
    }

    connect_btn = tk.Button(content, text="Connect", command=connect, **btn_style)
    connect_btn.grid(row=3, column=0, pady=20, padx=10)

    disconnect_btn = tk.Button(content, text="Disconnect", command=disconnect, **btn_style)
    disconnect_btn.grid(row=3, column=1, pady=20, padx=10)

    global status_label 
    status_label = tk.Label(content, text="", bg="white", font=("Helvetica", 14))
    status_label.grid(row=4, column=0, columnspan=2, pady=10)


def read_serial_data(dashboardFrame,ser,data_queue):
    global buffer,start_reading,null_sequence,values,last_AH,AH_meter,Percentage_SOC,patterns
    try:
        while 1:
            if ser is not None and ser.isOpen():
                buffer += ser.read(ser.in_waiting or 1)  # Read available data
               # If the null sequence is found, start reading after it
                if not start_reading and null_sequence in buffer:
                    start_reading = True
                    buffer = buffer.split(null_sequence, 1)[1]
                
                # If we haven't started reading and the buffer has data, start reading without waiting for nulls
                if not start_reading and len(buffer) > 0:
                    start_reading = True

                if start_reading:
                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)
                        line = line.replace(b'\x00', b'')  # Remove null characters
                        try:
                            decoded_line = line.decode('utf-8')
                        except UnicodeDecodeError:
                            print("UnicodeDecodeError: Invalid UTF-8 bytes encountered, skipping line.")
                            continue  # Skip processing this line and move to the next iteration

                        # Extract values using regex patterns
                        for key, pattern in patterns.items():
                            match = pattern.search(decoded_line)
                            if match:
                                values[key] = match.group(1)
                            
                    #CONDITIONS   
                        # Handle STATUS_CODE using the dictionary
                        if "STATUS_CODE" in values:
                            status_info = status_code_map.get(values["STATUS_CODE"], ("Unknown Status", lambda: None))
                            BATT_Status, action = status_info
                            values["STATUS"] = BATT_Status
                            action()  # Execute the associated action (if any)

                        elif values["STATUS"] == 'Charging':
                            AH_meter = round(((float(values["IBAT"]+IchOff)) * 0.00028), 6) + AH_meter
                            Percentage_SOC = (AH_meter / Battery_AH) * 100
                            
                        elif values["STATUS"] == 'Discharging':
                            AH_meter = round(((float(values["IBAT"]+IdchOff)) * -0.00028), 6) + AH_meter
                            Percentage_SOC = (last_AH / Battery_AH) * 100
                            
                        elif values["STATUS"] == "Standby":
                            pass
                       
                        values["SOC"]=round(Percentage_SOC,2)
                        values["PACKAH"]=round(AH_meter,2)
                        #update_gui_values(dashboardFrame,values)  
                        update_dashboard(dashboardFrame, values) 
            else:
                print("serial error:")
    except serial.SerialException as e:
        print(f"SerialException: {e}")
    except OSError as e:
        print(f"OSError: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
          
# Modified function to update the gui elements.
def update_dashboard(frames, values):
    # Update simple labels
    color='black'
    if "VBAT" in values:
        frames["VBAT"][1].config(text=f"{values['VBAT']}V")
    if "IBAT" in values:
        frames["IBAT"][1].config(text=f"{values['IBAT']}A")
    if "STATUS" in values:
        if values['STATUS'] == 'Discharging':
            color = 'red'
        if values['STATUS'] == 'Charging':
            color = 'green'
        frames["STATUS"][1].config(text=f"{values['STATUS']}",fg=color)
    if "PACKAH" in values:
        frames["PACKAH"][1].config(text=f"{values['PACKAH']}Ah")
    if "SOC" in values:
        frames["SOC"][1].config(text=f"{round(values['SOC'], 2)}%")
    if "SSR" in values:
        frames["SSR"][1].config(text=values['SSR'])

    # Update cell voltage labels and progress bars
    for i in range(1, num_v_values+1):  # Assuming there are 8 cells
        cell_key = f"V{i}"
        if cell_key in values:
            if values[cell_key]!=None:
                voltage = values[cell_key]
                label = frames[cell_key][1]  # Assuming labels are stored like { 'V1': (frame, label) }
                progress_bar = frames[cell_key][2]  # Assuming progress bars are stored like { 'V1': (frame, label, progress_bar) }

                # Update label with the new voltage value
                label.config(text=f"{voltage}mV")

                # Update the progress bar (you might need to adjust the scale)
                progress_bar['value'] = int(voltage)  # Assuming voltage is already an integer

    # Update temperature labels
    for i in range(1, 6):  # Assuming there are 5 temperature sensors
        temp_key = f"T{i}"
        if temp_key in values:
            temp_value = values[temp_key]
            if temp_value!=None:
                label = frames[f"Temp T{i}"][1]  # Assuming labels are stored like { 'Temp T1': (frame, label) }
                progress_bar = frames[f"Temp T{i}"][2]  # Assuming progress bars are stored like { 'Temp T1': (frame, label, progress_bar) }
                # Update label with the new temperature value
                label.config(text=f"{temp_value}°C")
                # Update the progress bar (assuming temperature range from 0°C to 100°C)
                progress_bar['value'] = int(temp_value)

def create_data_logging_page(frame):
    frame.configure(bg="lightyellow")
    global logging_freq_entry, logging_freq_unit, log_file_entry, table_frame, table, status_indicator

    # Logging Frequency Section
    logging_freq_frame = tk.Frame(frame, bg="lightyellow")
    logging_freq_frame.pack(pady=20)

    logging_freq_label = tk.Label(logging_freq_frame, text="Logging Frequency:", font=("Helvetica", 14), bg="lightyellow")
    logging_freq_label.grid(row=0, column=0, padx=10, pady=5)

    logging_freq_entry = tk.Entry(logging_freq_frame, font=("Helvetica", 14))
    logging_freq_entry.grid(row=0, column=1, padx=10, pady=5)

    logging_freq_unit = ttk.Combobox(logging_freq_frame, values=["sec", "msec"], font=("Helvetica", 14))
    logging_freq_unit.set("sec")  # Default value
    logging_freq_unit.grid(row=0, column=2, padx=10, pady=5)

    set_button = tk.Button(logging_freq_frame, text="Set", font=("Helvetica", 14), bg="#444", fg="white", activebackground="#555", activeforeground="white", bd=0, highlightthickness=0, relief="flat", command=set_logging_interval)
    set_button.grid(row=0, column=3, padx=10, pady=5)

    # Choose Log File Path Section
    log_file_frame = tk.Frame(frame, bg="lightyellow")
    log_file_frame.pack(pady=20)

    log_file_label = tk.Label(log_file_frame, text="Choose A Log File Path:", font=("Helvetica", 14), bg="lightyellow")
    log_file_label.grid(row=0, column=0, padx=10, pady=5)

    log_file_entry = tk.Entry(log_file_frame, font=("Helvetica", 14), width=50)
    log_file_entry.grid(row=0, column=1, padx=10, pady=5)

    browse_button = tk.Button(log_file_frame, text="Browse", font=("Helvetica", 14), bg="#444", fg="white", activebackground="#555", activeforeground="white", bd=0, highlightthickness=0, relief="flat", command=browse_file)
    browse_button.grid(row=0, column=2, padx=10, pady=5)

    # Start and Stop Buttons
    control_frame = tk.Frame(frame, bg="lightyellow")
    control_frame.pack(pady=20)

    start_button = tk.Button(control_frame, text="Start", font=("Helvetica", 14), bg="#444", fg="white", activebackground="#555", activeforeground="white", bd=0, highlightthickness=0, relief="flat", command=start_logging)
    start_button.grid(row=0, column=0, padx=10, pady=5)

    stop_button = tk.Button(control_frame, text="Stop", font=("Helvetica", 14), bg="#444", fg="white", activebackground="#555", activeforeground="white", bd=0, highlightthickness=0, relief="flat", command=stop_logging)
    stop_button.grid(row=0, column=1, padx=10, pady=5)

    # Logging Status Indicator
    status_frame = tk.Frame(frame, bg="lightyellow")
    status_frame.pack(pady=10)

    tk.Label(status_frame, text="Logging Status:", font=("Helvetica", 14), bg="lightyellow").pack(side="left", padx=10)
    status_indicator = tk.Label(status_frame, bg="red", width=2, height=1, relief="solid", borderwidth=2)
    status_indicator.pack(side="left")

    # Display DataFrame Section
    table_frame = tk.Frame(frame, bg="lightyellow")
    table_frame.pack(pady=20)
    
    columns = ['Time']
    columns += list(serial_data.keys()) #['Time', 'VBAT', 'IBAT', 'SOC']

    # Create a Scrollbar
    scrollbar_y = ttk.Scrollbar(table_frame, orient="vertical")
    scrollbar_y.pack(side="right", fill="y")

    # Create horizontal scrollbar
    scrollbar_x = ttk.Scrollbar(table_frame, orient="horizontal")
    scrollbar_x.pack(side="bottom", fill="x")

    table = ttk.Treeview(table_frame, columns=columns, show='headings', yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
    for col in columns:
        table.heading(col, text=col)
        table.column(col, anchor="center", width=50)
    table.pack(fill="both", expand=True)
    
    # Configure the scrollbar
    scrollbar_y.config(command=table.yview)
    scrollbar_x.config(command=table.xview)

def start_logging():
    global logging_running, logged_data
    logging_running = True
    logged_data = []
    if ser!=None and ser.isOpen():
        status_indicator.config(bg="green")  # Set the indicator to green when logging starts
        log_data()

def stop_logging():
    global logging_running
    status_indicator.config(bg="red")  # Set the indicator to red when logging stops
    logging_running = False

def log_data():
    global logging_running, log_file_path, logging_interval, logged_data
    if logging_running:
        # Simulate logging data from serial
        current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        data = {
            'Time': current_time,
            'VBAT':values["VBAT"],
            'IBAT':values["IBAT"],
            'PACK_AH': values["PACKAH"],
            'STATUS':values["STATUS"],
            'SSR':values["SSR"],
            'STATUS_CODE':values["STATUS_CODE"],
            'SOC':values["SOC"],
            'TBMS':values["TBMS"],
            'T1':values["T1"],
            'T2':values["T2"],
            'T3':values["T3"],
            'T4':values["T4"],
            'V1':values["V1"],
            'V2':values["V2"],
            'V3':values["V3"],
            'V4':values["V4"],
            'V5':values["V5"],
            'V6':values["V6"],
            'V7':values["V7"],
            'V8':values["V8"]
        }
        logged_data.append(data)
        
        # Write data to file
        df = pd.DataFrame(logged_data)
        df.to_csv(log_file_path, index=False)
        
        # Update UI with new data
        update_table(data)
        
        # Schedule the next logging
        threading.Timer(logging_interval, log_data).start()

def browse_file():
    global log_file_path
    log_file_path = asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
    log_file_entry.delete(0, tk.END)
    log_file_entry.insert(0, log_file_path)

def set_logging_interval():
    global logging_interval
    interval_value = logging_freq_entry.get()
    interval_unit = logging_freq_unit.get()
    if interval_unit == "msec":
        logging_interval = int(interval_value) / 1000
    else:
        logging_interval = int(interval_value)

def update_table(df):
    global table
    table.insert("", "end", values=tuple(df.values()))

def create_settings_page(frame):
    settings = load_settings()

    # Add padding and create a frame for grouped settings
    container = tk.Frame(frame, padx=10, pady=10)
    container.grid(row=0, column=0, sticky=tk.NSEW)

    # Section: Cell and Temperature Sensor Configuration
    cell_temp_frame = ttk.LabelFrame(container, text="Cell and Temperature Sensor Configuration", padding=(10, 5))
    cell_temp_frame.grid(row=0, column=0, pady=10, sticky=tk.W + tk.E)

    ttk.Label(cell_temp_frame, text="Number of Cells:").grid(row=0, column=0, sticky=tk.W, pady=5)
    cells_var = tk.IntVar(value=settings.get('num_cells', 1))
    ttk.Spinbox(cell_temp_frame, from_=1, to=16, textvariable=cells_var, width=5).grid(row=0, column=1, pady=5)

    ttk.Label(cell_temp_frame, text="Number of Temperature Sensors:").grid(row=1, column=0, sticky=tk.W, pady=5)
    temp_sensors_var = tk.IntVar(value=settings.get('num_temp_sensors', 1))
    ttk.Spinbox(cell_temp_frame, from_=1, to=10, textvariable=temp_sensors_var, width=5).grid(row=1, column=1, pady=5)

    # Section: Battery Voltage Limits
    voltage_frame = ttk.LabelFrame(container, text="Battery Voltage Limits", padding=(10, 5))
    voltage_frame.grid(row=1, column=0, pady=10, sticky=tk.W + tk.E)

    ttk.Label(voltage_frame, text="Voltage Upper Limit:").grid(row=0, column=0, sticky=tk.W, pady=5)
    bv_upper_var = tk.DoubleVar(value=settings.get('bv_upper', 50.0))
    ttk.Entry(voltage_frame, textvariable=bv_upper_var).grid(row=0, column=1, pady=5)

    ttk.Label(voltage_frame, text="Voltage Lower Limit:").grid(row=1, column=0, sticky=tk.W, pady=5)
    bv_lower_var = tk.DoubleVar(value=settings.get('bv_lower', 10.0))
    ttk.Entry(voltage_frame, textvariable=bv_lower_var).grid(row=1, column=1, pady=5)

    # Section: Battery Current Limits
    current_frame = ttk.LabelFrame(container, text="Battery Current Limits", padding=(10, 5))
    current_frame.grid(row=2, column=0, pady=10, sticky=tk.W + tk.E)

    ttk.Label(current_frame, text="Current Upper Limit:").grid(row=0, column=0, sticky=tk.W, pady=5)
    bc_upper_var = tk.DoubleVar(value=settings.get('bc_upper', 20.0))
    ttk.Entry(current_frame, textvariable=bc_upper_var).grid(row=0, column=1, pady=5)

    # Section: Temperature Sensor Limits
    temp_frame = ttk.LabelFrame(container, text="Temperature Sensor Limits", padding=(10, 5))
    temp_frame.grid(row=3, column=0, pady=10, sticky=tk.W + tk.E)

    ttk.Label(temp_frame, text="Temperature Upper Limit:").grid(row=0, column=0, sticky=tk.W, pady=5)
    ts_upper_var = tk.DoubleVar(value=settings.get('ts_upper', 40.0))
    ttk.Entry(temp_frame, textvariable=ts_upper_var).grid(row=0, column=1, pady=5)

    ttk.Label(temp_frame, text="Temperature Lower Limit:").grid(row=1, column=0, sticky=tk.W, pady=5)
    ts_lower_var = tk.DoubleVar(value=settings.get('ts_lower', 15.0))
    ttk.Entry(temp_frame, textvariable=ts_lower_var).grid(row=1, column=1, pady=5)

    # Section: Cell Voltage Limits
    cell_voltage_frame = ttk.LabelFrame(container, text="Cell Voltage Limits", padding=(10, 5))
    cell_voltage_frame.grid(row=4, column=0, pady=10, sticky=tk.W + tk.E)

    ttk.Label(cell_voltage_frame, text="Voltage Upper Limit:").grid(row=0, column=0, sticky=tk.W, pady=5)
    cv_upper_var = tk.DoubleVar(value=settings.get('cv_upper', 4500.0))
    ttk.Entry(cell_voltage_frame, textvariable=cv_upper_var).grid(row=0, column=1, pady=5)

    ttk.Label(cell_voltage_frame, text="Voltage Lower Limit:").grid(row=1, column=0, sticky=tk.W, pady=5)
    cv_lower_var = tk.DoubleVar(value=settings.get('cv_lower', 2000.0))
    ttk.Entry(cell_voltage_frame, textvariable=cv_lower_var).grid(row=1, column=1, pady=5)

    # IchOffset Limits :
    IchOffset_frame = ttk.LabelFrame(container, text="IchOffset Limits", padding=(10, 5))
    IchOffset_frame.grid(row=5, column=0, pady=10, sticky=tk.W + tk.E)

    ttk.Label(IchOffset_frame, text="IchOffset : ").grid(row=0, column=0, sticky=tk.W, pady=5)
    IchOffset = tk.DoubleVar(value=settings.get('IchOffset', 0))
    ttk.Entry(IchOffset_frame, textvariable=IchOffset).grid(row=0, column=1, pady=5)

    # IdchOffset Limits :

    IdchOffset_frame = ttk.LabelFrame(container, text="IdchOffset Limits", padding=(10, 5))
    IdchOffset_frame.grid(row=6, column=0, pady=10, sticky=tk.W + tk.E)

    ttk.Label(IdchOffset_frame, text="IdchOffset : ").grid(row=0, column=0, sticky=tk.W, pady=5)
    IdchOffset = tk.DoubleVar(value=settings.get('IdchOffset', 0))
    ttk.Entry(IdchOffset_frame, textvariable=IdchOffset).grid(row=0, column=1, pady=5)
    

    # Save button at the bottom
    def save():
        new_settings = {
            'num_cells': cells_var.get(),
            'num_temp_sensors': temp_sensors_var.get(),
            'bv_upper': bv_upper_var.get(),
            'bv_lower': bv_lower_var.get(),
            'bc_upper': bc_upper_var.get(),
            'ts_upper': ts_upper_var.get(),
            'ts_lower': ts_lower_var.get(),
            'cv_upper': cv_upper_var.get(),
            'cv_lower': cv_lower_var.get(),
            'IchOffset': IchOffset.get(),
            'IdchOffset':IdchOffset.get()
        }
        save_settings(new_settings)
        messagebox.showinfo("Settings", "Settings saved successfully!")

    ttk.Button(container, text="Save Settings", command=save).grid(row=7, column=0, padx=1, pady=1, sticky=tk.E)

def main():
    root = tk.Tk()
    
    root.title("Retron Battery Management System V1.2")
    root.geometry("1366x768")
    root.iconbitmap(company_icon)
    
    frames = {}

    create_nav_bar(root, frames)  # Create the nav bar first

    container = tk.Frame(root)
    container.pack(side="top", fill="both", expand=True)
    container.grid_rowconfigure(0, weight=1)
    container.grid_columnconfigure(0, weight=1)

    frames["DashboardPage"] = tk.Frame(container)
    frames["ConnectionPage"] = tk.Frame(container)
    frames["DataLoggingPage"] = tk.Frame(container)
    frames["SettingsPage"] = tk.Frame(container)

    for frame in frames.values():
        frame.grid(row=0, column=0, sticky="nsew")

    create_dashboard_page(frames["DashboardPage"])
    create_connection_page(frames["ConnectionPage"])
    create_data_logging_page(frames["DataLoggingPage"])
    create_settings_page(frames["SettingsPage"])

    show_frame(frames, "DashboardPage")
    root.mainloop()

if __name__ == "__main__":
    main()
