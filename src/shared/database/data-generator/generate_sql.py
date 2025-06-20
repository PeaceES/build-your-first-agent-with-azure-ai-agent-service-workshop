import sqlite3
from pathlib import Path

# Output file
db_path = Path(__file__).resolve().parents[2] / "database" / "tutorials.db"
db_path.parent.mkdir(parents=True, exist_ok=True)

# Connect to SQLite
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Drop tables if they already exist (for reruns)
tables = ["tutorials", "students", "tutors", "rooms", "timeslots"]
for table in tables:
    cur.execute(f"DROP TABLE IF EXISTS {table};")

# Create schema
cur.execute("""
CREATE TABLE tutors (
    tutor_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL
);
""")

cur.execute("""
CREATE TABLE students (
    student_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    module_code TEXT NOT NULL
);
""")

cur.execute("""
CREATE TABLE rooms (
    room_id INTEGER PRIMARY KEY,
    building_name TEXT NOT NULL,
    room_number TEXT NOT NULL,
    capacity INTEGER NOT NULL
);
""")

cur.execute("""
CREATE TABLE timeslots (
    timeslot_id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    time_start TEXT NOT NULL,
    time_end TEXT NOT NULL
);
""")

cur.execute("""
CREATE TABLE tutorials (
    tutorial_id INTEGER PRIMARY KEY,
    module_code TEXT NOT NULL,
    tutor_id INTEGER NOT NULL,
    room_id INTEGER NOT NULL,
    timeslot_id INTEGER NOT NULL,
    FOREIGN KEY (tutor_id) REFERENCES tutors(tutor_id),
    FOREIGN KEY (room_id) REFERENCES rooms(room_id),
    FOREIGN KEY (timeslot_id) REFERENCES timeslots(timeslot_id)
);
""")

# Insert data
cur.executemany("INSERT INTO tutors (name, department) VALUES (?, ?);", [
    ("Dr. Patel", "Computer Science"),
    ("Dr. Lopez", "Mathematics"),
    ("Dr. Zhang", "Engineering"),
])

cur.executemany("INSERT INTO students (name, module_code) VALUES (?, ?);", [
    ("Alice Smith", "COMP001"),
    ("Bob Johnson", "MATH101"),
    ("Carol White", "ENGR204"),
])

cur.executemany("INSERT INTO rooms (building_name, room_number, capacity) VALUES (?, ?, ?);", [
    ("Roberts Building", "G12", 30),
    ("Engineering Hub", "203", 25),
    ("Mathematics Block", "101", 20),
])

cur.executemany("INSERT INTO timeslots (day, time_start, time_end) VALUES (?, ?, ?);", [
    ("Monday", "10:00", "11:00"),
    ("Wednesday", "13:00", "14:00"),
    ("Friday", "15:00", "16:00"),
])

cur.executemany("INSERT INTO tutorials (module_code, tutor_id, room_id, timeslot_id) VALUES (?, ?, ?, ?);", [
    ("COMP001", 1, 1, 1),
    ("MATH101", 2, 3, 2),
    ("ENGR204", 3, 2, 3),
])

# Save and close
conn.commit()
conn.close()

print(f"✅ Created database at: {db_path}")

