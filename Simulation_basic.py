"""
    MOPSI Project
RL and autonomous vehicles

Simulations with no trained agents.
The simulations are rendered as gif and stored in the results' folder.

Authors : Even Matencio - Charles.A Gourio
Date : 15/02:2021
"""

# Standard library
import os
import sys
import numpy as np
from matplotlib import pyplot as plt
import pygame
import gym
from tqdm import tqdm

# Local source
import highway_env

# 3rd party packages
from datetime import datetime
import imageio


#=====================================================================================
#============================== FUNCTIONS ============================================
#=====================================================================================

def show_var_infos(vari,title="swow_var_info", dirpath = None, average_speed = None):
    title_file = title
    fig,ax = plt.subplots()
    ax.plot(vari)
    ax.set_title("variance evolution from t=0 to t=T")
    ax.set_xlabel("Time (nb it)")
    ax.set_ylabel("variance (m/s)")

    if average_speed is not None:
        fig2,ax2 = plt.subplots()
        ax2.plot(average_speed)
        ax2.set_title("average speed evolution from t=0 to t=T")
        ax2.set_xlabel("Time (nb it)")
        ax2.set_ylabel("average speed (m/s)")

    if dirpath != None:
        fig.savefig(dirpath+"/"+ title_file +".png")
    plt.show()

env = gym.make('mopsi-env-v0')

#=====================================================================================
#================== CONFIGURATION AND GLOBAL VARIABLES ===============================
#=====================================================================================

# Configuration
env.config["number_of_lane"] = 1
env.config["other_vehicles"] = 17
env.config["controlled_vehicles"] = 1
env.config["duration"] = 1000
env.config["circle_radius"] = 60

env.config["screen_width"] = 800
env.config["screen_height"] = 800

# Saving results and data
SAVE_SIMULATION = False

# Uncomment next line "sim" below for an IDM simulation
# env.config["config_reset"] = "sim"

# Uncomment next line "manual" below for a manual control
env.config["config_reset"] = "manual"

env.reset()


#=====================================================================================
#============================ MAIN PROGRAM ===========================================
#=====================================================================================

if __name__ == "__main__":

    # Initialisation
    hist = []
    speed_hist = []
    done = False
    nb_vehicles = env.config["other_vehicles"] + env.config["controlled_vehicles"]
    real_nb_vehicles = len(env.road.vehicles)
    # print(real_nb_vehicles)
    duration = env.config["duration"]

    if SAVE_SIMULATION and duration < 100:
        raise SystemError("Simulation must have at least 100it")

    # Initialisation of results folder
    time = str(datetime.now().date()) + "___" + str(
        datetime.now().hour) + "_" + str(datetime.now().minute) + "_" + str(datetime.now().second)
    result_folder_path = "results/Simulation__" + time
    if SAVE_SIMULATION:
        os.mkdir(result_folder_path)

        time_gif = duration//2
        duration_gif = 50
        filenames = []


    # Main Loop
    for i in tqdm(range(duration)):

        # Building renders for the beginning and the end of the simulation
        if SAVE_SIMULATION and i == 1:
            name_picture = result_folder_path + "/" + "render_begin" + str(i) + ".png"
            plt.imsave(name_picture, env.render(mode="rgb_array"))

        if SAVE_SIMULATION and i == duration - 1:
            name_picture = result_folder_path + "/" + "render_end" + str(i) + ".png"
            plt.imsave(name_picture, env.render(mode="rgb_array"))

        # Gif
        if SAVE_SIMULATION and i >= time_gif and i <= time_gif + duration_gif:
            name_picture = result_folder_path + "/" + "render" + str(i) + ".png"
            filenames.append(name_picture)
            plt.imsave(name_picture, env.render(mode="rgb_array"))

        # Failure
        if SAVE_SIMULATION and done and i!=duration - 1:
            name_picture = result_folder_path + "/" + "render_fail" + str(i) + ".png"
            plt.imsave(name_picture, env.render(mode="rgb_array"))
            sys.exit()

        # Action
        obs, reward, done, info = env.step([1, 0])
        env.render()

        # Histogram
        hist.append(env.var_speed())
        speed_hist.append(env.average_speed())


    # Create gif

    if SAVE_SIMULATION:
        with imageio.get_writer(result_folder_path + "/results.gif", mode = "I") as writer :
            for filename in filenames:
                image = imageio.imread(filename)
                writer.append_data(image)
        for filename in set(filenames):
            os.remove(filename)

        show_var_infos(hist[10:], "traffic_" + str(real_nb_vehicles) + "_vehicles" + "__" + str(duration) + "it__",
                   dirpath=result_folder_path,average_speed=speed_hist)

    else:
        show_var_infos(hist[10:], "traffic_" + str(real_nb_vehicles) + "_vehicles" + "__" + str(duration) + "it__",
                   dirpath= None, average_speed=speed_hist)
