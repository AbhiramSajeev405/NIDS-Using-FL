import os
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import plotly.graph_objects as go
import glob

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = dash.Dash(__name__, title="FL-NIDS Dashboard")

app.layout = html.Div([
    html.H1("Federated Learning NIDS - Live Attack Dashboard", style={'textAlign': 'center', 'color': '#2c3e50', 'fontFamily': 'Arial'}),

    html.Div([
        html.Div([
            html.H3("Overall Detection Metrics"),
            dcc.Graph(id='metrics-bar-chart')
        ], style={'width': '48%', 'display': 'inline-block'}),

        html.Div([
            html.H3("Recent Attack Traffic & Detections"),
            html.Div(id='live-attack-table', style={'height': '400px', 'overflowY': 'scroll'})
        ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'})
    ]),

    # Auto-refresh every 2 seconds
    dcc.Interval(
        id='interval-component',
        interval=2*1000,
        n_intervals=0
    )
], style={'padding': '20px'})


def get_latest_metrics_file():
    logs_dir = os.path.join(_PROJECT_ROOT, "utils", "logs")
    if not os.path.exists(logs_dir):
        return None
    files = glob.glob(os.path.join(logs_dir, "*.csv"))
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
    # Just grab the most recently modified attack file for the table preview
    return max(files, key=os.path.getctime)

@app.callback(
    Output('metrics-bar-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_metrics_graph(n):
    metrics_file = get_latest_metrics_file()
    if not metrics_file:
        return go.Figure().update_layout(title="No metrics data found yet. Run an experiment.")

    try:
        df = pd.read_csv(metrics_file)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df['client_id'],
            y=df['detection_rate'] * 100,
            name='Detection Rate (%)',
            marker_color='green'
        ))
        fig.add_trace(go.Bar(
            x=df['client_id'],
            y=df['false_positive_rate'] * 100,
            name='False Positive Rate (%)',
            marker_color='red'
        ))

        fig.update_layout(
            barmode='group',
            yaxis_title="Percentage (%)",
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig
    except Exception as e:
        return go.Figure().update_layout(title=f"Error reading metrics: {str(e)}")

@app.callback(
    Output('live-attack-table', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_table(n):
    attack_file = get_latest_simulated_attack_file()
    if not attack_file:
        return html.P("Waiting for attack traffic to be simulated...")

    try:
        df = pd.read_csv(attack_file)
        # Filter to just show rows that are attacks (label == 1) to simulate the "attack viewer"
        attacks_df = df[df['label'] == 1].tail(15) # show last 15

        if attacks_df.empty:
            return html.P("No attacks found in the latest stream.")

        # Create a simple HTML table
        return html.Table(
            # Header
            [html.Tr([html.Th(col) for col in ['protocol', 'flow_duration', 'tot_fwd_pkts', 'Status']])] +
            # Body
            [html.Tr([
                html.Td(row['protocol']),
                html.Td(f"{row['flow_duration']:.2f}"),
                html.Td(f"{row['tot_fwd_pkts']:.0f}"),
                html.Td("⚠️ ATTACK DETECTED", style={'color': 'red', 'fontWeight': 'bold'})
            ]) for _, row in attacks_df.iterrows()],
            style={'width': '100%', 'textAlign': 'left', 'borderCollapse': 'collapse'}
        )
    except Exception as e:
        return html.P(f"Error reading attack data: {str(e)}")

if __name__ == '__main__':
    print("Starting FL-NIDS Dashboard at http://127.0.0.1:8050/")
    app.run(debug=True, port=8050)
