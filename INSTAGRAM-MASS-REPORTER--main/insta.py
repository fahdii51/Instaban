import random
import time
import os
import threading
from concurrent.futures import ThreadPoolExecutor
import logging
import requests
from fake_useragent import UserAgent
import json
import webbrowser
try:
    import tkinter as tk
    from tkinter import messagebox, scrolledtext
    from tkinter.ttk import Progressbar
except ImportError:
    tk = None  # Fallback to terminal if tkinter is unavailable

# Custom logging handler to update GUI text area
class TextAreaHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.configure(state='normal')
        self.text_widget.insert(tk.END, msg + '\n')
        self.text_widget.see(tk.END)
        self.text_widget.configure(state='disabled')
        self.text_widget.update()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Function to display ASCII art (fallback for terminal)
def display_ascii_art():
    ascii_art = """
█ █▄░█ █▀ ▀█▀ ▄▀█
█ █░▀█ ▄█ ░█░ █▀█

█▀█ █▀▀ █▀█ █▀█ █▀█ ▀█▀ █▀▀ █▀█
█▀▄ ██▄ █▀▀ █▄█ █▀▄ ░█░ ██▄ █▀▄

𝗜𝗡𝗦𝗧𝗔𝗚𝗥𝗔𝗠 𝗥𝗘𝗣𝗢𝗥𝗧𝗘𝗥

𝗦C𝗥𝗜𝗣𝗧 𝗕𝗬 𝗦𝗛𝗥𝗜𝗝𝗔𝗡 𝗧𝗜𝗪𝗔𝗥𝗜 
"""
    print(ascii_art)

# Function to load accounts from accounts.json
def load_accounts():
    accounts_file = 'accounts.json'
    if not os.path.exists(accounts_file):
        logging.error(f"{accounts_file} not found. Please create it with account credentials.")
        return []
    
    try:
        with open(accounts_file, 'r') as f:
            accounts_data = json.load(f)
            accounts = []
            for account in accounts_data:
                username = account.get('username')
                password = account.get('password')
                if username and password:
                    accounts.append((username, password))
                else:
                    logging.warning(f"Invalid account entry in {accounts_file}: {account}")
            logging.info(f"Loaded {len(accounts)} accounts from {accounts_file}")
            return accounts
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing {accounts_file}: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error reading {accounts_file}: {e}")
        return []

