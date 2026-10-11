# Oil-heat winter kWh validation gap accepted for v0.1

The mock model produces ~850 kWh/month for oil-heat homes in winter versus the EIA RECS target of 1,180 kWh/month (-28%). We accept this gap for the v0.1 release rather than artificially tuning coefficients to hit the target.

The gap exists because the mock model only accounts for the electric *fraction* of space heating in oil-heated homes. Real NE oil homes have additional winter electric usage (electric water heaters, supplemental space heaters, heat tape, dehumidifiers) that varies widely by household and is not well-characterized by aggregate EIA data. Closing this gap requires per-end-use metering data (e.g., Pecan Street) that decomposes total electric usage into individual appliance categories.

We chose to document the gap rather than overfit the model because: (1) tuning one coefficient to hit one target distorts other outputs, (2) the CVAE trained on biased mock data propagates the bias, and (3) an honest failing check is more useful to downstream researchers than a falsely passing one. The validation screen in the showcase app flags this explicitly.
