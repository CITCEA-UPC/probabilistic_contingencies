import json
import os
import sys
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from collections import defaultdict

# ==========================================
# 1. CONFIGURATION & RELIABILITY DATA
# ==========================================

# Default failure rates (lambda) per element type [failures/year]
DEFAULT_RELIABILITY = {
    'line': {'lambda': 1/20},  # MTTF = 20 years
    'transformer': {'lambda': 1/50},  # MTTF = 50 years
    'generator': {'lambda': 1/10}  # MTTF = 10 years
}

# (Optional) Specific exceptions for individual components
# Format: 'type': { 'id': {'lambda': value} }
SPECIAL_RELIABILITY = {
    # Example:
    # 'line': { '63': {'lambda': 0.2} }
}


def get_reliability_lambda(el_type, el_id):
    """
    Retrieves lambda for a specific component.
    Prioritizes SPECIAL_RELIABILITY, falls back to DEFAULT_RELIABILITY.
    """
    # 1. Check for specific exception
    specific_data = SPECIAL_RELIABILITY.get(el_type, {}).get(str(el_id))
    if specific_data:
        return specific_data['lambda']

    # 2. Fallback to default
    data = DEFAULT_RELIABILITY.get(el_type)
    if data:
        return data['lambda']

    raise ValueError(f"Unknown element type: {el_type}")


# ==========================================
# 2. PLOTTING & FORMATTING FUNCTIONS
# ==========================================

def format_risk_label(value):
    """
    Smart formatting for risk values on the plot.
    - If val >= 0.001: Returns decimal string (e.g., "0.050")
    - If val < 0.001:  Returns LaTeX scientific notation (e.g., "1.2 \cdot 10^{-4}")
    """
    if value == 0:
        return "0"

    if value >= 0.001:
        return f"{value:.3f}"  # 3 decimal places

    # For very small numbers, use LaTeX scientific notation
    str_val = f"{value:.1e}"
    base, exponent = str_val.split('e')
    return f"${base} \\cdot 10^{{{int(exponent)}}}$"


def plot_risk_horizontal(ids, n1_scores, n2_scores, title, filename_suffix, legend_title=None):
    """
    Generates a high-quality horizontal bar chart (IEEE style).
    Now accepts 'legend_title' to display MTTF info.
    """
    # Prepare data arrays
    ids = np.array(ids)
    n1_scores = np.array(n1_scores)
    n2_scores = np.array(n2_scores)
    total_scores = n1_scores + n2_scores

    # Determine figure height based on number of items (dynamic)
    num_items = len(ids)
    fig_height = max(6, num_items * 0.4)  # Adjust height so bars aren't squashed

    # Style configuration: WHITE background (no default harsh grid)
    sns.set_theme(style="white")
    sns.set_context("paper", font_scale=1.4)

    fig, ax = plt.subplots(figsize=(12, fig_height))

    # --- SOFT GRID CONFIGURATION ---
    # Only vertical lines, dashed, and very transparent (alpha=0.3)
    ax.grid(True, axis='x', linestyle='--', alpha=0.3, color='gray')
    ax.set_axisbelow(True)  # Ensure grid is BEHIND the bars

    # Plot Bars (Stacked)
    # N-1 Risk (Base layer)
    ax.barh(ids, n1_scores, color='#d9534f', label='N-1 Risk ($F_e \cdot S_e$)', edgecolor='white', height=0.7)
    # N-2 Risk (Top layer)
    ax.barh(ids, n2_scores, left=n1_scores, color='#5bc0de', label='N-2 Risk ($\sum F_{e,j} \cdot S_{e,j}$)',
            edgecolor='white', height=0.7)

    # Labels and Title
    ax.set_xlabel("Risk Index ($R_e$) [failures/year]", fontsize=14, weight='bold')
    ax.set_ylabel("Component ID", fontsize=14, weight='bold')
    ax.set_title(title, fontsize=16, weight='bold', pad=20)

    # Aesthetics: Remove top and right borders
    sns.despine(left=True, bottom=True)

    # --- LEGEND WITH MTTF ---
    # We use the 'title' parameter of the legend to show the MTTF
    legend = ax.legend(loc='lower right', frameon=True, framealpha=0.9,
                       title=legend_title, title_fontsize=11)

    # Align legend title to the left for better readability if long
    legend._legend_box.align = "left"

    # Smart Annotations (Values at the end of bars)
    max_x = max(total_scores) if len(total_scores) > 0 else 1e-9

    for i, v in enumerate(total_scores):
        label_text = format_risk_label(v)
        # Add text slightly to the right of the bar
        ax.text(v + (max_x * 0.01), i, label_text,
                va='center', fontsize=10, color='#444444')  # Dark grey text

    # Adjust X-axis limit to fit text
    ax.set_xlim(0, max_x * 1.20)
    plt.tight_layout()

    # Save High-Res Image
    safe_filename = f"risk_index_{filename_suffix}.png"
    plt.savefig(safe_filename, dpi=300, bbox_inches='tight')
    print(f"Plot saved: {safe_filename}")
    plt.close()


