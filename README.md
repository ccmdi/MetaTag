# MetaTag
This is a tool designed to take simple latitude/longitude JSON's and add various Street View metadata to them. This includes:
* Temporal data
	* Date
	* Time
	* Month
	* Year
* Geographical data
	* Country
	* State
	* Locality
	* ~~Population
	* ~~Population density
* Terrestrial data
	* Solar azimuth (direction)
	* Solar altitude (height)
	* ~~Cloud cover
	* ~~Precipitation
	* ~~Snow depth
	* ~~Elevation
* Driving direction

The underlying script works around the `maps` folder; the paths can be configured in [config.json](https://github.com/ccmdi/MetaTag/blob/main/config.json). `maps/base` is a convenient folder to store all maps you work with, however you can run the script from anywhere. For any map you wish to tag, there are two options:
* Run `MetaTag.exe` for a simple GUI and visualization
* `python metatag.py <mapfile> <arguments>`

# GUI
For any given map, simply upload the file. You will see a view showing settings to add on the left, a simplistic map viewer on the right. Checking the checkboxes and clicking submit will run the script with for desired attributes, and refresh the map view with the new map file. It will also be outputted to the `maps/tagged` folder for external use.

# CLI
If you are running `metatag.py`, this is the list of arguments that are presently available. Each section name denotes an action, followed by the command's name.
## Tagging: `tag`
### Information
* `-t --time`
* `-d --date`
* `-m --month`
* `-y --year`
* `-a --country`
* `-b --state`
* `-c --locality`
* `-s --solar` Stores class-based information about the sun, such as cardinal directions
* `-S --SOLAR` Stores raw information about the sun (rounded to nearest integer)

### Options
* `--round <int>` Integer by which to round time (nearest 15min, 30min, etc.)
* `--load` Loads date from tags
* `--accuracy <int>` Accuracy of date fetch (in seconds) -- defaults to 1
* `-n --no-cache-in` No cache input
* `-N --no-cache-out` No cache output

## Deletion: `delete`
### Options
* `-b --base` Base file
* `-m --meta` Associated meta file
* `-t --tagged` Associated tagged file(s)
* `-c --cascade` All associated files
 
<p style="font-size: 12px"> Inspired by <a href="https://github.com/macca7224/sv-date-analyser" target="_blank">this project</a> by macca7224. </p>
