import os
import matplotlib.pyplot as plt
import utils
import numpy as np
from itertools import combinations
import math
from collections import OrderedDict


def find_min_max_latlon(train_df, output_folder):
    max_lat, max_lon = -1000, -1000
    min_lat, min_lon = 1000, 1000
    llats, llons = [],[]
    for index, row in train_df.iterrows():
        train_points = eval(row["points"])
        lats = [t[2] for t in train_points]
        lons = [t[1] for t in train_points]
        llats.extend(lats)
        llons.extend(lons)
        max_lon = max(lons + [max_lon])
        min_lon = min(lons + [min_lon])
        max_lat = max(lats + [max_lat])
        min_lat = min(lats + [min_lat])
    plt.plot(llons,llats,"b.")
    plt.savefig(os.path.join(output_folder,"data_minmax_grid_extent.png"))
    plt.close()
    return (max_lon,max_lat),(min_lon, min_lat),llats, llons #max_lat, max_lon, min_lat, min_lon


def create_grid(number_of_cells, max_lonlat,min_lonlat,all_lats, all_lons, output_folder):
    total_dists = [ m-n for (m,n) in zip(max_lonlat, min_lonlat)]
    cell_dists = [m/n for (m,n) in zip(total_dists, number_of_cells)]
    cell_lat_dist, cell_lon_dist = cell_dists

    rows = create_grid_lines(number_of_cells[0], min_lonlat[1], cell_lat_dist)
    columns=create_grid_lines(number_of_cells[1], min_lonlat[0], cell_lon_dist)
    cell_names = create_cell_names(number_of_cells)

    visualize_grid(rows,columns,min_lonlat,max_lonlat,output_folder=output_folder)
    visualize_grid(rows,columns,min_lonlat,max_lonlat,output_folder=output_folder, points=(all_lons, all_lats))
    return (rows, columns, cell_names)


def get_distance_per_cell(number_of_cells, min_lat, min_lon, max_lat, max_lon):
    total_lat_dist = max_lat - min_lat
    total_lon_dist = max_lon - min_lon
    cell_lat_dist = total_lat_dist / number_of_cells[0]
    cell_lon_dist = total_lon_dist / number_of_cells[1]
    return cell_lat_dist, cell_lon_dist


def create_grid_lines(number_of_cells, min_point, dist):
    lines_list = []
    new_min = min_point
    for i in range(number_of_cells -1):
        new_point = new_min + dist
        lines_list.append(new_point)
        new_min = new_point
    return lines_list


def create_cell_names(number_of_cells):
    cell_names = []
    for i in range(number_of_cells[0]):
        cell_names.append([])
        for j in range(number_of_cells[1]):
            cell_names[-1].append(str(i) + str(j))
    return cell_names


def map_to_features(data_df, grid, output_file):
    rows, columns, cell_names = grid
    raw_features, timestamps = map_to_features_pointwise(data_df, grid)
    headername = "points" if "points" in data_df else "Trajectory"
    maxlen = -1
    for i,(featlist,ts) in enumerate(zip(raw_features,timestamps)):
        # squeeze duplicate points
        sq_feats = []
        for f,t in zip(featlist,ts):
            if (not sq_feats) or (f not in [ v[-1] for v in sq_feats]): # alternate check
            # if (not sq_feats) or (f != sq_feats[-1][-1]): # alternate check
                sq_feats.append([t, f])
        if len(sq_feats) > maxlen:
            maxlen = len(sq_feats)
        data_df.at[i,headername] = sq_feats
    print("Max squeezed feature length:",maxlen)
    if output_file is not None:
        data_df.to_csv(output_file)
    else:
        return data_df


def map_to_features_pointwise(data_df, grid):
    rows, columns, cell_names = grid
    # measure some statistics
    grid_hist = {}
    total_points = 0
    numcells = (len(rows) + 1) * (len(columns) + 1)
    for cc in cell_names:
        for c in cc:
            grid_hist['C' + str(c)] = 0

    points_header = "points" if "points" in data_df else "Trajectory"
    features, timestamps = [], []
    for index,row in data_df.iterrows():
        train_points = row[points_header]
        train_points = eval(train_points)

        ts = [p[0] for p in train_points]
        timestamps.append(ts)
        train_lonlats = utils.idx_to_lonlat(train_points, format="tuples")
        feature_list = []
        for i,lonlat in enumerate(train_lonlats):
            lon = lonlat[0]  # for columns
            lat = lonlat[1]  # for rows
            row_idx = find_cell_index(rows, lat)
            col_idx = find_cell_index(columns, lon)
            cell_name = 'C'+cell_names[row_idx][col_idx]
            # visualize_grid(rows,columns,None,None,[[lon],[lat]])
            grid_hist[cell_name] += 1
            total_points += 1

            feature_list.append(cell_name)
        features.append(feature_list)
    # show stats
    print()
    print("Grid assignment frequencies of the total of %d points:" % total_points)
    ssum = 0
    for i, name in enumerate(grid_hist):
        print(i,"/", numcells, name, grid_hist[name])
        ssum += grid_hist[name]
    return features, timestamps


