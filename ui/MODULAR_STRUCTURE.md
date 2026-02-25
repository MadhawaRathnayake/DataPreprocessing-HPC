# Modular UI Structure Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        main_app.py                              │
│                   (Main Application)                            │
│                                                                 │
│  - Loads C libraries                                           │
│  - Creates notebook (tabbed interface)                         │
│  - Instantiates all tab modules                                │
│  - Manages shared application state                            │
│  - Coordinates tab communication                               │
└────────┬────────────────────────────────────────────────────────┘
         │
         │ Creates and manages ↓
         │
    ┌────┴────────────────────────────────────────┐
    │                                             │
    │         Tab Module Instances                │
    │                                             │
    ├──────────────────┬──────────────────────────┤
    │                  │                          │
    ▼                  ▼                          ▼
┌─────────┐      ┌──────────┐            ┌──────────────┐
│ Import  │      │  Serial  │     ...    │   Export     │
│   Tab   │      │ Analyzer │            │     Tab      │
│         │      │   Tab    │            │              │
└────┬────┘      └────┬─────┘            └──────┬───────┘
     │                │                          │
     │                │                          │
     └────────────────┴──────────────────────────┘
                      │
                      │ All inherit from
                      ▼
              ┌──────────────┐
              │   BaseTab    │
              │  (Abstract)  │
              │              │
              │ - frame      │
              │ - app_context│
              │ - build_ui() │
              └──────────────┘


File Organization:
═══════════════════

ui/
├── main_app.py              ← Entry point, coordinates everything
├── base_tab.py              ← Abstract base class
│
├── import_tab.py            ← Import functionality
├── serial_analyzer_tab.py   ← Serial analysis
├── openmp_analyzer_tab.py   ← OpenMP analysis
├── mpi_analyzer_tab.py      ← MPI analysis
└── export_tab.py            ← Export functionality


Data Flow:
══════════

┌────────────┐
│    User    │
└──────┬─────┘
       │ Interacts with
       ▼
┌─────────────────┐
│  Tab Module     │
│  (e.g., Import) │
└────┬────────────┘
     │ Updates shared data via
     ▼
┌──────────────────┐
│  App Context     │
│  (main_app.py)   │
│                  │
│  • csv_data      │ ← Shared across all tabs
│  • csv_lib       │
│  • current_file  │
└────┬─────────────┘
     │ Accessible to
     ▼
┌────────────────────┐
│   Other Tabs       │
│   (Serial, OpenMP, │
│    MPI, Export)    │
└────────────────────┘


Communication Pattern:
══════════════════════

Tab A ──→ self.app.csv_data = data ──→ App Context
                                           │
                                           │ Available to
                                           ▼
Tab B ──→ data = self.app.csv_data ──→ App Context


Tab Lifecycle:
═══════════════

1. __init__(parent, app_context)
   │
   ├─→ super().__init__()     # Call base class
   │
   └─→ self.build_ui()        # Build UI elements

2. User switches to tab
   │
   └─→ on_tab_selected()      # Optional hook

3. User switches away
   │
   └─→ on_tab_deselected()    # Optional hook


Benefits of Modular Structure:
═══════════════════════════════

┌──────────────────────┐
│  Maintainability     │  Each tab in separate file
│  ✓ Easy to debug     │  Smaller, focused modules
│  ✓ Clear structure   │  
└──────────────────────┘

┌──────────────────────┐
│  Extensibility       │  Add new tabs easily
│  ✓ Plugin-ready      │  Modify tabs independently
│  ✓ Reusable          │
└──────────────────────┘

┌──────────────────────┐
│  Testability         │  Test tabs in isolation
│  ✓ Unit testable     │  Mock app context
│  ✓ Independent       │
└──────────────────────┘

┌──────────────────────┐
│  Collaboration       │  Multiple devs per tab
│  ✓ Less conflicts    │  Clear ownership
│  ✓ Parallel work     │
└──────────────────────┘
```

## Quick Reference

### Adding a New Tab

1. Create `ui/my_new_tab.py`:
```python
from base_tab import BaseTab

class MyNewTab(BaseTab):
    def build_ui(self):
        # Your UI code here
        pass
```

2. Import in `main_app.py`:
```python
from my_new_tab import MyNewTab
```

3. Add to notebook:
```python
self.tabs['mynew'] = MyNewTab(self.notebook, self)
self.notebook.add(self.tabs['mynew'].get_frame(), text="My New Tab")
```

### Accessing Shared Data

```python
# In any tab:
data = self.app.csv_data          # Get data
self.app.current_file = "file"    # Set data
self.app.set_status("Ready")      # Update status
```

### Using C Libraries

```python
# In any tab:
if self.app.csv_lib:
    result = self.app.csv_lib.some_function()
```
