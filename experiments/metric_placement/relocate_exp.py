import os
import argparse
import random
from time import sleep, perf_counter
import requests
from pathlib import Path

import numpy as np
from tqdm import tqdm


def extract_args(args):
    nodes = args.placement.split(";")
    if len(nodes) == 1:
        raise ValueError("Invalid Value for Placement")

    seed = args.seed
    return nodes, seed, args.output, args.metric


def get_metrics(url):
    regions = requests.get(f"{url}/export/regions")
    lines = regions.text.split("\n")
    samples = lines[-6:-1]
    time = []
    energy = []
    for sample in samples:
        content = sample.split(",")
        energy.append(float(content[-1]))
        time.append(float(content[-2]) - float(content[-3]))
    return np.mean(energy), np.std(energy), np.mean(time), np.std(time)


def compare(metrics, eval_metric):
    index = 0 if eval_metric == "energy" else 2
    min_node = 0
    for i, metric in enumerate(metrics):
        if metric[index] < metrics[min_node][index]:
            min_node = i
    return min_node


def evaluate(args):
    nodes, seed, output, metric = extract_args(args)
    print(nodes)
    random.seed(seed)
    start = perf_counter()
    server = f"http://{nodes[0].split(':')[1]}:8080"
    meta_server = f"http://{nodes[0].split(':')[1]}:2002"
    for _ in tqdm(range(100)):
        requests.post(f"{server}/add", data=str(random.randint(1, 1000)))
    add = perf_counter() - start
    configs = ["local", "relocate"]
    nodes_metrics = []
    for i, config in enumerate(configs):
        set_config = requests.get(f"{meta_server}/meta/{config}")
        sleep(5)
        for _ in tqdm(range(5)):
            requests.get(f"{server}/get")
        node_name, ip = nodes[i].split(":")
        get_time = perf_counter() - start
        metrics = get_metrics(f"http://{ip}:8000")
        nodes_metrics.append((*metrics, get_time, config))
    best_config_index = compare(nodes_metrics, metric)
    best_config = configs[best_config_index]
    search = perf_counter() - start
    requests.get(f"{meta_server}/meta/{best_config}")
    print(f"{best_config} is the best config")
    for i in range(3):
        sleep(5)
        for _ in tqdm(range(5)):
            requests.get(f"{server}/get")
        node_name, ip = nodes[best_config_index].split(":")
        get_time = perf_counter() - start
        metrics = get_metrics(f"http://{ip}:8000")
        nodes_metrics.append((*metrics, get_time, best_config))

    with open(os.path.join(output, f"exp_relocate_metrics.csv"), "w") as f:
        f.write("energy,energy_std,time,time_std,exp_time,config\n")
        for metrics in nodes_metrics:
            f.write(f"{','.join(map(str, metrics))}\n")
    with open(os.path.join(output, f"exp_relocate_exp_events.csv"), "w") as f:
        f.write("event,time\n")
        f.write(f"add,{add}\n")
        f.write(f"search,{search}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-o",
        "--output",
        help="path to CSV outputs",
        type=Path,
        default="outputs_relocate",
    )

    parser.add_argument(
        "-s", "--seed", help="seed for random number generator", type=int, default=10
    )

    parser.add_argument(
        "-p",
        "--placement",
        help="String containing info about node and their respective IPs, in the following order SERVER:IP;REMOTE_DIST:IP;REMOTE_DIST2:IP",
        required=True,
    )

    parser.add_argument(
        "-m",
        "--metric",
        help="metric used for comparison",
        choices=["energy", "time"],
        default="energy",
    )

    args = parser.parse_args()

    evaluate(args)