def map_to_features_bow_bigrams(data_df, grid, output_file):
    rows, columns, cell_names = grid

    points_header = "points" if "points" in data_df else "Trajectory"

    features = []
    num_cells = len([0 for cc in cell_names for c in cc])
    # vector order: for N cells: bigrams of (cell1, cell2), cell1,cell3
    cell_pairs = list(combinations(list(range(num_cells)), 2))
    for n in range(num_cells):
        cell_pairs.append((n,n))
    pairs_to_idxs = {}
    # map each cell pair to a vector index
    for pair in cell_pairs:
        pairs_to_idxs[pair] = len(pairs_to_idxs)

    bigram_dim = len(pairs_to_idxs)

    for index,row in data_df.iterrows():
        bow_vector = [0 for _ in range(bigram_dim)]
        train_points = row[points_header]
        train_points = eval(train_points)

        train_lonlats = utils.idx_to_lonlat(train_points, format="tuples")
        # loop into bigrams
        for i in range(len(train_lonlats)-1):
            lon1, lat1 = tuple(train_lonlats[i][0:2])
            lon2, lat2 = tuple(train_lonlats[i+1][0:2])
            r1, c1 = find_cell_index(rows, lat1), find_cell_index(rows, lon1)
            r2, c2 = find_cell_index(rows, lat2), find_cell_index(rows, lon2)

            linear_idx1 = r1 * len(columns) + c1
            linear_idx2 = r2 * len(columns) + c2
            stuple = tuple(sorted((linear_idx1, linear_idx2)))
            vec_idx = pairs_to_idxs[stuple]
            bow_vector[vec_idx] += 1
        features.append(bow_vector)

    for i,feats in enumerate(features):
        data_df.at[i,points_header] = feats
    if output_file is not None:
        data_df.to_csv(output_file)
    else:
        return features

def map_to_features_vlad(data_df, grid, output_file):
    print("Computing VLAD encoding")
    rows, columns, cell_names = grid
    # internal midpoints
    r_dists = [u-d for (u, d) in zip(rows[1:],rows[:-1])]
    c_dists = [u-d for (u, d) in zip(columns[1:],columns[:-1])]
    r_mids = [r+m/2 for (r,m) in zip(rows[:-1],r_dists)]
    c_mids = [r+m/2 for (r,m) in zip(columns[:-1],c_dists)]
    # edge midpoints, with distance the mean of the internals
    r_dists, c_dists = np.mean(r_dists), np.mean(c_dists)
    r_mids = [rows[0] - r_dists/2] + r_mids + [rows[-1] + r_dists/2]
    c_mids = [columns[0] - c_dists/2] + c_mids + [columns[-1] + c_dists/2]

    centroids = [(c,r) for c in c_mids for r in r_mids]


    points_header = "points" if "points" in data_df else "Trajectory"

    features = []
    for index,row in data_df.iterrows():
        vlad_vector = [0 for _ in centroids]
        train_points = row[points_header]
        train_points = eval(train_points)

        train_lonlats = utils.idx_to_lonlat(train_points, format="tuples")
        for i,lonlat in enumerate(train_lonlats):
            lon = lonlat[0]  # for columns
            lat = lonlat[1]  # for rows
            dists = []
            # get distance from each centroid
            for centroid in centroids:
                dists.append(utils.euc_dist(centroid,lonlat))

            dnorm = np.sqrt(sum([pow(d,2) for d in dists]))
            dists = [1 - d/dnorm for d in dists]
            vlad_vector = [v + d for (v,d) in zip(vlad_vector, dists)]

        dnorm = np.sqrt(sum([pow(d,2) for d in dists]))
        vlad_vector = [1 - d/dnorm for d in vlad_vector]
        features.append(vlad_vector)

    print("Done computing VLAD encoding")
    for i,feats in enumerate(features):
        data_df.at[i,points_header] = feats
    if output_file is not None:
        data_df.to_csv(output_file)
    else:
        return features


