from pathlib import Path
import json, csv

class SVMap:
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
        from metatag import CONFIG

        try:
            with open(file, 'w') as f:
                json.dump(self.data, f, indent = None if CONFIG['compressFile'] else 4)
            print("Saved to " + str(file))
        except:
             print("Failed to save to " + str(file))
         

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



