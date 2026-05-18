#!/usr/bin/env python3
"""Render an interactive 3D heat map from scans.csv."""
import argparse
import numpy as np
import pandas as pd
import plotly.graph_objects as go

DEFAULT_FLOOR_HEIGHT_M = 2.0
RSSI_MIN = -90
RSSI_MAX = -30

ORANGE_SCALE = [
    [0.0, "rgb(30,8,0)"],
    [0.25, "rgb(90,30,5)"],
    [0.5, "rgb(170,70,15)"],
    [0.75, "rgb(235,130,30)"],
    [1.0, "rgb(255,200,60)"],
]


def load(path):
    df = pd.read_csv(path)
    for col in ("x", "y", "floor", "rssi_dbm"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def aggregate(df, mode):
    """Per (floor, x, y) collapse to a single rssi_dbm value."""
    if mode == "sum_linear":
        d = df.dropna(subset=["rssi_dbm"]).copy()
        d["mw"] = 10 ** (d["rssi_dbm"] / 10)
        agg = d.groupby(["floor", "x", "y"], as_index=False)["mw"].sum()
        agg["rssi_dbm"] = 10 * np.log10(agg["mw"])
        out = agg[["floor", "x", "y", "rssi_dbm"]]
    else:
        out = df.groupby(["floor", "x", "y"], as_index=False)["rssi_dbm"].agg(mode)

    positions = df[["floor", "x", "y"]].drop_duplicates()
    return positions.merge(out, on=["floor", "x", "y"], how="left")


def build_figure(agg, floor_height, title):
    agg = agg.copy()
    agg["z"] = agg["floor"] * floor_height

    finite = agg.dropna(subset=["rssi_dbm"])
    missing = agg[agg["rssi_dbm"].isna()]

    fig = go.Figure()

    if not finite.empty:
        fig.add_trace(go.Scatter3d(
            x=finite["x"], y=finite["y"], z=finite["z"],
            mode="markers",
            marker=dict(
                size=10,
                color=finite["rssi_dbm"],
                colorscale=ORANGE_SCALE,
                cmin=RSSI_MIN, cmax=RSSI_MAX,
                colorbar=dict(
                    title=dict(text="RSSI (dBm)", font=dict(color="white")),
                    tickfont=dict(color="white"),
                ),
                opacity=0.92,
                line=dict(width=0),
            ),
            text=[f"floor {int(f)}<br>({x:g}, {y:g})<br>{r:.1f} dBm"
                  for f, x, y, r in zip(finite["floor"], finite["x"],
                                        finite["y"], finite["rssi_dbm"])],
            hoverinfo="text",
            name="eduroam",
        ))

    if not missing.empty:
        fig.add_trace(go.Scatter3d(
            x=missing["x"], y=missing["y"], z=missing["z"],
            mode="markers",
            marker=dict(size=5, color="rgb(50,50,50)", opacity=0.6,
                        line=dict(width=0)),
            text=[f"floor {int(f)}<br>({x:g}, {y:g})<br>no signal"
                  for f, x, y in zip(missing["floor"], missing["x"], missing["y"])],
            hoverinfo="text",
            name="no signal",
        ))

    fig.update_layout(
        title=dict(text=title, font=dict(color="white")),
        scene=dict(
            xaxis=dict(title="X (m)", color="white", backgroundcolor="rgb(15,15,15)",
                       gridcolor="rgb(60,60,60)"),
            yaxis=dict(title="Y (m)", color="white", backgroundcolor="rgb(15,15,15)",
                       gridcolor="rgb(60,60,60)"),
            zaxis=dict(title="height (m)", color="white",
                       backgroundcolor="rgb(15,15,15)", gridcolor="rgb(60,60,60)"),
            bgcolor="rgb(15,15,15)",
        ),
        paper_bgcolor="rgb(20,20,20)",
        font=dict(color="white"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="scans.csv")
    ap.add_argument("--out", default="heatmap.html")
    ap.add_argument("--agg", choices=["max", "mean", "sum_linear"], default="max",
                    help="how to combine multiple rows per grid point")
    ap.add_argument("--floor-height", type=float, default=DEFAULT_FLOOR_HEIGHT_M,
                    help="meters between floors for the z axis")
    ap.add_argument("--title", default="eduroam signal heat map")
    args = ap.parse_args()

    df = load(args.csv)
    agg = aggregate(df, args.agg)
    fig = build_figure(agg, args.floor_height, args.title)
    fig.write_html(args.out, include_plotlyjs="cdn")
    print(f"wrote {args.out} ({len(agg)} grid points, "
          f"{agg['rssi_dbm'].notna().sum()} with signal)")


if __name__ == "__main__":
    main()
