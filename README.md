# Lịch Trường

A local timetable planner for Vietnamese lower secondary schools. Prepare teaching assignments, generate a timetable with Google OR-Tools CP-SAT, adjust lessons manually, and export schedules for classes, teachers, or the whole school.

The application interface is in Vietnamese. This guide keeps exact interface labels, import headers, and recognized subject names where needed.

## Contents

- [Requirements](#requirements)
- [Getting started](#getting-started)
- [Preparing teaching data](#preparing-teaching-data)
- [Scheduling rules](#scheduling-rules)
- [Generating and editing a timetable](#generating-and-editing-a-timetable)
- [Exporting schedules](#exporting-schedules)
- [Accounts, storage, and backups](#accounts-storage-and-backups)
- [Legacy data](#legacy-data)

## Requirements

| Component | Purpose |
| --- | --- |
| Python 3.10 or later with pip | Run the server, the CP-SAT scheduler, and the SQLite database |
| Node.js and npm | Run the development launcher and the frontend tests |

Ensure `node`, `npm`, and `python` (`python3` on Linux and macOS) are available on your `PATH`. No database server, JDK, or `npm install` step is required.

## Getting started

### 1. Install the scheduling dependency

Run once from the project root:

```powershell
python -m pip install --target build/vendor ortools
```

### 2. Moving from SQL Server (only for older installations)

Earlier versions stored data in SQL Server. To copy accounts and timetables into the new database, run once on the Windows machine that used SQL Server, with the old `.env` file still in the project root and the server stopped:

```powershell
python scripts/migrate_sqlserver.py
```

Passwords keep working; everyone signs in again afterwards. The script refuses to run if the new database already has accounts. After migrating, `.env` and `scripts/sql-query.ps1` are no longer used.

### 3. Start the application

```powershell
npm run dev
```

Open [http://localhost:3000](http://localhost:3000), register an account, and prepare your teaching data. Use **Dùng dữ liệu mẫu** (Load sample data) to explore the interface.

Press **Ctrl+C** in the terminal to stop the server.

## Preparing teaching data

### Classes, teachers, and assignments

Create classes individually or in batches by grade, main shift, and class count. Batch creation produces names such as `9/1`, `9/2`, and so on.

Add one assignment row for each teacher teaching a subject to a class. Each row specifies the class, subject, teacher, and weekly period count. The count must be an integer from **1 to 30**. A separate subject list per grade is not required.

Assignments for the same subject are considered together when applying scheduling rules. Subject matching normalizes case, accents, and spacing. These aliases are also grouped together:

| Subject | Recognized names |
| --- | --- |
| Literature | `Văn`, `Ngữ văn` |
| English | `Anh`, `Tiếng Anh` |

Teacher names must be unique. Matching ignores case and extra whitespace but preserves Vietnamese accents. Existing teachers are reused when importing assignments; duplicate entries in teacher imports are skipped and listed in the preview. If two people have the same name, distinguish them with a middle name or identifier.

Configure fixed activities in **Thiết lập tuần học** (School week setup).

### CSV and Excel imports

Classes, teachers, assignments, and fixed activities support UTF-8 CSV and `.xlsx` imports. Only the first worksheet of an Excel file is read.

1. Download the CSV template from the relevant section.
2. Fill it in and save it as UTF-8 CSV or `.xlsx`.
3. Upload the file and review the preview.
4. Correct any validation errors before confirming the import.

Format class-name columns as **Text** in Excel so names such as `9/1` are not converted into dates.

Create classes before importing assignments. Assignment imports use the following headers; headers from older templates are also accepted:

| Header | Meaning |
| --- | --- |
| `Giáo viên` | Teacher |
| `Lớp` | Class |
| `Môn` | Subject |
| `Tiết/Tuần` | Periods per week |

Teachers that do not exist yet are added when the import is confirmed. Within a group, a blank teacher cell inherits the preceding teacher name. A completely blank row ends the group, so the next group must start with an explicit teacher name. Check inherited names in the preview.

The teacher template only requires the teacher-name column. Configure individual session rules after importing.

### Opposite-shift subjects

Use **Thêm phân công trái buổi** (Add opposite-shift assignments) to add missing assignments for `Hoạt động trải nghiệm` (Experiential activities) and `Thể dục` (Physical education). Each subject receives two periods per class; select a teacher for every new row.

If either subject is assigned, every class must have both subjects. The scheduler places all four periods on the same day, in the shift opposite the class's main shift:

- One subject occupies periods **1–2**.
- The other occupies periods **3–4**.

Use the Vietnamese subject names above; recognition ignores case and accents. Lessons in the opposite shift can also be placed and locked manually.

## Scheduling rules

A **session** is one morning or afternoon of teaching. The school week runs from **Monday through Friday**, with five periods per shift.

### General constraints

- A class or teacher cannot have overlapping lessons.
- Fixed activities and locked lessons must be preserved.
- A class cannot have empty periods between lessons or activities within a session.
- A teacher may have at most one empty period between consecutive teaching periods in the same session. The break between morning and afternoon does not count.
- Teacher time-off settings must be respected.

### Teacher workloads

Teachers use **4–5 sessions per week** by default. Each teacher can instead be assigned exactly **1, 2, 3, 4, 5, or 6 sessions**. Opposite-shift teaching counts toward this total. Teachers without assignments are exempt.

Every occupied teaching session must contain at least **two periods**. Both this minimum and the required session count apply to automatically generated timetables and manual edits of a complete timetable. During partial placement, minimum requirements are checked when all periods have been placed.

### Subject distribution

| Subject or condition | Rule |
| --- | --- |
| Mathematics (`Toán`) | At most two periods per class per session, separated by at least one other period |
| English (`Anh` / `Tiếng Anh`) | At most one period per class per session |
| Literature (`Văn` / `Ngữ văn`) | Consecutive two-period pairs, with at most two periods per session |
| Other main-shift subjects | Consecutive periods of the same subject are not allowed |
| Subjects with fewer than three weekly periods | At least one intervening day between occurrences, subject to the exceptions below |
| Subjects with three or more weekly periods | No minimum separation between teaching days |

Mathematics and English are exempt from the intervening-day rule. Literature follows its pairing rule: four weekly periods occupy exactly two sessions, which may fall on consecutive days. An odd weekly literature total allows exactly one unpaired period. A single literature period may temporarily stand alone while a timetable is being edited.

For a teacher assigned exactly one session, two periods of a low-frequency subject may share that session. They must remain nonadjacent unless they are literature or one of the two opposite-shift subjects.

### Search preferences and limitations

The scheduler initially tries, for up to **eight seconds**, to place at most one mathematics period per class per session and pair experiential-activity classes taught by the same teacher. Two classes can share a teacher's session by using periods 1–2 and 3–4.

If this search does not find a timetable, the scheduler relaxes these preferences while keeping all mandatory constraints and locks.

After the first valid timetable is found, the scheduler spends up to **20 seconds** improving it. After the two preferences above, it favors fewer teaching sessions per teacher (teachers on the default 4–5 session rule are moved toward 4 sessions) and fewer empty periods between a teacher's lessons; one extra session weighs as much as five such gaps. It does **not** guarantee an optimal timetable. Stopping during this phase keeps the current timetable and discards the new result.

Results identify sessions with two mathematics periods and teachers whose experiential-activity classes remain unpaired. These counts are not guaranteed to be minimal. A timetable is reported as infeasible only when the solver proves that the constraints cannot all be satisfied.

## Generating and editing a timetable

Select **Tạo thời khóa biểu** (Generate timetable) to start the CP-SAT solver. Progress shows elapsed time; completion time cannot be predicted. Each generated timetable must pass an independent validator before it is displayed.

Select **Dừng xếp lịch** (Stop scheduling) to cancel the search and keep the current timetable. If generation fails, review assignment counts, teacher session rules, fixed activities, time off, and locked lessons.

For manual editing:

- **Place a lesson:** select a shift, then drag an unplaced lesson card into its class column and period, or select the card followed by a cell.
- **Move a lesson:** drag an unlocked lesson into an empty cell.
- **Remove a lesson:** use **×** to return it to the unplaced list.
- **Lock a lesson:** double-click an occupied cell or use its lock button. Locked lessons stay in place during regeneration; unlocked lessons may move.
- **Swap lessons:** in the class timetable view, select two cells to exchange their lessons.
- **Change a fixed activity:** edit it in the school week setup.

The latest **15 timetable versions** are stored with the account after generation or editing. A version can be restored only if its classes, teachers, assignments, and fixed activities still match the current input data.

## Exporting schedules

| Action | Output |
| --- | --- |
| **Xuất CSV đang xem** (Export current CSV) | The selected class or teacher timetable |
| **Xuất Excel toàn trường** (Export whole-school Excel) | An `.xlsx` workbook with one worksheet per grade, classes side by side, and separate morning and afternoon sections |
| **In / PDF** (Print / PDF) | The current view, using the browser's print or save-to-PDF option |

Classes without a recognized grade appear on a separate worksheet. Exports reflect the current timetable; unplaced lessons are not included.

## Accounts, storage, and backups

Register with a 3–40-character username without accents and a password of at least 10 characters. The first account created in a database receives a copy of any legacy application data. Later accounts have separate data.

A new login invalidates the account's previous session immediately on the server. The previous interface reports this on its next request or periodic session check. Password reset is not supported.

Data is stored in `data/lich-truong.db` (SQLite). Set the `LT_DB_FILE` environment variable to use a different file.

The status bar reports server connectivity and save results. If a connection fails, temporary data remains in the browser. Existing browser data is transferred to the database when no account data is stored there. If local unsynchronized data conflicts with database data, synchronization pauses to avoid overwriting either copy. Back up and resolve the conflicting data before continuing.

Back up regularly by copying `data/lich-truong.db` while the server is stopped, or at any time with `sqlite3 data/lich-truong.db ".backup backup.db"`.

The application currently listens only on localhost. Access from other devices requires a shared deployment with HTTPS and corresponding server and security configuration changes.

## Legacy data

When older six-day-week data is loaded:

- Saturday lessons return to the unplaced list.
- Saturday fixed activities are removed and must be assigned a new day if still needed.
- Timetable versions containing Saturday lessons remain available for reference but cannot be restored.
