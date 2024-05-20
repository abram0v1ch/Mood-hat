import numpy as np
import threading
import time
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mne import create_info
from mne.epochs import EpochsArray
from mne.time_frequency import psd_array_multitaper
from queue import Queue
from pythonosc import dispatcher, osc_server

'''
Class to manage collection of the BCI data and store into a buffer store. Used as the input of
the pipeline to apply functions onto the data storage in the BCICollector.
'''
class BCI:
    def __init__(self, BCI_name="MuseS", BCI_params=None, osc_ip="127.0.0.1", osc_port=5000):
        self.name = BCI_name
        if BCI_params is None:
            self.BCI_params = {
                "sampling_rate": 256,
                "streaming_software": "Petals",
                "streaming_protocol": "OSC",
                "cache_size": 256 * 30
            }
        else:
            self.BCI_params = BCI_params
        
        self.osc_ip = osc_ip
        self.osc_port = osc_port
        
        self.sampling_rate = self.BCI_params["sampling_rate"]
        self.streaming_software = self.BCI_params["streaming_software"]
        self.streaming_protocol = self.BCI_params["streaming_protocol"]
        self.cache_size = self.BCI_params["cache_size"]
        self.cache = np.zeros((self.cache_size, 4))  # Simulated 4-channel data cache
        self.lock = threading.Lock()


    def simulate_data_stream(self):
        while True:
            new_data = np.random.randn(self.sampling_rate, 4)  # Simulate one second of data
            with self.lock:
                self.cache = np.roll(self.cache, -self.sampling_rate, axis=0)
                self.cache[-self.sampling_rate:, :] = new_data
            time.sleep(1)


    def osc_data_handler(self, unused_addr, *args):
        new_data = np.array(args).reshape(1, -1)
        with self.lock:
            self.cache = np.roll(self.cache, -1, axis=0)
            self.cache[-1, :] = new_data


    def start_osc_stream(self):
        disp = dispatcher.Dispatcher()
        disp.map("/muse/eeg", self.osc_data_handler)
        server = osc_server.ThreadingOSCUDPServer((self.osc_ip, self.osc_port), disp)
        print(f"Serving on {self.osc_ip}:{self.osc_port}")
        server.serve_forever()


class PreProcessingSubBlock:
    pass


class PostProcessingSubBlock:
    pass


class MovingAverageFilter(PreProcessingSubBlock):
    def __init__(self, kernel_size=8, channel_count=4):
        self.kernel_size = kernel_size
        self.channel_count = channel_count


    def start(self, stream):
        with stream.lock:
            for ch in range(self.channel_count):
                stream.cache[:, ch] = np.convolve(
                    stream.cache[:, ch], np.ones(self.kernel_size) / self.kernel_size, mode='same'
                )


class FrequencyDecompositionFilter(PostProcessingSubBlock):
    def __init__(self, sfreq):
        self.sfreq = sfreq


    def start(self, stream):
        info = create_info(ch_names=['TP9', 'AF7', 'AF8', 'TP10'], sfreq=self.sfreq, ch_types=['eeg'] * 4)
        with stream.lock:
            data = stream.cache[-self.sfreq:].T  # Use only the most recent second of data
            epochs = EpochsArray(data[np.newaxis, :, :], info)
            psds, freqs = psd_array_multitaper(data, sfreq=self.sfreq, fmin=1, fmax=40, adaptive=True, normalization='full', n_jobs=1)

        bands = {'alpha': (8, 12), 'beta': (13, 30), 'gamma': (31, 40), 'theta': (4, 7)}
        band_powers = {}
        for band, (fmin, fmax) in bands.items():
            idx = np.where((freqs >= fmin) & (freqs <= fmax))[0]
            band_powers[band] = psds[:, idx].mean(axis=1)

        return band_powers


class OutputBlock:
    def __init__(self, queue):
        self.queue = queue
        self.fig, self.ax = plt.subplots()
        self.color_map = np.zeros((100, 400, 3))
        self.labels = ["Alpha", "Beta", "Gamma", "Theta"]


    def update_plot(self, frame):
        if not self.queue.empty():
            band_powers = self.queue.get()
            if band_powers is None:
                return

            colors = {
                'alpha': 'Greens',
                'beta': 'Oranges',
                'gamma': 'Reds',
                'theta': 'Blues'
            }

            self.color_map.fill(0)  # Clear the color_map
            for i, (label, band) in enumerate(zip(self.labels, ['alpha', 'beta', 'gamma', 'theta'])):
                power = band_powers[band]
                cmap = plt.get_cmap(colors[band])
                norm_power = power / power.max()
                for j in range(4):
                    self.color_map[:, i * 100:(i + 1) * 100, :] = cmap(norm_power[j])[:3]

            self.ax.clear()
            self.ax.imshow(self.color_map)
            self.ax.axis('off')
            for i, label in enumerate(self.labels):
                self.ax.text(i * 100 + 50, 110, label, ha='center', va='top', fontsize=12, color='white', bbox=dict(facecolor='black', alpha=0.5))


    def start_animation(self):
        self.ani = FuncAnimation(self.fig, self.update_plot, interval=1000)
        plt.show()


class ProcessingPipeline:
    def __init__(self, bci: BCI, queue: Queue, **args):
        self.board = bci
        self.queue = queue
        self.PreProcessingBlock = []
        self.PostProcessingBlock = []
        self.output_block = None
        for arg in args.values():
            if isinstance(arg, PreProcessingSubBlock):
                self.PreProcessingBlock.append(arg)
            elif isinstance(arg, PostProcessingSubBlock):
                self.PostProcessingBlock.append(arg)
            elif isinstance(arg, OutputBlock):
                self.output_block = arg
            else:
                raise TypeError("Argument is not a processing subblock")


    def run(self):
        while True:
            for pre_block in self.PreProcessingBlock:
                pre_block.start(self.board)
            band_powers = {}
            for post_block in self.PostProcessingBlock:
                band_powers = post_block.start(self.board)
            self.queue.put(band_powers)
            time.sleep(1)

# Initialize BCI
bci = BCI()

# Create a queue for communication between threads
queue = Queue()

# Initialize blocks
moving_average_filter = MovingAverageFilter()
freq_decomp_filter = FrequencyDecompositionFilter(sfreq=bci.sampling_rate)
output_block = OutputBlock(queue)

# Define processing pipeline
pipeline = ProcessingPipeline(bci, queue, pre=moving_average_filter, post=freq_decomp_filter, output=output_block)

# Start the data stream handling
data_thread = threading.Thread(target=bci.simulate_data_stream) # simulation
# data_thread = threading.Thread(target=bci.start_osc_stream) # headset stream
data_thread.start()

# Start the processing
pipeline_thread = threading.Thread(target=pipeline.run)
pipeline_thread.start()

# Start the plot updating
output_block.start_animation()
