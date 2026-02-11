import os
import importlib.util
from datetime import date

# ---------------- PATHS ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODULES_DIR = os.path.join(BASE_DIR, "modules")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
DEFAULTS_DIR = os.path.join(BASE_DIR, "defaults")

# ---------------- MODULE LOADER ----------------
def load_python_module(path):
    spec = importlib.util.spec_from_file_location("mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# ---------------- PLACEHOLDER REPLACER ----------------
def replace_placeholders(doc, data):
    placeholders = {f"{{{{{k}}}}}": v for k, v in data.items()}

    def process_paragraph(paragraph):
        runs = paragraph.runs
        if not runs:
            return

        # Build full text with run boundaries preserved
        run_texts = [run.text for run in runs]
        full_text = "".join(run_texts)

        replaced = full_text
        for ph, val in placeholders.items():
            replaced = replaced.replace(ph, val)

        if replaced == full_text:
            return  # nothing to do

        # Now re-distribute text BACK into existing runs
        idx = 0
        for run, original_text in zip(runs, run_texts):
            length = len(original_text)
            if length == 0:
                continue

            run.text = replaced[idx:idx + length]
            idx += length

        # If replacement text is longer, append safely
        if idx < len(replaced):
            runs[-1].text += replaced[idx:]

    # Normal paragraphs
    for p in doc.paragraphs:
        process_paragraph(p)

    # Tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    process_paragraph(p)



# ---------------- LOADERS ----------------
def load_states():
    return sorted(
        d for d in os.listdir(MODULES_DIR)
        if os.path.isdir(os.path.join(MODULES_DIR, d))
    )

def load_courts(state):
    base = os.path.join(MODULES_DIR, state)
    return sorted(
        d for d in os.listdir(base)
        if os.path.isdir(os.path.join(base, d))
    ) if os.path.isdir(base) else []

def load_cases(state, court):
    base = os.path.join(MODULES_DIR, state, court)
    return sorted(
        f[:-3] for f in os.listdir(base)
        if f.endswith(".py")
    ) if os.path.isdir(base) else []

# ---------------- BENCH / COURT ----------------
def load_benches(state, court):
    profile = load_court_profile(state, court)
    if profile and "benches" in profile:
        return [b.strip() for b in profile["benches"].split(",")]
    return []

def load_court_profile(state, court):
    fname = f"{state}_{court}.txt".replace(" ", "_")
    path = os.path.join(DEFAULTS_DIR, "courts", fname)
    if not os.path.exists(path):
        return None

    profile = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                profile[k.strip()] = v.strip()
    return profile

def get_court_name_for_bench(state, court, bench):
    fname = f"{state}_{court}_{bench}.txt".replace(" ", "_")
    path = os.path.join(DEFAULTS_DIR, "courts", fname)
    if not os.path.exists(path):
        return ""

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("court_name="):
                return line.split("=", 1)[1].strip()
    return ""
