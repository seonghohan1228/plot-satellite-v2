#### MODULES ############################################################
import os
os.environ["PROJ_LIB"] = "/home/seonghohan/anaconda3/share";
import h5py
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.gridspec as gridspec
from mpl_toolkits.basemap import Basemap
from datetime import datetime
import aacgmv2
from spacepy import coordinates as coords
from spacepy.time import Ticktock
import spacepy.datamodel as dm
import warnings

#########################################################################


#### CONSTANTS ##########################################################

# Filename (file path is created automatically in hdf_read()).
NORTH_POLE = 90
SOUTH_POLE = -90

DATASET1 = 'block1_values'
DATASET2 = 'block2_values'
PDF = 'PDF'
PNG = 'PNG'

# Data indices
HEPD_TIME = 7       # Time (UNIX)
MEPD_TIME = 10      # Time (UNIX)
DT = 4              # Subunit ID
PC1 = 5             # Packet count 1
POS = 16            # Position (deg)
POS_LEN = 3         # Position data length
MAG = 0             # Magnetic field
MAG_LEN = 8         # Magnetic field data length
DET0 = 13           # Detector 0
DET1 = 81           # Detector 1
DET2 = 149          # Detector 2
DET3 = 217          # Detector 3
DET_LEN = 64        # Detector data length
TEL0 = 9            # Telescope 0
TEL1 = 50           # Telescope 1
TEL2 = 91           # Telescope 2
TEL_LEN = 40        # Telescope data length



#### FUNCTIONS ########################################################

def get_file_names(orbit_no, files):
    if orbit_no < 0:
        print('Error: Invalid orbit number.')
        exit()
    if orbit_no < 10000:
        orbit_no = '0' + str(orbit_no)
    else:
        orbit_no = str(orbit_no)

    for filename in files:
        # Check orbit number for match.
        if filename[27:32] == orbit_no:
            # HEPD
            if filename[0:4] == 'HEPD':
                hepd = filename
                continue
            elif filename[0:4] == 'MEPD':
                mepd = filename
                continue
        
        # No match found.
        if filename == files[-1]:
            print('Error: No matching file found.')
            exit()

    return hepd, mepd

## Data read function
# Read HDF5 data and returns all required datasets.
def read_hdf(filename):
    # group: HEPD_DIV or MEPD_SCI
    group = filename[0:8]
    filepath = 'data/' + filename

    # Reads hdf file and closes as it leaves with statement.
    with h5py.File(filepath, 'r') as hdf:
        path1 = '/' + group + '/' + DATASET1
        path2 = '/' + group + '/' + DATASET2

        dataset1 = np.array(hdf[path1])
        dataset2 = np.array(hdf[path2])

    return dataset1, dataset2


## Data select functions
def select_HEPD(dataset1, dataset2):
    time = dataset1[:, HEPD_TIME]
    pc1 = dataset1[:, PC1]
    pos = dataset2[:, POS:POS + POS_LEN]
    mag = dataset2[:, MAG:MAG + MAG_LEN]
    tel0 = dataset1[:, TEL0:TEL0 + TEL_LEN]
    tel1 = dataset1[:, TEL1:TEL1 + TEL_LEN]
    tel2 = dataset1[:, TEL2:TEL2 + TEL_LEN]

    return time, pc1, pos, mag, tel0, tel1, tel2

def select_MEPD(dataset1, dataset2):
    time = dataset1[:, MEPD_TIME]
    dt = dataset1[:, DT]
    pc1 = dataset1[:, PC1]
    pos = dataset2[:, POS:POS + POS_LEN]
    mag = dataset2[:, MAG:MAG + MAG_LEN]
    det0 = dataset1[:, DET0:DET0 + DET_LEN]
    det1 = dataset1[:, DET1:DET1 + DET_LEN]
    det2 = dataset1[:, DET2:DET2 + DET_LEN]
    det3 = dataset1[:, DET3:DET3 + DET_LEN]

    return time, dt, pc1, pos, mag, det0, det1, det2, det3


## Calculating functions
# Slice data into MEPD-A and MEPD-B (works for PC1 and TIME)
def sliceAB(data, subunit, n):
    A = []
    B = []
    for i in range(len(data)):
        if subunit[i] == n:
            A.append(data[i])
        else:
            B.append(data[i])

    return A, B

