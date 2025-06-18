import os
import folium
import osmnx as ox
import networkx as nx
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, Point
import io
import gpxpy
import gpxpy.gpx

import fitparse
import gzip

OUTPUT_MAP = "runless_seattle_roads.html"
ACTIVITIES_FOLDER = "./manual_strava_archive_subset/activities"  # folder containing your Strava activities


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


# Get the city boundary for Seattle
gdf = ox.geocode_to_gdf("Seattle, Washington, USA")
seattle_center_ll = [47.6062, -122.3321]

# Filter for geometries that are Polygon or MultiPolygon
gdf_poly = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]

if gdf_poly.empty:
    raise ValueError("No polygon or multipolygon geometry found for Seattle")

# Use the first valid polygon
polygon = gdf_poly.geometry.iloc[0]
if polygon.geom_type == 'Polygon':
    coords = list(polygon.exterior.coords)
elif polygon.geom_type == 'MultiPolygon':
    coords = list(polygon.geoms[0].exterior.coords)

# Create a folium Map object
m = folium.Map(location=seattle_center_ll, zoom_start=12)

# Draw a border of Seattle on the map using the gdf data
if polygon.geom_type == 'Polygon':
    border_coords = [(lat, lon) for lon, lat in polygon.exterior.coords]
    folium.PolyLine(border_coords, color="red", weight=3).add_to(m)
elif polygon.geom_type == 'MultiPolygon':
    for poly in polygon.geoms:
        border_coords = [(lat, lon) for lon, lat in poly.exterior.coords]
        folium.PolyLine(border_coords, color="red", weight=3).add_to(m)

# Download the road network for the Seattle area
G = ox.graph_from_polygon(polygon, network_type='drive')

# Convert the graph edges to a GeoDataFrame and add to map
edge_gdf = ox.graph_to_gdfs(G, nodes=False, edges=True)


# Process all activity files
num_activities = 0
for activity_file in os.listdir(ACTIVITIES_FOLDER):
    full_path = os.path.join(ACTIVITIES_FOLDER, activity_file)
    coords = []
    activity_type = "unknown"
    if activity_file.endswith('.gpx'):
        coords, activity_type = extract_track_from_gpx(full_path)
    elif activity_file.endswith('.fit'):
        coords, activity_type = extract_track_from_fit(full_path)
    elif activity_file.endswith('.fit.gz'):
        coords, activity_type = extract_track_from_fit_gz(full_path)

    if coords:
        # Skip this activity if it falls outside the borders of Seattle
        activity_center = Point(coords[len(coords)//2][1], coords[len(coords)//2][0])  # lon, lat
        if not polygon.contains(activity_center):
            print(f"Skipping activity outside Seattle boundary: {activity_file}")
            continue

        
        num_activities += 1
      
        # Draw the run line in a pink dotted line
        polyline = folium.PolyLine(coords, color='#82B4DD', weight=2.5, opacity=0.8, dash_array='5,5')
        polyline.add_to(m)

        # Iterate through the edges in edge_gdf and remove any that correspond to the current activity. 
        from shapely.geometry import LineString
        run_line = LineString([(lon, lat) for lat, lon in coords])
        # Buffer the run line slightly to capture nearby road edges
        run_buffer = run_line.buffer(0.0001)  # ~10 meters buffer
        # Remove edges that intersect with this activity
        edge_gdf = edge_gdf[~edge_gdf.intersects(run_buffer)]
        

# Add remaining roads of the map graph to the map
for _, row in edge_gdf.iterrows():
    line = row['geometry']
    if line.geom_type == 'LineString':
        points = [(lat, lon) for lon, lat in line.coords]
        folium.PolyLine(points, color="#D53F33", weight=1).add_to(m)
    elif line.geom_type == 'MultiLineString':
        for linestring in line.geoms:
            points = [(lat, lon) for lon, lat in linestring.coords]
            folium.PolyLine(points, color="#D53F33", weight=1).add_to(m)


# Save the map
m.save(OUTPUT_MAP)
print(f"Map saved to {OUTPUT_MAP}")
