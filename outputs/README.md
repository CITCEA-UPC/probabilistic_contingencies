# Resultats generats

Aquesta carpeta conté dades locals d’execució i queda exclosa de Git, excepte aquest fitxer.

- `databases/`: bases de dades de contingències i resultats.
- `plots/risk_analysis/`: CSV, resum JSON i gràfics de risc per xarxa.
- `plots/modal_analysis/`: figures modals desades explícitament.
- `plots/`: també conserva els gràfics de risc històrics que eren a l’arrel.
- `logs/compss/`: logs del llançador PyCOMPSs i directori `.COMPSs/`.
- `logs/slurm/`: logs dels jobs històrics de Slurm.
- `profiles/`: perfils i figures de rendiment existents.
- `temp_grids/`: còpies de xarxes temporals conservades de l’estructura anterior.
- `reorganization.json`: registre local dels trasllats, amb SHA-256 de les BD traslladades.

El preprocess crea `databases/` si falta. Els llançadors i els analitzadors creen les seves carpetes de sortida quan les necessiten. No cal versionar els resultats per executar el pipeline.
