# DBMS Lab End-Sem Assignment — Player Telemetry Analytics

**Institution:** National Institute of Technology Warangal (NIT Warangal)  
**Student:** S. Mohan Reddy  |  **Roll No:** 24MAB0A32  
**Course:** Database Management Systems (DBMS)  
**Instructor:** Dr. Vikas Srivastava  
**Submission Date:** 25 November 2026  

## Contents
- `DBMS_Lab_EndSem_Readout_24MAB0A32.pptx`: 12-slide presentation (Slides 1–8: Executive Readout for Product Director; Slides 9–12: Appendix with Data Quality Audit, Retention Grid, Summary Metrics, and Churn Model Diagnostics).
- `deliverable_1_queries.sql`: Standalone SQL queries for Deliverables 1(a)–1(d) with deduplication, refund handling, right-censoring, and ad-status filtering.
- `run_full_analysis.py`: End-to-end Python script reproducing SQLite verification, Kitagawa ARPDAU mix-shift decomposition (Deliverable 2a), HC3-robust channel regressions (Deliverable 3), and out-of-time logistic regression churn modeling (Deliverable 4).
- `ANALYSIS_NOTES.md`: Complete written summary of findings, data-quality handling, judgement calls, and missing-input decision rules.
- `charts/`: Publication-quality PNG charts embedded in the slide deck.

## How to Run
Place the 5 supplied CSV files (`player_profile.csv`, `player_day.csv`, `purchase.csv`, `currency_spend.csv`, `ad_view.csv`) in the same folder and execute:
```bash
pip install pandas numpy scipy scikit-learn statsmodels matplotlib python-pptx
python run_full_analysis.py
```
