# RUNNING.md

## How to Run Transport Scripts

### 1. From the Command Line (Recommended)

- Always run scripts from the **repo root** (the top-level folder containing `transport/`, `residential/`, etc.).
- Use the canonical import style: all scripts in `transport/` use `from transport...` imports.
- Example:

```bash
python -m transport.build_config_transport
```

- This ensures all imports and paths resolve correctly.

### 2. Using the VS Code Interactive Window or Jupyter Notebooks

- **Problem:** `__file__` is not defined in interactive sessions, and the working directory may not be the repo root.
- **Solution:**
  - All scripts use a fallback to `Path.cwd()` if `__file__` is not defined.
  - **Before running code interactively:**
    1. **Set your working directory to the repo root**:
       - In a notebook cell, run:
         ```python
         import os
         os.chdir(r'C:/Users/eduque/Documents/models/sectoral-energy-demands')
         ```
    2. **(Optional) Add repo root to `sys.path`** (if you want to import modules):
         ```python
         import sys
         sys.path.insert(0, r'C:/Users/eduque/Documents/models/sectoral-energy-demands')
         ```
    3. **Now you can import and run any transport module:**
         ```python
         from transport import build_config_transport
         # Use functions/classes as needed
         ```

- **Tip:** If you copy-paste code from a script, make sure any `if __name__ == "__main__":` block is run manually.

### 3. General Best Practices

- Always use **absolute imports** (e.g., `from transport.helpers import ...`), never relative imports.
- Avoid running scripts directly from inside the `transport/` folder; always run from the repo root.
- If you get `ModuleNotFoundError`, check your working directory and `sys.path`.

---

**Summary Table**

| Use Case         | Where to Run         | How to Run/Import                                    |
|------------------|---------------------|------------------------------------------------------|
| CLI script       | Repo root           | `python -m transport.build_config_transport`         |
| Interactive Win  | Any (set cwd first) | `os.chdir(...)`, `sys.path.insert(...)`, then import |
| Notebook         | Any (set cwd first) | Same as above                                       |

---

For more help, see the comments in each script or ask your friendly Copilot!