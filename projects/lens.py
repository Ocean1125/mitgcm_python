##################################################################
# JSPS Amundsen Sea simulations forced with LENS
##################################################################

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import os
from scipy.stats import linregress, ttest_1samp

from ..plot_1d import read_plot_timeseries_ensemble
from ..utils import real_dir, fix_lon_range, add_time_dim, days_per_month, xy_to_xyz
from ..grid import Grid
from ..ics_obcs import find_obcs_boundary, trim_slice_to_grid
from ..file_io import read_netcdf, read_binary, netcdf_time, write_binary
from ..constants import deg_string, months_per_year
from ..plot_utils.windows import set_panels, finished_plot
from ..plot_utils.colours import set_colours
from ..plot_utils.labels import reduce_cbar_labels
from ..interpolation import interp_slice_helper, interp_slice_helper_nonreg, extract_slice_nonreg, interp_bdry
from ..postprocess import precompute_timeseries_coupled


# Update the timeseries calculations from wherever they left off before.
def update_lens_timeseries (num_ens=5, base_dir='./'):

    timeseries_types = ['amundsen_shelf_break_uwind_avg', 'all_massloss', 'amundsen_shelf_temp_btw_200_700m', 'amundsen_shelf_salt_btw_200_700m', 'amundsen_shelf_sst_avg', 'amundsen_shelf_sss_avg', 'dotson_to_cosgrove_massloss', 'amundsen_shelf_isotherm_0.5C_below_100m']
    base_dir = real_dir(base_dir)
    sim_dir = [base_dir + 'PAS_LENS' + str(n+1).zfill(3) + '/output/' for n in range(num_ens)]
    timeseries_file = 'timeseries.nc'

    for n in range(num_ens):
        # Work out the first year based on where the timeseries file left off
        start_year = netcdf_time(sim_dir[n]+timeseries_file, monthly=False)[-1].year+1
        # Work on the last year based on the contents of the output directory
        sim_years = []
        for fname in os.listdir(sim_dir[n]):
            if os.path.isdir(sim_dir[n]+fname) and fname.endswith('01'):
                sim_years.append(int(fname))
        sim_years.sort()
        end_year = sim_years[-1]//100
        print('Processing years '+str(start_year)+'-'+str(end_year))
        segment_dir = [str(year)+'01' for year in range(start_year, end_year+1)]
        precompute_timeseries_coupled(output_dir=sim_dir[n], segment_dir=segment_dir, timeseries_types=timeseries_types, hovmoller_loc=[], timeseries_file=timeseries_file, key='PAS')        


# Plot a bunch of precomputed timeseries from ongoing LENS-forced test simulations (ensemble of 5 to start), compared to the PACE-forced ensemble mean.
def check_lens_timeseries (num_ens=5, base_dir='./', fig_dir=None):

    var_names = ['amundsen_shelf_break_uwind_avg', 'all_massloss', 'amundsen_shelf_temp_btw_200_700m', 'amundsen_shelf_salt_btw_200_700m', 'amundsen_shelf_sst_avg', 'amundsen_shelf_sss_avg', 'dotson_to_cosgrove_massloss', 'amundsen_shelf_isotherm_0.5C_below_100m']
    base_dir = real_dir(base_dir)
    pace_file = base_dir+'timeseries_pace_mean.nc'
    file_paths = ['PAS_LENS'+str(n+1).zfill(3)+'/output/timeseries.nc' for n in range(num_ens)] + [pace_file]
    sim_names = ['LENS ensemble'] + [None for n in range(num_ens-1)] + ['PACE mean']
    colours = ['DarkGrey' for n in range(num_ens)] + ['blue']
    smooth = 24
    start_year = 1920

    for var in var_names:
        if fig_dir is not None:
            fig_name = real_dir(fig_dir) + 'timeseries_LENS_' + var + '.png'
        else:
            fig_name=None
        read_plot_timeseries_ensemble(var, file_paths, sim_names=sim_names, precomputed=True, colours=colours, smooth=smooth, vline=start_year, time_use=None, fig_name=fig_name)


# Helper function to build the POP grid, given any LENS ocean file.
def read_pop_grid (file_path):

    lon = fix_lon_range(read_netcdf(file_path, 'TLONG'))
    lat = read_netcdf(file_path, 'TLAT')
    z = -1e-2*read_netcdf(file_path, 'z_t')
    nz = z.size
    ny = lat.shape[0]
    nx = lon.shape[1]
    return lon, lat, z, nx, ny, nz
        

