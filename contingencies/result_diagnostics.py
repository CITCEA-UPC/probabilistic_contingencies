"""Criteris compartits de lectura i diagnòstic dels resultats, sense motor EMT."""

import json
import math

# Criteri del pipeline per als exponents de Floquet calculats (domini s).
STABLE_MAX_REAL_PART = 1e-6


def parse_eigenvalues(raw):
    """Retorna modes complexos, None si falten, o ValueError si són invàlids."""
    if raw is None or raw == "":
        return None
    try:
        pairs = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_eigenvalues") from exc
    if pairs is None or pairs == []:
        return None
    if not isinstance(pairs, list) or any(
        not isinstance(pair, list) or len(pair) != 2
        or any(type(x) not in (int, float) or not math.isfinite(x) for x in pair)
        for pair in pairs
    ):
        raise ValueError("invalid_eigenvalues")
    return [complex(real, imag) for real, imag in pairs]


def classify(row):
    """Diagnòstic de risc segons el criteri adoptat: PF no convergit implica failure."""
    status = row.get("status")
    if status == "pending":
        return "unknown", "pending"
    n_islands = row.get("n_islands")
    if (n_islands is not None and n_islands > 1) or (n_islands is None and row.get("islands") == 1):
        return "failure", "islanding"
    if status in {"pf_not_converged", "pf3_not_converged"}:
        return "failure", status
    # El PF balancejat s’executa abans del filtre EMT. El seu resultat real
    # continua sent un criteri de risc encara que després es rebutgi el terminal.
    if status == "isolated_buses" and row.get("powerflow_converged") == 0:
        return "failure", "pf_not_converged"
    # En canvi, exception utilitza False com a valor de reserva: no acredita
    # que s’hagi arribat a executar el PF ni que aquest hagi retornat no-convergència.
    if status != "ok":
        return "unknown", status or "missing_status"
    if row.get("errors"):
        return "unknown", "calculation_error"
    try:
        modes = parse_eigenvalues(row.get("eigenvalues"))
    except ValueError:
        return "unknown", "invalid_eigenvalues"
    if modes is None:
        return "unknown", "missing_eigenvalues"
    if max(z.real for z in modes) > STABLE_MAX_REAL_PART:
        return "failure", "modal_instability"
    if row.get("stable") == 1:
        return "stable", "completed_stable"
    return "unknown", "emt_health_unresolved"
