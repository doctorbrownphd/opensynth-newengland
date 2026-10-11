# Single repo for package and showcase app

The `opensynth-newengland` repo contains both the Python package (`src/opensynth_ne/`) and the React + FastAPI showcase web app (`web/`). We considered splitting the showcase app into a separate repo under Linux Energy, but the app's primary purpose is demonstrating the package — keeping them together means one clone, one CI pipeline, and the app always stays in sync with the API it calls. The showcase app is not part of the OpenSynth contribution; it is a separate concern that happens to live in the same repo.