# Compare time-averaged temperature and salinity boundary conditions from PACE over 2006-2013 (equivalent to the first 20 ensemble members of LENS actually!) to the WOA boundary conditions used for the original simulations.
def compare_bcs_ts_mean (fig_dir='./'):

    # Bunch of file paths
    base_dir = '/data/oceans_output/shelf/kaight/'
    grid_dir = base_dir + 'mitgcm/PAS_grid/'
    obcs_dir = base_dir + 'ics_obcs/PAS/'
    obcs_file_head = 'OB'
    obcs_file_tail = '_woa_mon.bin'
    obcs_var = ['theta', 'salt']
    obcs_bdry = ['N', 'W', 'E']
    pace_dir = '/data/oceans_input/raw_input_data/CESM/PPACE/monthly/'
    pace_var = ['TEMP', 'SALT']
    num_ens = 20
    pace_file_head = '/b.e11.BRCP85LENS.f09_g16.SST.restoring.ens'
    pace_file_mid = '.pop.h.'
    pace_file_tail = '.200601-201312.nc'
    num_var = len(pace_var)
    var_titles = ['Temperature ('+deg_string+'C)', 'Salinity (psu)']
    fig_dir = real_dir(fig_dir)
    
    # Build the grids
    mit_grid = Grid(grid_dir)    
    pace_grid_file = pace_dir + pace_var[0] + pace_file_head + '01' + pace_file_mid + pace_var[0] + pace_file_tail
    pace_lon, pace_lat, pace_z, pace_nx, pace_ny, pace_nz = read_pop_grid(pace_grid_file)

    # Read the PACE output to create a time-mean, ensemble-mean (no seasonal cycle for now)
    pace_data_mean_3d = np.ma.zeros([num_var, pace_nz, pace_ny, pace_nx])
    for v in range(num_var):
        for n in range(num_ens):
            pace_file = pace_dir + pace_var[v] + pace_file_head + str(n+1).zfill(2) + pace_file_mid + pace_var[v] + pace_file_tail
            print('Reading ' + pace_file)
            pace_data_mean_3d[v,:] += read_netcdf(pace_file, pace_var[v], time_average=True)
    # Convert from ensemble-integral to ensemble-mean
    pace_data_mean_3d /= num_ens

    # Now loop over boundaries
    for bdry in obcs_bdry:
        # Find the location of this boundary (lat/lon)
        loc0 = find_obcs_boundary(mit_grid, bdry)[0]
        # Find interpolation coefficients to the PACE grid - unfortunately not a regular grid in POP
        if bdry in ['N', 'S']:
            direction = 'lat'
            mit_h = mit_grid.lon_1d
            pace_h_2d = pace_lon
        elif bdry in ['E', 'W']:
            direction = 'lon'
            mit_h = mit_grid.lat_1d
            pace_h_2d = pace_lat
        i1, i2, c1, c2 = interp_slice_helper_nonreg(pace_lon, pace_lat, loc0, direction)
        for v in range(num_var):
            # Read and time-average the existing (WOA) boundary condition file
            obcs_file = obcs_dir + obcs_file_head + bdry + obcs_var[v] + obcs_file_tail
            if bdry in ['N', 'S']:
                dimensions = 'xzt'
            elif bdry in ['E', 'W']:
                dimensions = 'yzt'
            obcs_data_mean = np.mean(read_binary(obcs_file, [mit_grid.nx, mit_grid.ny, mit_grid.nz], dimensions), axis=0)
            # Apply land mask
            if bdry == 'N':
                bdry_hfac = mit_grid.hfac[:,-1,:]
            elif bdry == 'S':
                bdry_hfac = mit_grid.hfac[:,0,:]
            elif bdry == 'W':
                bdry_hfac = mit_grid.hfac[:,:,0]
            elif bdry == 'E':
                bdry_hfac = mit_grid.hfac[:,:,-1]
            obcs_data_mean = np.ma.masked_where(bdry_hfac==0, obcs_data_mean)
            # Interpolate to the PACE grid
            pace_data_mean = extract_slice_nonreg(pace_data_mean_3d, direction, i1, i2, c1, c2)
            pace_h = extract_slice_nonreg(pace_h_2d, direction, i1, i2, c1, c2)
            # Trim
            pace_data_mean, pace_h = trim_slice_to_grid(pace_data_mean, pace_h, mit_grid, direction)
            # Find bounds for colour scale
            vmin = min(np.amin(obcs_data_mean), np.amin(pace_data_mean))
            vmax = max(np.amax(obcs_data_mean), np.amax(pace_data_mean))
            # Plot
            fig, gs, cax = set_panels('1x2C1')
            # WOA OBCS
            ax = plt.subplot(gs[0,0])
            ax.pcolormesh(mit_h, mit_grid.z*1e-3, obcs_data_mean, cmap='jet', vmin=vmin, vmax=vmax)
            ax.set_title('WOA 2018', fontsize=14)
            # PACE
            ax = plt.subplot(gs[0,1])
            img = plt.pcolormesh(pace_h, pace_z*1e-3, pace_data_mean, cmap='jet', vmin=vmin, vmax=vmax)
            ax.set_title('LENS 20-member mean', fontsize=14)
            plt.colorbar(img, cax=cax, orientation='horizontal')
            plt.suptitle(var_titles[v]+', '+bdry+' boundary', fontsize=16)
            finished_plot(fig, fig_name=fig_dir+'pace_obcs_'+pace_var[v]+'_'+str(bdry)+'.png')


