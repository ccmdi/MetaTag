from pathlib import Path
import json, csv

class SVMap:
    """
    StreetView metadata map object.

    Args:
        file (str): The path to the file containing map data.

    Attributes:
        data (dict): The top-level map data.
        locs (list): The list of coordinate data.
    """
    KNOWN_FIELDS = ['lat', 'lng', 'heading', 'panoId', 'extra', 'pitch', 'tags', 'drivingDirection', 'elevation', 'altitude', 
                    'country', 'state', 'locality', 'imageDate', 'timestamp', 'altitude', 'azimuth', 'altitudeClass', 'azimuthClass',
                    'sunEvent', 'cloudCover', 'cloudCoverClass', 'precipitation', 'snowDepth']
    CRITICAL_FIELDS = ['lat', 'lng', 'heading', 'panoId', 'extra', 'pitch']

    def __init__(self, file):
        with open(file) as f:
            if Path(file).suffix == '.json':
                self.data = json.load(f)
                if not 'customCoordinates' in self.data:
                    self.data = {"customCoordinates": self.data}
                self.locs = self.data['customCoordinates']
        
            elif Path(file).suffix == '.csv':
                reader = csv.reader(f)
                headers = next(reader)
                content = list(reader)

                lat_index = headers.index('lat')
                lng_index = headers.index('lng')

                self.locs = []

                for row in content:
                    try:
                        self.locs.append({
                            "lat": float(row[lat_index]),
                            "lng": float(row[lng_index]),
                            "extra": {"tags": []}
                        })

                        for i, value in enumerate(row):
                            if i not in (lat_index, lng_index):
                                self.locs[-1][headers[i]] = value

                        if 'heading' not in self.locs[-1]:
                            self.locs[-1]['heading'] = 0
                    
                    except:
                        continue

                self.data = {'name': Path(file).stem, "customCoordinates": self.locs}

    def save(self, file):
        """
        Saves the map data to a file.

        Args:
            file (str): The path to the file to save the data to.
        """
        from metatag import CONFIG

        try:
            with open(file, 'w') as f:
                json.dump(self.data, f, indent = None if CONFIG['compressFile'] else 4)
            print("Saved to " + str(file))
        except:
             print("Failed to save to " + str(file))
    
    def purge(self, exclude=CRITICAL_FIELDS):
        """
        Removes all non-excluded fields from the map data. By default, critical fields are excluded.
        """
        for loc in self.locs:
            for key in list(loc.keys()):
                if key not in exclude:
                    del loc[key]
        return self
    
    def verify_map_styles(self):
        if 'extra' not in self.data:
            self.data['extra'] = {}
        if 'tags' not in self.data['extra']:
            self.data['extra']['tags'] = {}

    def __str__(self):
         return self.data['name'] if 'name' in self.data else "" + " (" + str(len(self.locs)) + " locations)"
    
    class CacheError(Exception):
        """Exception raised when cached data does not contain requested data."""
        def __init__(self, message="Cache does not contain requested data"):
            self.message = message
            super().__init__(self.message)

    COLORS = {
        "red": [255, 0, 0],
        "green": [0, 255, 0],
        "blue": [0, 0, 255],
        "yellow": [255, 255, 0],
        "cyan": [0, 255, 255],
        "pink": [255, 0, 255],
        "purple": [128, 0, 128],
    }


class Classifier:
    def altitude(altitude):
        if altitude < 6:
            return "Very Low"
        if 6 <= altitude < 15:
            return "Low"
        elif 15 <= altitude < 30:
            return "Medium"
        elif 30 <= altitude < 45:
            return "High"
        else:
            return "Very High"

    def direction(direction):
        try:
            if 337.5 <= direction or direction < 22.5:
                return "North"
            elif 22.5 <= direction < 67.5:
                return "North-East"
            elif 67.5 <= direction < 112.5:
                return "East"
            elif 112.5 <= direction < 157.5:
                return "South-East"
            elif 157.5 <= direction < 202.5:
                return "South"
            elif 202.5 <= direction < 247.5:
                return "South-West"
            elif 247.5 <= direction < 292.5:
                return "West"
            else:
                return "North-West"
        except:
            return None

    def sun_event(altitude, azimuth):
        if -6 <= altitude <= 6:
            if 0 <= azimuth < 180:
                return "Sunrise"
            elif 180 <= azimuth < 360:
                return "Sunset"
        return None

    
    def cloud_cover_event(cover):
        if cover < 10:
            return "Clear"
        if 10 <= cover < 50:
            return "Partly Cloudy"
        elif 50 <= cover < 80:
            return "Mostly Cloudy"
        else:
            return "Overcast"

def verify_extra(loc, tags = False):
    if 'extra' not in loc:
        return False
    if tags and ('tags' not in loc['extra'] or not loc['extra']['tags'] or not isinstance(loc['extra']['tags'], list)):
        return False
    return True

def force_extra(loc, tags = False):
    if 'extra' not in loc:
        loc['extra'] = {}
    if 'tags' not in loc['extra'] and tags:
        loc['extra']['tags'] = []
    return loc

def clear_tags(loc):
    if 'extra' in loc and 'tags' in loc['extra']:
        loc['extra']['tags'] = []
    return loc