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


logo_path = os.path.join(sys._MEIPASS, 'logo.png')
cell_path = os.path.join(sys._MEIPASS, 'cell.png')
temp_path = os.path.join(sys._MEIPASS, 'temp.png')
AH_meter = 0
Battery_AH = 6   #setting input
Percentage_SOC=0
stopFlag=False
last_AH = 0 
ser=None
buffer = b''
start_reading = False
null_sequence = b'\x00' * 128
settings_file = 'settings.json'

def load_settings():
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            return json.load(f)
    return {}

# Save settings to file
def save_settings(settings):
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=4)
# Define regular expression patterns for each value
settings_data = load_settings()
num_v_values = settings_data.get("num_cells",1) if settings_data!=None else 8 #setting input      # Set the number of 'V' values expected
patterns = {
'VBAT': re.compile(r'VBAT:(\d+\.\d+)V'),
'IBAT': re.compile(r'IBAT:(\d+\.\d+)A'),
'STATUS': re.compile(r'(Charging|Discharging|Standby)'),
'SSR': re.compile(r'SSR:(\d+)'),
'STATUS_CODE': re.compile(r'STATUS:(\d+)'),
'T1': re.compile(r'T1:(\d+)°C'),
'T2': re.compile(r'T2:(\d+)°C'),
'T3': re.compile(r'T3:(\d+)°C'),
'T4': re.compile(r'T4:(\d+)°C'),
'TBMS': re.compile(r'TBMS:(\d+)°C'),
}

# Add 'V' patterns dynamically based on num_v_values
for i in range(1, num_v_values + 1):
    patterns[f'V{i}'] = re.compile(rf'V{i}:(\d+)')

# Initialize variables
values = {key: None for key in patterns}

serial_data = {
    'VBAT': '25.359',
    'IBAT': '2.8',
    'STATUS': 'Discharging',
    'SSR': '1',
    'STATUS_CODE': '108',
    'SOC': '56',
    'TBMS': '12',
    'T1': '31',
    'T2': '31',
    'T3': '31',
    'T4': '31',
    'V1': '3185',
    'V2': '3153',
    'V3': '3165',
    'V4': '3168',
    'V5': '3171',
    'V6': '2800',
    'V7': '2700',
    'V8': '2600'
}

# Global variables
log_file_path = ""
logging_interval = 1  # Default to 1 second
logging_running = False
logged_data = []

def show_frame(frames, frame_name):
    frame = frames[frame_name]
    frame.tkraise()

