import streamlit as st
import requests
import pandas as pd
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, Legend
from bokeh.models.tools import HoverTool
from random import randint

HOST = "https://ergast.com/api/f1"
STANDINGS_TYPE = frozenset({"DriverStandings", "ConstructorStandings"})


def build_url_base(season="current") -> str:
    return f"{HOST}/{season}"


def standings_url(season, standings_type, race_round="last") -> str:
    if standings_type not in STANDINGS_TYPE:
        raise Exception("%s must be in %s" % standings_type, STANDINGS_TYPE)
    return f"{build_url_base(season)}/{race_round}/{standings_type}.json"


def get_num_races(season):
    url = f"{build_url_base(season)}/last/results.json"
    response = requests.get(url).json()
    return int(response['MRData']['RaceTable']['round'])


@st.cache(show_spinner=False)
def hit_standings_api(season, race_round, standings_type):
    url = standings_url(season, standings_type, race_round)
    results = requests.get(url)
    return parse_standings_response(race_round, standings_type, results.json())


def get_standings(season, race_round, standings_type):
    standings = []
    latest_iteration = st.empty()
    bar = st.progress(0)

    for r in range(1, race_round+1, 1):
        latest_iteration.text(f'Fetching data for round {r}')
        bar.progress(r/(race_round+1))
        parsed_response = hit_standings_api(season, r, standings_type)
        
        standings.extend(parsed_response)
    latest_iteration.empty()
    bar.empty()
    return standings


def clean_championship_type(season_type: str) -> str:
    return standings_type[:-9]


def parse_standings_response(race_num, standings_type, response):
    standings = response['MRData']['StandingsTable']['StandingsLists'][0][standings_type]
    parsed_response = []
    championship_type = clean_championship_type(standings_type)
    for r in standings:
        standing = {
            'race_num': race_num,
            'position': int(r['position']),
            championship_type: str(r[championship_type][f"{championship_type.lower()}Id"].capitalize()),
            'points': int(r['points'])
        }
        parsed_response.append(standing)
    return parsed_response


st.title("F1 Season Tracker")
st.markdown("This data is courtesy of [Ergast](http://ergast.com/mrd/)")

season_dropdown = st.sidebar.slider('Season', min_value=1950, max_value=2021, step=1, value=2021)
round_slider = st.sidebar.slider('Race Round', min_value=1, max_value=get_num_races(season_dropdown), step=1, value=get_num_races(season_dropdown))
standings_type = st.sidebar.radio('Championship', options=STANDINGS_TYPE, index=1)

standings = get_standings(season_dropdown, round_slider, standings_type)
title = clean_championship_type(standings_type)

df = pd.DataFrame.from_records(standings)

p = figure(
    title=f'{season_dropdown} F1 {title.capitalize()} Standings after round {round_slider}',
    x_axis_label='Race Number',
    y_axis_label='Number of Points',
    tools=[HoverTool(), 'save'],
    tooltips="@team: Race Number:@races Points: @points",
)

legend_it = []

for t in df[title].unique():
    driver_df = df[df[title] == t]
    color = (randint(0, 255), randint(0, 255), randint(0, 255))
    source = ColumnDataSource(data=dict(points=driver_df['points'], races=driver_df['race_num'], team=driver_df[title]))
    c = p.line(x='races', y='points', line_width=2, line_color=color, source=source)
    points_last_race = int(driver_df[driver_df['race_num'] == round_slider]['points'])
    legend_it.append((f"{t}\t{points_last_race}", [c]))

legend = Legend(items=legend_it)
legend.click_policy = 'hide'
legend.title = title.capitalize()

p.add_layout(legend, 'left')

st.bokeh_chart(p, use_container_width=True)
