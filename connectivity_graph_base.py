import pyedflib
import numpy as np
import connectivipy as cp
import matplotlib.pyplot as plt
import mne
import networkx as nx


class ConnectivityGraph:
    """Class to handle data and methods for the creation of the
    Connectivity Graphs, directed binary and directed weighted.
    """

    def __init__(self, path):
        """
        Args:
        ----------
        path : string
            Filepath of the EDF file.
        """
        self.channel_loc_path = "./data/channel_locations.txt"
        self.sample_freq = None
        self.values = None
        self.channels = None
        self.num_of_channels = None
        self.num_of_samples = None
        self.read_edf_data(path)
        self.channel_locations = None
        self.connectivity_matrix = None
        self.binary_adjacency_matrix = None
        self.G = None
        self.Gw = None

    def read_edf_data(self, path):
        """Reads the EDF file and saves data and info as attributes
        of the class instance.

        Args:
        ----------
        path : string
            Filepath of the EDF file.
        """
        raw = mne.io.read_raw_edf(path)
        df = raw.to_data_frame()
        self.sample_freq = raw.info['sfreq']
        df = df.drop(['time'], axis=1)
        self.values = df.T.values
        self.channels = list(map(lambda x: x.strip('.'), df.columns))
        self.num_of_channels, self.num_of_samples = self.values.shape
        print("EDF data loaded!")

    def load_channel_locations(self):
        locations = {}

        with open(self.channel_loc_path, newline='') as fp:
            _ = fp.__next__()

            for line in fp:
                _, label, x, y = line.split()
                label = label.rstrip(".")
                x = float(x)
                y = float(y)
                locations[label] = (x, y)

            self.channel_locations = locations

    def compute_connectivity(self, freq, method="PDC", algorithm="yw",
                             order=None, max_order=10, plot=False,
                             resolution=100, threshold=None):
        """Pass
        """
        if not order:
            best, crit = cp.Mvar.order_akaike(self.values, max_order)
            if plot:
                plt.plot(1+np.arange(len(crit)), crit, marker='o',
                         linestyle='dashed', markersize=8, markerfacecolor='yellow')
                plt.grid()
                plt.show()
            p = best
        else:
            p = order

        data = cp.Data(self.values, chan_names=self.channels)
        data.fit_mvar(p, algorithm)
        # multivariate model coefficient (see slides)
        ar, vr = data.mvar_coefficients
        if method == 'DTF':
            Adj = cp.conn.dtf_fun(ar, vr, fs=self.sample_freq,
                                  resolution=100)[freq, :, :]
        else:
            Adj = cp.conn.pdc_fun(ar, vr, fs=self.sample_freq,
                                  resolution=100)[freq, :, :]

        np.fill_diagonal(Adj, 0)

        # create Graph from Adj matrix
        G = nx.from_numpy_matrix(np.array(Adj), create_using=nx.DiGraph)
        A = nx.adjacency_matrix(G)
        A = A.toarray()

        # set values of diagonal zero to avoid self-loops
        np.fill_diagonal(A, 0)

        # reduce Graph density
        while(nx.density(G) > threshold):
            # find min values different from zeros
            arg_min = np.argwhere(A == np.min(A[np.nonzero(A)]))
            i, j = arg_min[0][0], arg_min[0][1]
            # remove i,j edge from the graph
            G.remove_edge(i, j)
            # recalculate the graph
            A = nx.adjacency_matrix(G)
            A = A.toarray()
            np.fill_diagonal(A, 0)
            # np.fill_diagonal(A,diag)

        density = nx.density(G)
        connectivity_matrix = A.copy()
        A[A > 0] = 1
        binary_adjacency_matrix = A

        self.connectivity_matrix = connectivity_matrix
        self.binary_adjacency_matrix = binary_adjacency_matrix

        # load coordinates
        self.load_channel_locations()

        # create directed binary graph
        G = nx.DiGraph(binary_adjacency_matrix)
        new_labels = {}
        for i, node in enumerate(G.nodes):
            new_labels[node] = self.channels[i]
        self.G = nx.relabel.relabel_nodes(G, new_labels, copy=True)
        # nx.set_node_attributes(self.G, self.channel_locations, "pos")

        # create directed weighted graph
        Gw = nx.DiGraph(connectivity_matrix)
        self.Gw = nx.relabel.relabel_nodes(Gw, new_labels, copy=True)
        # nx.set_node_attributes(self.Gw, self.channel_locations, "pos")