# MetaTag
![Metatag GUI](https://i.imgur.com/850LAhl.png)

This is a tool designed to take simple latitude/longitude JSON's and add various Google Street View metadata to them. This includes:
* Temporal data
	* Date
	* Time
	* Month
	* Year
* Geographical data
	* Country
	* State
	* Locality
	* Population[^1]
	* Elevation
* Terrestrial data
	* Solar azimuth (direction)
	* Solar altitude (height)
	* Cloud cover
	* Precipitation
	* Snow depth
* Driving direction

[^1]: Requires additional dataset. See `pop` folder for instructions.

The underlying script works around the `maps` folder; the paths can be configured in [config.json](https://github.com/ccmdi/MetaTag/blob/main/config.json). `maps/base` is a convenient folder to store all maps you work with, however you can run the script from anywhere. For any map you wish to tag, there are two options:
* ~~Run `MetaTag.exe` for a simple GUI and visualization~~
* `python metatag.py <command: tag, delete, clear> <mapfile> <arguments>`

## Installation
To enable functionality, follow these steps:
1. `git clone https://github.com/ccmdi/MetaTag.git`
2. `pip install -r requirements.txt`

Example command: `python metatag.py tag 'maps\base\Tunisia Car.json' -d`

# GUI
For any given map, simply upload the file. You will see a view showing settings to add on the left, and a simplistic map viewer on the right. Checking the checkboxes and clicking submit will run the script with for desired attributes, and refresh the map view with the new map file. It will also be outputted to the `maps/tagged` folder for external use.

# CLI
If you are running `metatag.py`, this is the list of arguments that are presently available. Each section name denotes an action, followed by the command's name.
## Tagging: `tag <file> <args>`
### Information
* `-t --time`
* `-d --date`
* `-m --month`
* `-y --year`
* `-a --country`
* `-b --state`
* `-c --locality`
* `-s --solar` Direction/altitude cardinal directions
* `-S --SOLAR` Direction/altitude exact (° rounded to nearest integer)
* `-u --clouds` Cloud cover classification (Overcast, Mostly Cloudy, Partly Cloudy, Clear)
* `-U --CLOUDS` Cloud cover exact (% rounded to nearest integer)
* `-p --precipitation` Precipitation (mm)
* `-s --snow` Snow depth (m)
* `-e --elevation` Elevation (m)
* `-D --drivingdirection` Driving direction (°)
* `-H --heading` Orient heading to \[drivingdirection, solar, `<heading>,<pitch>`\]

### Options
* `--round <int>` Integer by which to round **time** (nearest 15 min, 30 min, etc.)[^2]
* `--load` Loads date from tags
* `--accuracy <int>` Accuracy of date fetch (in seconds) -- defaults to 1
* `-n --no-cache-in` No cache input (ignores existing meta file; **this will overwrite**)
* `-N --no-cache-out` No cache output (does not create meta file)
* `-M --meta` Only creates meta file, no tagging

[^2]: Appears in tagging output only

## Deletion: `delete <file> <args>`
### Options
* `-b --base` Base file
* `-m --meta` Associated meta file
* `-t --tagged` Associated tagged file(s)
* `-c --cascade` All associated files

## Clearing tags: `clear <file>`

## Attribute tables: `extract <file> --key <key> --attr <attribute list> <args>`
* `--format [percent/count]` Format of output -- defaults to 'count'
* `--classify [direction, altitude, cloud_cover_event, none]` Post-processing classifier for attribute (can use 'none' in the case of multiple attributes)
* `--include-none` Include 'none' values for attribute as seperate column


# Integrations
Tagged files are designed for elements you want visible, in whatever application is using it. [map-making.app](https://map-making.app) is an example of an existing Street View map viewer that is quite effective, though it becomes hard to handle at more than a thousand tags. MetaTag includes metadata associated with map-making.app, like tag ordering and colors. These are enabled by default, but once again can be changed in configuration.

# Limitations
**Cloud cover, precipitation and snow depth are not precise**. These attributes are fetched at hourly intervals and rounded lat/lng with historic data from Open-Meteo. This data is fantastic and wide-ranging, but low resolution; do not expect precise results. Also, file size is a concern that is not addressed at the moment. There is often duplicate data in several places with the current setup, with the intention to isolate your data; the original file is never touched. Likewise, with plain text, file size is hardly a concern, so duplication of data shouldn't be either. However, it would be ideal to remove the need for a `tagged` folder at all.

Inspired by [this project](https://github.com/macca7224/sv-date-analyser) by macca7224.
