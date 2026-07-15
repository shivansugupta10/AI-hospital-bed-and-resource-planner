"""
AI Hospital Bed and Resource Planner
-------------------------------------------------
Single-screen tool: pick (or manually enter) a hospital's current resources,
enter expected new admissions, and instantly see how that load compares to
available beds, staff, ventilators, and oxygen — with a clear
Sufficient/Shortage verdict AND a Claude-generated action plan.

The "AI recommendation" is generated entirely on-device by a rule-based
decision engine (see `generate_recommendation` below) — no API key, no
internet connection, and no external service required.

Setup:
  pip install streamlit pandas plotly

Run with:  streamlit run app.py

Note: `hospital_ai_recommendation.csv` is OPTIONAL. If it isn't found next
to this script, the app switches to manual-entry mode instead of stopping,
so the tool is usable on its own without any external data file.
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

APP_DIR = Path(__file__).parent
DATA_PATH = APP_DIR / "hospital_ai_recommendation.csv"

st.set_page_config(page_title="AI Hospital Bed and Resource Planner", page_icon="🏥", layout="wide")

st.markdown(
    """
    <style>
    .metric-card { background:#f8f9fb; border:1px solid #e6e9ef; border-radius:10px; padding:14px 18px; }
    .status-ok   { color:#15803d; font-weight:700; }
    .status-bad  { color:#b91c1c; font-weight:700; }
    .ai-box      { background:#eff6ff; border:1px solid #bfdbfe; border-radius:10px; padding:16px 20px; }
    </style>
    """,
    unsafe_allow_html=True,
)

DEPARTMENTS = ["ICU", "General", "Emergency"]


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["Date"]).sort_values("Date")


# ----------------------------------------------------------------------------
# Load data if available; otherwise fall back to manual entry (app stays usable)
# ----------------------------------------------------------------------------
df_all = None
hospital_map = None
data_available = DATA_PATH.exists()

if data_available:
    try:
        df_all = load_data(str(DATA_PATH))
        hospital_map = df_all[["Hospital_ID", "Hospital_Name", "City"]].drop_duplicates().set_index("Hospital_ID")
    except Exception as e:
        st.warning(f"Couldn't read `hospital_ai_recommendation.csv` ({e}). Switching to manual entry mode.")
        data_available = False

# ----------------------------------------------------------------------------
# Header + hospital picker
# ----------------------------------------------------------------------------
st.title("🏥 AI Hospital Bed and Resource Planner")
st.caption(
    "See exactly how new admissions would affect your available beds, staff, ventilators, "
    "and oxygen — with an AI-generated action plan."
)

if data_available:
    col_h, col_d = st.columns([2, 1])
    with col_h:
        hid = st.selectbox(
            "Hospital",
            hospital_map.index.tolist(),
            format_func=lambda h: f"{hospital_map.loc[h, 'Hospital_Name']} ({h}) — {hospital_map.loc[h, 'City']}",
        )
    hdf = df_all[df_all["Hospital_ID"] == hid].sort_values("Date")
    available_dates = hdf["Date"].dt.date.tolist()
    with col_d:
        selected_date = st.date_input(
            "Data as of",
            value=available_dates[-1],
            min_value=available_dates[0],
            max_value=available_dates[-1],
        )

    exact_match = hdf[hdf["Date"].dt.date == selected_date]
    if not exact_match.empty:
        latest = exact_match.iloc[-1]
    else:
        prior_records = hdf[hdf["Date"].dt.date <= selected_date]
        if not prior_records.empty:
            latest = prior_records.iloc[-1]
        else:
            latest = hdf.iloc[0]
        st.caption(f"No record for {selected_date} — showing the closest available date, {latest['Date'].date()}.")

    hospital_label = f"{hospital_map.loc[hid, 'Hospital_Name']} ({hid}) — {hospital_map.loc[hid, 'City']}"
    report_date = latest["Date"].date()
    default_icu = int(latest["Available_ICU_Beds"])
    default_general = int(latest["Available_General_Beds"])
    default_emergency = int(latest["Available_Emergency_Beds"])
    default_doctors = int(latest["Doctors"])
    default_nurses = int(latest["Nurses"])
    default_ventilators = int(latest["Ventilators"])
    default_oxygen = int(latest["Oxygen_Cylinders"])
else:
    st.info(
        "No `hospital_ai_recommendation.csv` found next to this script — you're in **manual entry mode**. "
        "Just fill in your hospital's current numbers below."
    )
    col_h, col_d = st.columns([2, 1])
    with col_h:
        hospital_label = st.text_input("Hospital name", value="My Hospital")
    with col_d:
        report_date = st.date_input("Data as of")
    default_icu = default_general = default_emergency = 0
    default_doctors = default_nurses = default_ventilators = default_oxygen = 0

# ----------------------------------------------------------------------------
# Current available resources (editable, defaulted from latest real data if any)
# ----------------------------------------------------------------------------
st.subheader("1️⃣ Current Available Resources")
st.caption(
    "Pre-filled from the hospital's latest record — adjust if today's numbers are different."
    if data_available
    else "Enter today's numbers for this hospital."
)

r1, r2, r3 = st.columns(3)
avail = {}
avail["ICU"] = r1.number_input("Available ICU Beds", min_value=0, value=default_icu)
avail["General"] = r2.number_input("Available General Beds", min_value=0, value=default_general)
avail["Emergency"] = r3.number_input("Available Emergency Beds", min_value=0, value=default_emergency)

r4, r5, r6, r7 = st.columns(4)
avail_doctors = r4.number_input("Doctors on Duty", min_value=0, value=default_doctors)
avail_nurses = r5.number_input("Nurses on Duty", min_value=0, value=default_nurses)
avail_ventilators = r6.number_input("Ventilators Available", min_value=0, value=default_ventilators)
avail_oxygen = r7.number_input("Oxygen Cylinders Available", min_value=0, value=default_oxygen)

st.divider()

# ----------------------------------------------------------------------------
# New admissions input
# ----------------------------------------------------------------------------
st.subheader("2️⃣ New Admissions")
st.caption("Enter how many new patients are expected, by ward.")

a1, a2, a3 = st.columns(3)
new_admissions = {}
new_admissions["ICU"] = a1.number_input("New ICU Admissions", min_value=0, value=5, key="adm_icu")
new_admissions["General"] = a2.number_input("New General Admissions", min_value=0, value=15, key="adm_gen")
new_admissions["Emergency"] = a3.number_input("New Emergency Admissions", min_value=0, value=8, key="adm_er")
total_new = sum(new_admissions.values())

with st.expander("⚙️ Resource-per-patient assumptions (adjust if needed)"):
    st.caption("Used to estimate how many staff / ventilators / oxygen cylinders the new admissions will need.")
    c1, c2, c3 = st.columns(3)
    nurse_ratio = {
        "ICU": c1.number_input("ICU patients per nurse", min_value=1, value=1),
        "General": c2.number_input("General patients per nurse", min_value=1, value=4),
        "Emergency": c3.number_input("Emergency patients per nurse", min_value=1, value=3),
    }
    c4, c5, c6 = st.columns(3)
    doctor_ratio = {
        "ICU": c4.number_input("ICU patients per doctor", min_value=1, value=3),
        "General": c5.number_input("General patients per doctor", min_value=1, value=10),
        "Emergency": c6.number_input("Emergency patients per doctor", min_value=1, value=6),
    }
    c7, c8 = st.columns(2)
    vent_need_pct = c7.slider("% of ICU admissions needing a ventilator", 0, 100, 60)
    oxygen_per_patient = c8.number_input("Oxygen cylinders per new admission", min_value=0.0, value=1.0, step=0.5)

st.divider()

# ----------------------------------------------------------------------------
# Calculate requirements
# ----------------------------------------------------------------------------
beds_needed = {dept: new_admissions[dept] for dept in DEPARTMENTS}
nurses_needed = sum(-(-new_admissions[d] // nurse_ratio[d]) for d in DEPARTMENTS)  # ceil division
doctors_needed = sum(-(-new_admissions[d] // doctor_ratio[d]) for d in DEPARTMENTS)
ventilators_needed = -(-(new_admissions["ICU"] * vent_need_pct) // 100)  # ceil division, no float truncation bug
oxygen_needed = round(total_new * oxygen_per_patient)

# ----------------------------------------------------------------------------
# 3. Results — Availability vs Requirement
# ----------------------------------------------------------------------------
st.subheader("3️⃣ Availability vs. Requirement")

rows = []
for dept in DEPARTMENTS:
    rows.append({
        "Resource": f"{dept} Beds", "Available Now": avail[dept],
        "Required for New Admissions": beds_needed[dept],
        "Remaining After": avail[dept] - beds_needed[dept],
    })
rows.append({"Resource": "Doctors", "Available Now": avail_doctors, "Required for New Admissions": doctors_needed, "Remaining After": avail_doctors - doctors_needed})
rows.append({"Resource": "Nurses", "Available Now": avail_nurses, "Required for New Admissions": nurses_needed, "Remaining After": avail_nurses - nurses_needed})
rows.append({"Resource": "Ventilators", "Available Now": avail_ventilators, "Required for New Admissions": ventilators_needed, "Remaining After": avail_ventilators - ventilators_needed})
rows.append({"Resource": "Oxygen Cylinders", "Available Now": avail_oxygen, "Required for New Admissions": oxygen_needed, "Remaining After": avail_oxygen - oxygen_needed})

result_df = pd.DataFrame(rows)
result_df["Status"] = result_df["Remaining After"].apply(lambda x: "✅ Sufficient" if x >= 0 else "⚠️ Shortage")

def highlight_row(row):
    color = "background-color:#dcfce7" if row["Remaining After"] >= 0 else "background-color:#fecaca"
    return [color] * len(row)

st.dataframe(result_df.style.apply(highlight_row, axis=1), use_container_width=True, hide_index=True)

shortages = result_df[result_df["Remaining After"] < 0]
if not shortages.empty:
    short_list = ", ".join(f"{r['Resource']} (short by {abs(r['Remaining After'])})" for _, r in shortages.iterrows())
    st.error(f"⚠️ With {total_new} new admissions, you would be **short on**: {short_list}.")
else:
    st.success(f"✅ Current resources are **sufficient** to absorb {total_new} new admissions.")

# ----------------------------------------------------------------------------
# Visual comparison
# ----------------------------------------------------------------------------
st.subheader("Visual Comparison")
fig = go.Figure()
fig.add_trace(go.Bar(name="Available Now", x=result_df["Resource"], y=result_df["Available Now"], marker_color="#2563eb"))
fig.add_trace(go.Bar(name="Required for New Admissions", x=result_df["Resource"], y=result_df["Required for New Admissions"], marker_color="#f59e0b"))
fig.update_layout(barmode="group", height=420, yaxis_title="Count", legend_title="")
st.plotly_chart(fig, use_container_width=True)

csv_export = result_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Download this comparison (CSV)",
    csv_export,
    f"resource_availability_{hospital_label.replace(' ', '_')}_{report_date}.csv",
    "text/csv",
)

st.divider()

# ----------------------------------------------------------------------------
# 4. AI-generated recommendation — local rule-based engine, no API required
# ----------------------------------------------------------------------------
st.subheader("4️⃣ AI-Generated Recommendation")
st.caption("A built-in decision engine reads the comparison above and predicts an action plan — no API key or internet connection needed.")

# Mitigation playbook the engine draws from for each resource type.
MITIGATIONS = {
    "ICU Beds": [
        "step down stable ICU patients to General as soon as they're eligible",
        "activate transfer agreements with nearby facilities for incoming ICU cases",
        "delay elective procedures that would need an ICU bed post-op",
    ],
    "General Beds": [
        "expedite discharge planning for patients ready to leave today",
        "open overflow/surge beds if the facility has them",
        "transfer stable patients to a partner facility with spare capacity",
    ],
    "Emergency Beds": [
        "fast-track triage to move stable ER patients to General sooner",
        "divert non-critical ambulance traffic to nearby facilities",
        "pull in extra ER staff to speed up turnover",
    ],
    "Doctors": [
        "call in on-call or backup physicians",
        "temporarily reassign doctors from lower-acuity wards",
        "bring in locum/agency physician coverage for the shift",
    ],
    "Nurses": [
        "call in on-call or float-pool nurses",
        "adjust nurse-to-patient ratios temporarily with charge-nurse approval",
        "bring in agency nursing staff for the shift",
    ],
    "Ventilators": [
        "borrow ventilators from a partner hospital or regional stockpile",
        "reassess which ICU patients can step down from ventilator support",
        "defer any non-urgent procedure that would require ventilator support",
    ],
    "Oxygen Cylinders": [
        "place an urgent reorder with the oxygen supplier",
        "borrow cylinders from a nearby facility or regional stockpile",
        "check central oxygen supply lines as a supplement to cylinders",
    ],
}

# How close "sufficient" still counts as tight enough to flag proactively.
TIGHT_BUFFER_RATIO = 0.15  # remaining < 15% of what's available now


def generate_recommendation(df: pd.DataFrame, hospital: str, incoming: int) -> str:
    """Rule-based decision engine: predicts an action plan from the resource
    comparison table. This mimics an AI triage assistant's reasoning without
    calling any external model or API."""

    short_rows = df[df["Remaining After"] < 0].copy()
    tight_rows = df[
        (df["Remaining After"] >= 0)
        & (df["Available Now"] > 0)
        & (df["Remaining After"] <= df["Available Now"] * TIGHT_BUFFER_RATIO)
    ]

    if short_rows.empty:
        lines = [
            f"**Prediction: resources are sufficient** to absorb {incoming} incoming admissions at "
            f"{hospital} — no shortages detected across beds, staffing, ventilators, or oxygen."
        ]
        if not tight_rows.empty:
            watch_list = ", ".join(
                f"{r['Resource']} ({r['Remaining After']} left)" for _, r in tight_rows.iterrows()
            )
            lines.append(
                f"That said, keep an eye on: **{watch_list}** — these will be running close to capacity "
                "after the new admissions, so a small surge could tip them into shortage."
            )
        else:
            lines.append("All resources retain a comfortable buffer after the new admissions are absorbed.")
        return "\n\n".join(lines)

    # Rank shortages by severity (largest deficit relative to what's required)
    short_rows["severity"] = short_rows.apply(
        lambda r: abs(r["Remaining After"]) / max(r["Required for New Admissions"], 1), axis=1
    )
    short_rows = short_rows.sort_values("severity", ascending=False)

    top = short_rows.iloc[0]
    lines = [
        f"**Prediction: shortage risk** for {incoming} incoming admissions at {hospital}. "
        f"Highest priority: **{top['Resource']}**, short by {abs(top['Remaining After'])} "
        f"({top['Available Now']} available vs {top['Required for New Admissions']} needed)."
    ]

    for _, r in short_rows.iterrows():
        deficit = abs(r["Remaining After"])
        options = MITIGATIONS.get(r["Resource"], ["escalate to hospital administration for support"])
        picked = options[:2] if deficit >= max(1, r["Required for New Admissions"] * 0.5) else options[:1]
        lines.append(f"- **{r['Resource']}** — short by {deficit}: " + "; ".join(picked) + ".")

    if len(short_rows) > 1:
        lines.append(
            f"With {len(short_rows)} resources short at once, consider deferring non-urgent admissions "
            "until the highest-priority shortage above is resolved."
        )

    return "\n\n".join(lines)


col_btn, col_note = st.columns([1, 3])
with col_btn:
    generate_clicked = st.button("🤖 Generate AI Recommendation", use_container_width=True)

if generate_clicked:
    with st.spinner("Running the AI decision engine..."):
        st.session_state["ai_recommendation"] = generate_recommendation(result_df, hospital_label, total_new)

if "ai_recommendation" in st.session_state:
    st.markdown(f'<div class="ai-box">{st.session_state["ai_recommendation"]}</div>', unsafe_allow_html=True)