# Plot the LENS bias corrections for OBCS at all three boundaries with annual mean, for each variable.
def plot_lens_obcs_bias_corrections_annual (fig_dir=None):

    base_dir = '/data/oceans_output/shelf/kaight/'
    mit_grid_dir = base_dir + 'mitgcm/PAS_grid/'
    in_dir = base_dir + 'CESM_bias_correction/obcs/'
    bdry_loc = ['N', 'W', 'E']
    oce_var = ['TEMP', 'SALT', 'UVEL', 'VVEL']
    ice_var = ['aice', 'hi', 'hs', 'uvel', 'vvel']
    gtype_oce = ['t', 't', 'u', 'v']
    gtype_ice = ['t', 't', 't', 'u', 'v']
    oce_titles = ['Temperature ('+deg_string+'C)', 'Salinity (psu)', 'Zonal velocity (m/s)', 'Meridional velocity (m/s)']
    ice_titles = ['Sea ice concentration', 'Sea ice thickness (m)', 'Snow thickness (m)', 'Sea ice zonal velocity (m/s)', 'Sea ice meridional velocity (m/s)']
    file_head = in_dir + 'LENS_offset_'
    bdry_patches = [None, None, None]
    num_bdry = len(bdry_loc)

    grid = Grid(mit_grid_dir)

    # Loop over ocean and ice variables
    for var_names, gtype, titles, oce in zip([oce_var, ice_var], [gtype_oce, gtype_ice], [oce_titles, ice_titles], [True, False]):
        for v in range(len(var_names)):
            data = []
            h = []
            vmin = 0
            vmax = 0
            lon, lat = grid.get_lon_lat(gtype=gtype[v], dim=1)
            hfac = grid.get_hfac(gtype=gtype[v])
            for n in range(num_bdry):
                # Read and time-average the file (don't worry about different month lengths for plotting purposes)
                file_path = file_head + var_names[v] + '_' + bdry_loc[n]
                if bdry_loc[n] in ['N', 'S']:
                    dimensions = 'x'
                    h.append(lon)
                    h_label = 'Longitude'
                elif bdry_loc[n] in ['E', 'W']:
                    dimensions = 'y'
                    h.append(lat)
                    h_label = 'Latitude'
                if oce:
                    dimensions += 'z'
                dimensions += 't'
                data_tmp = read_binary(file_path, [grid.nx, grid.ny, grid.nz], dimensions)
                data_tmp = np.mean(data_tmp, axis=0)
                # Mask
                if bdry_loc[n] == 'N':
                    hfac_bdry = hfac[:,-1,:]
                elif bdry_loc[n] == 'S':
                    hfac_bdry = hfac[:,0,:]
                elif bdry_loc[n] == 'E':
                    hfac_bdry = hfac[:,:,-1]
                elif bdry_loc[n] == 'W':
                    hfac_bdry = hfac[:,:,0]
                if not oce:
                    hfac_bdry = hfac_bdry[0,:]
                data_tmp = np.ma.masked_where(hfac_bdry==0, data_tmp)
                data.append(data_tmp)
                # Keep track of min and max across all boundaries
                vmin = min(vmin, np.amin(data_tmp))
                vmax = max(vmax, np.amax(data_tmp))
            # Now plot each boundary
            if oce:
                fig, gs, cax = set_panels('1x3C1')
            else:
                fig, gs = set_panels('1x3C0')
                gs.update(left=0.05, wspace=0.1, bottom=0.1)
            cmap = set_colours(data[0], ctype='plusminus', vmin=vmin, vmax=vmax)[0]
            for n in range(num_bdry):
                ax = plt.subplot(gs[0,n])
                if oce:
                    # Simple slice plot (don't worry about partial cells or lat/lon edges vs centres)
                    img = plt.pcolormesh(h[n], grid.z*1e-3, data[n], cmap=cmap, vmin=vmin, vmax=vmax)
                    if n==0:
                        ax.set_ylabel('Depth (km)')
                    if n==num_bdry-1:
                        plt.colorbar(img, cax=cax, orientation='horizontal')
                else:
                    # Line plot
                    plt.plot(h[n], data[n])
                    ax.grid(linestyle='dotted')
                    ax.set_ylim([vmin, vmax])
                    ax.axhline(color='black')
                if n==0:
                    ax.set_xlabel(h_label)
                ax.set_title(bdry_loc[n], fontsize=12)
                plt.suptitle(titles[v], fontsize=16)
                if fig_dir is not None:
                    fig_name = real_dir(fig_dir) + 'obcs_offset_' + var_names[v] + '.png'
                else:
                    fig_name = None
                finished_plot(fig, fig_name=fig_name)


