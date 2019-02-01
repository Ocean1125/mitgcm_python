# Type "conda activate animations" before running the animation functions so you can access ffmpeg.
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import os

from ..grid import Grid
from ..plot_latlon import latlon_plot
from ..utils import str_is_int, real_dir, convert_ismr, mask_except_ice, mask_land, select_top, select_bottom
from ..constants import deg_string
from ..file_io import read_netcdf


def animate_latlon (var, output_dir='./', file_name='output.nc', vmin=None, vmax=None, mov_name=None):

    output_dir = real_dir(output_dir)

    # Get all the directories, one per segment
    segment_dir = []
    for name in os.listdir(output_dir):
        # Look for directories composed of numbers (date codes)
        if os.path.isdir(output_dir+name) and str_is_int(name[:-1]):
            segment_dir.append(name)
    # Make sure in chronological order
    segment_dir.sort()

    # Inner function to read and process data from a single file
    def read_process_data (file_path, var_name, grid, mask_option='3d', gtype='t', lev_option=None, ismr=False):
        data = read_netcdf(file_path, var_name)
        if mask_option == '3d':
            data = mask_3d(data, grid, gtype=gtype, time_dependent=True)
        elif mask_option == 'except_ice':
            data = mask_except_ice(data, grid, gtype=gtype, time_dependent=True)
        elif mask_option == 'land':
            data = mask_land(data, grid, gtype=gtype, time_dependent=True)
        else:
            print 'Error (read_process_data): invalid mask_option ' + mask_option
            sys.exit()
        if lev_option is not None:
            if lev_option == 'top':
                data = select_top(data)
            elif lev_option == 'bottom':
                data = select_bottom(data)
            else:
                print 'Error (read_process_data): invalid lev_option ' + lev_option
                sys.exit()
        if ismr:
            data = convert_ismr(data)
        return data

    all_data = []
    all_grids = []
    # Loop over segments
    for sdir in segment_dir:
        # Construct the file name
        file_path = output_dir + sdir + 'MITgcm/' + file_name
        print 'Processing ' + file_path
        # Build the grid
        grid = Grid(file_path)
        # Read and process the variable we need
        ctype = 'basic'
        if var == 'ismr':
            read_process_data(file_path, 'SHIfwFlx', grid, mask_option='except_ice', ismr=True)
            title = 'Ice shelf melt rate (m/y)'
            ctype = 'ismr'
        elif var == 'bwtemp':
            read_process_data(file_path, 'THETA', grid, lev_option='bottom')
            title = 'Bottom water temperature ('+deg_string+'C)'
        elif var == 'bwsalt':
            read_process_data(file_path, 'SALT', grid, lev_option='bottom')
            title = 'Bottom water salinity (psu)'
        elif var == 'bdry_temp':
            read_process_data(file_path, 'THETA', grid, mask_option='except_ice', lev_option='top')
            title = 'Boundary layer temperature ('+deg_string+'C)'
        elif var == 'bdry_salt':
            read_process_data(file_path, 'SALT', grid, mask_option='except_ice', lev_option='top')
            title = 'Boundary layer salinity (psu)'
        else:
            print 'Error (animate_latlon): invalid var ' + var
            sys.exit()
        # Loop over timesteps
        for t in range(data.shape[0]):
            # Extract the data from this timestep
            # Save it and the grid to the long lists
            all_data.append(data[t,:])
            all_grids.append(grid)

    if vmin is None:
        vmin = np.amin(data)
    if vmax is None:
        vmax = np.amax(data)

    # Make the initial figure
    fig, ax = latlon_plot(all_data[0], all_grids[0], gtype=gtype, ctype=ctype, vmin=vmin, vmax=vmax, date_string='1', title=title, label_latlon=False, return_fig=True)

    # Function to update figure with the given frame
    def animate(i):
        latlon_plot(all_data[i], all_grids[i], ax=ax, gtype=gtype, ctype=ctype, vmin=vmin, vmax=vmax, date_string=str(i+1), title=title, label_latlon=False)

    # Call this for each frame
    anim = animation.FuncAnimation(fig, func=animate, frames=range(len(all_data)), interval=1000)
    if mov_name is not None:
        anim.save(mov_name)
    else:
        plt.show()