
import json
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Make sure WEIGHT_SINGLE_FAILURE is defined before calling this function
# Example: WEIGHT_SINGLE_FAILURE = 1000

def plot_risk_index(risk_index, title, top_n=15):
    """
    Creates and saves a bar chart for the 'top_n' elements
    with the highest risk.
    """
    print(f"Generating chart for: {title}...")

    if not risk_index:
        print(f"No chart generated for '{title}' (no data available).\n")
        return

    # Sort data from highest to lowest risk
    sorted_risk = sorted(
        risk_index.items(),
        key=lambda item: item[1],
        reverse=True
    )

    # Limit to Top N
    top_items = sorted_risk[:top_n]

    # If there is nothing to plot (maybe all CRIs are 0)
    if not top_items:
        print(f"No chart generated for '{title}' (no elements with risk found).\n")
        return

    # "Unzip" the data:
    # IDs (as strings, for the categorical axis) and scores
    element_ids = [str(item[0]) for item in top_items]
    scores = [item[1] for item in top_items]

    # Create the figure (a bit larger for readability)
    plt.figure(figsize=(14, 8))

    # --- Color Logic ---
    # Assign different colors based on the risk score
    # Red for N-1 failures, Blue for N-2 failures
    colors = ['#d9534f' if score >= WEIGHT_SINGLE_FAILURE else '#5bc0de' for score in scores]

    # Create the bars
    plt.bar(element_ids, scores, color=colors)

    # Add titles and labels
    plt.title(f"{title} (Top {min(top_n, len(element_ids))})", fontsize=16)
    plt.ylabel("Risk Score (CRI)", fontsize=12)
    plt.xlabel("Element ID", fontsize=12)

    # Rotate X-axis labels for better readability
    plt.xticks(rotation=90)

    # Add horizontal grid
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    # --- Custom Legend ---
    # Create "fake" graphic elements (patches) for the legend
    patch_n1 = mpatches.Patch(color='#d9534f', label=f'N-1 Failure (CRI >= {WEIGHT_SINGLE_FAILURE})')
    patch_n2 = mpatches.Patch(color='#5bc0de', label=f'N-2 Failure (CRI < {WEIGHT_SINGLE_FAILURE})')
    plt.legend(handles=[patch_n1, patch_n2])

    # Adjust layout to prevent labels from being cut off
    plt.tight_layout()

    # --- Save the Figure ---
    # Create a safe filename from the title
    safe_filename = title.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('/', '') + ".png"
    plt.savefig(safe_filename)
    print(f"Chart saved as: {safe_filename}\n")

    # Close the figure to free up memory
    plt.close()

def load_results(file_path, file_name):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

if __name__ == "__main__":
    file_name = 'results_parallel.json'
    file_path = os.path.join(os.path.dirname(__file__), file_name)

    results = load_results(file_path, file_name)
    total_cases = [case for case in results]
    errors_cases = [case for case in results if case['errors'] != False] # Perquè tenim l'error al camp error i no True
    print(f'total cases: {len(total_cases)}, ok cases: {len(total_cases)-len(errors_cases)}, errors: {len(errors_cases)}')

    # Filtrem els casos on level == 'single'
    single_cases = [case for case in results if case['level'] == 'single']

    # Filtrem els casos on level == 'double'
    double_cases = [case for case in results if case['level'] == 'double']

    # Imprimim els recomptes (opcional)
    print(f"Tenim {len(single_cases)} casos 'single'.")
    print(f"Tenim {len(double_cases)} casos 'double'.")

    from collections import defaultdict

    # --- 1. Definir els pesos del risc ---
    WEIGHT_SINGLE_FAILURE = 1000
    WEIGHT_DOUBLE_FAILURE = 1

    # --- 2. Inicialitzar els contenidors de l'índex de risc ---
    line_risk_index = defaultdict(int)
    transformer_risk_index = defaultdict(int)
    generator_risk_index = defaultdict(int)

    risk_index_map = {
        'line': line_risk_index,
        'transformer': transformer_risk_index,
        'generator': generator_risk_index
    }

    # --- 3. Analitzar tots els resultats ---
    # (Assumint que les teves dades estan a la variable 'results')

    for case in results:

        # --- A. Definir la condició de FALLADA (ACTUALITZADA) ---
        # Un cas és una "fallada" si QUALSEVOL d'aquestes condicions es compleix:
        is_failure = (
                not case['gce.powerflow_converged'] or
                case['stability'] == 0 or
                case['islands'] is True
            # Compte: 'stability == 0' no és el mateix que 'stability: null'
            # 'is True' és més segur que només 'case['islands']'
        )

        # Si el cas NO és una fallada (és un èxit), l'ignorem i passem al següent.
        if not is_failure:
            continue

        # --- B. Si és una fallada, determinar el pes ---
        # (Aquesta part és més eficient que abans)

        weight_to_apply = 0
        if case['level'] == 'single':
            weight_to_apply = WEIGHT_SINGLE_FAILURE
        elif case['level'] == 'double':
            weight_to_apply = WEIGHT_DOUBLE_FAILURE
        else:
            # Ignorar altres 'levels' si n'hi hagués
            continue

        # --- C. Aplicar el pes a tots els elements involucrats ---
        for element in case['elements']:
            el_type = element['type']
            el_id = element['id']

            # Busquem el diccionari de risc correcte (line, trans, gen)
            if el_type in risk_index_map:
                # Afegim el pes (1000 o 1) a l'índex del component
                risk_index_map[el_type][el_id] += weight_to_apply


    # --- 4. Resultats: Ordenar i Mostrar ---

    def print_risk_index(title, risk_index):
        print(f"--- {title} ---")
        print("(Ordenat de més a menys crític)\n")

        if not risk_index:
            print("No s'han trobat elements amb risc en aquesta categoria.\n")
            return

        sorted_risk = sorted(
            risk_index.items(),
            key=lambda item: item[1],
            reverse=True
        )

        for el_id, risk_score in sorted_risk:
            print(f"ID {el_id}: \t Puntuació de Risc = {risk_score}")
        print("\n" + "=" * 40 + "\n")


    # --- 4. Results: Print (Optional) ---
    # (This step is optional if you are only generating plots)
    print_risk_index("Risk Index (CRI) for LINES", line_risk_index)
    print_risk_index("Risk Index (CRI) for TRANSFORMERS", transformer_risk_index)
    print_risk_index("Risk Index (CRI) for GENERATORS", generator_risk_index)

    # --- 5. Generate the Plots ---
    # Call the new plotting function for each risk index

    plot_risk_index(line_risk_index, "Risk Index (CRI) for LINES")
    plot_risk_index(transformer_risk_index, "Risk Index (CRI) for TRANSFORMERS")
    plot_risk_index(generator_risk_index, "Risk Index (CRI) for GENERATORS")

    print("Anàlisi completada. Gràfics generats.")

