# IO
from pathlib import Path
import csv, json
import argparse
import os
import re

# Implicit processing
import datetime
from datetime import datetime as dt
import time
from timezonefinder import TimezoneFinder
import pytz
import calendar
from pysolar.solar import get_altitude, get_azimuth

# Explicit processing
import asyncio, aiohttp
from aiolimiter import AsyncLimiter
from tqdm import tqdm

# Local
from sv_map import SVMap, Classifier
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
    }
}

for folder in FOLDERS.values():
    if not os.path.exists(folder['path']):
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
        
        self.args = self.parser.parse_args()
        self.userparser =  self.subparsers.choices[self.args.command]
        self.filepath = Path(self.args.file)

        if self.args.command == 'tag':
            self.cached_file = (FOLDERS['meta']['path'] / self.filepath.name).absolute()
            if self.cached_file.exists() and not self.args.no_cache_in:
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
        self.add_argument(parser, '-s','--solar', action='store_true', group='terrestrial')
        self.add_argument(parser, '-S','--SOLAR', action='store_true', group='terrestrial')
        self.add_argument(parser, '-w','--weather', action='store_true', group='terrestrial')
        self.add_argument(parser, '-W', '--WEATHER', action='store_true', group='terrestrial')
        self.add_argument(parser, '--heading', type=str, default=None, help='Update heading; orient towards object i.e. solar', group='terrestrial')
        self.add_argument(parser, '-drivingdirection', action='store_true', help='Update driving direction', group='terrestrial')

    def add_delete_arguments(self, parser):
        self.add_argument(parser, 'file', type=str, help='Path to file to delete')
        self.add_argument(parser, '-b', '--base', action='store_true', help='Delete base file')
        self.add_argument(parser, '-m', '--meta', action='store_true', help='Delete meta file')
        self.add_argument(parser, '-t', '--tagged', action='store_true', help='Deleted tagged file(s)')
        self.add_argument(parser, '-c', '--cascade', action='store_true', help='Delete all associated files')

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

        self.start_time = time.time()
        self.attr_sets = {
            'dates': set(),
            'altitudes': set(),
            'azimuths': set(),
            'cloud_cover': set()
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
                    # Comprehension
                    lat = float(item['lat'])
                    lng = float(item['lng'])
                    if self.arg_parser.group_true('temporal'):
                        unix_time = float(item['timestamp'])

                        if unix_time and not (now - 20*365*24*60*60 <= unix_time <= now):
                            raise ValueError(f"Invalid UNIX time at line {i+2}: {unix_time}")
                        
                        timestamp = self.tz_datestring(lat, lng, unix_time, self.args.round)

                    if self.arg_parser.group_true('geographical'):
                        country = item['country'] if 'country' in item else None
                        state = item['state'] if 'state' in item else None
                        locality = item['locality'] if 'locality' in item else None

                    if self.args.drivingdirection:
                        driving_direction = item['drivingDirection'] if 'drivingDirection' in item else None

                    if self.args.solar or self.args.SOLAR:
                        try:
                            altitude_class = str(item['altitude_class'])
                            azimuth_class = str(item['azimuth_class'])
                            sun_event = str(item['sun_event'])

                            altitude = str(round(float(item['altitude'])))
                            azimuth = str(round(float(item['azimuth'])))
                        except:
                            if self.arg_parser.cached:
                                raise SVMap.CacheError()
                            else:
                                raise ValueError("Solar data not found")
                    if self.args.weather or self.args.WEATHER:
                        cloud_cover_class = str(item['cloudCoverClass']) if 'cloudCoverClass' in item else None #CHANGE name & figure out why error thrown
                        cloud_cover = str(item['cloudCover']) if 'cloudCover' in item else None


                    # Tagging
                    tags = []
                    if self.arg_parser.group_true('temporal'):
                        tags.append(timestamp)
                        self.attr_sets['dates'].add(timestamp)
                    if self.arg_parser.group_true('geographical'):
                        if self.args.country:
                            tags.append(country)
                        if self.args.state:
                            tags.append(state)
                        if self.args.locality:
                            tags.append(locality)
                    if self.args.drivingdirection:
                        tags.append(Classifier.direction(driving_direction))
                    if self.args.solar:
                        tags.extend(["#"+str(altitude_class), "@"+str(azimuth_class), sun_event])
                    if self.args.SOLAR:
                        tags.extend([str(altitude)+" #", str(azimuth)+" @"])
                        self.attr_sets['altitudes'].add(altitude+" #")
                        self.attr_sets['azimuths'].add(azimuth +" @")
                    if self.args.weather:
                        if cloud_cover_class:
                            tags.append(cloud_cover_class)
                    if self.args.WEATHER:
                        if cloud_cover:
                            tags.append(cloud_cover)
                            self.attr_sets['cloud_cover'].add(cloud_cover)

                    # Prune empty tags
                    tags = [tag for tag in tags if tag]

                    # Append to data
                    if "extra" in item and "tags" in item["extra"]:
                        # Edge case if tag(s) are non-array
                        if not isinstance(item['extra']['tags'], list):
                            item['extra']['tags'] = [item['extra']['tags']]
                        
                        item["extra"]["tags"].extend(tags)
                    else:
                        item["extra"] = {"tags": tags}

                    if (self.args.SOLAR or self.args.solar) and self.args.heading=='solar':
                        item.update({
                            "heading": float(azimuth),
                            "pitch": float(altitude)
                        })

                except SVMap.CacheError as e:
                    print(e)
                    exit(1)
                except Exception as e:
                    print(e)

            if self.arg_parser.group_true('temporal'):
                sorted_dates = self.order_tags(self.attr_sets['dates'])
                self.offset += sorted_dates[2]
                # print("Datetime span:", sorted_dates[0], "to", sorted_dates[1])

            if self.args.SOLAR:
                sorted_altitude = self.order_tags(self.attr_sets['altitudes'], sortby='solar')
                self.offset += sorted_altitude[2]
                sorted_azimuth = self.order_tags(self.attr_sets['azimuths'], sortby='solar')
                self.offset += sorted_azimuth[2]
            
            if self.args.WEATHER:
                sorted_weather = self.order_tags(self.attr_sets['cloud_cover'], sortby='cloud_cover')
                self.offset += sorted_weather[2]

        except Exception as e:
            print(f'Error: {e}')
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
            q = dt.fromtimestamp(unix_time, pytz.timezone(timezone_str))
            if roundt:
                discard = datetime.timedelta(minutes=q.minute % roundt,
                             seconds=q.second,
                             microseconds=q.microsecond)
                q -= discard
                if discard >= datetime.timedelta(minutes=roundt/2):
                    q += datetime.timedelta(minutes=roundt)
        else:
            lt = time.localtime(unix_time)
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
            sortby (str): The sort order ('date' or 'solar').

        Returns:
            list: A list containing the start value, end value, and offset.
        """
        if 'extra' not in self.map.data:
            self.map.data['extra'] = {}
        if 'tags' not in self.map.data['extra']:
            self.map.data['extra']['tags'] = {}
        
        if sortby == 'date':
            sli = sorted(list(attribute_set), key=lambda i: dt.strptime(i, self.datestring) if self.datestring else i)
        elif sortby == 'solar':
            sli = sorted(list(attribute_set), key=lambda i: int(re.search(r'\d+', i).group()) if int(re.search(r'\d+', i).group()) else i)
        elif sortby == 'cloud_cover':
            sli = sorted(list(attribute_set), key=lambda i: int(re.search(r'\d+', i).group()))
        start = sli[0]
        end = sli[-1]
        i = 0 if self.offset == 0 else 1

        for i, item in enumerate(sli):
            self.map.data["extra"]["tags"][item] = {"order": i+self.offset}
            color_scale = [int(start + (end - start) * (i / len(sli))) for start, end in zip(self.color2, self.color)]
            self.map.data["extra"]["tags"][item]['color'] = color_scale
        return [start,end,i]

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
            if 'extra' not in loc:
                loc['extra'] = {}
                
            if 'imageDate' in loc and loc['imageDate']:
                month = loc['imageDate']
            elif 'panoDate' in loc['extra'] and loc['extra']['panoDate']:
                month = loc['extra']['panoDate']
            elif 'timestamp' in loc and loc['timestamp']:
                month = dt.fromtimestamp(loc['timestamp'], pytz.utc).strftime('%Y-%m')
            elif self.args.load and 'tags' in loc['extra']:
                tags = loc['extra']['tags']
                months = [month.lower() for month in calendar.month_name[1:]] + [month.lower() for month in calendar.month_abbr[1:]]
                years = [str(year) for year in range(2007,  dt.now().year+1)]

                matching_month = next((tag for tag in tags if tag.lower() in months), None)
                matching_year = next((tag for tag in tags if tag in years), None)

                if matching_month and matching_year:
                    month_number = str(dt.strptime(matching_month, '%b' if len(matching_month) == 3 else '%B').month).zfill(2)
                    month = matching_year + "-" + month_number
                
            if month:
                if 'timestamp' not in loc:
                    timestamp = await find_accurate_timestamp(lat, lng, month, self.RADIUS, self.args.accuracy)
                    loc['timestamp'] = timestamp
            else:
                raise Exception("Unable to date image "+str(lat), str(lng))

        except Exception as e:
            #print(e)
            self.err += 1
            self.map.locs.remove(loc)
            print("Error: ",e)
            progress.update(1)
            return None
        progress.update(1)
        return loc
    
    async def fetch_meta(self, loc, progress):
        lat, lng = loc['lat'], loc['lng']

        async with aiohttp.ClientSession() as session:
            if ('imageDate' not in loc and 'timestamp' not in loc) or ('country' not in loc and self.args.country) or self.args.heading == "drivingdirection":
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
                            loc['drivingDirection'] = loads[1][5][0][3][0][4][2][2][0] #loads[1][5][0][3][0][10][2][2][0]
                        except IndexError:
                            loc['drivingDirection'] = None

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

                        if self.args.heading == "drivingdirection":
                            #print(loads[1][5][0][3][0][4][2][2][0])
                            try:
                                if loc['drivingDirection']:
                                    loc['heading'] = loc['drivingDirection']
                                else:
                                    raise IndexError
                            except IndexError:
                                loc['heading'] = 0

                except Exception as e:
                    print(e)
                    self.err += 1
                    self.map.locs.remove(loc)
                    progress.update(1)
                    return None

            progress.update(1)
            return loc

    async def solar(self, loc, progress):
        lat, lng = loc['lat'], loc['lng']
        if 'timestamp' not in loc:
            raise ValueError("Timestamp not found")
        
        timestamp = loc['timestamp']
        timestamp_date = dt.fromtimestamp(timestamp, pytz.utc)
        try:
            if('azimuth' not in loc or 'altitude' not in loc):
                altitude = get_altitude(lat, lng, timestamp_date)
                azimuth = get_azimuth(lat, lng, timestamp_date)
                loc['altitude'] = altitude
                loc['azimuth'] = azimuth
            if('altitude_class' not in loc or 'azimuth_class' not in loc or 'sun_event' not in loc):
                loc['altitude_class'] = Classifier.altitude(altitude)
                loc['azimuth_class'] = Classifier.direction(azimuth)
                loc['sun_event'] = Classifier.sun_event(altitude, azimuth)
        except Exception as e:
            print(e)
            self.err += 1
            progress.update(1)
            return None
        progress.update(1)
        return loc

    async def weather(self):
        # IMPORTANT: You are limited to ~10000 requests per day.
        # Accuracy may vary! Low resolution data -- hourly & imprecise lat/lng.
        
        #TODO: elevation and rain etc
        if(self.arg_parser.cached and 'cloudCover' in self.map.locs[0]):
            return

        chunk_size = 100
        loc_pool = []
        request_count = 0
        METEO_MAX_RATE = (600/chunk_size) # You can also self-host the API https://github.com/open-meteo/open-meteo/blob/main/docs/getting-started.md

        rate_limiter = AsyncLimiter(max_rate=METEO_MAX_RATE, time_period=60)

        async def process_chunk(latstring, lngstring, datestring, chunk_num):
            nonlocal request_count
            request_url = f"https://archive-api.open-meteo.com/v1/archive?latitude={latstring}&longitude={lngstring}&start_date={datestring}&end_date={datestring}&hourly=cloud_cover&timezone=GMT&format=json&timeformat=unixtime"

            try:
                async with aiohttp.ClientSession() as session:
                    async with rate_limiter:
                        async with session.get(request_url) as response:
                            request_count += 1
                            print(f"Request {request_count} for chunk {chunk_num + 1}")
                            if response.status == 200:
                                response_data = await response.json()
                                return response_data
                            else:
                                print(f"Request failed for chunk {chunk_num + 1} with status code: {response.status}")
                                return None
            except Exception as e:
                print(f"Error processing chunk {chunk_num + 1}: {str(e)}")
                return None

        chunks = []
        latstring, lngstring, datestring = "", "", ""
        
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

        tasks = [process_chunk(lat, lng, date, i) for i, (lat, lng, date) in enumerate(chunks)]
        chunk_results = await asyncio.gather(*tasks)

        for chunk_data in chunk_results:
            for loc in chunk_data:
                if loc and 'hourly' in loc:
                    times = loc['hourly']['time']
                    cloud_covers = loc['hourly']['cloud_cover']
                    # print(loc)
                    for time, cloud_cover in zip(times, cloud_covers):
                        loc_pool.append({'time': time, 'cloud_cover': cloud_cover})

        for i, loc in enumerate(self.map.locs):
            min_time = loc['timestamp'] - 1800
            max_time = loc['timestamp'] + 1800
            filtered_data = [data for data in loc_pool if min_time <= data['time'] <= max_time]
            
            if filtered_data:
                # Find the data entry with the closest timestamp
                closest_data = min(filtered_data, key=lambda data: abs(data['time'] - loc['timestamp']))
                print(f"Closest data for location {loc['lat']},{loc['lng']}: {closest_data}")
                if not closest_data or 'cloud_cover' not in closest_data or not closest_data['cloud_cover']:
                    continue
                cloud_cover = closest_data['cloud_cover']
                loc['cloudCoverClass'] = str(Classifier.cloud_cover_event(cloud_cover))
                loc['cloudCover'] = cloud_cover


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
            #print(f"Errors: {self.err}")
            print("Retained:", len(results))



if __name__ == '__main__':
    # ArgParser
    argparser = ArgParser()

    FOLDERS['base']['files'] = argparser.filepath.absolute()
    FOLDERS['meta']['files'] = Path(f"{FOLDERS['meta']['path']}\{argparser.filepath.stem}.json")
    FOLDERS['tagged']['files'] = list(Path(FOLDERS['tagged']['path']).glob(f"{argparser.filepath.stem}-*.json"))

    FOLDERS['base']['exists'] =  argparser.filepath.exists()
    FOLDERS['meta']['exists'] = FOLDERS['meta']['files'].exists()
    FOLDERS['tagged']['exists'] = len(FOLDERS['tagged']['files']) > 0


    if argparser.args.command == 'tag':
        if not any(getattr(argparser.args, k) for k in argparser.SHORT_ARGS) and not argparser.group_true('geographical'):
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
        mfparser = MetaFetchParser(map_obj, argparser)
        asyncio.run(mfparser.bulk_parse(mfparser.fetch_meta))

        if argparser.group_true('temporal') or argparser.group_true('terrestrial'):
            try:
                asyncio.run(mfparser.bulk_parse(mfparser.timestamp))
            except Exception as e:
                print("Temporal data retrieval error: ",e)
                exit(1)
        
        if argparser.args.solar or argparser.args.SOLAR:
            try:
                asyncio.run(mfparser.bulk_parse(mfparser.solar))
            except Exception as e:
                print("Solar data retrieval error: ",e)
                exit(1)
        
        if argparser.args.weather or argparser.args.WEATHER:
            try:
                asyncio.run(mfparser.weather())
            except Exception as e:
                print("Weather data retrieval error: ",e)
                exit(1)

        map_obj.save(Path(f"{FOLDERS['meta']['path']}/{FOLDERS['base']['files'].stem}.json").absolute()) # Save to meta folder
        
        # MetaTag
        meta = MetaTag(map_obj, argparser)
        map_obj.save(Path(f"{FOLDERS['tagged']['path']}/{FOLDERS['base']['files'].stem}-{arg_string}.json"))

        end_time = time.time()
        runtime = end_time - meta.start_time

        #print(f"Tagging runtime: {round(runtime,5)} seconds")
    elif argparser.args.command == 'delete':
        if argparser.args.cascade or argparser.args.meta:
            try:
                if not FOLDERS['meta']['exists']:
                    raise FileNotFoundError(f"Meta file {FOLDERS['meta']['files']} does not exist")
                
                # os.remove(FOLDERS['meta']['files'])
                print("Deleted " + str(FOLDERS['meta']['files']))
            except FileNotFoundError as e:
                print("Failed to delete: " + str(e))

        if argparser.args.cascade or argparser.args.tagged:
            for FILE in FOLDERS['tagged']['files']:
                try:
                    # os.remove(file)
                    print("Deleted " + str(FILE))
                except FileNotFoundError as e:
                    print("Failed to delete: " + str(e))

        if argparser.args.cascade or argparser.args.base:
            try:
                if not FOLDERS['base']['exists']:
                    raise FileNotFoundError(f"Base file {FOLDERS['base']['files']} does not exist")
                
                # os.remove(FOLDERS['base']['files'])
                print("Deleted " + str(FOLDERS['base']['files']))
            except FileNotFoundError as e:
                print("Failed to delete: " + str(e))
