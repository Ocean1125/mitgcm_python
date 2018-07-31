#######################################################
# 1D plots, e.g. timeseries
#######################################################

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import numpy as np
import sys

from grid import choose_grid
from file_io import netcdf_time
from timeseries import fris_melt, timeseries_max, timeseries_avg_sfc, timeseries_int_sfc, timeseries_avg_3d
from plot_utils.labels import monthly_ticks, yearly_ticks
from plot_utils.windows import finished_plot


# Helper function to calculate timeseries from one or more files.

# Arguments:
# file_path: either a single filename or a list of filenames

# Optional keyword arguments:
# option: 'fris_melt': calculates total melting and freezing beneath FRIS
#          'max': calculates maximum value of variable in region; must specify var_name and possibly xmin etc.
#          'avg_sfc': calculates area-averaged value over the sea surface, i.e. not counting cavities
#          'int_sfc': calculates area-integrated value over the sea surface
#          'avg_fris': calculates volume-averaged value in the FRIS cavity
# grid: as in function read_plot_latlon
# gtype: as in function read_plot_latlon
# var_name: variable name to process. Only matters for 'max', 'avg_sfc', 'int_sfc', and 'avg_fris'.
# xmin, xmax, ymin, ymax: as in function var_min_max
# monthly: as in function netcdf_time

# Output:
# if option='fris_melt', returns three 1D arrays of time, melting, and freezing.
# if option='max', 'avg_sfc', or 'avg_fris', returns two 1D arrays of time and the relevant timeseries.
# if option='time', just returns the time array.

