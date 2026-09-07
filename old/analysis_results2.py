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

DEFAULT_RELIABILITY = {
    'line': {'lambda': 1 / 20},  # MTTF = 20 years
    'transformer': {'lambda': 1 / 50},  # MTTF = 50 years
    'generator': {'lambda': 1 / 10}  # MTTF = 10 years
}

SPECIAL_RELIABILITY = {}


def get_reliability_lambda(el_type, el_id):
    specific_data = SPECIAL_RELIABILITY.get(el_type, {}).get(str(el_id))
    if specific_data:
        return specific_data['lambda']
    data = DEFAULT_RELIABILITY.get(el_type)
    if data:
        return data['lambda']
    raise ValueError(f"Unknown element type: {el_type}")


# ==========================================
# 2. PLOTTING & FORMATTING FUNCTIONS
# ==========================================

def format_risk_label(value):
    """
    Formato inteligente para los valores de riesgo.
    """
    if value == 0:
        return "0"
    if value >= 0.001:
        return f"{value:.3f}"

    # Notación científica LaTeX para valores muy pequeños
    str_val = f"{value:.1e}"
    base, exponent = str_val.split('e')
    return f"${base} \\cdot 10^{{{int(exponent)}}}$"


def plot_risk_horizontal(ids, n1_scores, n2_scores, title, filename_suffix, legend_title=None):
    """
    Genera un gráfico de barras horizontales con fuentes MASSIVES (+10% extra)
    y valores explícitos al final de las barras.
    """
    ids = np.array(ids)
    n1_scores = np.array(n1_scores)
    n2_scores = np.array(n2_scores)
    total_scores = n1_scores + n2_scores

    num_items = len(ids)
    # Aumentamos la separación vertical aún más
    # Antes 0.7 -> Ahora 0.8
    fig_height = max(10, num_items * 0.8)

    # --- CAMBIO 1: Aumentar escala de fuente global (+10% extra) ---
    sns.set_theme(style="white")
    # Antes 1.45 -> Ahora 1.6
    sns.set_context("poster", font_scale=1.6)

    fig, ax = plt.subplots(figsize=(16, fig_height))

    # Grid suave
    ax.grid(True, axis='x', linestyle='--', alpha=0.3, color='gray')
    ax.set_axisbelow(True)

    # Plot Bars (Stacked)
    ax.barh(ids, n1_scores, color='#d9534f', label='N-1 Risk ($F_e \cdot S_e$)', edgecolor='white', height=0.7)
    ax.barh(ids, n2_scores, left=n1_scores, color='#5bc0de', label='N-2 Risk ($\sum F_{e,j} \cdot S_{e,j}$)',
            edgecolor='white', height=0.7)

    # Labels and Title (+10% extra)
    # Ejes: 27 -> 30
    ax.set_xlabel("Risk Index ($R_e$) [failures/year]", fontsize=30, weight='bold')
    ax.set_ylabel("Component ID", fontsize=30, weight='bold')
    # Título: 31 -> 34
    ax.set_title(title, fontsize=34, weight='bold', pad=35)

    # Ticks: 24 -> 26
    ax.tick_params(axis='both', which='major', labelsize=26)

    sns.despine(left=True, bottom=True)

    # Legend (+10% extra)
    # Title: 24 -> 26, Text: 22 -> 24
    legend = ax.legend(loc='lower right', frameon=True, framealpha=0.95,
                       title=legend_title, title_fontsize=26, fontsize=24)
    legend._legend_box.align = "left"

    # --- Valores numéricos al lado de la barra ---
    max_x = max(total_scores) if len(total_scores) > 0 else 1e-9

    for i, v in enumerate(total_scores):
        label_text = format_risk_label(v)

        # Texto de valor: 22 -> 24
        ax.text(v + (max_x * 0.01), i, label_text,
                va='center', fontsize=24, weight='bold', color='#333333')

    # Ajuste de margen derecho fijo a 1.2
    ax.set_xlim(0, max_x * 1.1)

    plt.tight_layout()

    safe_filename = f"risk_index_{filename_suffix}.png"
    plt.savefig(safe_filename, dpi=300, bbox_inches='tight')
    print(f"Plot saved: {safe_filename}")
    plt.close()


