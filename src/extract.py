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


def _valid_driver_id(driver_id) -> bool:
    if pd.isna(driver_id):
        return False
    return str(driver_id).strip().lower() not in ('', 'nan', 'none')


def save_drivers(race_results_df, session):
    for _, row in race_results_df.iterrows():
        if not _valid_driver_id(row['DriverId']):
            continue
        existing = session.query(Driver).filter_by(driver_id=row['DriverId']).first()
        if not existing:
            driver = Driver(
                driver_id=row['DriverId'],
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
        existing = session.query(RaceResult).filter_by(
            race_id=race_id, driver_id=row['DriverId']
        ).first()
        if existing:
            continue

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


def save_qualifying(race_id, quali_results_df, race_results_df, session):
    number_to_id = dict(zip(
        race_results_df['DriverNumber'].astype(str),
        race_results_df['DriverId'],
    ))

    for _, row in quali_results_df.iterrows():
        driver_id = row['DriverId']
        if not _valid_driver_id(driver_id):
            driver_id = number_to_id.get(str(row['DriverNumber']))
        if not _valid_driver_id(driver_id):
            print(f"Skipping qualifying for driver number {row['DriverNumber']} — no valid driver_id")
            continue

        existing = session.query(QualifyingResult).filter_by(
            race_id=race_id, driver_id=driver_id
        ).first()
        if existing:
            continue

        def lap_to_seconds(t):
            if pd.isna(t):
                return None
            return t.total_seconds()

        qualifying = QualifyingResult(
            race_id=race_id,
            driver_id=driver_id,
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
    
    existing = session.query(Weather).filter_by(race_id=race_id).first()
    if existing:
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


def save_tyre_stints(race_id, laps_df, race_results_df, session):
    if laps_df.empty:
        return

    number_to_id = dict(zip(
        race_results_df['DriverNumber'].astype(str),
        race_results_df['DriverId'],
    ))
    laps_df = laps_df.copy()
    laps_df['DriverId'] = laps_df['DriverNumber'].astype(str).map(number_to_id)
    laps_df = laps_df.dropna(subset=['DriverId'])

    stints = laps_df.groupby(['DriverId', 'Stint']).agg(
        compound=('Compound', 'first'),
        laps_on_tyre=('LapNumber', 'count'),
    ).reset_index()

    saved = 0
    for _, row in stints.iterrows():
        stint_number = int(row['Stint'])
        existing = session.query(TyreStint).filter_by(
            race_id=race_id,
            driver_id=row['DriverId'],
            stint_number=stint_number,
        ).first()
        if existing:
            continue

        stint = TyreStint(
            race_id=race_id,
            driver_id=row['DriverId'],
            stint_number=stint_number,
            compound=row['compound'],
            laps_on_tyre=int(row['laps_on_tyre']),
        )
        session.add(stint)
        saved += 1

    if saved:
        session.commit()
        print(f"Tyre stints saved for race_id {race_id} ({saved} new)")

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
    save_qualifying(race_id, quali.results, race.results, session)
    save_weather(race_id, race.weather_data, session)
    save_tyre_stints(race_id, race.laps, race.results, session)

    print(f"Done: {race.event['EventName']}")


def backfill_tyre_stints(years: list[int] | None = None):
    session = Session()
    try:
        query = session.query(Race).order_by(Race.season, Race.round)
        if years:
            query = query.filter(Race.season.in_(years))
        races = query.all()

        for race in races:
            existing = session.query(TyreStint).filter_by(race_id=race.race_id).first()
            if existing:
                print(f"Tyre stints already exist for {race.season} R{race.round}, skipping...")
                continue

            print(f"Backfilling tyre stints for {race.season} round {race.round}...")
            ff1_race = fastf1.get_session(race.season, race.round, 'R')
            ff1_race.load()
            save_tyre_stints(race.race_id, ff1_race.laps, ff1_race.results, session)
    finally:
        session.close()


def extract_season(year: int):
    print(f"Starting extraction for {year} season...")
    session = Session()

    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        print(f"Found {len(schedule)} races in {year}")
        
        for round_number in range(1, len(schedule) + 1):
            extract_race(year, round_number, session)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract F1 data into the database")
    parser.add_argument(
        "--backfill-tyres",
        action="store_true",
        help="Backfill tyre_stints for races already in the database",
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2023, 2024, 2025],
    )
    args = parser.parse_args()

    if args.backfill_tyres:
        backfill_tyre_stints(args.years)
    else:
        for year in args.years:
            extract_season(year)