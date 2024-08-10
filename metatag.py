# IO
from pathlib import Path
import csv, json
import argparse
from os import path as os_path, remove as os_remove
import re

# Implicit processing
from datetime import datetime as dt, timedelta
from time import time, localtime
from timezonefinder import TimezoneFinder
from pytz import utc, timezone
import calendar
from pysolar.solar import get_altitude, get_azimuth

# Explicit processing
import asyncio, aiohttp
from aiolimiter import AsyncLimiter
from tqdm import tqdm
import logging
from collections import defaultdict

# Local
from sv_map import SVMap, Classifier, verify_extra, force_extra, clear_tags
from get_date import find_accurate_timestamp

FILE = Path(__file__).parent
CONFIG = json.load(open(FILE / 'config.json', 'r'))
FOLDERS = {
    'base': {
        'path': (FILE / CONFIG['path']['base']).resolve(),
        'files': None,
        'exists': False
    },
    'meta': {
        'path': (FILE / CONFIG['path']['meta']).resolve(),
        'files': None,
        'exists': False
    },
    'tagged': {
        'path': (FILE / CONFIG['path']['tagged']).resolve(),
        'files': None,
        'exists': False
    },
    'views': {
        'path': (FILE / CONFIG['path']['views']).resolve(),
        'files': None,
        'exists': False
    }
}
DEBUG = CONFIG['debug']
if DEBUG:
    if DEBUG == True: DEBUG = 0
    logging.basicConfig(level=CONFIG['debug'], format='%(asctime)s - %(levelname)s - %(message)s')


for folder in FOLDERS.values():
    if not os_path.exists(folder['path']):
        raise FileNotFoundError(f"Path {folder['path']} does not exist")



