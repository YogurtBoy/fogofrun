import os
import glob
import folium
import gpxpy
import gpxpy.gpx
import fitparse
import gzip
from folium.features import DivIcon
import io

print(os.getcwd())

# CONFIGURATION
GPX_FOLDER = "./manual_strava_archive_subset/activities"  # folder containing your Strava GPX files
OUTPUT_MAP = "strava_runs_map.html"

# Create a base map
map_center = [47.607330, -122.335604]  # change this to your typical run location
m = folium.Map(location=map_center, zoom_start=12, tiles='OpenStreetMap')

# Valid activity types to include
VALID_RUN_TYPES = {"run", "running", "trail running", "treadmill"}

#### EXTRACTOR FUNCTIONS
# Extract from .gpx
def extract_track_from_gpx(file_path):
    coords = []
    activity_type = "unknown"
    try:
        with open(file_path, 'r', encoding='utf-8') as gpx_file:
            gpx = gpxpy.parse(gpx_file)

            if gpx.tracks:
                type_name = gpx.tracks[0].type
                activity_type = type_name or "unknown"
                if type_name and type_name.lower() not in VALID_RUN_TYPES:
                    print(f"Skipping non-run activity in {os.path.basename(file_path)}: {type_name}")
                    return [], activity_type

            for track in gpx.tracks:
                for segment in track.segments:
                    coords.extend((point.latitude, point.longitude) for point in segment.points)

            if not coords:
                for route in gpx.routes:
                    print("Did not find a gpx track, but did find a route...")
                    coords.extend((point.latitude, point.longitude) for point in route.points)

            if not coords:
                print(f"No coordinates found in: {os.path.basename(file_path)}")

    except Exception as e:
        print(f"Error reading {os.path.basename(file_path)}: {e}")

    return coords, activity_type

# Extract from .fit
def extract_track_from_fit(file_path):
    coords = []
    activity_type = "unknown"
    try:
        fitfile = fitparse.FitFile(file_path)

        sport = None
        for msg in fitfile.get_messages("sport"):
            for record in msg:
                if record.name == "sport":
                    sport = record.value
        activity_type = sport or "unknown"
        if sport and sport.lower() not in VALID_RUN_TYPES:
            print(f"Skipping non-run activity in {os.path.basename(file_path) if isinstance(file_path, str) else '<buffer>'}: {sport}")
            return [], activity_type

        for record in fitfile.get_messages("record"):
            lat = None
            lon = None
            for data in record:
                if data.name == "position_lat":
                    lat = data.value / 11930464.71
                elif data.name == "position_long":
                    lon = data.value / 11930464.71
            if lat is not None and lon is not None:
                coords.append((lat, lon))
        if not coords:
            print(f"No coordinates found in: {os.path.basename(file_path) if isinstance(file_path, str) else '<buffer>'}")
    except Exception as e:
        print(f"Error reading {os.path.basename(file_path) if isinstance(file_path, str) else '<buffer>'}: {e}")
    return coords, activity_type

# Extract from .fit.gz. This just unpacks the gzip and calls the .fit opener
def extract_track_from_fit_gz(file_path):
    with gzip.open(file_path, 'rb') as f:
        fit_data = io.BytesIO(f.read())
        return extract_track_from_fit(fit_data)

# Process all activity files
num_activities = 0
for activity_file in os.listdir(GPX_FOLDER):
    full_path = os.path.join(GPX_FOLDER, activity_file)
    coords = []
    activity_type = "unknown"
    if activity_file.endswith('.gpx'):
        coords, activity_type = extract_track_from_gpx(full_path)
    elif activity_file.endswith('.fit'):
        coords, activity_type = extract_track_from_fit(full_path)
    elif activity_file.endswith('.fit.gz'):
        coords, activity_type = extract_track_from_fit_gz(full_path)

    if coords:
        num_activities += 1
        polyline = folium.PolyLine(coords, color='blue', weight=2.5, opacity=0.8)
        polyline.add_to(m)
        # # Add a hoverable, clickable popup marker near the start of the route
        # folium.Marker(
        #     location=coords[0],
        #     icon=DivIcon(icon_size=(150,36), icon_anchor=(0,0), html=f'<div style="background: white; padding: 2px 4px; border: 1px solid black; border-radius: 4px;">{activity_type.title()}</div>')
        # ).add_to(m)

print(num_activities)

# Save the map
m.save(OUTPUT_MAP)
print(f"Map saved to {OUTPUT_MAP}")
