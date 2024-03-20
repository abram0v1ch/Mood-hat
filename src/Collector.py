import numpy as np
import threading

from pythonosc import dispatcher, osc_server

received_data_lock = threading.Lock() # shared between stream handler and first pre-processor

# for development
sampling_rate = 1 # make sure to set the same in dummy server
save_latest = 10 # number of latest samples to save


'''
Class to manage collection of the BCI data and store into a buffer store. Used as the input of
the pipeline to apply functions onto the data storage in the BCICollector.
'''
class BCI:
	def __init__(self, BCI_name="MuseS", BCI_params={}):
		self.name = BCI_name
		if BCI_name == "MuseS":
			if BCI_params:
				self.BCI_params == BCI_params
			else:
				self.BCI_params = {"sampling_rate": 256, "streaming_software":"Petals", "streaming_protocol":"OSC", "cache_size":256*30, "channel_size": 4}
		elif BCI_name == "DUMMY":
			self.BCI_params = {"sampling_rate": sampling_rate, "streaming_software":"DUMMY", "streaming_protocol":"OSC", "cache_size":sampling_rate * save_latest, "channel_size": 4}
		else:
			raise Exception("Unsupported BCI board") # change this when adding other headsets
		
		self.sampling_rate = self.BCI_params["sampling_rate"]
		self.streaming_software = self.BCI_params["streaming_software"]
		self.streaming_protocol = self.BCI_params["streaming_protocol"]
		self.cache_size = self.BCI_params["cache_size"]
		self.cache = np.empty((save_latest, self.BCI_params["channel_size"] + 1))  # cache of received data; development


	def receive_stream(self):
		# TODO: make it general, based on the BCI_params
		if self.name == "DUMMY":
			disp = dispatcher.Dispatcher()
			disp.map('/random', self.handle_stream)

			server = osc_server.ThreadingOSCUDPServer(
				("127.0.0.1", 14739),
				disp
			)
			server.serve_forever()
	

	def handle_stream(self, *args):
		global received_data_lock
		sample_id = args[3]
		data = args[4:-1]  # get data from the streamer
		with received_data_lock:
			# shift the cache to the left by one position
			self.cache = np.roll(self.cache, -1, axis=0)
			# add the new data to the end of the cache
			self.cache[-1] = (sample_id,) + data


class PreProcessingSubBlock:
	# add cache with preprocessed data?
	pass

class PostProcessingSubBlock:
	pass

class MovingAverageFilter(PreProcessingSubBlock):
	def __init__(self, kernel_size=8, channel_count=4):
		self.kernel_size = kernel_size
		self.channel_count = channel_count

	def start(self, stream):
		... #TODO implement moving average filter

class OutputBlock:
	pass


class ProcessingPipeline:
	def __init__(self, bci:BCI, *args):
		self.board = bci
		self.PreProcessingBlock = []
		self.PostProcessingBlock = []
		for arg in args:
			if isinstance(arg, PreProcessingSubBlock):
				self.PreProcessingBlock.append(arg)
			elif isinstance(arg, PostProcessingSubBlock):
				self.PostProcessingBlock.append(arg)
			else:
				raise TypeError("Argument is not a processing subblock")

	def run(self):
		receive_thread = threading.Thread(target=self.board.receive_stream)

		# start threads
		receive_thread.start()

		# finish threafs
		receive_thread.join()


if __name__ == "__main__":
	bci = BCI("DUMMY")
	processor = ProcessingPipeline(bci, MovingAverageFilter(2, 4))

	processor.run()