class ArgParser:
    def __init__(self):
        self.parser = argparse.ArgumentParser()
        self.SHORT_ARGS = {}
        self.args_by_group = {}

        # Create subparsers
        self.subparsers = self.parser.add_subparsers(dest='command', required=True)

        # Tag subparser (main process)
        self.tag_parser = self.subparsers.add_parser('tag', help='Tag a file')
        self.add_tag_arguments(self.tag_parser)

        self.delete_parser = self.subparsers.add_parser('delete', help='Delete a file')
        self.add_delete_arguments(self.delete_parser)

        self.clear_parser = self.subparsers.add_parser('clear', help='Clear tags for meta file')
        self.add_clear_arguments(self.clear_parser)
        
        self.extract_parser = self.subparsers.add_parser('extract', help='Extract attributes as table')
        self.add_extract_arguments(self.extract_parser)

        self.args = self.parser.parse_args()
        self.userparser =  self.subparsers.choices[self.args.command]
        self.filepath = Path(self.args.file)

        # Cache
        if self.args.command == 'tag' or self.args.command == 'extract':
            self.cached_file = (FOLDERS['meta']['path'] / self.filepath.name).absolute()
            if str(FOLDERS['base']['path']) in str(self.filepath.absolute())  and self.cached_file.exists() and ((hasattr(self.args, 'no_cache_in',) and not self.args.no_cache_in) or not hasattr(self.args, 'no_cache_in')):
                print("Found cached file")
                self.cached = True
            else:
                self.cached = False

        for action in self.userparser._actions:
            if len(action.option_strings) == 2:
                long_arg = max(action.option_strings, key=len).replace('--', '')
                short_arg = min(action.option_strings, key=len).replace('-', '')
                if long_arg != 'help' and long_arg != 'no-cache-in' and long_arg != 'no-cache-out':
                    self.SHORT_ARGS[long_arg] = short_arg

    def add_tag_arguments(self, parser):
        self.add_argument(parser, 'file', type=str, help='Path to CSV or JSON file', group='files')
        self.add_argument(parser, '-n', '--no-cache-in', action='store_true', help='No cache input', group='files')
        self.add_argument(parser, '-N', '--no-cache-out', action='store_true', help='No cache output', group='files')
        self.add_argument(parser, '-M', '--meta', action='store_true', help='Meta file only', group='files')
        self.add_argument(parser, '-o', '--overwrite', action='store_true', help='Overwrite tags', group='files')

        self.add_argument(parser, '--color', type=str, help='Colorscale color', default="red", group='cosmetic')
        self.add_argument(parser, '--color2', type=str, help='Colorscale color 2', default="red", group='cosmetic')

        self.add_argument(parser, '-t','--time', action='store_true', group='temporal')
        self.add_argument(parser, '-d','--date', action='store_true', group='temporal')
        self.add_argument(parser, '-m', '--month', action='store_true', group='temporal')
        self.add_argument(parser, '-y', '--year', action='store_true', group='temporal')
        self.add_argument(parser, '--round', type=int, help='Round to nearest minute', group='temporal')
        self.add_argument(parser, '--load', action='store_true', help='Load date from tags', group='temporal')
        self.add_argument(parser, '--accuracy', type=int, default=1, help='Accuracy of date retrieval (in seconds)', group='temporal')
        
        self.add_argument(parser, '-a', '--country', action='store_true', group='geographical')
        self.add_argument(parser, '-b', '--state', action='store_true', group='geographical')
        self.add_argument(parser, '-c', '--locality', action='store_true', group='geographical')
        self.add_argument(parser, '-e', '--elevation', action='store_true', group='geographical')

        self.add_argument(parser, '-s','--solar', action='store_true', group='terrestrial')
        self.add_argument(parser, '-S','--SOLAR', action='store_true', group='terrestrial')
        self.add_argument(parser, '-u','--clouds', action='store_true', group='terrestrial')
        self.add_argument(parser, '-U', '--CLOUDS', action='store_true', group='terrestrial')
        self.add_argument(parser, '-p', '--precipitation', action='store_true', group='terrestrial')
        self.add_argument(parser, '-w', '--snow', action='store_true', group='terrestrial')

        self.add_argument(parser, '-H', '--heading', type=str, default=None, help='Update heading; orient towards object i.e. solar')
        self.add_argument(parser, '-D', '--drivingdirection', action='store_true', help='Update driving direction')

    def add_delete_arguments(self, parser):
        self.add_argument(parser, 'file', type=str, help='Path to file to delete')
        self.add_argument(parser, '-b', '--base', action='store_true', help='Delete base file')
        self.add_argument(parser, '-m', '--meta', action='store_true', help='Delete meta file')
        self.add_argument(parser, '-t', '--tagged', action='store_true', help='Deleted tagged file(s)')
        self.add_argument(parser, '-c', '--cascade', action='store_true', help='Delete all associated files')
    
    def add_clear_arguments(self, parser):
        self.add_argument(parser, 'file', type=str, help='Path to file to clear')

    def add_extract_arguments(self, parser):
        self.add_argument(parser, 'file', type=str, help='Path to JSON file to extract from')
        self.add_argument(parser, '--key', type=str, required=True, help='Key for rows')
        self.add_argument(parser, '--attr', type=str, nargs='+', required=True, help='Keys to extract from JSON for columns')
        self.add_argument(parser, '--format', choices=['percent', 'count'], default='count', help='Format of the output (percent or count)')
        self.add_argument(parser, '--classify', nargs='*', help='Post-processing classifier types (one per attribute, use "none" to skip)')
        self.add_argument(parser, '--include-none', action='store_true', help='Include None values as a separate category')

    def add_argument(self, parser, *args, **kwargs):
        group = kwargs.pop('group', None)
        action = parser.add_argument(*args, **kwargs)
        if group:
            if group not in self.args_by_group:
                self.args_by_group[group] = []
            self.args_by_group[group].append(action.dest)
    
    def group_true(self, group):
        return any(getattr(self.args, arg) is True for arg in self.args_by_group.get(group, []))
    

