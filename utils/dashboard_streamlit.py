import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import glob
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Set page config
st.set_page_config(page_title="FL-NIDS Dashboard", layout="wide", initial_sidebar_state="expanded")

# --- Helper Functions ---
def get_latest_metrics_file():
    logs_dir = os.path.join(_PROJECT_ROOT, "utils", "logs")
    if not os.path.exists(logs_dir):
        return None
    files = glob.glob(os.path.join(logs_dir, "experiment_metrics*.csv"))
    if not files:
        return None
    return max(files, key=os.path.getctime)

def get_latest_simulated_attack_file():
    sim_dir = os.path.join(_PROJECT_ROOT, "data", "simulated_attacks")
    if not os.path.exists(sim_dir):
        return None
    files = glob.glob(os.path.join(sim_dir, "*_attack.csv"))
    if not files:
        return None
    return max(files, key=os.path.getctime)

def get_incident_response_log():
    log_file = os.path.join(_PROJECT_ROOT, "utils", "logs", "incident_response_log.csv")
    if not os.path.exists(log_file):
        return None
    try:
        df = pd.read_csv(log_file)
        if df.empty:
            return None
        return df.tail(30).sort_index(ascending=False) # Get latest 30 descending
    except Exception:
        return None

# --- UI Layout ---
st.title("🛡️ Federated Learning NIDS - Live Dashboard")
st.markdown("Monitoring network traffic, federated model performance, and Automated Incident Response.")

# 1. Success Rate Metric Row
metric_placeholder = st.empty()

# 2. Charts Row
col1, col2 = st.columns(2)
chart_placeholder_1 = col1.empty()
chart_placeholder_2 = col2.empty()

# 3. Table Row
st.markdown("---")
st.subheader("🚨 Automated Incident Response & Mitigation Log")
ir_placeholder = st.empty()


# We use an infinite loop to keep checking for updates
while True:
    metrics_file = get_latest_metrics_file()

    if metrics_file:
        try:
            df_metrics = pd.read_csv(metrics_file)

            # --- Success Rate (Overall Metrics) ---
            with metric_placeholder.container():
                # Average metrics across all clients
                avg_dr = df_metrics['detection_rate'].mean() * 100
                avg_fpr = df_metrics['false_positive_rate'].mean() * 100
                total_caught = int(df_metrics['tp'].sum() if 'tp' in df_metrics.columns else 0)
                total_missed = int(df_metrics['fn'].sum() if 'fn' in df_metrics.columns else 0)

                if (total_caught + total_missed) > 0:
                    overall_success_rate = (total_caught / (total_caught + total_missed)) * 100
                else:
                    overall_success_rate = 0.0

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Overall Success Rate", f"{overall_success_rate:.1f}%")
                m2.metric("Attacks Prevented (TP)", f"{total_caught}")
                m3.metric("Attacks Evaded (FN)", f"{total_missed}")
                m4.metric("False Positives (FPR)", f"{avg_fpr:.1f}%")

            # --- Chart 1: Detection Rate by Client ---
            with chart_placeholder_1.container():
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=df_metrics['client_id'],
                    y=df_metrics['detection_rate'] * 100,
                    name='Detection Rate (%)',
                    marker_color='green'
                ))
                fig.update_layout(
                    title="Detection Accuracy Per Client",
                    yaxis_title="Percentage (%)",
                    plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(l=0, r=0, t=30, b=0)
                )
                st.plotly_chart(fig, use_container_width=True, key=f"bar_{time.time()}")

        except Exception as e:
            pass # Silent fail if file is locked or empty during write

    # --- Chart 2: Attack Sequences (Timeline) ---
    with chart_placeholder_2.container():
        df_ir = get_incident_response_log()
        if df_ir is not None and 'timestamp' in df_ir.columns:
            # Group attacks by timestamp for a sequence graph
            df_ir['timestamp'] = pd.to_datetime(df_ir['timestamp'])
            timeline_data = df_ir.groupby('timestamp').size().reset_index(name='attack_count')

            fig2 = px.line(timeline_data, x="timestamp", y="attack_count",
                           title="Attack Sequence / Incident Volume",
                           markers=True)
            fig2.update_traces(line_color='red')
            fig2.update_layout(plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig2, use_container_width=True, key=f"line_{time.time()}")
        else:
            st.info("Waiting for incidents to chart attack sequence...")

    # --- Incident Response Log (Table) ---
    with ir_placeholder.container():
        if df_ir is not None:
            # Drop the index and style the 'action_taken' column
            display_ir = df_ir[['timestamp', 'client_id', 'attack_type', 'action_taken', 'status']]

            def highlight_status(val):
                return 'background-color: #2e7d32; color: white' if val == 'Mitigated' else ''

            def highlight_action(val):
                if 'Block' in str(val) or 'Reset' in str(val):
                    return 'color: #d32f2f; font-weight: bold'
                return 'color: #f57c00; font-weight: bold'

            st.dataframe(
                display_ir.style.map(highlight_status, subset=['status'])
                              .map(highlight_action, subset=['action_taken']),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No attacks detected yet. Waiting for incident stream...")

    # Wait 2 seconds before reloading data
    time.sleep(2)