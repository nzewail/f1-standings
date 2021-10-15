from random import randint
from datetime import date
import aiohttp
import asyncio
import time
import pandas as pd
import pandas as pd
from bokeh.models import ColumnDataSource, Legend
from bokeh.models.tools import HoverTool
from bokeh.plotting import figure
from typing import Tuple
import requests

import streamlit as st

start_time = time.time()


HOST = "https://ergast.com/api/f1"
CHAMPIONSHIPS = frozenset({"DriverStandings", "ConstructorStandings"})
FIRST_F1_SEASON = 1950
CURRENT_F1_SEASON = date.today().year
PAGE_NAME = "F1 Season Tracker"


def build_url_base(season) -> str:
    return f"{HOST}/{season}"


@st.cache(show_spinner=False)
def get_season_num_rounds(season="current") -> Tuple[int, int]:
    url = f"{build_url_base(season)}/last.json"
    response = requests.get(url).json()
    race_table = response["MRData"]["RaceTable"]
    return int(race_table["season"]), int(race_table["round"])


def clean_championship_type(championship: str) -> str:
    return championship[:-9]


def parse_standings_response(response, race_num, championship):
    standings = response["MRData"]["StandingsTable"]["StandingsLists"][0][championship]
    parsed_response = []
    championship_type = clean_championship_type(championship)
    team_id = f"{championship_type.lower()}Id"
    for team in standings:
        standing = {
            "race_num": race_num,
            "position": int(team["position"]),
            championship_type: str(team[championship_type][team_id].capitalize()),
            "points": float(team["points"]),
        }
        parsed_response.append(standing)
    return parsed_response


async def get_standings(session, url, race_num, championship):
    async with session.get(url) as resp:
        pokemon = await resp.json()
        return parse_standings_response(pokemon, race_num, championship)


def render(results, championship, race_round, season):
    df = pd.DataFrame.from_records(results)
    title = clean_championship_type(championship)
    st.write(title)

    plot = figure(
        title=f"{season} F1 {title.capitalize()} Standings after Round {race_round}",
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
        plr = team_df.iloc[team_df["race_num"].argmax()]["points"]
        points_last_race = float(plr)
        legend_it.append((f"{team}\t{points_last_race}", [line]))

    legend_it.sort(reverse=True, key=lambda x: float(x[0].split("\t")[-1]))
    legend = Legend(items=legend_it)
    legend.click_policy = "hide"
    legend.title = title.capitalize()

    plot.add_layout(legend, "left")

    st.bokeh_chart(plot, use_container_width=True)


async def main():
    st.set_page_config(
        page_title=PAGE_NAME,
    )
    st.title(PAGE_NAME)
    st.markdown("This data is courtesy of [Ergast](http://ergast.com/mrd/)")

    season = st.sidebar.slider(
        "Season", min_value=FIRST_F1_SEASON, max_value=CURRENT_F1_SEASON, step=1, value=CURRENT_F1_SEASON
    )

    _, num_races = get_season_num_rounds(season)

    race_round = st.sidebar.slider(
        "Race Round",
        min_value=1,
        max_value=num_races,
        step=1,
        value=num_races,
    )
    championship = st.sidebar.radio("Championship", options=CHAMPIONSHIPS, index=1)

    async with aiohttp.ClientSession() as session:

        tasks = []
        for number in range(1, race_round):
            url = f'https://ergast.com/api/f1/{season}/{number}/{championship}.json'
            tasks.append(asyncio.ensure_future(get_standings(session, url, number, championship)))

        start_time = time.time()
        original_standings = await asyncio.gather(*tasks)
        print("--- %s seconds ---" % (time.time() - start_time))

    standings = []
    for standing in original_standings:
        standings.extend(standing)
    render(standings, championship, race_round, season)


if __name__ == '__main__':
    asyncio.run(main())
