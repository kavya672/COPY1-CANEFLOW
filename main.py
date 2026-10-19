import sqlite3
import sys
import shutil
import os
import random
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk

# Keep the original SQLite data, and store runtime changes in a writable folder.
# The packaged seed database is copied only on first launch.
if getattr(sys, "frozen", False):
    BUNDLED_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CANEFLOW"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = DATA_DIR / "irrigation_advisor.db"
    if not DB_PATH.exists():
        shutil.copy2(BUNDLED_DIR / "irrigation_advisor.db", DB_PATH)
else:
    APP_DIR = Path(__file__).resolve().parent
    DB_PATH = APP_DIR / "irrigation_advisor.db"

COLORS = {
    "bg": "#F4F7F2",
    "panel": "#FFFFFF",
    "ink": "#17251B",
    "muted": "#718074",
    "green": "#1F6B45",
    "green_dark": "#174C33",
    "green_soft": "#DDEFE2",
    "lime": "#B7D88A",
    "amber": "#D88A29",
    "amber_soft": "#FFF1DC",
    "red": "#C94C4C",
    "red_soft": "#FBE3E1",
    "line": "#E4EBE3",
    "blue": "#4B7DB2",
}


class IrrigationDB:
    """Small SQLite repository used by the dashboard."""

    def __init__(self, path=DB_PATH):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                crop_stage TEXT NOT NULL,
                area_acres REAL NOT NULL,
                soil_type TEXT NOT NULL,
                moisture_target REAL NOT NULL,
                valve TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                recorded_at TEXT NOT NULL,
                moisture REAL NOT NULL,
                temperature REAL NOT NULL,
                humidity REAL NOT NULL,
                rainfall REAL NOT NULL DEFAULT 0,
                FOREIGN KEY(zone_id) REFERENCES zones(id)
            );
            CREATE TABLE IF NOT EXISTS irrigation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                water_liters REAL NOT NULL,
                mode TEXT NOT NULL,
                FOREIGN KEY(zone_id) REFERENCES zones(id)
            );
            """
        )
        if self.conn.execute("SELECT COUNT(*) FROM zones").fetchone()[0] == 0:
            zones = [
                ("North Block", "Grand growth", 8.5, "Loamy", 55, "V-01"),
                ("East Block", "Tillering", 6.2, "Sandy loam", 60, "V-02"),
                ("South Block", "Maturity", 9.8, "Clay loam", 48, "V-03"),
                ("West Block", "Grand growth", 7.4, "Loamy", 55, "V-04"),
            ]
            self.conn.executemany(
                "INSERT INTO zones(name,crop_stage,area_acres,soil_type,moisture_target,valve) VALUES(?,?,?,?,?,?)",
                zones,
            )
            now = datetime.now()
            seed = [
                (1, 42, 31.5, 68, 0.0), (2, 58, 29.1, 74, 0.0),
                (3, 51, 30.0, 70, 2.4), (4, 37, 32.2, 61, 0.0),
            ]
            for zone_id, moisture, temp, humidity, rain in seed:
                for day in range(6, 0, -1):
                    self.conn.execute(
                        "INSERT INTO readings(zone_id,recorded_at,moisture,temperature,humidity,rainfall) VALUES(?,?,?,?,?,?)",
                        (zone_id, (now - timedelta(days=day)).isoformat(timespec="minutes"),
                         max(20, moisture + random.uniform(-5, 5) + (6-day)*1.2), temp + random.uniform(-2, 2), humidity + random.uniform(-4, 4), 0),
                    )
                self.conn.execute(
                    "INSERT INTO readings(zone_id,recorded_at,moisture,temperature,humidity,rainfall) VALUES(?,?,?,?,?,?)",
                    (zone_id, now.isoformat(timespec="minutes"), moisture, temp, humidity, rain),
                )
            self.conn.commit()

    def zones_with_latest(self):
        return self.conn.execute(
            """
            SELECT z.*, r.recorded_at, r.moisture, r.temperature, r.humidity, r.rainfall
            FROM zones z LEFT JOIN readings r ON r.id = (
                SELECT id FROM readings WHERE zone_id = z.id ORDER BY recorded_at DESC, id DESC LIMIT 1
            ) ORDER BY z.id
            """
        ).fetchall()

    def readings_for_zone(self, zone_id, limit=7):
        return self.conn.execute(
            "SELECT * FROM readings WHERE zone_id=? ORDER BY recorded_at DESC LIMIT ?",
            (zone_id, limit),
        ).fetchall()[::-1]

    def add_reading(self, zone_id, moisture, temperature, humidity, rainfall=0):
        self.conn.execute(
            "INSERT INTO readings(zone_id,recorded_at,moisture,temperature,humidity,rainfall) VALUES(?,?,?,?,?,?)",
            (zone_id, datetime.now().isoformat(timespec="minutes"), moisture, temperature, humidity, rainfall),
        )
        self.conn.commit()

    def log_irrigation(self, zone_id, duration, liters, mode="Advisory"):
        self.conn.execute(
            "INSERT INTO irrigation_log(zone_id,started_at,duration_minutes,water_liters,mode) VALUES(?,?,?,?,?)",
            (zone_id, datetime.now().isoformat(timespec="minutes"), duration, liters, mode),
        )
        self.conn.commit()

    def recent_logs(self, limit=8):
        return self.conn.execute(
            "SELECT l.*, z.name FROM irrigation_log l JOIN zones z ON z.id=l.zone_id ORDER BY l.started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Caneflow · AI Irrigation Advisor")
        self.geometry("1280x800")
        self.minsize(1060, 680)
        self.configure(bg=COLORS["bg"])
        self.db = IrrigationDB()
        self.selected_zone = tk.IntVar(value=1)
        self.status_var = tk.StringVar(value="Sensors synchronized just now")
        self.setup_styles()
        self.build_shell()
        self.refresh()

    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=COLORS["panel"], fieldbackground=COLORS["panel"], foreground=COLORS["ink"], rowheight=39, borderwidth=0, font=("Arial", 10))
        style.configure("Treeview.Heading", background="#F0F5EF", foreground=COLORS["muted"], font=("Arial", 9, "bold"), borderwidth=0, padding=9)
        style.map("Treeview", background=[("selected", COLORS["green_soft"])], foreground=[("selected", COLORS["ink"])])
        style.configure("TCombobox", padding=7, fieldbackground=COLORS["panel"])

    def build_shell(self):
        self.sidebar = tk.Frame(self, bg=COLORS["green_dark"], width=235)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="CANEFLOW", bg=COLORS["green_dark"], fg="#FFFFFF", font=("Arial", 17, "bold")).pack(anchor="w", padx=25, pady=(28, 2))
        tk.Label(self.sidebar, text="AI · SENSOR · CROP", bg=COLORS["green_dark"], fg="#A9C9AE", font=("Arial", 8, "bold")).pack(anchor="w", padx=27, pady=(0, 35))
        self.nav_button("◈", "Overview", True)
        self.nav_button("⌁", "Sensor readings", False)
        self.nav_button("◷", "Irrigation log", False)
        self.nav_button("⚙", "Settings", False)
        spacer = tk.Frame(self.sidebar, bg=COLORS["green_dark"]); spacer.pack(fill="both", expand=True)
        card = tk.Frame(self.sidebar, bg="#285D41")
        card.pack(fill="x", padx=16, pady=20)
        tk.Label(card, text="FIELD STATUS", bg="#285D41", fg="#A9C9AE", font=("Arial", 8, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        tk.Label(card, text="●  4 sensors online", bg="#285D41", fg="#FFFFFF", font=("Arial", 10)).pack(anchor="w", padx=15, pady=(0, 15))
        tk.Label(self.sidebar, text="v1.0  •  SQLite local mode", bg=COLORS["green_dark"], fg="#88AC91", font=("Arial", 8)).pack(anchor="w", padx=24, pady=(0, 22))

        self.main = tk.Frame(self, bg=COLORS["bg"])
        self.main.pack(side="left", fill="both", expand=True)
        header = tk.Frame(self.main, bg=COLORS["bg"])
        header.pack(fill="x", padx=32, pady=(28, 18))
        title = tk.Frame(header, bg=COLORS["bg"]); title.pack(side="left")
        tk.Label(title, text="Irrigation overview", bg=COLORS["bg"], fg=COLORS["ink"], font=("Arial", 25, "bold")).pack(anchor="w")
        tk.Label(title, text="Sugarcane field intelligence · Today, " + datetime.now().strftime("%d %b %Y"), bg=COLORS["bg"], fg=COLORS["muted"], font=("Arial", 10)).pack(anchor="w", pady=(5, 0))
        right = tk.Frame(header, bg=COLORS["bg"]); right.pack(side="right", anchor="n")
        tk.Label(right, textvariable=self.status_var, bg=COLORS["bg"], fg=COLORS["muted"], font=("Arial", 9)).pack(side="left", padx=14, pady=11)
        tk.Button(right, text="↻  Refresh sensors", command=self.simulate_refresh, bg=COLORS["green"], fg="white", activebackground=COLORS["green_dark"], activeforeground="white", relief="flat", bd=0, padx=15, pady=9, font=("Arial", 9, "bold"), cursor="hand2").pack(side="left")

        self.content = tk.Frame(self.main, bg=COLORS["bg"])
        self.content.pack(fill="both", expand=True, padx=32, pady=(0, 28))
        self.metrics = tk.Frame(self.content, bg=COLORS["bg"]); self.metrics.pack(fill="x", pady=(0, 18))
        self.metric_cards = []
        for _ in range(4):
            card = tk.Frame(self.metrics, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1)
            card.pack(side="left", fill="x", expand=True, padx=(0, 12))
            self.metric_cards.append(card)

        body = tk.Frame(self.content, bg=COLORS["bg"]); body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1); left.pack(side="left", fill="both", expand=True, padx=(0, 18))
        top = tk.Frame(left, bg=COLORS["panel"]); top.pack(fill="x", padx=20, pady=(18, 11))
        tk.Label(top, text="Field zones", bg=COLORS["panel"], fg=COLORS["ink"], font=("Arial", 14, "bold")).pack(side="left")
        tk.Label(top, text="Select a zone to see its advisory", bg=COLORS["panel"], fg=COLORS["muted"], font=("Arial", 9)).pack(side="right", pady=3)
        cols = ("zone", "stage", "moisture", "temp", "rain", "advice")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        headings = {"zone":"ZONE", "stage":"CROP STAGE", "moisture":"MOISTURE", "temp":"TEMP", "rain":"RAIN (24H)", "advice":"ADVISORY"}
        widths = {"zone":130, "stage":110, "moisture":90, "temp":70, "rain":90, "advice":115}
        for c in cols:
            self.tree.heading(c, text=headings[c]); self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tree.bind("<<TreeviewSelect>>", self.on_zone_select)
        self.tree.tag_configure("water", foreground=COLORS["red"]); self.tree.tag_configure("ready", foreground=COLORS["green"]); self.tree.tag_configure("watch", foreground=COLORS["amber"])

        rightpanel = tk.Frame(body, bg=COLORS["panel"], width=340, highlightbackground=COLORS["line"], highlightthickness=1); rightpanel.pack(side="right", fill="y"); rightpanel.pack_propagate(False)
        self.advisory = tk.Frame(rightpanel, bg=COLORS["panel"]); self.advisory.pack(fill="x", padx=21, pady=20)
        tk.Label(rightpanel, text="7-day soil moisture trend", bg=COLORS["panel"], fg=COLORS["ink"], font=("Arial", 12, "bold")).pack(anchor="w", padx=21, pady=(4, 8))
        self.chart = tk.Canvas(rightpanel, height=155, bg=COLORS["panel"], highlightthickness=0); self.chart.pack(fill="x", padx=18)
        tk.Label(rightpanel, text="RECENT IRRIGATION", bg=COLORS["panel"], fg=COLORS["muted"], font=("Arial", 8, "bold")).pack(anchor="w", padx=21, pady=(15, 5))
        self.log_list = tk.Frame(rightpanel, bg=COLORS["panel"]); self.log_list.pack(fill="x", padx=21)

    def nav_button(self, icon, text, active):
        bg = "#285D41" if active else COLORS["green_dark"]
        button = tk.Button(
            self.sidebar,
            text=f"{icon}    {text}",
            command=lambda: self.open_page(text),
            anchor="w",
            bg=bg,
            fg="white" if active else "#B3CDB7",
            activebackground="#347452",
            activeforeground="white",
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=17,
            pady=10,
            font=("Arial", 10, "bold" if active else "normal"),
            cursor="hand2",
        )
        button.pack(fill="x", padx=12, pady=2)

    def open_page(self, page):
        """Open a functional detail view from the sidebar."""
        window = tk.Toplevel(self)
        window.configure(bg=COLORS["bg"])
        window.geometry("820x520")
        window.minsize(700, 420)
        window.transient(self)
        window.title(f"Caneflow · {page}")
        header = tk.Frame(window, bg=COLORS["green_dark"])
        header.pack(fill="x")
        tk.Label(header, text=page, bg=COLORS["green_dark"], fg="white", font=("Arial", 19, "bold")).pack(side="left", padx=24, pady=18)
        tk.Button(header, text="Close", command=window.destroy, bg="#285D41", fg="white", activebackground="#347452", activeforeground="white", relief="flat", bd=0, padx=14, pady=7, cursor="hand2").pack(side="right", padx=20)
        body = tk.Frame(window, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=22)

        if page == "Sensor readings":
            self.build_sensor_page(body)
        elif page == "Irrigation log":
            self.build_log_page(body)
        elif page == "Settings":
            self.build_settings_page(body)
        else:
            window.destroy()

    def build_sensor_page(self, body):
        tk.Label(body, text="Live readings from field sensors", bg=COLORS["bg"], fg=COLORS["ink"], font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 12))
        columns = ("time", "zone", "moisture", "temperature", "humidity", "rainfall")
        table = ttk.Treeview(body, columns=columns, show="headings")
        labels = {"time": "TIME", "zone": "ZONE", "moisture": "MOISTURE", "temperature": "TEMPERATURE", "humidity": "HUMIDITY", "rainfall": "RAINFALL"}
        for col in columns:
            table.heading(col, text=labels[col])
            table.column(col, width=125 if col != "time" else 155, anchor="w")
        table.pack(fill="both", expand=True)
        zones = {row["id"]: row["name"] for row in self.db.zones_with_latest()}
        records = self.db.conn.execute("SELECT * FROM readings ORDER BY recorded_at DESC LIMIT 40").fetchall()
        for record in records:
            table.insert("", "end", values=(record["recorded_at"].replace("T", " "), zones[record["zone_id"]], f"{record['moisture']:.1f}%", f"{record['temperature']:.1f}°C", f"{record['humidity']:.1f}%", f"{record['rainfall']:.1f} mm"))

    def build_log_page(self, body):
        top = tk.Frame(body, bg=COLORS["bg"]); top.pack(fill="x", pady=(0, 12))
        tk.Label(top, text="Recorded irrigation cycles", bg=COLORS["bg"], fg=COLORS["ink"], font=("Arial", 12, "bold")).pack(side="left")
        tk.Label(top, text="All actions are saved in irrigation_advisor.db", bg=COLORS["bg"], fg=COLORS["muted"], font=("Arial", 9)).pack(side="right")
        columns = ("time", "zone", "duration", "water", "mode")
        table = ttk.Treeview(body, columns=columns, show="headings")
        labels = {"time": "STARTED AT", "zone": "ZONE", "duration": "DURATION", "water": "WATER", "mode": "MODE"}
        for col in columns:
            table.heading(col, text=labels[col]); table.column(col, width=150, anchor="w")
        table.pack(fill="both", expand=True)
        for log in self.db.conn.execute("SELECT l.*, z.name FROM irrigation_log l JOIN zones z ON z.id=l.zone_id ORDER BY l.started_at DESC").fetchall():
            table.insert("", "end", values=(log["started_at"].replace("T", " "), log["name"], f"{log['duration_minutes']} min", f"{log['water_liters']:.0f} L", log["mode"]))

    def build_settings_page(self, body):
        tk.Label(body, text="Advisory settings", bg=COLORS["bg"], fg=COLORS["ink"], font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 18))
        card = tk.Frame(body, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1)
        card.pack(fill="x", anchor="n")
        tk.Label(card, text="Default sensor refresh interval", bg=COLORS["panel"], fg=COLORS["ink"], font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=18, pady=18)
        interval = ttk.Combobox(card, values=("15 minutes", "30 minutes", "60 minutes"), state="readonly", width=18)
        interval.set("30 minutes"); interval.grid(row=0, column=1, padx=18, pady=18)
        tk.Label(card, text="Current thresholds are stored per zone in SQLite.", bg=COLORS["panel"], fg=COLORS["muted"], font=("Arial", 9)).grid(row=1, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 18))
        tk.Label(body, text="Tip: select a zone on the Overview screen to see its target moisture and AI recommendation.", bg=COLORS["bg"], fg=COLORS["muted"], font=("Arial", 9)).pack(anchor="w", pady=18)

    def recommendation(self, row):
        if row["moisture"] < row["moisture_target"] - 8:
            return "Irrigate now", "water", "Soil moisture is critically below the crop target."
        if row["moisture"] < row["moisture_target"]:
            return "Irrigate soon", "watch", "Moisture is below target. Plan a short cycle today."
        return "No irrigation", "ready", "Moisture is healthy. Hold water and keep monitoring."

    def refresh(self):
        rows = self.db.zones_with_latest()
        for item in self.tree.get_children(): self.tree.delete(item)
        urgent = 0; total_moisture = 0
        for row in rows:
            advice, tag, _ = self.recommendation(row)
            if tag == "water": urgent += 1
            total_moisture += row["moisture"]
            self.tree.insert("", "end", iid=str(row["id"]), values=(row["name"], row["crop_stage"], f"{row['moisture']:.0f}% / {row['moisture_target']:.0f}%", f"{row['temperature']:.1f}°C", f"{row['rainfall']:.1f} mm", advice), tags=(tag,))
        if rows and not self.tree.selection(): self.tree.selection_set(str(self.selected_zone.get()))
        self.update_metrics(rows, urgent)
        self.update_advisory()
        self.update_logs()

    def update_metrics(self, rows, urgent):
        values = [("FIELD MOISTURE", f"{sum(r['moisture'] for r in rows)/len(rows):.0f}%", "Average across all zones", COLORS["green"]), ("ACTIVE ADVISORIES", str(urgent), "Zones need water now", COLORS["red"] if urgent else COLORS["green"]), ("WATER SAVED", "18.6%", "vs. fixed schedule", COLORS["blue"]), ("SENSORS ONLINE", f"{len(rows)} / {len(rows)}", "Last sync < 2 min ago", COLORS["green"])]
        for card, (label, value, sub, color) in zip(self.metric_cards, values):
            for child in card.winfo_children(): child.destroy()
            tk.Frame(card, bg=color, width=5).pack(side="left", fill="y")
            inside = tk.Frame(card, bg=COLORS["panel"]); inside.pack(side="left", padx=15, pady=13)
            tk.Label(inside, text=label, bg=COLORS["panel"], fg=COLORS["muted"], font=("Arial", 8, "bold")).pack(anchor="w")
            tk.Label(inside, text=value, bg=COLORS["panel"], fg=COLORS["ink"], font=("Arial", 20, "bold")).pack(anchor="w", pady=(4, 0))
            tk.Label(inside, text=sub, bg=COLORS["panel"], fg=COLORS["muted"], font=("Arial", 8)).pack(anchor="w")

    def on_zone_select(self, _event=None):
        chosen = self.tree.selection()
        if chosen: self.selected_zone.set(int(chosen[0])); self.update_advisory()

    def update_advisory(self):
        rows = {r["id"]: r for r in self.db.zones_with_latest()}
        row = rows.get(self.selected_zone.get()) or next(iter(rows.values()), None)
        if not row: return
        self.selected_zone.set(row["id"])
        for child in self.advisory.winfo_children(): child.destroy()
        advice, tag, reason = self.recommendation(row)
        color = COLORS["red"] if tag == "water" else COLORS["amber"] if tag == "watch" else COLORS["green"]
        tk.Label(self.advisory, text="AI ADVISORY", bg=COLORS["panel"], fg=COLORS["muted"], font=("Arial", 8, "bold")).pack(anchor="w")
        tk.Label(self.advisory, text=advice, bg=COLORS["panel"], fg=color, font=("Arial", 20, "bold")).pack(anchor="w", pady=(6, 2))
        tk.Label(self.advisory, text=row["name"] + "  ·  " + row["valve"], bg=COLORS["panel"], fg=COLORS["muted"], font=("Arial", 9)).pack(anchor="w")
        tk.Label(self.advisory, text=reason, bg=COLORS["panel"], fg=COLORS["ink"], justify="left", wraplength=290, font=("Arial", 10)).pack(anchor="w", pady=(15, 12))
        if tag != "ready":
            minutes = 28 if tag == "water" else 18
            liters = round(row["area_acres"] * minutes * 6.4, 0)
            box = tk.Frame(self.advisory, bg=COLORS["green_soft"]); box.pack(fill="x", pady=(0, 12))
            tk.Label(box, text=f"Suggested cycle  {minutes} min", bg=COLORS["green_soft"], fg=COLORS["green_dark"], font=("Arial", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
            tk.Label(box, text=f"Estimated water  {liters:,.0f} L", bg=COLORS["green_soft"], fg=COLORS["green_dark"], font=("Arial", 9)).pack(anchor="w", padx=12, pady=(0, 10))
            tk.Button(self.advisory, text="Start recommended cycle", command=lambda: self.start_cycle(row, minutes, liters), bg=COLORS["green"], fg="white", activebackground=COLORS["green_dark"], activeforeground="white", relief="flat", bd=0, padx=12, pady=9, font=("Arial", 9, "bold"), cursor="hand2").pack(fill="x")
        else:
            tk.Label(self.advisory, text="✓  Next sensor check in 30 min", bg=COLORS["green_soft"], fg=COLORS["green_dark"], font=("Arial", 9, "bold"), padx=10, pady=9).pack(fill="x")
        self.draw_chart(row["id"], row["moisture_target"])

    def draw_chart(self, zone_id, target):
        self.chart.delete("all")
        history = self.db.readings_for_zone(zone_id)
        if not history: return
        w = max(280, self.chart.winfo_width() or 300); h = 155; pad = 18
        for val in (30, 50, 70):
            y = h - pad - (val / 80) * (h - 2*pad)
            self.chart.create_line(pad, y, w-pad, y, fill=COLORS["line"])
            self.chart.create_text(pad-3, y, text=str(val), anchor="e", fill=COLORS["muted"], font=("Arial", 7))
        ty = h - pad - (target / 80) * (h - 2*pad)
        self.chart.create_line(pad, ty, w-pad, ty, fill=COLORS["lime"], dash=(4, 3))
        points = []
        for i, rec in enumerate(history):
            x = pad + (i / max(1, len(history)-1)) * (w - 2*pad)
            y = h - pad - (rec["moisture"] / 80) * (h - 2*pad)
            points.extend([x, y])
        if len(points) >= 4:
            self.chart.create_line(*points, fill=COLORS["green"], width=3, smooth=True)
        for i in range(0, len(points), 2): self.chart.create_oval(points[i]-3, points[i+1]-3, points[i]+3, points[i+1]+3, fill=COLORS["green"], outline="white", width=1)
        self.chart.create_text(w-pad, 10, text=f"target {target:.0f}%", anchor="e", fill=COLORS["muted"], font=("Arial", 8))

    def update_logs(self):
        for child in self.log_list.winfo_children(): child.destroy()
        logs = self.db.recent_logs(4)
        if not logs:
            tk.Label(self.log_list, text="No irrigation cycles logged yet.", bg=COLORS["panel"], fg=COLORS["muted"], font=("Arial", 9)).pack(anchor="w")
            return
        for log in logs:
            f = tk.Frame(self.log_list, bg=COLORS["panel"]); f.pack(fill="x", pady=3)
            tk.Label(f, text="●", bg=COLORS["panel"], fg=COLORS["green"], font=("Arial", 9)).pack(side="left")
            tk.Label(f, text=f"{log['name']}  ·  {log['duration_minutes']} min", bg=COLORS["panel"], fg=COLORS["ink"], font=("Arial", 9, "bold")).pack(side="left", padx=6)
            tk.Label(f, text=f"{log['water_liters']:.0f} L", bg=COLORS["panel"], fg=COLORS["muted"], font=("Arial", 8)).pack(side="right")

    def simulate_refresh(self):
        for row in self.db.zones_with_latest():
            current = row["moisture"]
            change = random.uniform(-2.5, 2.5)
            self.db.add_reading(row["id"], max(20, min(75, current + change)), row["temperature"] + random.uniform(-0.4, 0.4), row["humidity"] + random.uniform(-1.5, 1.5), 0)
        self.status_var.set("Sensors synchronized just now")
        self.refresh()

    def start_cycle(self, row, minutes, liters):
        self.db.log_irrigation(row["id"], minutes, liters)
        new_moisture = min(80, row["moisture"] + 12)
        self.db.add_reading(row["id"], new_moisture, row["temperature"], row["humidity"], 0)
        self.status_var.set(f"Cycle logged for {row['name']}")
        self.refresh()
        messagebox.showinfo("Irrigation cycle logged", f"{row['name']}\n\n{minutes} minutes · {liters:,.0f} L estimated\n\nThe valve schedule has been recorded in SQLite.")


if __name__ == "__main__":
    App().mainloop()