# sliceAB 2D array data of MEPD data
def sliceAB2(data, subunit, n):
    A = []
    B = []
    for i in range(len(data)):
        if subunit[i] == n:
            A.append(data[i, :])
        else:
            B.append(data[i, :])
    
    return A, B

# Calculate average magnetic field.
def B_avg(B):
    avg = []
    for i in range(len(B)):
        avg.append(np.sqrt((B[i, 4])**2 + (B[i, 5])**2 + (B[i, 6])**2))

    return avg

# Custom colormap, cmap
def new_cmap():
    jet = plt.cm.get_cmap('jet', 256)
    newcolors = jet(np.linspace(0, 1, 256))
    white = np.array([256/256, 256/256, 256/256, 1])
    newcolors[0, :] = white
    new_cmap = matplotlib.colors.ListedColormap(newcolors)

    return new_cmap

# Select closest value
def closest(arr, value):
    c = 0
    for i in range(len(arr)):
        if (abs(arr[i] - value) < abs(arr[c] - value)):
            c = i
    
    return c

# Geomagnetic latitude
def geo_lat(alt, start_time):
    arr = np.zeros((181, 360))
    geo_lat = np.zeros((5, 360))
    for j in range(360):
        for i in range(181):
            # Change altitude into km.
            coordinates = coords.Coords([alt / 1000, i - 90, j - 180], 'GEO', 'sph')
            coordinates.ticks = Ticktock(['2019-07-17T17:51:15'], 'ISO') # Unable to use 2020 data.
            arr[i][j] = coordinates.convert('MAG', 'sph').lati
            #arr[i][j] = (np.array(aacgmv2.get_aacgm_coord(i - 90, j - 180, int(alt / 1000), start_time)))[0]
    
    for j in range(360):
        for i in range(5):
            geo_lat[i, j] = closest(arr[:, j], 30 * i - 60) - 90
    
    return geo_lat

# Telescope data (proton, electron)
def div_tel(tel0, tel1, tel2):
    # Return proton and electron data.
    return tel0[:, 17:21], tel1[:, 17:21], tel2[:, 17:21], tel0[:, 2:13], tel1[:, 2:13], tel2[:, 2:13]


