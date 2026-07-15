# AI Hospital Bed & Resource Planner

A Streamlit dashboard for hospital administrators, built directly on top of:

- **`hospital_ai_recommendation.csv`** — 3 years (2023–2025) of daily records
  for 3 hospitals (CityCare, Apollo, MedLife), including beds, staffing,
  occupancy rates, case-mix, and pre-computed AI alerts/recommendations.
- **`admission_prediction_model.pkl`** — a trained `RandomForestRegressor`
  (200 trees) that estimates a hospital's daily admissions from its 25-feature
  same-day resource/ratio profile.

## Features

- **Dashboard** — latest real snapshot for the selected hospital: occupancy
  gauges for ICU/General/Emergency wards, staffing on duty, ventilators, and
  the dataset's own Alert Level / Risk Level / Bed Status / AI Recommendation.
- **Historical Trends** — explore admissions, discharges, occupancy rates,
  and alert-level distribution over any date range, with an option to compare
  all three hospitals at once.
- **AI Admission Predictor** — loads a historical day's full feature profile
  into an editable form, runs it through the RandomForest model, and shows
  the predicted vs. actual admissions. Every input is editable so you can
  explore "what admission load is this resource profile consistent with?"
  (see the important caveat below).
- **Resource Planner & What-If** — a transparent trend + day-of-week
  seasonality model, fit on the selected hospital's real admissions history,
  projects occupancy forward and flags projected bed/staff shortfalls. Includes
  a surge slider for scenario planning (e.g. flu season, mass casualty event).
- **Data & Model** — browse/download the underlying data and see model details.

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

Keep `hospital_ai_recommendation.csv` and `admission_prediction_model.pkl` in
the same folder as `app.py` — the app loads them by relative path and will
show an error if either is missing.

The app opens at `http://localhost:8501`.

## ⚠️ Important note on the ML model

Several of the 25 features the RandomForest model was trained on (e.g.
`Doctor_Patient_Ratio`, `Patients_Per_Bed`) are themselves *derived from*
that day's admissions count. As a result, the model has effectively learned
to invert those ratios back into admissions — it reproduces the historical
`Admissions` column almost exactly (near-zero error), which is a sign of
data leakage rather than genuine forward prediction.

Because of this, the app uses the model only in the **AI Admission
Predictor** tab, framed honestly as a same-day consistency/scenario tool. For
actual forward-looking demand forecasting, the **Resource Planner** tab uses
a separate, leakage-free trend + seasonality model fit purely on historical
admissions by date.

If you retrain the model, dropping admission-derived ratio features (or
lagging them by one day) would let it be used for genuine next-day
forecasting instead.

## Using your own data

To point the app at different hospitals, replace `hospital_ai_recommendation.csv`
with a file using the same 97 columns (see the "Data & Model" tab for the full
schema), and optionally retrain/replace `admission_prediction_model.pkl` with
a `scikit-learn` regressor exposing `.feature_names_in_` and `.predict()`.

## Configuration

Forecast horizon, assumed average length of stay, and planned staffing/
ventilator levels are all adjustable live in the sidebar — no code changes
needed.
