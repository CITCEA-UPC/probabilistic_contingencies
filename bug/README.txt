VeraGrid EMT topology report
===========================

Start with report.pdf (or report.tex). It follows the requested issue template.

Files:
  IEEE118busNREL.raw       Original input, copied byte-for-byte.
  reproduce.py            Standalone API reproduction; also builds a tiny
                          synthetic two-bus example with --minimal.
  observed_ieee118.json    Output from the tested IEEE118 reproduction.
  observed_minimal.json    Output from the tested synthetic reproduction.
  report.tex / report.pdf Short English report.

Requirements:
  The tested VeraGrid_TenSyGrid development checkout, commit
  2692754f16a097c9b387b8b5741ae8ebc87efd52 (engine reports 6.7.0),
  with its usual Python dependencies. A stock release may differ.
  Put that checkout's src directory on PYTHONPATH if not installed:

    export PYTHONPATH=/path/to/VeraGrid_TenSyGrid/src

Run from this directory:

    python reproduce.py --out result.json
    python reproduce.py --minimal --out minimal.json

No application checkout, config.py, SQLite, PyCOMPSs or Slurm is required.
No engine or network patch is applied. A reproduced topology rejection is
recorded as an expected diagnostic outcome (exit 0); a different exception
returns exit 1. If the constructor accepts the case, the JSON says that the
reported rejection was not reproduced. UUIDs can differ between imports.

Scope:
  The script calls the public EMT constructor. It does not run a transient
  simulation or establish physical validity of the entire dynamic model.
  Generic dynamic templates are attached explicitly in the script.

Original RAW SHA256:
  5d0f3d1ccbb641e7c7f75fb71eb7f9ce42d5d50bb658137e4449fb03e84c0882

Build the report, if needed:
    pdflatex -interaction=nonstopmode -halt-on-error report.tex
