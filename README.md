# CANEFLOW – AI Irrigation Advisor

Python Tkinter + SQLite desktop dashboard for simulated sugarcane irrigation management.

## Download the Windows application
Open the **Actions** tab, select the latest successful **Build CANEFLOW Windows App** run, and download the **CANEFLOW-Windows** artifact. Unzip it to obtain `CANEFLOW.exe`. GitHub login may be required to download workflow artifacts.

## Run from source
With Python and Tkinter installed: `python main.py`

## Important notes
The app uses simulated sensor readings and rule-based recommendations, not a trained ML model or real irrigation hardware. On first launch, the Windows executable copies the bundled seed SQLite database to `%LOCALAPPDATA%\CANEFLOW\irrigation_advisor.db` for persistent local changes. Each computer has its own local database copy.

The executable is unsigned; follow your organization's software policies.