# Instagram Reporter class
class InstagramReporter:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.ua = UserAgent()
        self.base_url = "https://www.instagram.com"
        self.lock = threading.Lock()
        self.session = None
        self.report_reasons = [
            "spam", "inappropriate", "harassment", "impersonation",
            "scam", "hate_speech", "violence", "nudity"
        ]

    def get_session(self):
        session = requests.Session()
        session.headers.update({
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": self.base_url,
        })
        return session

    def login(self, session, retries=3):
        for attempt in range(retries):
            try:
                response = session.get(f"{self.base_url}/accounts/login/", timeout=5)
                csrf_token = response.cookies.get("csrftoken")
                if not csrf_token:
                    logging.error(f"No CSRF token for {self.username}")
                    time.sleep(1)
                    continue

                payload = {
                    "username": self.username,
                    "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{self.password}",
                    "queryParams": {},
                    "optIntoOneTap": "false"
                }
                headers = {
                    "X-CSRFToken": csrf_token,
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded",
                }
                login_url = f"{self.base_url}/accounts/login/ajax/"
                response = session.post(login_url, data=payload, headers=headers, timeout=5)
                if response.status_code == 200 and response.json().get("authenticated"):
                    logging.info(f"Logged in with {self.username}")
                    return session
                else:
                    logging.warning(f"Login attempt {attempt + 1} failed for {self.username}: {response.text}")
                    time.sleep(1)
            except Exception as e:
                logging.warning(f"Login error for {self.username} (attempt {attempt + 1}): {e}")
                time.sleep(1)
        logging.error(f"Login failed for {self.username} after {retries} attempts")
        return None

    def initialize_session(self):
        if self.session is None:
            self.session = self.get_session()
            self.session = self.login(self.session)
        return self.session is not None

    def refresh_session(self):
        logging.info(f"Refreshing session for {self.username}")
        self.session = None
        return self.initialize_session()

    def report_user(self, target_username, reason=None):
        if not self.session:
            logging.error(f"No active session for {self.username}")
            return False

        selected_reason = random.choice(self.report_reasons) if reason is None else reason
        if selected_reason not in self.report_reasons:
            logging.warning(f"Invalid reason '{selected_reason}' for {self.username}, defaulting to 'spam'")
            selected_reason = "spam"

        try:
            profile_url = f"{self.base_url}/{target_username}/"
            response = self.session.get(profile_url, timeout=5)
            if response.status_code != 200:
                if response.status_code == 403:
                    logging.warning(f"Session expired for {self.username}, refreshing")
                    if self.refresh_session():
                        response = self.session.get(profile_url, timeout=5)
                        if response.status_code != 200:
                            logging.error(f"Failed to access {target_username}'s profile with {self.username}")
                            return False
                    else:
                        logging.error(f"Failed to refresh session for {self.username}")
                        return False
                else:
                    logging.error(f"Failed to access {target_username}'s profile with {self.username}: {response.status_code}")
                    return False

            user_id = None
            try:
                user_id = response.text.split('"id":"')[1].split('"')[0]
            except:
                logging.error(f"Failed to extract user ID for {target_username} with {self.username}")
                return False

            report_url = f"{self.base_url}/users/{user_id}/report/"
            payload = {
                "source_name": "",
                "reason": selected_reason,
                "frx_prompt_request_type": "1"
            }
            headers = {
                "X-CSRFToken": self.session.cookies.get("csrftoken"),
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            response = self.session.post(report_url, data=payload, headers=headers, timeout=5)
            if response.status_code == 200:
                logging.info(f"Successfully reported {target_username} with {self.username} for '{selected_reason}'")
                return True
            else:
                logging.error(f"Report failed for {target_username} with {self.username} for '{selected_reason}': {response.status_code}")
                if response.status_code == 403:
                    logging.warning(f"Session expired during report for {self.username}, refreshing")
                    if self.refresh_session():
                        response = self.session.post(report_url, data=payload, headers=headers, timeout=5)
                        if response.status_code == 200:
                            logging.info(f"Successfully reported {target_username} with {self.username} after session refresh")
                            return True
                return False
        except Exception as e:
            logging.error(f"Report error for {target_username} with {self.username} for '{selected_reason}': {e}")
            return False

# Worker function to handle reporting for one account
def make_reports(reporter, target_username, num_reports, progress_callback=None):
    if not reporter.initialize_session():
        logging.error(f"Skipping reports for {reporter.username} due to login failure")
        return

    for i in range(num_reports):
        success = reporter.report_user(target_username)
        with reporter.lock:
            if success:
                logging.info(f"Report #{i + 1} completed by {reporter.username}")
            else:
                logging.warning(f"Report #{i + 1} failed by {reporter.username}")
            if progress_callback:
                progress_callback(success)
        time.sleep(random.uniform(0.3, 0.8))  # Reduced delay for speed

# Main function to manage reporting
def mass_report(target_username, accounts, num_reports_per_account=1, max_workers=10, progress_callback=None):
    if not accounts:
        logging.error("No accounts provided for reporting")
        return

    logging.info(f"Starting {len(accounts) * num_reports_per_account} reports for {target_username} with {max_workers} threads")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for username, password in accounts:
            reporter = InstagramReporter(username, password)
            executor.submit(make_reports, reporter, target_username, num_reports_per_account, progress_callback)

    logging.info("All reports completed")

# GUI for splash screen, reporting input, and progress
def run_gui():
    # Redirect to WhatsApp channel at the start
    webbrowser.open("https://whatsapp.com/channel/0029Vb5btVqDeON7IdBgvF3n")

    def show_splash():
        root = tk.Tk()
        root.title("Instagram Reporter")
        root.geometry("400x300")

        # Colors for background cycle
        colors = ["#1E90FF", "#FF0000", "#800080", "#008000"]  # Blue, Red, Purple, Green
        color_index = [0]

        # Label for typewriter effect
        splash_label = tk.Label(
            root, 
            text="",
            font=("Courier", 24, "bold"),
            fg="#FFFFFF",
            bg=colors[color_index[0]]
        )
        splash_label.pack(expand=True)

        def update_background():
            color_index[0] = (color_index[0] + 1) % len(colors)
            root.configure(bg=colors[color_index[0]])
            splash_label.configure(bg=colors[color_index[0]])
            root.after(1000, update_background)  # Change every 1 second

        def typewriter_effect():
            full_text = "SHRIJAN TIWARI"
            current_text = [""]

            def type_forward(pos=0):
                if pos < len(full_text):
                    current_text[0] = full_text[:pos + 1]
                    splash_label.configure(text=current_text[0])
                    root.after(100, type_forward, pos + 1)
                else:
                    root.after(500, type_backward, len(full_text))

            def type_backward(pos):
                if pos > 0:
                    current_text[0] = full_text[:pos - 1]
                    splash_label.configure(text=current_text[0])
                    root.after(100, type_backward, pos - 1)

            type_forward()

        # Start animations
        root.configure(bg=colors[0])
        update_background()
        typewriter_effect()

        # Show reporting page after 4 seconds
        root.after(4000, lambda: [root.destroy(), show_reporting_page()])
        root.mainloop()

    def show_reporting_page():
        reporting_window = tk.Tk()
        reporting_window.title("Instagram Reporting Tool")
        reporting_window.geometry("400x400")
        reporting_window.configure(bg="#000000")

        # Reporting form
        tk.Label(
            reporting_window, 
            text="Instagram Mass Reporter",
            font=("Arial", 18, "bold"),
            fg="#FFFFFF",
            bg="#000000"
        ).pack(pady=20)

        tk.Label(
            reporting_window, 
            text="Target Username:",
            font=("Arial", 12),
            fg="#FFFFFF",
            bg="#000000"
        ).pack()
        username_entry = tk.Entry(reporting_window, width=30)
        username_entry.pack(pady=5)

        tk.Label(
            reporting_window, 
            text="Reports per Account:",
            font=("Arial", 12),
            fg="#FFFFFF",
            bg="#000000"
        ).pack()
        reports_entry = tk.Entry(reporting_window, width=30)
        reports_entry.pack(pady=5)

        def start_reporting():
            target_user = username_entry.get().strip()
            reports_str = reports_entry.get().strip()

            if not target_user:
                messagebox.showerror("Error", "Username cannot be empty.")
                return
            try:
                num_reports = int(reports_str)
                if num_reports < 1:
                    messagebox.showerror("Error", "Number of reports must be at least 1.")
                    return
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid number for reports.")
                return

            accounts = load_accounts()
            if not accounts:
                messagebox.showerror("Error", "No valid accounts loaded from accounts.json. Please check the file.")
                return

            reporting_window.destroy()  # Close reporting form
            show_progress_window(target_user, accounts, num_reports)

        tk.Button(
            reporting_window,
            text="Start Reporting",
            command=start_reporting,
            font=("Arial", 12),
            bg="#FF0000",
            fg="#FFFFFF",
            activebackground="#CC0000"
        ).pack(pady=20)

        reporting_window.mainloop()

    def show_progress_window(target_username, accounts, num_reports_per_account):
        progress_window = tk.Tk()
        progress_window.title("Reporting Progress")
        progress_window.geometry("500x400")
        progress_window.configure(bg="#000000")

        # Status label
        status_label = tk.Label(
            progress_window,
            text="Starting reports...",
            font=("Arial", 14, "bold"),
            fg="#FFFFFF",
            bg="#000000"
        ).pack(pady=10)

        # Progress bar
        total_reports = len(accounts) * num_reports_per_account
        progress_bar = Progressbar(
            progress_window,
            length=400,
            maximum=total_reports,
            style="red.Horizontal.TProgressbar"
        )
        progress_bar.pack(pady=10)

        # Text area for logs
        log_area = scrolledtext.ScrolledText(
            progress_window,
            width=60,
            height=15,
            font=("Courier", 10),
            fg="#FFFFFF",
            bg="#333333",
            state='disabled'
        )
        log_area.pack(pady=10)

        # Configure progress bar style
        progress_window.style = tk.ttk.Style()
        progress_window.style.configure("red.Horizontal.TProgressbar", background="#FF0000")

        # Set up logging to text area
        text_handler = TextAreaHandler(log_area)
        text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(text_handler)

        completed_reports = [0]
        def progress_callback(success):
            completed_reports[0] += 1
            progress_bar['value'] = completed_reports[0]
            progress_window.update()
            if completed_reports[0] >= total_reports:
                status_label.configure(text="Reporting completed!")
                progress_window.after(1000, lambda: [progress_window.destroy(), logging.getLogger().removeHandler(text_handler), show_splash()])

        # Start reporting in a separate thread
        threading.Thread(
            target=mass_report,
            args=(target_username, accounts, num_reports_per_account, 10, progress_callback),
            daemon=True
        ).start()

        progress_window.mainloop()

    show_splash()

# Fallback terminal input
def run_terminal():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')  # Clear terminal
        display_ascii_art()
        logging.info("WhatsApp channel redirect not available in terminal mode. Visit: https://whatsapp.com/channel/0029Vb5btVqDeON7IdBgvF3n")
        accounts = load_accounts()
        if not accounts:
            logging.error("No valid accounts loaded from accounts.json. Press Enter to retry.")
            input()
            continue

        target_user = None
        for _ in range(3):
            target_user = input("Enter the Instagram username to report: ").strip()
            if target_user:
                break
            logging.warning("Username cannot be empty. Try again.")
        if not target_user:
            logging.error("No valid username provided after 3 attempts. Press Enter to retry.")
            input()
            continue

        num_reports = None
        for _ in range(3):
            try:
                num_reports = int(input("Enter the number of reports per account: ").strip())
                if num_reports < 1:
                    logging.warning("Number of reports must be at least 1. Try again.")
                    continue
                break
            except ValueError:
                logging.warning("Invalid number of reports. Please enter a number. Try again.")
        if num_reports is None:
            logging.error("No valid number of reports provided after 3 attempts. Press Enter to retry.")
            input()
            continue

        mass_report(target_user, accounts, num_reports_per_account=num_reports, max_workers=10)
        logging.info("Reporting completed. Press Enter to start again or Ctrl+C to exit.")
        input()

# Main execution
if __name__ == "__main__":
    if tk:
        try:
            run_gui()
        except Exception as e:
            logging.error(f"GUI failed: {e}. Falling back to terminal.")
            run_terminal()
    else:
        logging.warning("tkinter not available. Using terminal interface.")
        run_terminal()
