# OpenSynth New England

A synthetic AMI dataset generator for New England residential and small commercial load profiles, contributed to the LF Energy / OpenSynth ecosystem.

## Language

### Grid domain

**AMI**:
Advanced Metering Infrastructure. The network of smart meters that records electricity consumption at regular intervals.
_Avoid_: smart grid, meter network

**Interval**:
A single 15-minute measurement period in a load profile. One day has 96 intervals; one year has 35,040.
_Avoid_: reading, sample, data point

**Load profile**:
A time series of electricity demand (kW) for a single meter across a span of intervals.
_Avoid_: consumption curve, demand curve, usage pattern

**Net load**:
The metered demand after subtracting behind-the-meter generation (solar, battery discharge). Can go negative during export.
_Avoid_: net demand, net consumption

**Gross load**:
Total electrical demand before subtracting behind-the-meter generation.
_Avoid_: total load, raw load

### Conditioning variables

**Archetype**:
A housing type that determines the baseline load shape and scale. One of eight types: colonial, cape, ranch, multi-family, antique, split-level, contemporary, mobile home.
_Avoid_: building type, housing class, dwelling type

**Fuel type**:
The primary heating fuel, which determines the electric share of heating load. One of: oil, natural gas, electric resistance, heat pump.
_Avoid_: heating source, energy source

**DER**:
Distributed Energy Resource. Behind-the-meter equipment that generates, stores, or shifts load: rooftop solar, EV charger, battery. Each is a boolean flag on a meter profile.
_Avoid_: distributed generation, on-site generation (too narrow, excludes EV/battery)

**Base type**:
A unique combination of archetype + fuel type + DER configuration. The dataset has 96 base types (8 x 4 x 3).
_Avoid_: profile type, category, segment

### Load components

**Baseload**:
Always-on electricity demand (refrigerator, standby, lighting). Present in every interval regardless of weather or behavior.

**Heating load**:
Electric demand driven by space heating. Scales with heating degree days and the fuel type's electric share.

**Cooling load**:
Electric demand from air conditioning. Low in New England due to limited AC saturation in older housing stock.

**Behavioral load**:
Occupant-driven demand (cooking, laundry, entertainment). Peaks at morning and evening activity periods.
_Avoid_: appliance load (ambiguous, baseload appliances are separate)

### Project artifacts

**Static dataset**:
The v1.0 fixed release of 10,000 synthetic meter profiles covering a full year, published as Hive-partitioned Parquet.
_Avoid_: snapshot, data dump

**Conditional generator**:
The trained model (CVAE) and its Python API that produces new synthetic profiles on demand, conditioned on archetype, fuel, weather, and DER.
_Avoid_: model, generator (too generic without "conditional")

**Showcase app**:
The React + FastAPI web application that demonstrates the conditional generator interactively. Not part of the OpenSynth contribution.
_Avoid_: demo, frontend, dashboard
