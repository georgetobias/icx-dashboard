# Internal CX Dashboard

A local analytics application for exploring internal customer experience survey ratings. Built with Python, FastAPI, pandas, React, TypeScript, and Plotly.

This repository contains the application source and a small, explicitly synthetic demo. It contains no company datasets, company logos, employee records, actual feedback, fixed company results, or original Git history. Optional organization-specific mappings and fixed reference scores were removed; analytics derive from the active CSV.

## Features

- Provider and customer perspectives with group and service drilldowns.
- Rating breakdowns, criticality scatterplots, frequency heatmaps, and attention queues.
- Inter/intra comparisons, received-versus-gave gaps, and respondent demographics.
- Validated CSV imports with atomic replacement, cached calculations, and refresh detection.
- PNG export, light/dark themes, and a Mac launcher with browser-session lifecycle handling.

## Run locally

Use Python 3.12+, Node.js 20+, and pnpm 9+.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
pnpm install --frozen-lockfile
pnpm build
python launcher.py
```

The launcher binds to loopback and opens the app in your browser. It uses `data/demo.csv` by default. The launcher is intended for macOS; other platforms can run `python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765` after building the frontend.

For development, run the API command above and `pnpm dev` in another terminal. Vite proxies `/api` to the local backend.

## Data contract

`data/schema.csv` defines the input columns. The `Service` header is accepted as an alias for `Service Cluster`. Ratings use the prefixes `BUSTED`, `LEVELED`, `UPLIFTED`, and `EXCEPTIONAL`; criticality values are 1–4. The score is `(uplifted + exceptional - busted) / ratings * 100`.

The included 54 ratings and all `DEMO-*` identifiers, `example.invalid` addresses, groups, and services are generated from scratch by `scripts/generate_demo.py`. They do not represent real people, organizations, results, or survey distributions.

Import your own CSV through Settings or configure a local `.env` using `.env.example`. Imports stay on your machine in a separate application data directory. Keep real inputs outside this repository. Private CSVs and environment files are ignored by Git; only the two explicitly named demo/schema CSV files are allowed.

## Verify

```bash
python -m pytest -q
pnpm build
python scripts/check_release.py
```

## Layout

```text
backend/       FastAPI routes, data validation, metrics, and chart generation
frontend/      React and TypeScript dashboard
data/          Generated fictional demo and header-only schema
scripts/       Demo generation and release checks
tests/         Tests using isolated synthetic data
packaging/     Optional PyInstaller recipe
launcher.py    Local macOS application launcher
```

The app is designed for trusted local use and does not include remote-hosting authentication. No open-source license is granted by this repository.