class MetaTag:
    """
    Class for handling tagging of SVMap metadata.
    """

    def __init__(self, map_obj, arg_parser): 
        self.arg_parser = arg_parser
        self.args = arg_parser.args
        self.map = map_obj

        self.start_time = time()
        self.attr_sets = {
            'dates': set(),
            'altitudes': set(),
            'azimuths': set(),
            'cloudCover': set(),
            'elevation': set()
        }
        
        self.tf = TimezoneFinder()
        self.datestring = self.datestring()
        self.offset = 0

        self.color = SVMap.COLORS[self.args.color]
        self.color2 = SVMap.COLORS[self.args.color2] if self.args.color2!=self.args.color else [int(comp / 4) for comp in SVMap.COLORS[self.args.color]]

        self.metatag()

    def metatag(self):
        """
        Performs JSON tagging.
        """
        try:
            now = dt.now().timestamp()

            # Data processing
            for i, item in enumerate(self.map.locs):
                try:
                    lat, lng = float(item['lat']), float(item['lng'])
                    tags = []

                    if self.arg_parser.group_true('temporal'):
                        unix_time = float(item['timestamp'])
                        if not (now - (20 * 365 * 24 * 60 * 60) <= unix_time <= now):
                            raise ValueError(f"Invalid UNIX time at line {i+2}: {unix_time}")
                        
                        timestamp = self.tz_datestring(lat, lng, unix_time, self.args.round)
                        tags.append(timestamp)
                        self.attr_sets['dates'].add(timestamp)

                    if self.arg_parser.group_true('geographical'):
                        tags.extend(filter(None, [
                            item.get('country') if self.args.country else None,
                            item.get('state') if self.args.state else None,
                            item.get('locality') if self.args.locality else None
                        ]))

                    if self.args.drivingdirection:
                        driving_direction = item.get('drivingDirection')
                        if driving_direction:
                            tags.append("DRIVING " + Classifier.direction(driving_direction))

                    if self.args.solar or self.args.SOLAR:
                        try:
                            altitude = round(float(item['altitude']))
                            azimuth = round(float(item['azimuth']))
                            altitude_class = str(item['altitudeClass'])
                            azimuth_class = str(item['azimuthClass'])
                            sun_event = item['sunEvent']

                            if self.args.solar:
                                tags.extend([f"#{altitude_class}", f"@{azimuth_class}"])
                                if sun_event:
                                    tags.append(sun_event)
                            if self.args.SOLAR:
                                altitude_str, azimuth_str = f"{altitude} #", f"{azimuth} @"
                                tags.extend([altitude_str, azimuth_str])
                                self.attr_sets['altitudes'].add(altitude_str)
                                self.attr_sets['azimuths'].add(azimuth_str)
                        except KeyError:
                            if self.arg_parser.cached:
                                raise SVMap.CacheError()
                            else:
                                raise ValueError("Solar data not found")

                    if self.args.clouds or self.args.CLOUDS:
                        cloud_cover = item.get('cloudCover')
                        if self.args.clouds and 'cloudCoverClass' in item:
                            tags.append(str(item['cloudCoverClass']))
                        if self.args.CLOUDS and cloud_cover:
                            cloud_tag = f"CLOUD {cloud_cover}"
                            tags.append(cloud_tag)
                            self.attr_sets['cloudCover'].add(cloud_tag)

                    if self.args.precipitation and 'precipitation' in item:
                        precipitation = item['precipitation']
                        if precipitation and precipitation > 0:
                            tags.append(f"PRCP {precipitation}")

                    if self.args.snow and 'snowDepth' in item:
                        snow_depth = item['snowDepth']
                        if snow_depth and snow_depth > 0:
                            tags.append(f"SNOW {snow_depth}")

                    if self.args.elevation and 'elevation' in item:
                        elevation = item['elevation']
                        if elevation:
                            elevation_str = f"ELEV {round(float(elevation))}"
                            tags.append(elevation_str)
                            self.attr_sets['elevation'].add(elevation_str)

                    if tags:
                        if verify_extra(item, tags=True):
                            item["extra"]["tags"].extend(tags)
                        else:
                            item = force_extra(item, tags=tags)
                            item["extra"]["tags"] = tags

                except SVMap.CacheError as e:
                    logging.error(e)
                    exit(1)
                except Exception as e:
                    logging.error(e)

            logging.info("Purge map")
            self.map.purge()
            if not CONFIG['mapMakingAppStyles']:
                return

            self.map.verify_map_styles()

            logging.info("Order tags - temporal")
            if self.arg_parser.group_true('temporal'):
                sorted_dates = self.order_tags(self.attr_sets['dates'])
                self.offset += sorted_dates[2]
                # print("Datetime span:", sorted_dates[0], "to", sorted_dates[1])

            logging.info("Order tags - solar")
            if self.args.SOLAR:
                sorted_altitude = self.order_tags(self.attr_sets['altitudes'], sortby='parseint')
                self.offset += sorted_altitude[2]
                sorted_azimuth = self.order_tags(self.attr_sets['azimuths'], sortby='parseint')
                self.offset += sorted_azimuth[2]
            
            logging.info("Order tags - clouds")
            if self.args.CLOUDS:
                sorted_cloud_cover = self.order_tags(self.attr_sets['cloudCover'], sortby='parseint')
                self.offset += sorted_cloud_cover[2]
            
            logging.info("Order tags - elevation")
            if self.args.elevation:
                sorted_elevation = self.order_tags(self.attr_sets['elevation'], sortby='parseint')
                self.offset += sorted_elevation[2]

        except Exception as e:
            logging.error(f'Error: {e}')
            exit(1)

    def tz_datestring(self, lat, lng, unix_time, roundt=False):
        """
        Generates a timezone-aware date string.

        Args:
            lat (float): The latitude.
            lng (float): The longitude.
            unix_time (float): The UNIX timestamp.
            roundt (bool): Whether to round the time.

        Returns:
            str: The generated date string.
        """
        timezone_str = self.tf.timezone_at(lng=lng, lat=lat) if self.args.time else None
        if timezone_str:
            q = dt.fromtimestamp(unix_time, timezone(timezone_str))
            if roundt:
                discard = timedelta(minutes=q.minute % roundt,
                             seconds=q.second,
                             microseconds=q.microsecond)
                q -= discard
                if discard >= timedelta(minutes=roundt/2):
                    q += timedelta(minutes=roundt)
        else:
            lt = localtime(unix_time)
            q = dt(lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour, lt.tm_min, lt.tm_sec)

        return q.strftime(self.datestring if self.datestring else '%Y-%m-%d %H:%M')

    def datestring(self):
        """
        Returns the appropriate date format string.

        Returns:
            str: The date format string.
        """
        if self.args.time and not self.args.date:
            return '%H:%M'
        elif self.args.date and not self.args.time:
            return '%Y-%m-%d'
        elif self.args.date and self.args.time:
            return '%Y-%m-%d %H:%M'
        elif self.args.month:
            return '%Y-%m'
        elif self.args.year:
            return '%Y'
        else:
            return None

    def order_tags(self, attribute_set, sortby='date'):
        """
        Orders the tags based on the specified attribute set and sort order.

        Args:
            attribute_set (set): The set of attributes to be ordered.
            sortby (str): The sort order.

        Returns:
            list: A list containing the start value, end value, and offset.
        """
        if sortby == 'date':
            sli = sorted(list(attribute_set), key=lambda i: dt.strptime(i, self.datestring) if self.datestring else i)
        elif sortby == 'parseint':
            sli = sorted(list(attribute_set), key=lambda i: int(re.search(r'-?\d+', i).group()) if int(re.search(r'-?\d+', i).group()) else i)
        start = sli[0]
        end = sli[-1]
        i = 0 if self.offset == 0 else 1

        for i, item in enumerate(sli):
            self.map.data["extra"]["tags"][item] = {"order": i+self.offset}
            color_scale = [int(start + (end - start) * (i / len(sli))) for start, end in zip(self.color2, self.color)]
            self.map.data["extra"]["tags"][item]['color'] = color_scale
        return [start, end, i]

