from random import randint
from typing import List, Tuple

import pandas as pd
import requests
import streamlit as st
from bokeh.models import ColumnDataSource, Legend
from bokeh.models.tools import HoverTool
from bokeh.plotting import figure

HOST = "https://ergast.com/api/f1"
CHAMPIONSHIPS = frozenset({"DriverStandings", "ConstructorStandings"})
FIRST_F1_SEASON = 1950


def hit_url(url: str):
    res = requests.get(url)
    if res.status_code == 200:
        return res.json()
    raise Exception(
        "%s returned an unsuccessful status_code: %s %s"
        % (url, res.status_code, res.text)
    )


def build_url_base(season) -> str:
    return f"{HOST}/{season}"


def standings_url(season: int, race_round: int, championship: str) -> str:
    if championship not in CHAMPIONSHIPS:
        raise Exception("%s must be in %s" % (championship, CHAMPIONSHIPS))
    return f"{build_url_base(season)}/{race_round}/{championship}.json"


def get_season_num_rounds(season="current") -> Tuple[int, int]:
    url = f"{build_url_base(season)}/last/results.json"
    response = hit_url(url)
    race_table = response["MRData"]["RaceTable"]
    return int(race_table["season"]), int(race_table["round"])


@st.cache(show_spinner=False)
def hit_standings_api(season: int, race_round: int, championship: str) -> List[dict]:
    url = standings_url(season, race_round, championship)
    results = hit_url(url)
    return parse_standings_response(race_round, championship, results)


def get_standings(season: int, race_round: int, championship: str) -> List[dict]:
    standings = []
    latest_iteration = st.empty()
    progress_bar = st.progress(0)

    for race in range(1, race_round + 1, 1):
        latest_iteration.text(f"Fetching data for round {race}")
        progress_bar.progress(race / (race_round + 1))
        parsed_response = hit_standings_api(season, race, championship)
        standings.extend(parsed_response)
    latest_iteration.empty()
    progress_bar.empty()
    return standings


def clean_championship_type(championship: str) -> str:
    return championship[:-9]


def parse_standings_response(race_num, championship, response):
    standings = response["MRData"]["StandingsTable"]["StandingsLists"][0][championship]
    parsed_response = []
    championship_type = clean_championship_type(championship)
    team_id = f"{championship_type.lower()}Id"
    for team in standings:
        standing = {
            "race_num": race_num,
            "position": int(team["position"]),
            championship_type: str(team[championship_type][team_id].capitalize()),
            "points": int(team["points"]),
        }
        parsed_response.append(standing)
    return parsed_response


def main():
    st.title("F1 Season Tracker")
    st.markdown("This data is courtesy of [Ergast](http://ergast.com/mrd/)")

    season, num_races = get_season_num_rounds()

    season_dropdown = st.sidebar.slider(
        "Season", min_value=FIRST_F1_SEASON, max_value=season, step=1, value=season
    )
    round_slider = st.sidebar.slider(
        "Race Round",
        min_value=1,
        max_value=num_races,
        step=1,
        value=num_races,
    )
    standings_type = st.sidebar.radio("Championship", options=CHAMPIONSHIPS, index=1)

    standings = get_standings(season_dropdown, round_slider, standings_type)
    title = clean_championship_type(standings_type)

    df = pd.DataFrame.from_records(standings)

    plot = figure(
        title=f"{season_dropdown} F1 {title.capitalize()} Standings after round {round_slider}",
        x_axis_label="Race Number",
        y_axis_label="Number of Points",
        tools=[HoverTool(), "save"],
        tooltips="""
            @team <br>
            Race Number: @races <br>
            Points: @points <br>
            Position: @position <br>
        """,
    )

    legend_it = []

    for team in df[title].unique():
        team_df = df[df[title] == team]
        color = (randint(0, 255), randint(0, 255), randint(0, 255))
        source = ColumnDataSource(
            data=dict(
                points=team_df["points"],
                races=team_df["race_num"],
                team=team_df[title],
                position=team_df["position"],
            )
        )
        line = plot.line(
            x="races", y="points", line_width=2, line_color=color, source=source
        )
        points_last_race = int(team_df[team_df["race_num"] == round_slider]["points"])
        legend_it.append((f"{team}\t{points_last_race}", [line]))

    legend = Legend(items=legend_it)
    legend.click_policy = "hide"
    legend.title = title.capitalize()

    plot.add_layout(legend, "left")

    st.bokeh_chart(plot, use_container_width=True)


if __name__ == "__main__":
    main()