# Now plot all months and the annual mean, for one variable and one boundary at a time.
def plot_lens_obcs_bias_corrections_monthly (fig_dir=None):

    base_dir = '/data/oceans_output/shelf/kaight/'
    mit_grid_dir = base_dir + 'mitgcm/PAS_grid/'
    in_dir = base_dir + 'CESM_bias_correction/obcs/'
    bdry_loc = ['N', 'W', 'E']
    oce_var = ['TEMP', 'SALT', 'UVEL', 'VVEL']
    ice_var = ['aice', 'hi', 'hs', 'uvel', 'vvel']
    gtype_oce = ['t', 't', 'u', 'v']
    gtype_ice = ['t', 't', 't', 'u', 'v']
    oce_titles = ['Temperature ('+deg_string+'C)', 'Salinity (psu)', 'Zonal velocity (m/s)', 'Meridional velocity (m/s)']
    ice_titles = ['Sea ice concentration', 'Sea ice thickness (m)', 'Snow thickness (m)', 'Sea ice zonal velocity (m/s)', 'Sea ice meridional velocity (m/s)']
    file_head = in_dir + 'LENS_offset_'
    bdry_patches = [None, None, None]
    num_bdry = len(bdry_loc)
    month_names = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']

    grid = Grid(mit_grid_dir)

    # Loop over ocean and ice variables
    for var_names, gtype, titles, oce in zip([oce_var, ice_var], [gtype_oce, gtype_ice], [oce_titles, ice_titles], [True, False]):
        for v in range(len(var_names)):
            lon, lat = grid.get_lon_lat(gtype=gtype[v], dim=1)
            hfac = grid.get_hfac(gtype=gtype[v])
            for n in range(num_bdry):
                # Read the file but no time-averaging
                file_path = file_head + var_names[v] + '_' + bdry_loc[n]
                if bdry_loc[n] in ['N', 'S']:
                    dimensions = 'x'
                    h = lon
                elif bdry_loc[n] in ['E', 'W']:
                    dimensions = 'y'
                    h = lat
                if oce:
                    dimensions += 'z'
                dimensions += 't'
                data = read_binary(file_path, [grid.nx, grid.ny, grid.nz], dimensions)
                # Mask
                if bdry_loc[n] == 'N':
                    hfac_bdry = hfac[:,-1,:]
                elif bdry_loc[n] == 'S':
                    hfac_bdry = hfac[:,0,:]
                elif bdry_loc[n] == 'E':
                    hfac_bdry = hfac[:,:,-1]
                elif bdry_loc[n] == 'W':
                    hfac_bdry = hfac[:,:,0]
                if not oce:
                    hfac_bdry = hfac_bdry[0,:]
                hfac_bdry = add_time_dim(hfac_bdry, months_per_year)
                data = np.ma.masked_where(hfac_bdry==0, data)
                # Now plot each month
                if oce:
                    fig, gs, cax = set_panels('3x4+1C1')
                else:
                    fig, gs = set_panels('3x4+1C0')
                cmap, vmin, vmax = set_colours(data, ctype='plusminus')
                for t in range(months_per_year):
                    ax = plt.subplot(gs[t//4+1, t%4])
                    if oce:
                        ax.pcolormesh(h, grid.z*1e-3, data[t,:], cmap=cmap, vmin=vmin, vmax=vmax)
                    else:
                        ax.plot(h, data[t,:])
                        ax.set_ylim([vmin, vmax])
                        ax.grid(linestyle='dotted')
                        ax.axhline(color='black')
                    ax.set_title(month_names[t], fontsize=10)
                    ax.set_xticklabels([])
                    ax.set_yticklabels([])
                # Now plot annual mean
                ax = plt.subplot(gs[0,3])
                if oce:
                    img = ax.pcolormesh(h, grid.z*1e-3, np.mean(data, axis=0), cmap=cmap, vmin=vmin, vmax=vmax)
                    cbar = plt.colorbar(img, cax=cax, orientation='horizontal')
                    reduce_cbar_labels(cbar)
                    ax.set_yticklabels([])
                else:
                    ax.plot(h, np.mean(data, axis=0))
                    ax.set_ylim([vmin, vmax])
                    ax.grid(linestyle='dotted')
                    ax.axhline(color='black')
                ax.set_xticklabels([])
                ax.set_title('Annual', fontsize=10)
                plt.suptitle(titles[v] + ', ' + bdry_loc[n] + ' boundary', fontsize=14)
                if fig_dir is not None:
                    fig_name = real_dir(fig_dir) + 'obcs_offset_monthly_' + var_names[v] + '_' + bdry_loc[n] + '.png'
                else:
                    fig_name = None
                finished_plot(fig, fig_name=fig_name)


# Calculate and plot the ensemble mean trends in the LENS ocean for the given boundary and given variable.
def calc_obcs_trends_lens (var_name, bdry, tmp_file, fig_name=None):

    in_dir = '/data/oceans_input/raw_input_data/CESM/LENS/monthly/'+var_name+'/'
    mit_grid_dir = '/data/oceans_output/shelf/kaight/archer2_mitgcm/PAS_grid/'
    file_head = 'b.e11.BRCP85C5CNBDRD.f09_g16.'
    file_mid = '.pop.h.'
    file_tail_1 = '.200601-208012.nc'
    file_tail_2 = '.208101-210012.nc'
    file_tail_alt = '.200601-210012.nc'
    num_ens = 40
    ens_break = 34
    ens_break2 = 36
    ens_offset = 101
    start_year = 2006
    end_year = 2100
    break_year = 2081
    t_break = (break_year-start_year)*months_per_year
    num_years = end_year - start_year + 1
    p0 = 0.05
    if var_name == 'TEMP':
        units = deg_string+'C'
    elif var_name == 'SALT':
        units = 'psu'
    else:
        print('Error (calc_obcs_trends_lens): unknown variable ' + var_name)
        sys.exit()

    # Read POP grid
    grid_file = in_dir + file_head + '001' + file_mid + var_name + file_tail_1
    lon, lat, z, nx, ny, nz = read_pop_grid(grid_file)

    # Read MITgcm grid and get boundary location
    mit_grid = Grid(mit_grid_dir)
    loc0 = find_obcs_boundary(mit_grid, bdry)[0]
    # Find interpolation coefficients to the POP grid
    if bdry in ['N', 'S']:
        direction = 'lat'
        hmin = find_obcs_boundary(mit_grid, 'W')[0]
        hmax = find_obcs_boundary(mit_grid, 'E')[0]
        h_2d = lon
    elif bdry in ['E', 'W']:
        direction = 'lon'
        hmin = find_obcs_boundary(mit_grid, 'S')[0]
        hmax = find_obcs_boundary(mit_grid, 'N')[0]
        h_2d = lat
    i1, i2, c1, c2 = interp_slice_helper_nonreg(lon, lat, loc0, direction)
    # Interpolate the horizontal axis to this boundary
    h = extract_slice_nonreg(h_2d, direction, i1, i2, c1, c2)
    nh = h.size
    # Trim to MITgcm grid
    h_trim = trim_slice_to_grid(h, h, mit_grid, direction)[0]
    nh_trim = h_trim.size

    if not os.path.isfile(tmp_file):
        # Calculate the trends
        trends = np.ma.zeros([num_ens, nz, nh_trim])
        # Loop over ensemble members
        for n in range(num_ens):
            print('Processing ensemble member ' + str(n+1))
            data_ens = np.ma.empty([num_years, nz, nh])
            for year in range(start_year, end_year+1):
                # Construct the file path and starting time index
                if n+1 < ens_break:
                    if year < break_year:
                        file_path = in_dir + file_head + str(n+1).zfill(3) + file_mid + var_name + file_tail_1
                        t0 = (year-start_year)*months_per_year
                    else:
                        file_path = in_dir + file_head + str(n+1).zfill(3) + file_mid + var_name + file_tail_2
                        t0 = (year-break_year)*months_per_year
                else:
                    if n+1 < ens_break2:
                        file_path = in_dir + file_head + str(n+1).zfill(3) + file_mid + var_name + file_tail_alt
                    else:
                        file_path = in_dir + file_head + str(n+1-ens_break2+ens_offset).zfill(3) + file_mid + var_name + file_tail_alt
                    t0 = (year-start_year)*months_per_year
                tf = t0+months_per_year
                print('...processing indices '+str(t0)+'-'+str(tf-1)+' from '+file_path)
                # Read just this year
                data_tmp = read_netcdf(file_path, var_name, t_start=t0, t_end=tf)
                # Annually average
                ndays = np.array([days_per_month(month+1, year) for month in range(12)])
                data_tmp = np.average(data_tmp, axis=0, weights=ndays)
                # Interpolate to the boundary
                data_ens[year-start_year,:] = extract_slice_nonreg(data_tmp, direction, i1, i2, c1, c2)
            # Now trim to the other boundaries
            data_ens = trim_slice_to_grid(data_ens, h, mit_grid, direction)[0]
            # Loop over each point and calculate trends
            print('...calculating trends')
            for k in range(nz):
                for j in range(nh_trim):
                    trends[n,k,j] = linregress(np.arange(num_years), data_ens[:,k,j])[0]
        # Save results in temporary binary file
        write_binary(trends, tmp_file)
    else:
        # Trends have been precomputed; read them (hack to assume nx=ny=nh)
        trends = read_binary(tmp_file, [nh_trim, nh_trim, nz], 'yzt')

    # Calculate the mean trend and significance
    mean_trend = np.mean(trends, axis=0)*1e2  # Per century
    p_val = ttest_1samp(trends, 0, axis=0)[1]
    # For any trends which aren't significant, fill with zeros
    mean_trend[p_val > p0] = 0

    # Plot
    fig, ax = plt.subplots()
    cmap, vmin, vmax = set_colours(mean_trend, ctype='plusminus')
    img = ax.pcolormesh(h_trim, z, mean_trend, cmap=cmap, vmin=vmin, vmax=vmax)
    cbar = plt.colorbar(img)
    plt.title(var_name+' trend at '+bdry+' boundary ('+units+'/century)', fontsize=14)
    finished_plot(fig, fig_name=fig_name)


# Plot T/S profiles horizontally averaged over the eastern boundary from 70S to the coastline, for a given month (1-indexed) and year. Show the original WOA climatology, the uncorrected LENS field from the first ensemble member, and the corrected LENS field using both annual and monthly offsets.
def plot_obcs_profiles (year, month, fig_name=None):

    base_dir = '/data/oceans_output/shelf/kaight/'
    mit_grid_dir = base_dir + 'archer2_mitgcm/PAS_grid/'
    woa_file_head = base_dir+'ics_obcs/PAS/OBE'
    woa_file_tail = '_woa_mon.bin'
    woa_var = ['theta', 'salt']
    units = [deg_string+'C', 'psu']
    offset_file_head = base_dir+'CESM_bias_correction/obcs/LENS_offset_'
    offset_file_tail = '_E'
    lens_var = ['TEMP', 'SALT']
    lens_dir = '/data/oceans_input/raw_input_data/CESM/LENS/monthly/'
    lens_file_head = 'b.e11.BRCP85C5CNBDRD.f09_g16.001.pop.h.'
    lens_file_tail_1 = '.200601-208012.nc'
    lens_file_tail_2 = '.208101-210012.nc'
    start_year = 2006
    break_year = 2081
    ymax = -70
    num_var = len(woa_var)
    lon0 = find_obcs_boundary(grid, 'E')[0]
    direction = 'lon'
    ndays = np.array([days_per_month(t+1, year) for t in range(12)])
    titles = ['WOA', 'LENS uncorrected', 'LENS corrected monthly', 'LENS corrected annual']
    colours = ['blue', 'black', 'red', 'green']
    num_profiles = len(titles)

    # Build the grids
    grid = Grid(mit_grid_dir)
    hfac_slice = grid.hfac[:,:,-1]
    # Mask out dA north of 70S, tile in the z direction, and select the boundary
    dA = np.ma.masked_where(grid.lat_2d > ymax, grid.dA), grid)
    dA = xy_to_xyz(dA, grid)
    dA_slice = dA[:,:,-1]
    lens_grid_file = lens_dir + lens_file_head + lens_var[0] + lens_file_tail_1
    lens_lon, lens_lat, lens_z, lens_nx, lens_ny, lens_nz = read_pop_grid(lens_grid_file)
    # Get the interpolation coefficients from LENS to the eastern boundary
    i1, i2, c1, c2 = interp_slice_helper_nonreg(lens_lon, lens_lat, lon0, direction)
    # Extract LENS latitude to this boundary
    lens_lat_slice_full = extract_slice_nonreg(lens_lat, direction, i1, i2, c1, c2)
    # Throw away the northern hemisphere
    lens_lat_slice = trim_slice(lens_lat_slice_full, lens_lat_slice_full, hmax=0, lon=True)[0]

    profiles = np.ma.empty([num_var, num_profiles, grid.nz])
    # Loop over variables
    for v in range(num_var):
        
        # Read WOA climatology
        woa_data = read_binary(woa_file_head+woa_var[v]+woa_file_tail, [grid.nx, grid.ny, grid.nz], 'yzt')
        # Extract the right month
        woa_data = woa_data[month-1,:]
        
        # Read LENS data for this month and year
        if year < break_year:
            lens_file = lens_dir+lens_file_head+lens_var[v]+lens_file_tail_1
            t0 = (year-start_year)*months_per_year + month-1
        else:
            lens_file = lense_dir+lens_file_head+lens_var[v]+lens_file_tail_2
            t0 = (year-break_year)*months_per_year + month-1
        lens_data_3d = read_netcdf(lens_file, lens_var[v], t_start=t0, t_end=t0+1)
        # Extract the slice
        lens_data_slice = extract_slice_nonreg(lens_data_3d, direction, i1, i2, c1, c2)
        # Trim the northern boundary
        lens_data_slice = trim_slice(lens_data_slice, lens_lat_slice_full, hmax=0, lon=True)[0]
        # Interpolate to the MITgcm grid
        lens_data_interp = interp_bdry(lens_lat_slice, lens_z, lens_data_slice, np.invert(lens_data_slice.mask).astype(float), grid.lat_1d, grid.z, hfac_slice, lon=False, depth_dependent=True)
        lens_data_uncorrected = lens_data_interp
        
        # Read the LENS offset
        lens_offset = read_binary(offset_file_head+lens_var[v]+offset_file_tail, [grid.nx, grid.ny, grid.nz], 'yzt')
        # Calculate corrected LENS fields using monthly and annual offsets
        lens_data_corrected_monthly = lens_data_uncorrected + lens_offset[month-1,:]
        lens_data_corrected_annual = lens_data_uncorrected + np.average(lens_offset, axis=0, weights=ndays)

        # Horizontally average everything south of 70S
        for data_slice, n in zip([woa_data, lens_data_uncorrected, lens_data_corrected_monthly, lens_data_corrected_annual], range(num_profiles)):
            profiles[v,n,:] = np.sum(data_slice*hfac_slice*dA_slice, axis=-1)/np.sum(hfac_slice*dA_slice, axis=-1)


    # Plot
    fig, gs = set_panels('1x2C0')
    for v in range(num_var):
        ax = plt.subplot(gs[0,v])
        for n in range(num_profiles):
            ax.plot(profiles[v,n,:], grid.z, color=colours[n], label=titles[n])
        ax.grid(linestyle='dotted')
        ax.set_title(lens_var[n], fontsize=16)
        ax.set_xlabel(units[n])
        if n==0:
            ax.set_ylabel('Depth (m)')
            ax.legend(loc='lower right', bbox_to_anchor=(1, -0.35))
    finished_plot(fig, fig_name=fig_name)
    
        
        
        
    
    
    
    


        
                    
                
            
            
            
        

    

    
                
                    
                

                    
                        
        
        

    
    
            
            
            
    