class MetaFetchParser:
    def __init__(self, map_obj, args, radius=30, chunk_size=15):
        # Constants
        self.RADIUS = radius
        self.CHUNK_SIZE = chunk_size
        
        # Variables
        self.map = map_obj
        self.err = 0
        self.arg_parser = args
        self.args = args.args

        self.PROCESS_NAMES = {
            self.fetch_meta: "Metadata fetch",
            self.timestamp: "Timestamp",
            self.solar: "Solar",
            self.weather: "Weather"
        }


    async def timestamp(self, loc, progress):
        try:
            lat, lng = loc['lat'], loc['lng']
            month = None
            loc = force_extra(loc, tags=True)

            if loc.get('imageDate'):
                month = loc['imageDate']
            elif loc.get('extra').get('panoDate'):
                month = loc['extra']['panoDate']
            elif loc.get('timestamp'):
                month = dt.fromtimestamp(loc['timestamp'], utc).strftime('%Y-%m')
            elif self.args.load and loc.get('extra').get('tags'):
                tags = loc['extra']['tags']
                months = [month.lower() for month in calendar.month_name[1:]] + [month.lower() for month in calendar.month_abbr[1:]]
                years = [str(year) for year in range(2007,  dt.now().year+1)]

                matching_month = next((tag for tag in tags if tag.lower() in months), None)
                matching_year = next((tag for tag in tags if tag in years), None)

                if matching_month and matching_year:
                    month_number = str(dt.strptime(matching_month, '%b' if len(matching_month) == 3 else '%B').month).zfill(2)
                    month = matching_year + "-" + month_number
                
            if month:
                if not loc.get('timestamp'):
                    timestamp = await find_accurate_timestamp(lat, lng, month, self.RADIUS, self.args.accuracy)
                    loc['timestamp'] = timestamp
            else:
                raise Exception("Unable to date image "+str(lat), str(lng))

        except Exception as e:
            logging.error(e)
            self.err += 1
            self.map.locs.remove(loc)
            progress.update(1)
            return None
        progress.update(1)
        return loc
    
    async def fetch_meta(self, loc, progress):
        lat, lng = loc['lat'], loc['lng']

        if (
            (('imageDate' in loc or 'timestamp' in loc) and (self.arg_parser.group_true('temporal') or self.arg_parser.group_true('terrestrial'))) or
            ('country' in loc and self.args.country) or
            (self.args.drivingdirection and 'drivingDirection' in loc)
        ) and not self.args.no_cache_in:
            progress.update(1)
            return loc

        async with aiohttp.ClientSession() as session:
            try:
                imagePayload = f"""
                [
                    ["apiv3", null, null, null, "US", null, null, null, null, null],
                    [
                        [null, null, {lat}, {lng}],
                        {self.RADIUS}
                    ],
                    [
                        null,
                        ["en", "US"],
                        null,
                        null,
                        null,
                        null,
                        null,
                        null,
                        [2],
                        null,
                        [
                            [
                                [2, true, 2]
                            ]
                        ]
                    ],
                    [
                        [2, 6]
                    ]
                ]
                """

                async with session.post(
                    'https://maps.googleapis.com/$rpc/google.internal.maps.mapsjs.v1.MapsJsInternalService/SingleImageSearch',
                    headers={'content-type': 'application/json+protobuf'},
                    data=imagePayload,
                ) as response:
                    res = await response.text()
                    loads = json.loads(res)
                    
                    # Driving direction
                    try:
                        loc['drivingDirection'] = loads[1][5][0][3][0][4][2][2][0]
                    except IndexError:
                        loc['drivingDirection'] = None

                    # Elevation
                    try:
                        loc['elevation'] = loads[1][5][0][3][0][2][2][1][0]
                    except IndexError:
                        loc['elevation'] = None

                    # Country
                    try:
                        country = loads[1][5][0][1][4]
                    except IndexError:
                        country = None

                    # Subdivisions
                    try:
                        if loads[1][3][2] is not None and len(loads[1][3][2]) > 1:
                            subdivision = loads[1][3][2][1][0]
                        else:
                            subdivision = loads[1][3][2][0][0] if loads[1][3][2] is not None else None
                        subdivision = subdivision.split(', ') if subdivision else None
                    except IndexError:
                        subdivision = None
                                            
                    state = subdivision[-1] if subdivision else None
                    locality = subdivision[-2] if subdivision and len(subdivision) > 1 else None

                    loc['country'] = country
                    loc['state'] = state
                    loc['locality'] = locality

                    # Image date
                    try:
                        month = str(loads[1][6][7][0])+"-"+str(loads[1][6][7][1])
                    except IndexError:
                        month = None
                    loc['imageDate'] = month

                    # Pano ID
                    try:
                        loc['panoId'] = loads[1][1][1]
                    except IndexError:
                        loc['panoId'] = None

                    if self.args.heading:
                        if self.args.heading == "drivingdirection":
                            loc['heading'] = loc.get('drivingDirection', 0)
                        elif ',' in self.args.heading:
                            try:
                                heading, pitch = map(int, self.args.heading.split(','))
                                loc.update({
                                    'heading': heading % 360,
                                    'pitch': pitch % 90
                                })
                            except:
                                raise ValueError("Invalid 'heading,pitch' tuple")

            except Exception as e:
                logging.error(e)
                self.err += 1
                self.map.locs.remove(loc)
                progress.update(1)
                return None

            progress.update(1)
            return loc

    async def solar(self, loc, progress):
        lat, lng = loc['lat'], loc['lng']
        if not loc.get('timestamp'):
            raise ValueError("Timestamp not found")
        
        timestamp = loc['timestamp']
        timestamp_date = dt.fromtimestamp(timestamp, utc)
        try:
            if not loc.get('altitude') or not loc.get('azimuth'):
                altitude = get_altitude(lat, lng, timestamp_date)
                azimuth = get_azimuth(lat, lng, timestamp_date)
                loc['altitude'] = altitude
                loc['azimuth'] = azimuth
            elif self.arg_parser.cached:
                altitude = loc['altitude']
                azimuth = loc['azimuth']
            if(not loc.get('altitudeClass') or not loc.get('azimuthClass') or not loc.get('sunEvent')):
                loc['altitudeClass'] = Classifier.altitude(altitude)
                loc['azimuthClass'] = Classifier.direction(azimuth)
                loc['sunEvent'] = Classifier.sun_event(altitude, azimuth)
            if self.args.heading == 'solar':
                loc.update({'heading': float(azimuth), 'pitch': float(altitude)})
        except Exception as e:
            logging.error(e)
            self.err += 1
            progress.update(1)
            return None
        progress.update(1)
        return loc

    async def weather(self):
        # IMPORTANT: You are limited to ~10000 requests per day.
        # Accuracy may vary! Low resolution data -- hourly & imprecise lat/lng.
        
        endpoints = {
            'clouds': ['cloud_cover', 'cloudCover'],
            'precipitation': ['precipitation', 'precipitation'],
            'snow': ['snow_depth', 'snowDepth']
        }
        requested_params = [
            param.lower() 
            for param in endpoints 
            if getattr(self.arg_parser.args, param.lower(), False) or getattr(self.arg_parser.args, param.upper(), False)
        ]
        METEO_ARGSTRING = ",".join([endpoints[param][0] for param in requested_params])

        total_locations = len(self.map.locs)
        progress = tqdm(total=total_locations, desc=self.PROCESS_NAMES[self.weather])

        if self.arg_parser.cached and (all(endpoints[param][1] in self.map.locs[0] for param in requested_params) or (self.arg_parser.args.CLOUDS and 'cloudCoverClass' in self.map.locs[0])):
            progress.update(total_locations)
            return

        chunk_size = 100
        loc_pool = []
        request_count = 0
        METEO_MAX_RATE = (600/chunk_size) # You can also self-host the API https://github.com/open-meteo/open-meteo/blob/main/docs/getting-started.md
        WEATHER_SEARCH_WINDOW = CONFIG['weatherSearchWindow']

        rate_limiter = AsyncLimiter(max_rate=METEO_MAX_RATE, time_period=60)

        async def process_chunk(latstring, lngstring, datestring, chunk_num, progress):
            nonlocal request_count
            request_url = f"https://archive-api.open-meteo.com/v1/archive?latitude={latstring}&longitude={lngstring}&start_date={datestring}&end_date={datestring}&hourly={METEO_ARGSTRING}&timezone=GMT&format=json&timeformat=unixtime"

            try:
                async with aiohttp.ClientSession() as session:
                    async with rate_limiter:
                        async with session.get(request_url) as response:
                            request_count += 1
                            # print(f"Request {request_count} for chunk {chunk_num + 1}")
                            progress.update(len(latstring.split(',')))
                            if response.status == 200:
                                response_data = await response.json()
                                return response_data
                            else:
                                print(f"Request failed for chunk {chunk_num + 1} with status code: {response.status}")
                                return None
            except Exception as e:
                progress.update(len(latstring.split(',')))
                logging.error(f"Error processing chunk {chunk_num + 1}: {str(e)}")
                return None

        chunks = []
        latstring, lngstring, datestring = "", "", ""
        
        # Generate chunks (pre-process)
        for i, loc in enumerate(self.map.locs):
            lat, lng = loc['lat'], loc['lng']
            timestamp = loc['timestamp']
            current_datetime = dt.utcfromtimestamp(timestamp)
            date = current_datetime.strftime('%Y-%m-%d')
            
            latstring += f"{lat},"
            lngstring += f"{lng},"
            datestring += f"{date},"
            
            if (i + 1) % chunk_size == 0 or i == len(self.map.locs) - 1:
                chunks.append((latstring[:-1], lngstring[:-1], datestring[:-1]))
                latstring, lngstring, datestring = "", "", ""

        # Gather chunks (process)
        async def process_chunks():
            tasks = [asyncio.create_task(process_chunk(lat, lng, date, i, progress)) 
                    for i, (lat, lng, date) in enumerate(chunks)]
            return await asyncio.gather(*tasks)

        chunk_results = await process_chunks()
        progress.close()

        # Matching (post-process)
        for chunk_data in chunk_results:
            for loc in chunk_data:
                if loc and 'hourly' in loc:
                    times = loc['hourly']['time']
                    for time in times:
                        weather_mapping = {'time': time, 'longitude': loc['longitude'], 'latitude': loc['latitude']}
                        
                        if 'cloud_cover' in loc['hourly']:
                            weather_mapping['cloud_cover'] = loc['hourly']['cloud_cover'][times.index(time)]
                        
                        if 'precipitation' in loc['hourly']:
                            weather_mapping['precipitation'] = loc['hourly']['precipitation'][times.index(time)]
                        
                        if 'snow_depth' in loc['hourly']:
                            weather_mapping['snow_depth'] = loc['hourly']['snow_depth'][times.index(time)]
                        
                        loc_pool.append(weather_mapping)

        for i, loc in enumerate(self.map.locs):
            min_time = loc['timestamp'] - 1800
            max_time = loc['timestamp'] + 1800
            min_lng = loc['lng'] - WEATHER_SEARCH_WINDOW
            max_lng = loc['lng'] + WEATHER_SEARCH_WINDOW
            min_lat = loc['lat'] - WEATHER_SEARCH_WINDOW
            max_lat = loc['lat'] + WEATHER_SEARCH_WINDOW
            
            filtered_data = [
                data for data in loc_pool 
                if min_time <= data['time'] <= max_time and min_lat <= data['latitude'] <= max_lat and min_lng <= data['longitude'] <= max_lng
            ]
            
            if filtered_data:
                closest_data = min(filtered_data, key=lambda data: abs(data['time'] - loc['timestamp']))
                # print(f"Closest data for location {i + 1}: {closest_data}")
                
                if 'cloud_cover' in closest_data:
                    cloud_cover = closest_data['cloud_cover']
                    loc['cloudCoverClass'] = str(Classifier.cloud_cover_event(cloud_cover))
                    loc['cloudCover'] = cloud_cover
                if 'precipitation' in closest_data:
                    loc['precipitation'] = closest_data['precipitation']
                if 'snow_depth' in closest_data:
                    loc['snowDepth'] = closest_data['snow_depth']
            else:
                logging.error(f"No weather data found within the time range for location {i + 1}")


    async def bulk_parse(self, func):
        chunks = [self.map.locs[i:i + self.CHUNK_SIZE] for i in range(0, len(self.map.locs), self.CHUNK_SIZE)]

        results = []
        progress = tqdm(total=len(self.map.locs), desc=self.PROCESS_NAMES[func])

        for chunk in chunks:
            tasks = [asyncio.create_task(func(loc, progress)) for loc in chunk]
            chunk_results = await asyncio.gather(*tasks)
            results.extend([res for res in chunk_results if res is not None])

        progress.close()
        if self.err > 0:
            retained = len(results)
            print("Retained:", retained)
            if retained == 0:
                raise ValueError("No data retained")