# Plot graphs
def plot_graph(orbit_no, HEPD_time,HEPD_pc1, HEPD_pos, HEPD_mag, tel0, tel1, tel2,
            MEPD_time, dt, MEPD_pc1, MEPD_pos, MEPD_mag, det0, det1, det2, det3, pole, filetype):
    # Create figure.
    fig = plt.figure(figsize=(20, 30))
    outer = gridspec.GridSpec(4, 2, wspace=0.1, hspace=0.3)

    ## PC1
    inner = gridspec.GridSpecFromSubplotSpec(1, 2,
                    subplot_spec=outer[0], wspace=0.1, hspace=0.1)
    
    # Divide PC1 data into MEPD-A and MEPD-B
    MEPD_pc1_A, MEPD_pc1_B = sliceAB(MEPD_pc1, dt, 3)
    MEPD_time_A, MEPD_time_B = sliceAB(MEPD_time, dt, 3)

    # Plot HEPD PC1 data.
    ax = plt.Subplot(fig, inner[0])
    ax.plot(HEPD_pc1, HEPD_time - HEPD_time[0], '-k')
    fig.add_subplot(ax)
    ax.set_title('HEPD: Time vs PC1')
    ax.set_xlabel('PC1')
    ax.set_ylabel('Time (sec)')

    # Plot MEPD-A and MEPD-B PC1 data.
    ax = plt.Subplot(fig, inner[1])
    ax.plot(MEPD_pc1_A, MEPD_time_A - MEPD_time_A[0], '-k', label='MEPD-A')
    ax.plot(MEPD_pc1_B, MEPD_time_B - MEPD_time_B[0], '-r', label='MEPD-B')
    fig.add_subplot(ax)
    ax.set_title('MEPD: Time vs PC1')
    ax.set_xlabel('PC1')

    plt.legend()

    ## Magnetic field
    inner = gridspec.GridSpecFromSubplotSpec(1, 1,
                    subplot_spec=outer[2], wspace=0.1, hspace=0.1)

    mag_avg = B_avg(HEPD_mag)

    # Plot magnetic field data.
    ax = plt.Subplot(fig, inner[0])
    ax.plot(HEPD_time, HEPD_mag[:, 0], 'k', label='Bx')
    ax.plot(HEPD_time, HEPD_mag[:, 1], 'b', label='By')
    ax.plot(HEPD_time, HEPD_mag[:, 2], 'r', label='Bz')
    ax.plot(HEPD_time, HEPD_mag[:, 4], '--k', label='IGRF Bx')
    ax.plot(HEPD_time, HEPD_mag[:, 5], '--b', label='IGRF By')
    ax.plot(HEPD_time, HEPD_mag[:, 6], '--r', label='IGRF Bz')
    ax.plot(HEPD_time, mag_avg, '--y', label='IGRF|B|')
    fig.add_subplot(ax)
    
    plt.ylabel('Magnetic Field (nT)')
    plt.ylim(-60000, 60000)
    plt.legend(loc='upper center', ncol=7, prop={'size': 8})

    ## Satellite position
    # Mercador projection
    inner = gridspec.GridSpecFromSubplotSpec(1, 1,
                    subplot_spec=outer[1], wspace=0.1, hspace=0.1)

    lat = MEPD_pos[:, 0]
    lon = MEPD_pos[:, 1]
    alt = MEPD_pos[:, 2]
    
    start_time = datetime.fromtimestamp(MEPD_time[0]) # Converts UNIX datetime to UTC datetime
    end_time = datetime.fromtimestamp(MEPD_time[-1])

    ax = plt.Subplot(fig, inner[0])
    
    m = Basemap(projection='merc',llcrnrlat=-85,urcrnrlat=85, llcrnrlon=-180,urcrnrlon=180, ax=ax)
    m.drawcoastlines()
    m.drawmeridians(np.arange(0,360,45), labels=[False, False, False, True])
    m.drawparallels(np.arange(-90,90,30), labels=[False, True, False, False])

    # Plot satellite position.
    X, Y = m(lon, lat)
    m.scatter(X, Y, marker='.', c=MEPD_time, cmap=plt.get_cmap('jet'))
    ax.annotate(start_time.strftime('%H:%M'), (X[0], Y[0]))
    ax.annotate(end_time.strftime('%H:%M'), (X[-1], Y[-1]))

    # Plot geomagnetic latitude.
    mat = geo_lat(alt[0], start_time)
    for i in range(5):
        x, y = m(np.arange(360) - 180, mat[i, :])
        m.plot(x, y, 'b', linewidth=1)
        if i < 2:
            ax.annotate(str(30 * i - 60) + 'S', (x[0], y[0]), color='b')
        elif i == 2:
            ax.annotate('0', (x[0], y[0]), color='b')
        elif i > 2:
            ax.annotate(str(30 * i - 60) + 'N', (x[0], y[0]), color='b')

    # Plot terminator
    m.nightshade(start_time)

    ax.set_title('Orbit (Mercador projection)')

    fig.add_subplot(ax)

    # Orthographic projection.
    inner = gridspec.GridSpecFromSubplotSpec(1, 1,
                    subplot_spec=outer[3], wspace=0.1, hspace=0.1)
    
    ax = plt.Subplot(fig, inner[0])

    m = Basemap(projection='ortho', lat_0=pole, lon_0=0, ax=ax)
    m.drawcoastlines()
    m.drawmeridians(np.arange(0,360,45), labels=[False, False, False, True])
    m.drawparallels(np.arange(-90,90,30)) # Cannot label parallels on Orthographic basemap.
    
    # Plot satellite position.
    X, Y = m(lon, lat)
    m.scatter(X, Y, marker='.', c=MEPD_time, cmap=plt.get_cmap('jet'))
    ax.annotate(start_time.strftime('%H:%M'), (X[0], Y[0]))
    ax.annotate(end_time.strftime('%H:%M'), (X[-1], Y[-1]))
    
    #cbar = fig.colorbar(s1, ax=ax2, label='Time (UNIX)')

    # Plot geomagnetic latitude.
    mat = geo_lat(alt[0], start_time)
    for i in range(5):
        x, y = m(np.arange(360) - 180, mat[i, :])
        m.plot(x, y, 'b', linewidth=1)
        if i < 2:
            ax.annotate(str(30 * i - 60) + 'S', (x[0], y[0]), color='b')
        elif i == 2:
            ax.annotate('0', (x[0], y[0]), color='b')
        elif i > 2:
            ax.annotate(str(30 * i - 60) + 'N', (x[0], y[0]), color='b')

    # Plot terminator
    m.nightshade(start_time)

    ax.set_title('Orbit (Orthographic projection)')

    fig.add_subplot(ax)

    ## Telescope
    p0, p1, p2, e0, e1, e2 = div_tel(tel0, tel1, tel2)
    
    # Plot HEPD proton data
    inner = gridspec.GridSpecFromSubplotSpec(3, 1,
                    subplot_spec=outer[4], wspace=0.05, hspace=0.01)

    xmin = mdates.date2num(datetime.fromtimestamp(HEPD_time[0]))
    xmax = mdates.date2num(datetime.fromtimestamp(HEPD_time[-1]))

    p = [p0, p1, p2]
    for i in range(3):
        ax = plt.Subplot(fig, inner[i])
        ax.imshow(X=np.transpose(p[i]), origin='lower', cmap=new_cmap(), aspect='auto',
            interpolation='none', extent = [xmin, xmax, 0, 400])
        ax.text(0.02, 0.85, ('Telescope ' + str(i)), horizontalalignment='left', transform=ax.transAxes)
        if i == 1:
            ax.set_ylabel('HEPD Proton Energy [MeV]')
        fig.add_subplot(ax)

    fig.subplots_adjust(left=0.08, right=0.9, bottom=0.01, top=0.99, wspace=0.0, hspace=0.0)
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    #cb_ax_p = fig_p.add_axes([0.92, 0.05, 0.02, 0.9])
    #cbar_p = fig_p.colorbar(im_p, cax=cb_ax_p)

    # Plot HEPD electron data
    inner = gridspec.GridSpecFromSubplotSpec(3, 1,
                    subplot_spec=outer[6], wspace=0.05, hspace=0.01)

    e = [e0, e1, e2]
    for i in range(3):
        ax = plt.Subplot(fig, inner[i])
        ax.imshow(X=np.transpose(e[i]), origin='lower', cmap=new_cmap(), aspect='auto', 
            interpolation='none', extent = [xmin, xmax, 0, 400])
        ax.text(0.02, 0.85, ('Telescope ' + str(i)), horizontalalignment='left', transform=ax.transAxes)
        if i == 1:
            ax.set_ylabel('HEPD Electron Energy [MeV]')
        fig.add_subplot(ax)
        
    fig.subplots_adjust(left=0.08, right=0.9, bottom=0.01, top=0.99, wspace=0.0, hspace=0.0)
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    #cb_ax_e = fig_e.add_axes([0.92, 0.05, 0.02, 0.9])
    #cbar_e = fig_e.colorbar(im_e, cax=cb_ax_e)


    ## Detector
    # Divide PC1 data into MEPD-A and MEPD-B
    det0_A, det0_B = sliceAB2(det0, dt, 3)
    det1_A, det1_B = sliceAB2(det1, dt, 3)
    det2_A, det2_B = sliceAB2(det2, dt, 3)
    det3_A, det3_B = sliceAB2(det3, dt, 3)
    MEPD_time_A, MEPD_time_B = sliceAB(MEPD_time, dt, 3)

    # MEPD-A
    inner = gridspec.GridSpecFromSubplotSpec(4, 1,
                    subplot_spec=outer[5], wspace=0.05, hspace=0.01)
    
    # Plot MEPD-A
    xmin = mdates.date2num(datetime.fromtimestamp(MEPD_time_A[0]))
    xmax = mdates.date2num(datetime.fromtimestamp(MEPD_time_A[-1]))
    
    det = [det0_A, det1_A, det2_A, det3_A]
    for i in range(4):
        ax = plt.Subplot(fig, inner[i])
        ax.imshow(X=np.transpose(det[i]), origin='lower',cmap=new_cmap(), 
            aspect='auto', interpolation='none', extent = [xmin, xmax, 0, 400])
        ax.text(0.02, 0.85, ('Detector ' + str(i)), horizontalalignment='left', transform=ax.transAxes)
        if i == 1:
            ax.set_ylabel('Energy [keV]')
        if i == 2:
            ax.set_ylabel('MEPD-A')
        fig.add_subplot(ax)
    
    fig.subplots_adjust(left=0.08, right=0.9, bottom=0.01, top=0.99, wspace=0.0, hspace=0.0)
    #cb_ax = fig.add_axes([0.92, 0.05, 0.02, 0.9])
    #cbar = fig.colorbar(im, cax=cb_ax)
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))


    # MEPD-B
    inner = gridspec.GridSpecFromSubplotSpec(4, 1,
                    subplot_spec=outer[7], wspace=0.05, hspace=0.01)
    
    # Plot MEPD-B
    det = [det0_B, det1_B, det2_B, det3_B]
    for i in range(4):
        ax = plt.Subplot(fig, inner[i])
        ax.imshow(X=np.transpose(det[i]), origin='lower',cmap=new_cmap(), 
            aspect='auto', interpolation='none', extent = [xmin, xmax, 0, 400])
        ax.text(0.02, 0.85, ('Detector ' + str(i)), horizontalalignment='left', transform=ax.transAxes)
        if i == 1:
            ax.set_ylabel('Energy [keV]')
        if i == 2:
            ax.set_ylabel('MEPD-B')
        fig.add_subplot(ax)

    fig.subplots_adjust(left=0.08, right=0.9, bottom=0.01, top=0.99, wspace=0.0, hspace=0.0)
    #cb_ax = fig.add_axes([0.92, 0.05, 0.02, 0.9])
    #cbar = fig.colorbar(im, cax=cb_ax)
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))


    a = start_time.strftime('%Y/%m/%d %H:%M:%S')
    b = end_time.strftime('%H:%M:%S')
    c = MEPD_time[-1] - MEPD_time[0]

    if orbit_no < 10000 :
        title = 'Orbit: 0' + str(orbit_no) + '   Date: ' + str(a) + ' - ' + str(b) + 'UT (' + str(c) + ' sec)'
        savename = './plots/ORB_0' + str(orbit_no)
    else:
        title = 'Orbit: ' + str(orbit_no) + '   Date: ' + str(a) + ' - ' + str(b) + 'UT (' + str(c) + ' sec)'
        savename = './plots/ORB_' + str(orbit_no)

    fig.suptitle(title, fontsize=20)

    if filetype == 'PDF':
        plt.savefig(savename + '.pdf')
    if filetype == 'PNG':
        plt.savefig(savename + '.png')