def plot_risk_category(risk_index, category_name, top_n):
    """Wrapper to prepare data for a single category (Lines, Gen, etc.)."""
    if not risk_index: return

    # Helper to calculate total risk
    def get_total(item):
        return item[1]['n1_risk'] + item[1]['n2_risk']

    # Filter zeros and sort
    valid_items = [x for x in risk_index.items() if get_total(x) > 0]
    sorted_items = sorted(valid_items, key=get_total)[-top_n:]  # Get top N

    if not sorted_items: return

    # Unpack data
    ids = [str(item[0]) for item in sorted_items]
    n1 = [item[1]['n1_risk'] for item in sorted_items]
    n2 = [item[1]['n2_risk'] for item in sorted_items]

    # --- MTTF LEGEND GENERATION ---
    # Map category display name to internal key
    key_map = {
        'Lines': 'line',
        'Generators': 'generator',
        'Transformers': 'transformer'
    }
    internal_key = key_map.get(category_name)

    mttf_text = None
    if internal_key:
        lam = DEFAULT_RELIABILITY[internal_key]['lambda']
        mttf_val = int(1 / lam)
        # Clean singular name for legend (remove 's')
        singular_name = category_name[:-1]
        mttf_text = f"MTTF ({singular_name}): {mttf_val} years"

    # Call plotter with legend title
    plot_risk_horizontal(ids, n1, n2,
                         f"Top {top_n} Critical {category_name} ($R_e$)",
                         category_name.lower(),
                         legend_title=mttf_text)


def plot_combined_risk(risk_maps, top_n):
    """
    Merges Lines, Generators, and Transformers to find the GLOBAL Top N.
    Adds prefixes (Gen, Line, Trafo) to display IDs.
    """
    print(f"Generating Combined Global Top {top_n} Plot...")

    merged_list = []

    # Map internal types to display prefixes
    type_map = {'line': 'Line', 'transformer': 'Trafo', 'generator': 'Gen'}

    # Flatten dictionary structure
    for type_key, risk_dict in risk_maps.items():
        prefix = type_map.get(type_key, type_key)

        for el_id, risks in risk_dict.items():
            total = risks['n1_risk'] + risks['n2_risk']
            if total > 0:
                merged_list.append({
                    'id': f"{prefix} {el_id}",
                    'n1': risks['n1_risk'],
                    'n2': risks['n2_risk'],
                    'total': total
                })

    # Sort by Total Risk
    merged_list.sort(key=lambda x: x['total'])

    # Slice Top N
    top_items = merged_list[-top_n:]

    if not top_items:
        print("No risk data found for combined plot.")
        return

    # Extract lists for plotting
    ids = [x['id'] for x in top_items]
    n1 = [x['n1'] for x in top_items]
    n2 = [x['n2'] for x in top_items]

    # --- COMBINED MTTF LEGEND ---
    mttf_gen = int(1 / DEFAULT_RELIABILITY['generator']['lambda'])
    mttf_line = int(1 / DEFAULT_RELIABILITY['line']['lambda'])
    mttf_trafo = int(1 / DEFAULT_RELIABILITY['transformer']['lambda'])

    combined_legend = f"MTTF: Gen={mttf_gen}y, Line={mttf_line}y, Trafo={mttf_trafo}y"

    plot_risk_horizontal(ids, n1, n2,
                         f"Global Top {top_n} Critical Components ($R_e$)",
                         "combined_global",
                         legend_title=combined_legend)


# ==========================================
# 3. MAIN EXECUTION LOGIC
# ==========================================

if __name__ == "__main__":
    # File configuration
    file_name = 'results_parallel.json'
    file_path = os.path.join(os.path.dirname(__file__), file_name)

    if not os.path.exists(file_path):
        print(f"ERROR: File {file_path} not found.")
        sys.exit(1)

    print(f"Loading results from {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        results = json.load(f)

    # Initialize Data Structures
    risk_maps = {
        'line': defaultdict(lambda: {'n1_risk': 0.0, 'n2_risk': 0.0}),
        'transformer': defaultdict(lambda: {'n1_risk': 0.0, 'n2_risk': 0.0}),
        'generator': defaultdict(lambda: {'n1_risk': 0.0, 'n2_risk': 0.0})
    }

    print("Calculating Risk Index ($R_e$)...")

    # --- PROCESS RESULTS ---
    for case in results:

        # 1. Severity Check (S_c)
        # S=1 if: Not converged OR Unstable (0) OR Islands formed
        is_unstable = (
                not case.get('gce.powerflow_converged', True) or
                case.get('stability') == 0 or
                case.get('islands') is True
        )

        # If stable (S=0), skip (Risk = 0)
        if not is_unstable: continue

        # 2. Frequency Calculation (F_c)
        elements = case.get('elements', [])
        if not elements: continue

        freq_case = 0.0
        risk_type = ''

        try:
            if case['level'] == 'single':
                # F = lambda_e
                el = elements[0]
                freq_case = get_reliability_lambda(el['type'], el['id'])
                risk_type = 'n1_risk'

            elif case['level'] == 'double':
                # F = lambda_e * lambda_j (No MTTR involved)
                if len(elements) < 2: continue
                lam1 = get_reliability_lambda(elements[0]['type'], elements[0]['id'])
                lam2 = get_reliability_lambda(elements[1]['type'], elements[1]['id'])
                freq_case = lam1 * lam2
                risk_type = 'n2_risk'

            # 3. Accumulate Risk to Components
            # R_e += F_c * S_c (where S_c is 1)
            for el in elements:
                if el['type'] in risk_maps:
                    risk_maps[el['type']][el['id']][risk_type] += freq_case

        except Exception as e:
            print(f"Error processing case {case.get('id', 'unknown')}: {e}")

    # --- GENERATE PLOTS ---

    # 1. Individual Categories (Top 15)
    print("Generating individual plots (Top 15)...")
    plot_risk_category(risk_maps['line'], "Lines", top_n=15)
    plot_risk_category(risk_maps['generator'], "Generators", top_n=15)
    plot_risk_category(risk_maps['transformer'], "Transformers", top_n=15)

    # 2. Combined Global Plot (Top 20)
    print("Generating global combined plot (Top 20)...")
    plot_combined_risk(risk_maps, top_n=20)

    print("\nProcessing complete. High-quality .png files created.")