def create_nav_bar(root, frames):
    nav_bar = tk.Frame(root, bg="#333")
    nav_bar.pack(side="top", fill="x")
    
    logo_image = Image.open(logo_path)  # Change to your logo file path
    logo_image = logo_image.resize((200, 60), Image.LANCZOS)  # Resize the image
    logo_img = ImageTk.PhotoImage(logo_image)


    logo_label = tk.Label(nav_bar, image=logo_img, bg="#333")
    logo_label.image = logo_img  # Keep a reference to avoid garbage collection
    logo_label.pack(side="left", padx=5, pady=5)

    button_style = {
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

    buttons = [
        ("Settings", "SettingsPage"),
        ("Graphs", "GraphsPage"),
        ("Data Log", "DataLoggingPage"),
        ("Dashboard", "DashboardPage"),
        ("Connection", "ConnectionPage"),
    ]

    for (text, frame_name) in buttons:
        button = tk.Button(nav_bar, text=text, command=lambda f=frame_name: show_frame(frames, f), **button_style)
        button.pack(side="right", padx=5, pady=5)

def style_frame(frame, name, values):
    frame.config(bg='#2c3e50', bd=2, relief='ridge', padx=20, pady=20)

    label = tk.Label(frame, text=f" {name.upper()}", font=('Helvetica', 24, 'bold'), bg='#34495e', fg='white', padx=10, pady=10)
    label.pack(fill='x')

    value_label = tk.Label(frame, text=f"Value: {values}", font=('Helvetica', 18), bg='#2c3e50', fg='white')
    value_label.pack(pady=5)

    
def create_frames(root):
    frames = {}
    names = ['VBAT', 'IBAT', 'STATUS', 'PACKAH', 'SOC', 'SSR']

    cell_voltages = [0, 0, 0, 0, 0, 0, 0, 0]  # Example data
    temp_readings = [0, 0, 0, 0]  # Example data for 5 sensors

    container = tk.Frame(root, bg='#ecf0f1')
    container.pack(fill='both', expand=True, padx=20, pady=20)

    # Load cell and temp logos
    cell_logo = ImageTk.PhotoImage(Image.open(cell_path).resize((30, 30), Image.LANCZOS))
    temp_logo = ImageTk.PhotoImage(Image.open(temp_path).resize((30, 30), Image.LANCZOS))

    for i, name in enumerate(names):
        frame = tk.Frame(container, width=500, height=500)
        frame.grid(row=0, column=i, padx=10, pady=10)
        frames[name] = frame
        style_frame(frame, name, {})  # Initial empty values

    container2 = tk.Frame(root, bg='#ecf0f1')
    container2.pack(fill='both', expand=True, padx=20, pady=20)

    for i, cell in enumerate(cell_voltages):
        frame = tk.Frame(container2, bg='#ecf0f1')
        frame.grid(row=i, column=1, padx=10, pady=10)

        cell_label = tk.Label(frame, text=f"Cell {i + 1}", font=("Helvetica", 14, 'bold'), bg='#ecf0f1')
        cell_label.grid(row=0, column=0, padx=10)

        cell_logo_label = tk.Label(frame, image=cell_logo, bg="lightblue")
        cell_logo_label.image = cell_logo
        cell_logo_label.grid(row=0, column=1, padx=10)

        cell_progress = ttk.Progressbar(frame, orient='horizontal', length=200, mode='determinate', maximum=5000)
        cell_progress['value'] = cell
        cell_progress.grid(row=0, column=2, padx=10)

        cell_value_label = tk.Label(frame, text=f"{cell} mV", font=("Helvetica", 14), bg="#ecf0f1")
        cell_value_label.grid(row=0, column=3, padx=10)
        frames[f"V{i + 1}"] = frame

    for i, temp in enumerate(temp_readings):
        frame = tk.Frame(container2, bg='#ecf0f1')
        frame.grid(row=i, column=2, padx=10, pady=10)

        temp_label = tk.Label(frame, text=f"Temp {i + 1}", font=("Helvetica", 14, 'bold'), bg="#ecf0f1")
        temp_label.grid(row=0, column=0, padx=10)

        temp_logo_label = tk.Label(frame, image=temp_logo, bg="#ecf0f1")
        temp_logo_label.image = temp_logo
        temp_logo_label.grid(row=0, column=1, padx=10)

        temp_progress = ttk.Progressbar(frame, orient='horizontal', length=200, mode='determinate', maximum=100)
        temp_progress['value'] = temp
        temp_progress.grid(row=0, column=2, padx=10)

        temp_value_label = tk.Label(frame, text=f"{temp} °C", font=("Helvetica", 14), bg="#ecf0f1")
        temp_value_label.grid(row=0, column=3, padx=10)
        frames[f"T{i + 1}"] = frame

    return frames

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
            data_queue = queue.Queue()
            thread = threading.Thread(target=read_serial_data, args=(dashboardFrame,ser, data_queue))
            thread.daemon = True  # Daemonize thread
            thread.start() 
        except Exception as e:
            status_label.config(text="Serial Not Connected", bg="red")

def disconnect():
    global ser
    print("serial close req:",ser)
    try:
        if ser.isOpen():
            ser.close()
            thread.join()
            print("serial is closed")
            status_label.config(text="Serial Disconnected", bg="red")
    except NameError:
        status_label.config(text="Serial Not Connected", bg="red")

def create_connection_page(frame):
    frame.configure(bg="lightgreen")
    global ser
    ser=None
    thread=None
    
    label = tk.Label(frame, text="Connection Page", bg="lightgreen", font=("Helvetica", 16))
    label.pack(side="top", fill="x", pady=10)

    content = tk.Frame(frame, bg="lightgreen")
    content.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    global com_port,baud_rate
    tk.Label(content, text="Select a COM Port:", bg="lightgreen", font=("Helvetica", 14)).grid(row=0, column=0, pady=10, padx=10, sticky='w')
    com_port = ttk.Combobox(content, values=[port.device for port in serial.tools.list_ports.comports()])
    com_port.grid(row=0, column=1, pady=10, padx=10, sticky='e')

    tk.Label(content, text="Select Baud Rate:", bg="lightgreen", font=("Helvetica", 14)).grid(row=1, column=0, pady=10, padx=10, sticky='w')
    baud_rate = ttk.Combobox(content, values=["9600", "115200"])
    baud_rate.grid(row=1, column=1, pady=10, padx=10, sticky='e')
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
    connect_btn.grid(row=2, column=0, pady=20, padx=10)

    disconnect_btn = tk.Button(content, text="Disconnect", command=disconnect, **btn_style)
    disconnect_btn.grid(row=2, column=1, pady=20, padx=10)

    global status_label 
    status_label = tk.Label(content, text="", bg="lightgreen", font=("Helvetica", 14))
    status_label.grid(row=3, column=0, columnspan=2, pady=10)

def read_serial_data(dashboardFrame,ser,data_queue):
    global buffer,start_reading,null_sequence,values,last_AH,AH_meter,Percentage_SOC,patterns
    while 1:
        if ser.isOpen():
            buffer += ser.read(ser.in_waiting or 1)  # Read available data
        # Check if the null sequence is in the buffer
            if not start_reading and null_sequence in buffer:
                start_reading = True
                # Truncate buffer to start after the null sequence
                buffer = buffer.split(null_sequence, 1)[1]
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
                    
                    # print("Current values:", values) # Print current values for debugging
                    #print("check : ",values["STATUS"])
                    
                    
                #CONDITIONS   
                    if values["STATUS_CODE"] in ['104','105','106']:
                        last_AH = AH_meter
                        AH_meter = 0                
                    elif values["STATUS"] == 'Charging':
                        AH_meter=round(((float(values["IBAT"])-0.1)*0.00005555),6)+AH_meter
                        Percentage_SOC = (AH_meter/Battery_AH)*100
                        # print("c")
                    elif values["STATUS"] == 'Discharging':
                        AH_meter=round(((float(values["IBAT"])+0.1)*-0.00005555),6)+AH_meter
                        Percentage_SOC = (last_AH/Battery_AH)*100
                        print("d")
                    elif values["STATUS"] == "Standby":
                        pass
                    #     AH_meter=round((float(values["IBAT"])*0.005),6)+AH_meter
                    #     print("AH value:", AH_meter,"-",datetime.datetime.now())
                    #     Percentage_SOC = (AH_meter/Battery_AH)*100
                    # print("Percentage : ",Percentage_SOC)
                    values["SOC"]=Percentage_SOC
                    values["PACKAH"]=AH_meter
                    update_gui_values(dashboardFrame,values)   
        else:
            print("serial error:")
        
def update_gui_values(frames, data_values):
   # Updating the frames
   # Update VBAT
    if 'VBAT' in frames:
        frame = frames['VBAT']
        for child in frame.winfo_children():
            if isinstance(child, tk.Label) and child.cget('text').startswith('Value:'):
                child.configure(text=f"Value: {values['VBAT']} V")
                break  # Assuming there's only one label with 'Value:' text
    if 'IBAT' in frames:
        frame = frames['IBAT']
        for child in frame.winfo_children():
            if isinstance(child, tk.Label) and child.cget('text').startswith('Value:'):
                child.configure(text=f"Value: {values['IBAT']} A")
                break

    # Update STATUS frame value label
    if 'STATUS' in frames:
        frame = frames['STATUS']
        for child in frame.winfo_children():
            if isinstance(child, tk.Label) and child.cget('text').startswith('Value:'):
                if values['STATUS'] == 'Discharging':
                    color = 'red'
                if values['STATUS'] == 'Charging':
                    color = 'green'
                child.configure(text=f"Value: {values['STATUS']}",fg=color)
                break

    if 'SSR' in frames:
        frame = frames['SSR']
        for child in frame.winfo_children():
            if isinstance(child, tk.Label) and child.cget('text').startswith('Value:'):
                child.configure(text=f"Value: {values['SSR']}")
                break
    
    if 'PACKAH' in frames:
        frame = frames['PACKAH']
        for child in frame.winfo_children():
            if isinstance(child, tk.Label) and child.cget('text').startswith('Value:'):
                child.configure(text=f"Value: {values['PACKAH']} Ah")
                break

    if 'SOC' in frames:
        frame = frames['SOC']
        for child in frame.winfo_children():
            if isinstance(child, tk.Label) and child.cget('text').startswith('Value:'):
                child.configure(text=f"Value: {values['SOC']} %")
                break
    # Update temperature readings (T1 to T4)
    for i in range(1, 5):
        temp_key = f"T{i}"
        if temp_key in values:
            # Update label text
            temp_label = frames[temp_key].children['!label3']
            temp_label.configure(text=f"{values[temp_key]} °C")
            # print("value",values[temp_key])
            # Example: Update progress bar (adjust as per your actual logic)
            # Calculate progress bar value based on received temperature value
            if values[temp_key]!=None:
                temp_progressbar = frames[temp_key].children['!progressbar']
                temp_value = int(values[temp_key])
                temp_progressbar.configure(value=temp_value)

    # Update cell voltages (V1 to V8)
    for i in range(1, 9):
        cell_key = f"V{i}"
        if cell_key in values:
            # Update label text
            cell_label = frames[cell_key].children['!label3']
            cell_label.configure(text=f"{values[cell_key]} mV")
            
            # Example: Update progress bar (adjust as per your actual logic)
            # Calculate progress bar value based on received cell voltage value
            if values[cell_key]!=None:
                cell_progressbar = frames[cell_key].children['!progressbar']
                cell_value = int(values[cell_key])
                cell_progressbar.configure(value=cell_value)
            
def create_data_logging_page(frame):
    frame.configure(bg="lightyellow")
    global logging_freq_entry, logging_freq_unit, log_file_entry, table_frame, table

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

    # Display DataFrame Section
    table_frame = tk.Frame(frame, bg="lightyellow")
    table_frame.pack(pady=20)
    columns = ['Time']
    columns+=list(serial_data.keys()) #['Time', 'VBAT', 'IBAT', 'SOC']
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
    log_data()

def stop_logging():
    global logging_running
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

def create_graphs_page(frame):
    frame.configure(bg="lightcoral")
    # Graph Page 
    GraphPage(frame, None).pack(fill="both", expand=True)


def create_settings_page(frame):
    settings = load_settings()

    tk.Label(frame, text="Number of Cells:").grid(row=0, column=0, sticky=tk.W)
    cells_var = tk.IntVar(value=settings.get('num_cells', 1))
    tk.Spinbox(frame, from_=1, to=16, textvariable=cells_var).grid(row=0, column=1)

    tk.Label(frame, text="Number of Temperature Sensors:").grid(row=1, column=0, sticky=tk.W)
    temp_sensors_var = tk.IntVar(value=settings.get('num_temp_sensors', 1))
    tk.Spinbox(frame, from_=1, to=10, textvariable=temp_sensors_var).grid(row=1, column=1)

    tk.Label(frame, text="Battery Voltage Upper Limit:").grid(row=2, column=0, sticky=tk.W)
    bv_upper_var = tk.DoubleVar(value=settings.get('bv_upper', 50.0))
    tk.Entry(frame, textvariable=bv_upper_var).grid(row=2, column=1)

    tk.Label(frame, text="Battery Voltage Lower Limit:").grid(row=3, column=0, sticky=tk.W)
    bv_lower_var = tk.DoubleVar(value=settings.get('bv_lower', 10.0))
    tk.Entry(frame, textvariable=bv_lower_var).grid(row=3, column=1)

    tk.Label(frame, text="Battery Current Upper Limit:").grid(row=4, column=0, sticky=tk.W)
    bc_upper_var = tk.DoubleVar(value=settings.get('bc_upper', 20.0))
    tk.Entry(frame, textvariable=bc_upper_var).grid(row=4, column=1)

    tk.Label(frame, text="Temperature Sensor Upper Limit:").grid(row=5, column=0, sticky=tk.W)
    ts_upper_var = tk.DoubleVar(value=settings.get('ts_upper', 40.0))
    tk.Entry(frame, textvariable=ts_upper_var).grid(row=5, column=1)

    tk.Label(frame, text="Temperature Sensor Lower Limit:").grid(row=6, column=0, sticky=tk.W)
    ts_lower_var = tk.DoubleVar(value=settings.get('ts_lower', 15.0))
    tk.Entry(frame, textvariable=ts_lower_var).grid(row=6, column=1)

    tk.Label(frame, text="Cell Voltage Upper Limit:").grid(row=7, column=0, sticky=tk.W)
    cv_upper_var = tk.DoubleVar(value=settings.get('cv_upper', 4500.0))
    tk.Entry(frame, textvariable=cv_upper_var).grid(row=7, column=1)

    tk.Label(frame, text="Cell Voltage Lower Limit:").grid(row=8, column=0, sticky=tk.W)
    cv_lower_var = tk.DoubleVar(value=settings.get('cv_lower', 2000.0))
    tk.Entry(frame, textvariable=cv_lower_var).grid(row=8, column=1)

    # Save button
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
        }
        save_settings(new_settings)
        messagebox.showinfo("Settings", "Settings saved successfully!")

    tk.Button(frame, text="Save", command=save).grid(row=9, column=0, columnspan=2)

class GraphPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(bg="lightcoral")

        # Create a canvas and a scrollbar
        self.canvas = tk.Canvas(self, bg="lightcoral")
        self.scrollbar_y = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollbar_x = tk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.scrollbar_y.set, xscrollcommand=self.scrollbar_x.set)

        self.scrollbar_y.pack(side="right", fill="y")
        self.scrollbar_x.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        # Pack the canvas and the scrollbar
        self.scrollbar_y.pack(side="right", fill="y")
        self.scrollbar_x.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Create a frame inside the canvas
        self.main_frame = tk.Frame(self.canvas, bg="lightcoral")
        self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        self.main_frame.bind("<Configure>", self.on_frame_configure)

        self.bind_all("<Up>", self.scroll_up)
        self.bind_all("<Down>", self.scroll_down)
        self.data = None

        # File path entry and browse button
        self.file_path_label = tk.Label(self.main_frame, text="Choose a Log File Path:", font=("Helvetica", 14), bg="lightcoral")
        self.file_path_label.grid(row=0, column=2, pady=10, padx=10, sticky="w")

        self.file_path_entry = tk.Entry(self.main_frame, font=("Helvetica", 14), width=50)
        self.file_path_entry.grid(row=0, column=3, pady=10, padx=10, sticky="we")

        self.browse_button = tk.Button(self.main_frame, text="Browse", font=("Helvetica", 14), bg="#444", fg="white",
                                       activebackground="#555", activeforeground="white", bd=0, highlightthickness=0,
                                       relief="flat", command=self.browse_file)
        self.browse_button.grid(row=0, column=4, pady=10, padx=10)

        # X-axis field selection
        self.x_label = tk.Label(self.main_frame, text="Select X field:", font=("Helvetica", 14), bg="lightcoral")
        self.x_label.grid(row=1, column=2, pady=10, padx=10, sticky="w")
        
        self.x_field = ttk.Combobox(self.main_frame, font=("Helvetica", 14))
        self.x_field.grid(row=1, column=3, pady=10, padx=10, sticky="we")
        
        # Y-axis fields selection
        self.y_label = tk.Label(self.main_frame, text="Select Y fields:", font=("Helvetica", 14), bg="lightcoral")
        self.y_label.grid(row=2, column=2, pady=10, padx=10, sticky="w")
        
        self.y_fields = tk.Listbox(self.main_frame, selectmode="multiple", font=("Helvetica", 14), height=6)
        self.y_fields.grid(row=2, column=3, pady=10, padx=10, sticky="we")

        # X-axis Interval
        self.interval_label = tk.Label(self.main_frame, text="X-axis Interval:", font=("Helvetica", 14), bg="lightcoral")
        self.interval_label.grid(row=3, column=2, pady=10, padx=10, sticky="w")

        self.interval_entry = tk.Entry(self.main_frame, font=("Helvetica", 14))
        self.interval_entry.grid(row=3, column=3, pady=10, padx=10, sticky="we")

        # Number of Samples
        self.sample_label = tk.Label(self.main_frame, text="Number of Samples:", font=("Helvetica", 14), bg="lightcoral")
        self.sample_label.grid(row=4, column=2, pady=10, padx=10, sticky="w")

        self.sample_entry = tk.Entry(self.main_frame, font=("Helvetica", 14))
        self.sample_entry.grid(row=4, column=3, pady=10, padx=10, sticky="we")
        
        # Plot and Save buttons
        self.plot_button = tk.Button(self.main_frame, text="Plot Graph", font=("Helvetica", 14), bg="#444", fg="white", command=self.plot_graph)
        self.plot_button.grid(row=5, column=2, columnspan=2, pady=10, padx=10, sticky="we")
        
        self.save_button = tk.Button(self.main_frame, text="Save Graph", font=("Helvetica", 14), bg="#444", fg="white", command=self.save_graph)
        self.save_button.grid(row=5, column=4, pady=10, padx=10, sticky="we")
        self.save_button.config(state="disabled")

        # Graph display area
        self.graph_frame = tk.Frame(self.main_frame, bg="lightcoral")
        self.graph_frame.grid(row=6, column=2, columnspan=3, pady=10, padx=10, sticky="nsew")
        self.graph_frame.grid_rowconfigure(0, weight=1)
        self.graph_frame.grid_columnconfigure(0, weight=1)

    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    def scroll_up(self, event):
        self.canvas.yview_scroll(-1, "units")

    def scroll_down(self, event):
        self.canvas.yview_scroll(1, "units")
    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        self.file_path_entry.delete(0, tk.END)
        self.file_path_entry.insert(0, file_path)
        if file_path:
            self.data = pd.read_csv(file_path)
            self.x_field['values'] = self.data.columns.tolist()
            self.y_fields.delete(0, tk.END)
            for col in self.data.columns:
                self.y_fields.insert(tk.END, col)

    def plot_graph(self):
        for widget in self.graph_frame.winfo_children():
            widget.destroy()
        
        x = self.x_field.get()
        y = [self.y_fields.get(idx) for idx in self.y_fields.curselection()]
        interval = int(self.interval_entry.get()) if self.interval_entry.get().isdigit() else 1
        sample_count = int(self.sample_entry.get()) if self.sample_entry.get().isdigit() else len(self.data)
        
        if x and y:
            fig, ax = plt.subplots(figsize=(10, 6))  # Increase the figure size for better fitting

            sample_data = self.data[::interval].head(sample_count)
            
            for y_field in y:
                ax.plot(sample_data[x], sample_data[y_field], label=y_field)
            
            ax.set_title('Generated Graph')
            ax.set_xlabel(x)
            ax.set_ylabel('Values')
            ax.legend()
            ax.tick_params(axis='x', rotation=90)  # Rotate x-axis labels vertically
            
            self.canvas_widget = FigureCanvasTkAgg(fig, master=self.graph_frame)
            self.canvas_widget.get_tk_widget().pack(fill="both", expand=True)
            self.canvas_widget.draw()
            
            plt.close(fig)  # Close the figure after embedding it in the canvas
            
            self.save_button.config(state="normal")
        else:
            messagebox.showerror("Error", "Please select both X and Y fields.")
    
    def save_graph(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png"), ("All files", "*.*")])
        if file_path:
            self.canvas_widget.figure.savefig(file_path)
            messagebox.showinfo("Save Graph", "Graph saved successfully!")

def main():
    root = tk.Tk()
    root.title("Battery Management System")
    root.geometry("1200x800")

    frames = {}

    create_nav_bar(root, frames)  # Create the nav bar first

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
    create_connection_page(frames["ConnectionPage"])
    create_data_logging_page(frames["DataLoggingPage"])
    create_graphs_page(frames["GraphsPage"])
    create_settings_page(frames["SettingsPage"])

    show_frame(frames, "DashboardPage")
    root.mainloop()

if __name__ == "__main__":
    main()