####################################################################################

#### RUN ##########################################################################

# Ignore warnings.
warnings.filterwarnings('ignore')

files = os.listdir(os.getcwd() + '/data/')

## Show available files.
print('\nAvailable files:')
for filename in files:
    print(filename)
print('\n')

ORBIT_NO = 8795

# Get filenames.
HEPD_filename, MEPD_filename = get_file_names(ORBIT_NO, files)

HEPD_data = dm.fromHDF5('data/' + HEPD_filename)
MEPD_data = dm.fromHDF5('data/' + MEPD_filename)

## Show file tree.
print('File trees:')
HEPD_data.tree(attrs=False)
MEPD_data.tree(attrs=False)
print('\n')

# Read and store data.
HEPD_dataset1, HEPD_dataset2 = read_hdf(HEPD_filename)
MEPD_dataset1, MEPD_dataset2 = read_hdf(MEPD_filename)

# Select required data from datasets.
HEPD_time, HEPD_pc1, HEPD_pos, HEPD_mag, tel0, tel1, tel2 = select_HEPD(HEPD_dataset1, HEPD_dataset2)
MEPD_time, dt, MEPD_pc1, MEPD_pos, MEPD_mag, det0, det1, det2, det3 = select_MEPD(MEPD_dataset1, MEPD_dataset2)

plot_graph(ORBIT_NO, HEPD_time,HEPD_pc1, HEPD_pos, HEPD_mag, tel0, tel1, tel2,
            MEPD_time, dt, MEPD_pc1, MEPD_pos, MEPD_mag, det0, det1, det2, det3, SOUTH_POLE, PDF)

######################################################################################








