import pandas as pd
import argparse

from pathlib import Path
from haversine import haversine, Unit

from datetime import datetime, timedelta
from scipy.spatial import cKDTree


def find_clusters(df):
    df.sort_values(by=['timestamp'], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df['cluster'] = -1  # initialize cluster column with -1
    cluster_number = 0

    # Create a cKDTree
    tree = cKDTree(df[['lat', 'lng']].values)

    def find_next_location(index, cluster_number):
        row = df.loc[index]
        current_timestamp = datetime.fromtimestamp(row['timestamp'])

        _, indices = tree.query([list(row[['lat', 'lng']])], k=7)  # Proximal neighbors
        indices = indices[0][1:]

        closest_speed = None
        closest_location = None
        for i in indices:
            # Skip if this location already has a cluster
            if df.loc[i, 'cluster'] != -1:
                continue

            # Get closest temporal neighbor to current row, if it is within the speed limit
            neighbor_timestamp = datetime.fromtimestamp(df.loc[i, 'timestamp'])
            time_diff = abs(current_timestamp - neighbor_timestamp).total_seconds() / 3600  # in hours
            if time_diff == 0:
                continue

            distance = haversine((row['lat'], row['lng']), (df.loc[i, 'lat'], df.loc[i, 'lng']), unit=Unit.MILES)
            speed = distance / time_diff

            if (1 < speed < 100 and (closest_speed is None or abs(70 - speed) < abs(70 - closest_speed))) or distance < 0.5:
                closest_speed = speed
                closest_location = i

        if closest_speed is not None and closest_location is not None:
            df.loc[index, 'cluster'] = cluster_number
            df.loc[closest_location, 'cluster'] = cluster_number
            find_next_location(closest_location, cluster_number)
        else:
            return

    for index, row in df.iterrows():
        # Skip if this row is already assigned to a cluster
        if df.loc[index, 'cluster'] != -1:
            continue

        find_next_location(index, cluster_number)
        cluster_number += 1


    return df

def find_drivers(df):
    df.sort_values(by=['timestamp'], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df['cluster'] = -1  # initialize cluster column with -1
    cluster_number = 0

    tree = cKDTree(df[['lat', 'lng']].values)

def find_times(df):
    df.sort_values(by=['timestamp'], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df['cluster'] = -1  # initialize cluster column with -1
    df['link_number'] = 0
    locs = len(df)
    k = min(100, locs)
    cluster_number = 0

    tree = cKDTree(df[['lat', 'lng']].values)

    def find_next_location(index, cluster_number, link_number):
        row = df.loc[index]
        current_timestamp = datetime.fromtimestamp(row['timestamp'])

        _, indices = tree.query([list(row[['lat', 'lng']])], k=k)  # Proximal neighbors
        indices = indices[0][1:]

        closest_speed = None
        closest_location = None
        for i in indices:
            if df.loc[i, 'cluster'] != -1:
                continue

            # Get closest temporal neighbor to current row, if it is within the speed limit
            neighbor_timestamp = datetime.fromtimestamp(df.loc[i, 'timestamp'])
            time_diff = abs(current_timestamp - neighbor_timestamp).total_seconds() / 3600  # in hours
            if time_diff == 0:
                continue

            distance = haversine((row['lat'], row['lng']), (df.loc[i, 'lat'], df.loc[i, 'lng']), unit=Unit.MILES)
            speed = distance / time_diff

            if ((10 <= speed <= 100) and (closest_speed is None or distance < closest_speed) and distance < 10 and time_diff < 6):
                closest_speed = distance
                closest_location = i

        if closest_speed is not None and closest_location is not None:
            df.loc[index, 'cluster'] = cluster_number
            df.loc[index, 'link_number'] = link_number
            df.loc[index, 'cluster_position'] = 'start' if link_number == 0 else ''
            df.loc[closest_location, 'cluster'] = cluster_number
            df.loc[closest_location, 'link_number'] = link_number + 1
            df.loc[closest_location, 'cluster_position'] = 'end' if df.loc[closest_location, 'link_number'] > df.loc[index, 'link_number'] else ''
            find_next_location(closest_location, cluster_number, link_number + 1)
        else:
            df.loc[index, 'cluster_position'] = 'end'
            return

    for index, row in df.iterrows():
        if df.loc[index, 'cluster'] != -1:
            continue

        find_next_location(index, cluster_number, 0)
        cluster_number += 1


    return df

if __name__ == '__main__':
    args = argparse.ArgumentParser()
    args.add_argument('csv_file', type=str, help='Path to the CSV file')
    args = args.parse_args()

    df = pd.read_csv(args.csv_file)
    #df = find_clusters(df)

    df = find_times(df)
    print(df['cluster'].nunique())
   
    output_file = f"{Path(args.csv_file).stem}_clusters.csv"
    df.to_csv(output_file, index=False)
    print(f"Clusters written to {output_file}")

#    print(clusters)
    # for i, cluster in enumerate(clusters):
    #     print(f"Cluster {i+1}:")
    #     #print(cluster[0])
    #     print(cluster[0].timestamp, cluster[-1].timestamp)
    #     print(len(cluster))

    

    # print(f"Runtime: {round(runtime,5)} seconds")