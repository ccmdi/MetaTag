# SV Date Tagging




Fork from [this project](https://github.com/macca7224/sv-date-analyser) by macca7224 to convert lat/lng JSONs to a "map-making.app friendly" datetimed JSON. Note this does not retrieve *exact* time, only the day. The script accepts JSONs without `imageDate` or `panoDate` metadata, but this reduces parsing speed slightly.

# Usage
1. `git clone https://github.com/ccmdi/sv-date-tagging`
2. `pip install -r requirements.txt`
3. Run `python parse_map.py <map>.json`
4. Once it's done, input `Y` to continue to tagging.
5. Your date-tagged JSON is saved in `datetime-maps/<map>.json`


TODO
numdates - how many different dates are available at this loc
copyright