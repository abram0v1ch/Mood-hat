import time
import random
from pythonosc import udp_client


def send_random_eeg_data(client, start_time, sample_id):
    unix_ts = time.time()
    lsl_ts = unix_ts - start_time
    data = tuple(random.randint(-1000, 1000) for _ in range(5))
    message = (unix_ts, lsl_ts, sample_id) + data
    client.send_message("/random", message)


if __name__ == "__main__":
    client = udp_client.SimpleUDPClient("127.0.0.1", 14739) # default OSC port
    sampling_rate = 256

    sample_id = 0

    while True:
        start_time = time.time()
        for _ in range(sampling_rate):
            send_random_eeg_data(client, start_time, sample_id)
            sample_id += 1
            time_elapsed = time.time() - start_time
            # ensure even rate
            if time_elapsed < 1.0:
                time.sleep((1.0 - time_elapsed) / sampling_rate)
        # time.sleep(1) # add delay between to see how packets arrive