def map_to_features_bow(data_df, grid, output_file):
    rows, columns, cell_names = grid
    points_header = "points" if "points" in data_df else "Trajectory"

    features = []
    for index,row in data_df.iterrows():
        bow_vector = [0 for cc in cell_names for c in cc]
        train_points = row[points_header]
        train_points = eval(train_points)

        train_lonlats = utils.idx_to_lonlat(train_points, format="tuples")
        for i,lonlat in enumerate(train_lonlats):
            lon = lonlat[0]  # for columns
            lat = lonlat[1]  # for rows
            row_idx = find_cell_index(rows, lat)
            col_idx = find_cell_index(columns, lon)
            linear_idx = row_idx * len(columns) + col_idx
            bow_vector[linear_idx] += 1
        bus_direction = find_trip_direction(train_lonlats)
        bow_vector = [bus_direction*x for x in bow_vector]
        #if(bus_direction<0):
            #bow_vector = list(reversed(bow_vector))
        features.append(bow_vector)

    for i,feats in enumerate(features):
        data_df.at[i,points_header] = feats
    if output_file is not None:
        data_df.to_csv(output_file)
    else:
        return features


def find_trip_direction(train_lonlats):
    first_point = train_lonlats[0]
    last_point = train_lonlats[-1]
    max_point = max(first_point,last_point)
    if(first_point == max_point):
        return -1
    else:
        return 1

def find_cell_index(points_list, point):
    count = 0
    for p in points_list:
        if point < p:
            return count
        count += 1
    return count

# Auxiliary function, visualizes the grid created above
def visualize_grid_gml_print(rows, columns, min_lonlat=None,  max_lonlat=None, points = [], cells = [], output_folder=""):
    # visualize
    min_lat = min(rows + points[1]) if min_lonlat is None else min_lonlat[1]
    min_lon = min(columns + points[0]) if min_lonlat is None else min_lonlat[0]
    max_lat = max(rows + points[1]) if max_lonlat is None else max_lonlat[1]
    max_lon = max(columns + points[0]) if max_lonlat is None else max_lonlat[0]

    fig = plt.figure()
    plt.plot([min_lat, max_lat], [min_lon, min_lon], 'k');
    plt.plot([min_lat, max_lat], [max_lon, max_lon], 'k');
    plt.plot([min_lat, min_lat], [min_lon, max_lon], 'k');
    plt.plot([max_lat, max_lat], [min_lon, max_lon], 'k');

    for x in rows:
        plt.plot([x, x], [min_lon, max_lon], 'r');
    for y in columns:
        plt.plot([min_lat, max_lat], [y, y], 'b');

    if points:
        plt.plot(points[1],points[0],".k")

    for p in cells:
        plt.plot(p[1],p[0],"*g")

    plt.xlabel("lat")
    plt.ylabel("lon")
    plt.savefig(os.path.join(output_folder, "grid.png"), dpi = fig.dpi)
    plt.close()

def visualize_grid(rows, columns, min_lonlat=None,  max_lonlat=None, points = [], cells = [], output_folder=""):
    # visualize
    min_lat = min(rows + points[1]) if min_lonlat is None else min_lonlat[1]
    min_lon = min(columns + points[0]) if min_lonlat is None else min_lonlat[0]
    max_lat = max(rows + points[1]) if max_lonlat is None else max_lonlat[1]
    max_lon = max(columns + points[0]) if max_lonlat is None else max_lonlat[0]

    fig = plt.figure()
    plt.plot([min_lon, min_lon], [min_lat, max_lat], 'k');
    plt.plot([max_lon, max_lon], [min_lat, max_lat], 'k');
    plt.plot([min_lon, max_lon], [min_lat, min_lat], 'k');
    plt.plot([min_lon, max_lon], [max_lat, max_lat], 'k');

    for x in rows:
        plt.plot([min_lon, max_lon], [x, x], 'r');
    for y in columns:
        plt.plot([y, y], [min_lat, max_lat],'b');

    if points:
        plt.plot(points[0],points[1],".k")

    for p in cells:
        plt.plot(p[0],p[1],"*g")

    plt.xlabel("lon")
    plt.ylabel("lat")
    plt.savefig(os.path.join(output_folder, "grid.png"), dpi = fig.dpi)
    plt.close()