def plot_risk_category(risk_index, category_name, top_n):
    if not risk_index: return

    def get_total(item):
        return item[1]['n1_risk'] + item[1]['n2_risk']

    valid_items = [x for x in risk_index.items() if get_total(x) > 0]
    sorted_items = sorted(valid_items, key=get_total)[-top_n:]

    if not sorted_items: return

    ids = [str(item[0]) for item in sorted_items]
    n1 = [item[1]['n1_risk'] for item in sorted_items]
    n2 = [item[1]['n2_risk'] for item in sorted_items]

    key_map = {'Lines': 'line', 'Generators': 'generator', 'Transformers': 'transformer'}
    internal_key = key_map.get(category_name)

    mttf_text = None
    if internal_key:
        lam = DEFAULT_RELIABILITY[internal_key]['lambda']
        mttf_val = int(1 / lam)
        singular_name = category_name[:-1]
        mttf_text = f"MTTF ({singular_name}): {mttf_val} years"

    plot_risk_horizontal(ids, n1, n2,
                         f"Top {top_n} Critical {category_name} ($R_e$)",
                         category_name.lower(),
                         legend_title=mttf_text)


def plot_combined_risk(risk_maps, top_n):
    print(f"Generating Combined Global Top {top_n} Plot...")
    merged_list = []
    type_map = {'line': 'Line', 'transformer': 'Trafo', 'generator': 'Gen'}

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

    merged_list.sort(key=lambda x: x['total'])
    top_items = merged_list[-top_n:]

    if not top_items:
        print("No risk data found for combined plot.")
        return

    ids = [x['id'] for x in top_items]
    n1 = [x['n1'] for x in top_items]
    n2 = [x['n2'] for x in top_items]

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
    file_name = 'results_parallel.json'
    file_path = os.path.join(os.path.dirname(__file__), file_name)

    if not os.path.exists(file_path):
        print(f"ERROR: File {file_path} not found.")
        sys.exit(1)

    print(f"Loading results from {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        results = json.load(f)

    risk_maps = {
        'line': defaultdict(lambda: {'n1_risk': 0.0, 'n2_risk': 0.0}),
        'transformer': defaultdict(lambda: {'n1_risk': 0.0, 'n2_risk': 0.0}),
        'generator': defaultdict(lambda: {'n1_risk': 0.0, 'n2_risk': 0.0})
    }

    print("Calculating Risk Index ($R_e$)...")

    total_cases = len(results)
    successful_cases = 0
    failed_cases = 0

    for case in results:
        is_unstable = (
                not case.get('gce.powerflow_converged', True) or
                case.get('stability') == 0 or
                case.get('islands') is True
        )

        if is_unstable:
            failed_cases += 1
        else:
            successful_cases += 1

        if not is_unstable: continue

        elements = case.get('elements', [])
        if not elements: continue

        freq_case = 0.0
        risk_type = ''

        try:
            if case['level'] == 'single':
                el = elements[0]
                freq_case = get_reliability_lambda(el['type'], el['id'])
                risk_type = 'n1_risk'
            elif case['level'] == 'double':
                if len(elements) < 2: continue
                lam1 = get_reliability_lambda(elements[0]['type'], elements[0]['id'])
                lam2 = get_reliability_lambda(elements[1]['type'], elements[1]['id'])
                freq_case = lam1 * lam2
                risk_type = 'n2_risk'

            for el in elements:
                if el['type'] in risk_maps:
                    risk_maps[el['type']][el['id']][risk_type] += freq_case

        except Exception as e:
            print(f"Error processing case {case.get('id', 'unknown')}: {e}")

    print("Generating individual plots (Top 15)...")
    plot_risk_category(risk_maps['line'], "Lines", top_n=15)
    plot_risk_category(risk_maps['generator'], "Generators", top_n=15)
    plot_risk_category(risk_maps['transformer'], "Transformers", top_n=15)

    print("Generating global combined plot (Top 20)...")
    plot_combined_risk(risk_maps, top_n=20)

    print("\n--- ANÀLISI DE CASOS DE FALLIDA ---")
    print(f"Casos totals analitzats: {total_cases}")
    print(f"Casos ESTABLES (Risk = 0, 'Bé'): {successful_cases}")
    print(f"Casos INESTABLES (Risk > 0, 'No Bé'): {failed_cases}")

    print("\nProcessing complete. High-quality .png files created.")