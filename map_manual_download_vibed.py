import os
import glob
import folium
import gpxpy
import gpxpy.gpx
import fitparse
import gzip

print(os.getcwd())

# CONFIGURATION
GPX_FOLDER = "./manual_strava_archive/activities"  # folder containing your Strava GPX files
OUTPUT_MAP = "strava_runs_map.html"

# Create a base map
map_center = [47.607330, -122.335604]  # change this to your typical run location
m = folium.Map(location=map_center, zoom_start=12, tiles='OpenStreetMap')

# Function to extract track points from GPX file

def extract_track_from_gpx(file_path):
    coords = []
    try:
        with open(file_path, 'r', encoding='utf-8') as gpx_file:
            gpx = gpxpy.parse(gpx_file)

            #### Fix 1: Accumulate all track segments, not just the first ####
            for track in gpx.tracks:
                for segment in track.segments:
                    coords.extend((point.latitude, point.longitude) for point in segment.points)

            #### Fix 2: Fallback to route data if no tracks present ####
            if not coords:
                for route in gpx.routes:
                    print("Did not find a gpx track, but did find a route...")
                    coords.extend((point.latitude, point.longitude) for point in route.points)

            #### Fix 3: Log empty files for investigation ####
            if not coords:
                print(f"No coordinates found in: {os.path.basename(file_path)}")

    except Exception as e:
        #### Fix 4: Handle malformed files gracefully ####
        print(f"Error reading {os.path.basename(file_path)}: {e}")

    return coords

def extract_track_from_fit(file_path):
    #### Implementation for .fit files ####
    coords = []
    try:
        fitfile = fitparse.FitFile(file_path)
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
            print(f"No coordinates found in: {os.path.basename(file_path)}")
    except Exception as e:
        print(f"Error reading {os.path.basename(file_path)}: {e}")
    return coords

def extract_track_from_fit_gz(file_path):
    #### Implementation for .fit.gz files ####
    coords = []
    try:
        with gzip.open(file_path, 'rb') as f:
            fitfile = fitparse.FitFile(f)
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
            print(f"No coordinates found in: {os.path.basename(file_path)}")
    except Exception as e:
        print(f"Error reading {os.path.basename(file_path)}: {e}")
    return coords

# Process all activity files
num_activities = 0
for activity_file in os.listdir(GPX_FOLDER):
    full_path = os.path.join(GPX_FOLDER, activity_file)
    coords = []
    if activity_file.endswith('.gpx'):
        coords = extract_track_from_gpx(full_path)
    elif activity_file.endswith('.fit'):
        coords = extract_track_from_fit(full_path)
    elif activity_file.endswith('.fit.gz'):
        coords = extract_track_from_fit_gz(full_path)

    if coords:
        num_activities += 1
        folium.PolyLine(coords, color='blue', weight=2.5, opacity=0.8).add_to(m)

print(num_activities)

# Save the map
m.save(OUTPUT_MAP)
print(f"Map saved to {OUTPUT_MAP}")