def read_timeseries (file_path, option=None, grid=None, gtype='t', var_name=None, xmin=None, xmax=None, ymin=None, ymax=None, monthly=True):

    if isinstance(file_path, str):
        # Just one file
        first_file = file_path
    elif isinstance(file_path, list):
        # More than one
        first_file = file_path[0]
    else:
        print 'Error (read_timeseries): file_path must be a string or a list'
        sys.exit()

    if option in ['max', 'avg_sfc', 'int_sfc', 'avg_fris'] and var_name is None:
        print 'Error (read_timeseries): must specify var_name'
        sys.exit()

    # Build the grid if needed
    if option != 'time':
        grid = choose_grid(grid, first_file)

    # Calculate timeseries on the first file
    if option == 'fris_melt':
        melt, freeze = fris_melt(first_file, grid, mass_balance=True)
    elif option == 'max':
        values = timeseries_max(first_file, var_name, grid, gtype=gtype, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
    elif option == 'avg_sfc':
        values = timeseries_avg_sfc(first_file, var_name, grid, gtype=gtype)
    elif option == 'int_sfc':
        values = timeseries_int_sfc(first_file, var_name, grid, gtype=gtype)
    elif option == 'avg_fris':
        values = timeseries_avg_3d(first_file, var_name, grid, gtype=gtype, fris=True)
    elif option != 'time':
        print 'Error (read_timeseries): invalid option ' + option
        sys.exit()
    # Read time axis
    time = netcdf_time(first_file, monthly=monthly)
    if isinstance(file_path, list):
        # More files to read
        for file in file_path[1:]:
            if option == 'fris_melt':
                melt_tmp, freeze_tmp = fris_melt(file, grid, mass_balance=True)
            elif option == 'max':
                values_tmp = timeseries_max(file, var_name, grid, gtype=gtype, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
            elif option == 'avg_sfc':
                values_tmp = timeseries_avg_sfc(file, var_name, grid, gtype=gtype)
            elif option == 'int_sfc':
                values_tmp = timeseries_int_sfc(file, var_name, grid, gtype=gtype)
            elif option == 'avg_fris':
                values_tmp = timeseries_avg_3d(file, var_name, grid, gtype=gtype, fris=True)
            time_tmp = netcdf_time(file, monthly=monthly)
            # Concatenate the arrays
            if option == 'fris_melt':
                melt = np.concatenate((melt, melt_tmp))
                freeze = np.concatenate((freeze, freeze_tmp))
            elif option in ['max', 'avg_sfc', 'int_sfc', 'avg_fris']:
                values = np.concatenate((values, values_tmp))
            time = np.concatenate((time, time_tmp))

    if option == 'fris_melt':
        return time, melt, freeze
    elif option in ['max', 'avg_sfc', 'int_sfc', 'avg_fris']:
        return time, values
    elif option == 'time':
        return time


# Helper function to calculate difference timeseries, trimming if needed.

# Arguments:
# time_1, time_2: 1D arrays containing time values for the two simulations (assumed to start at the same time, but might not be the same length)
# data_1, data_2: 1D arrays containing timeseries for the two simulations

# Output:
# time: 1D array containing time values for the overlapping period of simulation
# data_diff: 1D array containing differences (data_2 - data_1) at these times
def trim_and_diff (time_1, time_2, data_1, data_2):

    num_time = min(time_1.size, time_2.size)
    time = time_1[:num_time]
    data_diff = data_2[:num_time] - data_1[:num_time]
    return time, data_diff


# Helper function to call read_timeseries twice, for two simulations, and calculate the difference in the timeseries. Doesn't work for the complicated case of fris_melt.
def read_timeseries_diff (file_path_1, file_path_2, option=None, var_name=None, grid=None, gtype='t', xmin=None, xmax=None, ymin=None, ymax=None, monthly=True):

    if option == 'fris_melt':
        print "Error (read_timeseries_diff): this function can't be used for option="+option
        sys.exit()

    # Calculate timeseries for each
    time_1, values_1 = read_timeseries(file_path_1, option=option, var_name=var_name, grid=grid, gtype=gtype, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax, monthly=monthly)
    time_2, values_2 = read_timeseries(file_path_2, option=option, var_name=var_name, grid=grid, gtype=gtype, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax, monthly=monthly)
    # Find the difference, trimming if needed
    time, values_diff = trim_and_diff(time_1, time_2, values_1, values_2)
    return time, values_diff


# Helper function to plot timeseries.

# Arguments:
# time: 1D array of Date objects corresponding to time of each record
# data: 1D array of timeseries to plot

# Optional keyword arguments:
# melt_freeze: boolean (default False) indicating to plot melting, freezing, and total. Assumes melting is given by "data" and freezing by "data_2".
# data_2: if melt_freeze=True, array of freezing timeseries
# diff: boolean (default False) indicating this is an anomaly timeseries. Only matters for melt_freeze as it will change the legend labels.
# title: title for plot
# units: units of timeseries
# monthly: as in function netcdf_time
# fig_name: as in function finished_plot

def make_timeseries_plot (time, data, data_2=None, melt_freeze=False, diff=False, title='', units='', monthly=True, fig_name=None):

    fig, ax = plt.subplots()
    if melt_freeze:
        if diff:
            melt_label = 'Change in melting (>0)'
            freeze_label = 'Change in freezing (<0)'
            total_label = 'Change in net'
        else:
            melt_label = 'Melting'
            freeze_label = 'Freezing'
            total_label = 'Net'
        ax.plot_date(time, data, '-', color='red', linewidth=1.5, label=melt_label)
        ax.plot_date(time, data_2, '-', color='blue', linewidth=1.5, label=freeze_label)
        ax.plot_date(time, data+data_2, '-', color='black', linewidth=1.5, label=total_label)
        ax.legend()
    else:
        ax.plot_date(time, data, '-', linewidth=1.5)
    if melt_freeze or (np.amin(data) < 0 and np.amax(data) > 0):
        # Add a line at 0
        ax.axhline(color='black')
    ax.grid(True)
    if not monthly:
        monthly_ticks(ax)
    plt.title(title, fontsize=18)
    plt.ylabel(units, fontsize=16)
    finished_plot(fig, fig_name=fig_name)


# User interface for timeseries plots. Call this function with a specific variable key and a list of NetCDF files to get a nice lat-lon plot.

# Arguments:
# var: keyword indicating which timeseries to plot. The options are:
#      'fris_melt': melting, freezing, and net melting beneath FRIS
#      'hice_corner': maximum sea ice thickness in the southwest corner of the Weddell Sea, between the Ronne and the peninsula
#      'mld_ewed': maximum mixed layer depth in the open Eastern Weddell Sea
#      'eta_avg': area-averaged sea surface height
#      'seaice_area': total sea ice area
#      'fris_temp': volume-averaged temperature in the FRIS cavity
#      'fris_salt': volume-averaged salinity in the FRIS cavity
# file_path: either a single filename or a list of filenames, to NetCDF files containing the necessary variable:
#            'fris_melt': SHIfwFlx
#            'hice_corner': SIheff
#            'mld_ewed': MXLDEPTH
#            'eta_avg': ETAN
#            'seaice_area': SIarea
#            'fris_temp': THETA
#            'fris_salt': SALT

# Optional keyword arguments:
# grid: as in function read_plot_latlon
# fig_name: as in function finished_plot
# monthly: indicates the model output is monthly-averaged

def read_plot_timeseries (var, file_path, grid=None, fig_name=None, monthly=True):

    # Calculate timeseries and set plotting variables
    if var == 'fris_melt':
        # Special case for read_timeseries, with extra output argument
        time, data, data_2 = read_timeseries(file_path, option='fris_melt', grid=grid, monthly=monthly)
        title = 'Basal mass balance of FRIS'
        units = 'Gt/y'
    else:
        # Set parameters to call read_timeseries with
        data_2 = None
        xmin = None
        xmax = None
        ymin = None
        ymax = None
        if var in ['hice_corner', 'mld_ewed']:
            # Maximum between spatial bounds
            option = 'max'
            if var == 'hice_corner':
                var_name = 'SIheff'
                xmin = -62
                xmax = -59.5
                ymin = -75.5
                ymax = -74
                title = 'Maximum sea ice thickness in problematic corner'
                units = 'm'
            elif var == 'mld_ewed':
                var_name = 'MXLDEPTH'
                xmin = -30
                xmax = 30
                ymin = -69
                ymax = -60
                title = 'Maximum mixed layer depth in Eastern Weddell'
                units = 'm'
        elif var == 'avg_eta':
            option = 'avg_sfc'
            var_name = 'ETAN'
            title = 'Area-averaged sea surface height'
            units = 'm'
        elif var == 'seaice_area':
            option = 'int_sfc'
            var_name = 'SIarea'
            title = 'Total sea ice area'
            units = r'million km$^2$'
        elif var in ['fris_temp', 'fris_salt']:
            option = 'avg_fris'
            if var == 'fris_temp':
                var_name = 'THETA'
                title = 'Volume-averaged temperature in FRIS cavity'
                units = r'$^{\circ}$C'
            elif var == 'fris_salt':
                var_name = 'SALT'
                title = 'Volume-averaged salinity in FRIS cavity'
                units = 'psu'
        else:
            print 'Error (read_plot_timeseries): invalid variable ' + var
            sys.exit()
        # Now read the timeseries
        time, data = read_timeseries(file_path, option=option, var_name=var_name, grid=grid, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymin, monthly=monthly)
        
    # Plot
    make_timeseries_plot(time, data, data_2=data_2, melt_freeze=(var=='fris_melt'), title=title, units=units, monthly=monthly, fig_name=fig_name)

    


# Plot the difference in FRIS melting and freezing for two simulations (2 minus 1). It is assumed the two simulations start at the same time, but it's okay if one is longer - it will get trimmed.

def plot_fris_massbalance_diff (file_path_1, file_path_2, grid=None, fig_name=None, monthly=True):

    # Calculate timeseries for each
    time_1, melt_1, freeze_1 = read_timeseries(file_path_1, option='fris_melt', grid=grid, monthly=monthly)
    time_2, melt_2, freeze_2 = read_timeseries(file_path_2, option='fris_melt', grid=grid, monthly=monthly)
    # Find the difference, trimming if needed
    time, melt_diff = trim_and_diff(time_1, time_2, melt_1, melt_2)
    freeze_diff = trim_and_diff(time_1, time_2, freeze_1, freeze_2)[1]
    # Plot
    plot_timeseries(time, melt_diff, data_2=freeze_diff, melt_freeze=True, diff=True, title='Change in basal mass balance of FRIS', units='Gt/y', monthly=monthly, fig_name=fig_name)    


# Plot the difference in the maximum value of the given variable in the given region, between two simulations (2 minus 1). It is assumed the two simulations start at the same time, but it's okay if one is longer - it will get trimmed.

def plot_timeseries_max_diff (file_path_1, file_path_2, var_name, grid=None, gtype='t', xmin=None, xmax=None, ymin=None, ymax=None, title='', units='', fig_name=None, monthly=True):

    time, values_diff = read_timeseries_diff(file_path_1, file_path_2, option='max', var_name=var_name, grid=grid, gtype=gtype, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax, monthly=monthly)
    plot_timeseries(time, values_diff, title=title, units=units, monthly=monthly, fig_name=fig_name)


# Difference in this maximum sea ice between two simulations (2 minus 1).
def plot_hice_corner_diff (file_path_1, file_path_2, grid=None, fig_name=None, monthly=True):

    plot_timeseries_max_diff(file_path_1, file_path_2, 'SIheff', grid=grid, xmin=-62, xmax=-59.5, ymin=-75.5, ymax=-74, title='Change in maximum sea ice thickness in problematic corner', units='m', fig_name=fig_name, monthly=monthly)


# Difference in this maximum mixed layer depth between two simulations (2 minus 1).
def plot_mld_ewed_diff (file_path_1, file_path_2, grid=None, fig_name=None, monthly=True):

    plot_timeseries_max_diff(file_path_1, file_path_2, 'MXLDEPTH', grid=grid, xmin=-30, ymin=-69, title='Change in maximum mixed layer depth in Eastern Weddell', units='m', fig_name=fig_name, monthly=monthly)


# Difference in the area-averaged sea surface height between two simulations (2 minus 1).
def plot_eta_avg_diff (file_path_1, file_path_2, grid=None, fig_name=None, monthly=True):

    time, eta_diff = read_timeseries_diff(file_path_1, file_path_2, option='avg_sfc', var_name='ETAN', grid=grid, monthly=monthly)
    plot_timeseries(time, eta_diff, title='Change in area-averaged sea surface height', units='m', monthly=monthly, fig_name=fig_name)


# Difference in volume-averaged FRIS temperature between two simulations (2 minus 1).
def plot_fris_temp_avg_diff (file_path_1, file_path_2, grid=None, fig_name=None, monthly=True):

    time, temp_diff = read_timeseries_diff(file_path_1, file_path_2, option='avg_fris', var_name='THETA', grid=grid, monthly=monthly)
    plot_timeseries(time, temp_diff, title='Change in volume-averaged temperature in FRIS cavity', units=r'$^{\circ}$C', monthly=monthly, fig_name=fig_name)

# Difference in volume-averaged FRIS salinity between two simulations (2 minus 1).
def plot_fris_salt_avg_diff (file_path_1, file_path_2, grid=None, fig_name=None, monthly=True):

    time, salt_diff = read_timeseries_diff(file_path_1, file_path_2, option='avg_fris', var_name='SALT', grid=grid, monthly=monthly)
    plot_timeseries(time, salt_diff, title='Change in volume-averaged salinity in FRIS cavity', units='psu', monthly=monthly, fig_name=fig_name)


# Difference in total sea ice area between two simulations (2 minus 1).
def plot_total_seaice_area_diff (file_path_1, file_path_2, grid=None, fig_name=None, monthly=True):

    time, area_diff = read_timeseries_diff(file_path_1, file_path_2, option='int_sfc', var_name='SIarea', grid=grid, monthly=monthly)
    area_diff *= 1e-12
    plot_timeseries(time, area_diff, title='Change in total sea ice area', units=r'million km^2', monthly=monthly, fig_name=fig_name)