def main():
    logging.info("Starting process")
    # ArgParser
    argparser = ArgParser()

    FOLDERS['base']['files'] = argparser.filepath.absolute()
    FOLDERS['meta']['files'] = Path(f"{FOLDERS['meta']['path']}\{argparser.filepath.stem}.json")
    FOLDERS['tagged']['files'] = list(Path(FOLDERS['tagged']['path']).glob(f"{argparser.filepath.stem}-*.json"))
    FOLDERS['views']['files'] = list(Path(FOLDERS['views']['path']).glob(f"{argparser.filepath.stem}-*.csv"))

    FOLDERS['base']['exists'] =  argparser.filepath.exists()
    FOLDERS['meta']['exists'] = FOLDERS['meta']['files'].exists()
    FOLDERS['tagged']['exists'] = len(FOLDERS['tagged']['files']) > 0
    FOLDERS['views']['exists'] = len(FOLDERS['views']['files']) > 0

    if argparser.args.command == 'tag':
        if not any(getattr(argparser.args, k) for k in argparser.SHORT_ARGS) and not argparser.args.heading and not argparser.args.drivingdirection:
            raise ValueError("At least one output must be specified")
        if argparser.args.round and (not argparser.args.time or argparser.args.round > 60 or argparser.args.round <= 1):
            raise ValueError("Invalid round value")
        
        arg_string = ''.join([argparser.SHORT_ARGS[k] for k, v in vars(argparser.args).items() if v and k in argparser.SHORT_ARGS])
        if argparser.args.round:
            arg_string += str(argparser.args.round)

        # Map
        if(argparser.cached):
            map_obj = SVMap(argparser.cached_file)
        else:
            map_obj = SVMap(argparser.args.file)
        

        # MetaFetch
        logging.info("Metadata fetch")
        mfparser = MetaFetchParser(map_obj, argparser, CONFIG['panoFetchRadius'], CONFIG['panoFetchChunkSize'])
        asyncio.run(mfparser.bulk_parse(mfparser.fetch_meta))

        if argparser.group_true('temporal') or argparser.group_true('terrestrial') or argparser.args.heading == 'solar':
            logging.info("Temporal parsing")
            try:
                asyncio.run(mfparser.bulk_parse(mfparser.timestamp))
            except Exception as e:
                logging.error("Temporal data retrieval error: ",e)
                exit(1)
        
        if argparser.args.solar or argparser.args.SOLAR or argparser.args.heading == 'solar':
            logging.info("Solar parsing")
            try:
                asyncio.run(mfparser.bulk_parse(mfparser.solar))
            except Exception as e:
                logging.error("Solar data retrieval error: ",e)
                exit(1)
        
        if argparser.args.clouds or argparser.args.CLOUDS or argparser.args.precipitation or argparser.args.snow:
            logging.info("Weather parsing")
            try:
                asyncio.run(mfparser.weather())
            except Exception as e:
                logging.error("Weather data retrieval error: ",e)
                exit(1)
        
        if not CONFIG['keepUnknownFields']:
            map_obj.purge(SVMap.KNOWN_FIELDS)
        
        if not argparser.args.no_cache_out:
            map_obj.save(Path(f"{FOLDERS['meta']['path']}/{FOLDERS['base']['files'].stem}.json").absolute()) # Save to meta folder
        
        # MetaTag
        if argparser.args.meta:
            exit(0)
        meta = MetaTag(map_obj, argparser)
        map_obj.save(Path(f"{FOLDERS['tagged']['path']}/{FOLDERS['base']['files'].stem}-{arg_string}.json")) # Save to tagged folder

        end_time = time()
        runtime = end_time - meta.start_time

        logging.debug(f"Tagging runtime: {round(runtime,5)} seconds")
    elif argparser.args.command == 'delete':
        if argparser.args.cascade or argparser.args.meta:
            try:
                if not FOLDERS['meta']['exists']:
                    raise FileNotFoundError(f"Meta file {FOLDERS['meta']['files']} does not exist")
                
                # os_remove(FOLDERS['meta']['files'])
                print("Deleted " + str(FOLDERS['meta']['files']))
            except FileNotFoundError as e:
                logging.error("Failed to delete: " + str(e))

        if argparser.args.cascade or argparser.args.tagged:
            for file in FOLDERS['tagged']['files']:
                try:
                    # os_remove(file)
                    print("Deleted " + str(file))
                except FileNotFoundError as e:
                    logging.error("Failed to delete: " + str(e))

        if argparser.args.cascade or argparser.args.base:
            try:
                if not FOLDERS['base']['exists']:
                    raise FileNotFoundError(f"Base file {FOLDERS['base']['files']} does not exist")
                
                # os_remove(FOLDERS['base']['files'])
                print("Deleted " + str(FOLDERS['base']['files']))
            except FileNotFoundError as e:
                logging.error("Failed to delete: " + str(e))
    elif argparser.args.command == 'clear':
        map_obj = SVMap(argparser.args.file)
        removed = 0
        total = len(map_obj.locs)

        for loc in map_obj.locs:
            if verify_extra(loc, tags=True):
                removed += len(loc['extra']['tags'])
                loc = clear_tags(loc)
        if(argparser.filepath.parent.absolute() == FOLDERS['base']['path']):
            conf = input("Are you sure you want to clear the base file? (y/n) ")
            if conf == 'y':
                print(str(removed) + " tags removed from " + str(total) + " locations")
                map_obj.save(argparser.filepath.absolute())
            else:
                exit(0)
    elif argparser.args.command == 'extract':
        if(argparser.cached):
            map_obj = SVMap(argparser.cached_file)
        else:
            map_obj = SVMap(argparser.args.file)

        results = defaultdict(lambda: defaultdict(int))
        total_counts = defaultdict(int)

        classifiers = argparser.args.classify or ['none'] * len(argparser.args.attr)
        if len(classifiers) != len(argparser.args.attr):
            raise ValueError("Number of classifiers must match number of attributes")

        for coord in map_obj.locs:
            key_value = coord.get(argparser.args.key)
            if not key_value:
                continue

            attr_values = []
            for attr, classifier in zip(argparser.args.attr, classifiers):
                attr_value = coord.get(attr)
                if attr_value is None:
                    if argparser.args.include_none:
                        attr_value = "None"
                    else:
                        break
                elif classifier.lower() != 'none':
                    attr_value = getattr(Classifier, classifier)(attr_value)
                attr_values.append(str(attr_value))
            
            if len(attr_values) == len(argparser.args.attr):
                combined_attr = " - ".join(attr_values)
                results[key_value][combined_attr] += 1
                total_counts[key_value] += 1

        output_filename = f"{FOLDERS['views']['path'] / Path(argparser.args.file).stem} - {argparser.args.key.upper()} to {'+'.join(argparser.args.attr).upper()}.csv"
        with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            all_attr_combinations = set()
            for attr_counts in results.values():
                all_attr_combinations.update(attr_counts.keys())

            sorted_attr_combinations = sorted(
                all_attr_combinations,
                key=lambda x: (x.count("None"), x)
            )

            header = [argparser.args.key] + sorted_attr_combinations + ['TOTAL']
            writer.writerow(header)
            
            for key_value, attr_counts in results.items():
                row = [key_value]
                for attr_combination in sorted_attr_combinations:
                    count = attr_counts[attr_combination]
                    if argparser.args.format == 'count':
                        row.append(count)
                    else:  # percent
                        percentage = (count / total_counts[key_value]) * 100 if total_counts[key_value] else 0
                        row.append(f"{percentage:.2f}%")
                row.append(total_counts[key_value])
                writer.writerow(row)

        print(f"Results written to {output_filename}")

    logging.info("Finished process")

if __name__ == '__main__':
    main()