"""
Team3 - Singapore Jobs Analytics Dashboard
Streamlit dashboard for exploring Singapore job postings data.
"""

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="SG Jobs Analytics - Team3",
    page_icon="📊",
    layout="wide",
)

st.title("Singapore Jobs Analytics Dashboard")
st.markdown("**Team3** | Module 1 Assignment Project")


@st.cache_data
def load_data():
    """Load the processed dataset."""
    # Update the path to your processed data file
    # df = pd.read_csv("../data/processed/cleaned_jobs.csv")
    # return df
    return pd.DataFrame()


def main():
    df = load_data()

    if df.empty:
        st.warning(
            "No data loaded. Place your processed CSV in `data/processed/` "
            "and update the `load_data()` function."
        )
        return

    # --- Sidebar Filters ---
    st.sidebar.header("Filters")
    # Add your filters here

    # --- Overview Metrics ---
    st.header("Overview")
    # Add overview metrics (total postings, top roles, salary ranges, etc.)

    # --- Drill-down View ---
    st.header("Drill-down")
    # Add drill-down by role, industry, location, skills, etc.

    # --- Time Trend View ---
    st.header("Trends Over Time")
    # Add time trend charts (postings over time, salary trends, etc.)


if __name__ == "__main__":
    main()
