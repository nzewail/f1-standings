from random import randint
from typing import List

import pandas as pd
import requests
import streamlit as st
from bokeh.models import ColumnDataSource, Legend
from bokeh.models.tools import HoverTool
from bokeh.plotting import figure

HOST = "https://ergast.com/api/f1"
CHAMPIONSHIPS = frozenset({"DriverStandings", "ConstructorStandings"})


def hit_url(url: str):
    res = requests.get(url)
    if res.status_code == 200:
        return res.json()
    raise Exception(
        "%s returned an unsuccessful status_code: %s %s"
        % (url, res.status_code, res.text)
    )


def build_url_base(season: str = "current") -> str:
    return f"{HOST}/{season}"


def standings_url(season: str, championship: str, race_round="last") -> str:
    if championship not in CHAMPIONSHIPS:
        raise Exception("%s must be in %s" % (championship, CHAMPIONSHIPS))
    return f"{build_url_base(season)}/{race_round}/{championship}.json"


def get_num_races(season: str) -> int:
    url = f"{build_url_base(season)}/last/results.json"
    response = hit_url(url)
    return int(response["MRData"]["RaceTable"]["round"])


@st.cache(show_spinner=False)
def hit_standings_api(season: str, race_round: str, championship: str) -> List[dict]:
    url = standings_url(season, championship, race_round)
    results = hit_url(url)
    return parse_standings_response(race_round, championship, results)


def get_standings(season, race_round, championship):
    standings = []
    latest_iteration = st.empty()
    bar = st.progress(0)

    for r in range(1, race_round + 1, 1):
        latest_iteration.text(f"Fetching data for round {r}")
        bar.progress(r / (race_round + 1))
        parsed_response = hit_standings_api(season, r, championship)

        standings.extend(parsed_response)
    latest_iteration.empty()
    bar.empty()
    return standings


def clean_championship_type(season_type: str) -> str:
    return standings_type[:-9]


def parse_standings_response(race_num, standings_type, response):
    standings = response["MRData"]["StandingsTable"]["StandingsLists"][0][
        standings_type
    ]
    parsed_response = []
    championship_type = clean_championship_type(standings_type)
    for r in standings:
        standing = {
            "race_num": race_num,
            "position": int(r["position"]),
            championship_type: str(
                r[championship_type][f"{championship_type.lower()}Id"].capitalize()
            ),
            "points": int(r["points"]),
        }
        parsed_response.append(standing)
    return parsed_response


st.title("F1 Season Tracker")
st.markdown("This data is courtesy of [Ergast](http://ergast.com/mrd/)")

season_dropdown = st.sidebar.slider(
    "Season", min_value=1950, max_value=2021, step=1, value=2021
)
round_slider = st.sidebar.slider(
    "Race Round",
    min_value=1,
    max_value=get_num_races(season_dropdown),
    step=1,
    value=get_num_races(season_dropdown),
)
standings_type = st.sidebar.radio("Championship", options=CHAMPIONSHIPS, index=1)

standings = get_standings(season_dropdown, round_slider, standings_type)
title = clean_championship_type(standings_type)

df = pd.DataFrame.from_records(standings)

p = figure(
    title=f"{season_dropdown} F1 {title.capitalize()} Standings after round {round_slider}",
    x_axis_label="Race Number",
    y_axis_label="Number of Points",
    tools=[HoverTool(), "save"],
    tooltips="@team: Race Number:@races Points: @points",
)

legend_it = []

for t in df[title].unique():
    driver_df = df[df[title] == t]
    color = (randint(0, 255), randint(0, 255), randint(0, 255))
    source = ColumnDataSource(
        data=dict(
            points=driver_df["points"],
            races=driver_df["race_num"],
            team=driver_df[title],
        )
    )
    c = p.line(x="races", y="points", line_width=2, line_color=color, source=source)
    points_last_race = int(driver_df[driver_df["race_num"] == round_slider]["points"])
    legend_it.append((f"{t}\t{points_last_race}", [c]))

legend = Legend(items=legend_it)
legend.click_policy = "hide"
legend.title = title.capitalize()

p.add_layout(legend, "left")

st.bokeh_chart(p, use_container_width=True)
