import fastf1
import pandas as pd
from sqlalchemy.orm import sessionmaker
from database import engine
from models import Driver, Constructor, Circuit, Race, RaceResult, QualifyingResult, Weather, TyreStint
import os

# FastF1 cache setup
cache_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'cache')
os.makedirs(cache_dir, exist_ok=True)
fastf1.Cache.enable_cache(cache_dir)

Session = sessionmaker(bind=engine)


def save_drivers(race_results_df, session):
    for _, row in race_results_df.iterrows():
        existing = session.query(Driver).filter_by(driver_id=row['DriverId']).first()
        if not existing:
            driver = Driver(
                driver_id=row['Driver'],
                name=row['FullName'],
                nationality=row['CountryCode']
            )
            session.add(driver)
    session.commit()
    print("Drivers saved")


def save_constructors(race_results_df, session):
    for _, row in race_results_df.iterrows():
        existing = session.query(Constructor).filter_by(constructor_id=row['TeamId']).first()
        if not existing:
            constructor = Constructor(
                constructor_id=row['TeamId'],
                name=row['TeamName']
            )
            session.add(constructor)
    session.commit()
    print("Constructors saved")


def save_circuit(event, session):
    existing = session.query(Circuit).filter_by(circuit_id=event['Location']).first()
    if not existing:
        circuit = Circuit(
            circuit_id=event['Location'],
            name=event['EventName'],
            country=event['Country']
        )
        session.add(circuit)
        session.commit()
    return event['Location']


def save_race(event, year, round_number, session):
    existing = session.query(Race).filter_by(
        season=year, round=round_number
    ).first()
    if existing:
        return existing.race_id

    race = Race(
        circuit_id=event['Location'],
        season=year,
        round=round_number,
        date=event['EventDate'].date()
    )
    session.add(race)
    session.commit()
    return race.race_id


def save_race_results(race_id, race_results_df, session):
    for _, row in race_results_df.iterrows():
        result = RaceResult(
            race_id=race_id,
            driver_id=row['DriverId'],
            constructor_id=row['TeamId'],
            grid_position=int(row['GridPosition']) if pd.notna(row['GridPosition']) else None,
            finish_position=int(row['Position']) if pd.notna(row['Position']) else None,
            points=float(row['Points']) if pd.notna(row['Points']) else 0,
            points_finish=bool(row['Points'] > 0) if pd.notna(row['Points']) else False,
            status=row['Status']
        )
        session.add(result)
    session.commit()
    print(f"Race results saved for race_id {race_id}")


def save_qualifying(race_id, quali_results_df, session):
    for _, row in quali_results_df.iterrows():
        def lap_to_seconds(t):
            if pd.isna(t):
                return None
            return t.total_seconds()

        qualifying = QualifyingResult(
            race_id=race_id,
            driver_id=row['DriverId'],
            q1_time=lap_to_seconds(row['Q1']),
            q2_time=lap_to_seconds(row['Q2']),
            q3_time=lap_to_seconds(row['Q3']),
            grid_position=int(row['Position']) if pd.notna(row['Position']) else None
        )
        session.add(qualifying)
    session.commit()
    print(f"Qualifying results saved for race_id {race_id}")


def save_weather(race_id, weather_df, session):
    if weather_df.empty:
        return

    weather = Weather(
        race_id=race_id,
        air_temp=float(weather_df['AirTemp'].mean()),
        track_temp=float(weather_df['TrackTemp'].mean()),
        rainfall=bool(weather_df['Rainfall'].any()),
        humidity=float(weather_df['Humidity'].mean())
    )
    session.add(weather)
    session.commit()
    print(f"Weather saved for race_id {race_id}")


def save_tyres(race_id, laps_df, race_results_df, session):
    if laps_df.empty:
        return

    # Map driver number to driver_id
    number_to_id = dict(zip(race_results_df['DriverNumber'].astype(str), race_results_df['DriverId']))
    laps_df = laps_df.copy()
    laps_df['DriverId'] = laps_df['Driver'].map(number_to_id)

    stints = laps_df.groupby(['DriverId', 'Stint']).agg(
        compound=('Compound', 'first'),
        laps_on_tyre=('LapNumber', 'count')
    ).reset_index()

    for _, row in stints.iterrows():
        stint = TyreStint(
            race_id=race_id,
            driver_id=row['DriverId'],
            stint_number=int(row['Stint']),
            compound=row['compound'],
            laps_on_tyre=int(row['laps_on_tyre'])
        )
        session.add(stint)
    session.commit()
    print(f"Tyre stints saved for race_id {race_id}")

def extract_race(year: int, round_number: int, session: object):
    print(f"\nExtracting round {round_number} of {year}...")

    race = fastf1.get_session(year, round_number, 'R')
    race.load()

    quali = fastf1.get_session(year, round_number, 'Q')
    quali.load()

    save_drivers(race.results, session)
    save_constructors(race.results, session)

    event = race.event
    save_circuit(event, session)
    race_id = save_race(event, year, round_number, session)
    save_race_results(race_id, race.results, session)
    save_qualifying(race_id, quali.results, session)
    save_weather(race_id, race.weather_data, session)
    save_tyres(race_id, race.laps, race.results, session)

    print(f"Done: {race.event['EventName']}")


ddef extract_season(year: int):
    print(f"Starting extraction for {year} season...")
    session = Session()

    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        print(f"Found {len(schedule)} races in {year}")
        
        for round_number in range(1, len(schedule) + 1):
            # Skip if already extracted
            existing = session.query(Race).filter_by(
                season=year, round=round_number
            ).first()
            if existing:
                print(f"Round {round_number} already extracted, skipping...")
                continue
            
            extract_race(year, round_number, session)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    for year in [2023, 2024, 2025]:
        extract_season(year)