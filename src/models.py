from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Date, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Driver(Base):
    __tablename__ = 'drivers'
    
    driver_id = Column(String, primary_key=True)  # e.g. 'hamilton'
    name = Column(String, nullable=False)
    nationality = Column(String)
    date_of_birth = Column(Date)
    
    # relationships
    results = relationship('RaceResult', back_populates='driver')
    qualifying = relationship('QualifyingResult', back_populates='driver')

class Constructor(Base):
    __tablename__ = 'constructors'
    
    constructor_id = Column(String, primary_key=True)  # e.g. 'mercedes'
    name = Column(String, nullable=False)
    nationality = Column(String)
    
    # relationships
    results = relationship('RaceResult', back_populates='constructor')
    

class Circuit(Base):
    __tablename__ = 'circuits'
    
    circuit_id = Column(String, primary_key=True)  # e.g. 'monza'
    name = Column(String, nullable=False)
    location = Column(String)
    country = Column(String)
    
    # relationships
    races = relationship('Race', back_populates='circuit')


class Race(Base):
    __tablename__ = 'races'
    
    race_id = Column(Integer, primary_key=True, autoincrement=True)
    circuit_id = Column(String, ForeignKey('circuits.circuit_id'))
    season = Column(Integer, nullable=False)
    round = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    
    circuit = relationship('Circuit', back_populates='races')
    results = relationship('RaceResult', back_populates='race')
    qualifying = relationship('QualifyingResult', back_populates='race')
    weather = relationship('Weather', back_populates='race', uselist=False)
    tyre_stints = relationship('TyreStint', back_populates='race')   

class RaceResult(Base):
    __tablename__ = 'race_results'
    
    result_id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(Integer, ForeignKey('races.race_id'), nullable=False)
    driver_id = Column(String, ForeignKey('drivers.driver_id'), nullable=False)
    constructor_id = Column(String, ForeignKey('constructors.constructor_id'))
    grid_position = Column(Integer)
    finish_position = Column(Integer)
    points = Column(Float)
    points_finish = Column(Boolean)  # target variable
    status = Column(String)  # 'Finished', 'DNF', etc
    
    race = relationship('Race', back_populates='results')
    driver = relationship('Driver', back_populates='results')
    constructor = relationship('Constructor', back_populates='results')

class QualifyingResult(Base):
    __tablename__ = 'qualifying_results'
    
    qualifying_id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(Integer, ForeignKey('races.race_id'), nullable=False)
    driver_id = Column(String, ForeignKey('drivers.driver_id'), nullable=False)
    q1_time = Column(Float)
    q2_time = Column(Float)
    q3_time = Column(Float)
    grid_position = Column(Integer)
    
    race = relationship('Race', back_populates='qualifying')
    driver = relationship('Driver', back_populates='qualifying')

class Weather(Base):
    __tablename__ = 'weather'
    
    weather_id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(Integer, ForeignKey('races.race_id'), nullable=False)
    air_temp = Column(Float)
    track_temp = Column(Float)
    rainfall = Column(Boolean)
    humidity = Column(Float)
    
    race = relationship('Race', back_populates='weather')

class TyreStint(Base):
    __tablename__ = 'tyre_stints'
    
    stint_id = Column(Integer, primary_key=True, autoincrement=True)
    race_id = Column(Integer, ForeignKey('races.race_id'), nullable=False)
    driver_id = Column(String, ForeignKey('drivers.driver_id'), nullable=False)
    stint_number = Column(Integer)
    compound = Column(String)  # 'SOFT', 'MEDIUM', 'HARD'
    laps_on_tyre = Column(Integer)
    
    race = relationship('Race', back_populates='tyre_stints')