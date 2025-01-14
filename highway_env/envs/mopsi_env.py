from itertools import repeat, product
from typing import Tuple

from gym.envs.registration import register
import numpy as np

from highway_env import utils
from highway_env.envs.common.abstract import AbstractEnv
from highway_env.road.lane import LineType, StraightLane, CircularLane, SineLane
from highway_env.road.road import Road, RoadNetwork
from highway_env.vehicle.behavior import IDMVehicle
# import highway_env.vehicle.kinematics

import copy
import os
from typing import List, Tuple, Optional, Callable
import gym
from gym import Wrapper
from gym.utils import seeding
import numpy as np

from highway_env import utils
from highway_env.envs.common.action import action_factory, Action, DiscreteMetaAction, ActionType
from highway_env.envs.common.observation import observation_factory, ObservationType
from highway_env.envs.common.finite_mdp import finite_mdp
from highway_env.envs.common.graphics import EnvViewer
from highway_env.vehicle.behavior import IDMVehicle, LinearVehicle, ManuallyControlledVehicle
from highway_env.vehicle.controller import MDPVehicle
from highway_env.vehicle.kinematics import Vehicle

class MopsiEnv(AbstractEnv):
    """
    Our own environment, built from the racetrack_env.
    """

    def __init__(self,config: dict = None):
        super().__init__(config)
        self.action_reward = {"lane_centering" : 0,
                        "speed_reward" : 0,
                        "action_reward" : 0,
                        "reward" : 0}

    @classmethod
    def default_config(cls) -> dict:
        config = super().default_config()
        config.update({
            "observation": {
                "type": "OccupancyGrid",
                "features": ['presence','vx','vy','on_road'],
                "grid_size": [[-18, 18], [-18, 18]],
                "grid_step": [3, 1],
                "align_to_vehicle_axes": True,
                "features_range": {
                    "vx": [0, 20],
                    "vy": [0, 20]
                },
            },
            "action": {
                "type": "ContinuousAction",
                "longitudinal": True,
                "lateral": False,
                "target_speeds": [0, 5, 10]
            },
            "simulation_frequency": 15,
            "policy_frequency": 5,
            "duration": 1000,
            "number_of_lane" : 1,
            "collision_reward": -5,
            "lane_centering_cost": 4,
            "action_reward": -5,
            "controlled_vehicles": 1,
            "other_vehicles": 10,
            "circle_radius": 60,
            "screen_width": 800,
            "screen_height": 800,
            "centering_position": [0.5, 0.5],
            "lane_centering_coeff" : 5.0,
            "action_coeff" : 0.,
            "speed_coeff" : 5.0
        })
        return config


    def _reward(self, action: np.ndarray) -> float:
        # lane centering reward
        _, lateral = self.vehicle.lane.local_coordinates(self.vehicle.position)
        #lane_centering_reward = self.config["lane_centering_coeff"]/(1+self.config["lane_centering_cost"]*lateral**2)
        # action
        action_reward = self.config["action_coeff"] * self.config["action_reward"]*np.linalg.norm(action)
        # speed
        speed_reward = self.config["speed_coeff"] / (1+abs(
            self.road.vehicles[0].speed - self.config["action"]["target_speeds"][-1]))
        #reward
        reward = action_reward \
            + speed_reward
       # + lane_centering_reward \
        reward = reward if not self.vehicle.crashed else self.config["collision_reward"]
        #self.action_reward["lane_centering"] = lane_centering_reward
        self.action_reward["speed_reward"] = speed_reward
        self.action_reward["action_reward"] = action_reward
        self.action_reward["reward"] = reward
        return utils.lmap(reward, [self.config["collision_reward"],self.config["speed_coeff"]], [0, 10])

    def _is_terminal(self) -> bool:
        """The episode is over when a collision occurs or when the access ramp has been passed."""
        return self.vehicle.crashed or self.steps >= self.config["duration"]

    def _reset(self) -> None:
        config = self.config.get("config_reset") or "rl"
        self.action_reward = {"lane_centering": 0,
                              "speed_reward": 0,
                              "action_reward": 0,
                              "reward": 0}
        self._make_road()
        self._make_vehicles(config)

    def _make_road(self) -> None:

        nb_lane = self.config["number_of_lane"]
        radius = self.config["circle_radius"]
        net = RoadNetwork()

        # Set Speed Limits for Road Sections - Straight, Turn20, Straight, Turn 15, Turn15, Straight, Turn25x2, Turn18
        speedlimits = [None, 20, 20, 5, 20]

        # ===============================================================================================================
        # 2 - Circular Arc #1
        center1 = [0, 0]
        radii1 = radius
        if nb_lane == 1:
            net.add_lane("ENPC", "TV",
                         CircularLane(center1, radii1, np.deg2rad(90), np.deg2rad(0), width=5, clockwise=False,
                                      line_types=(LineType.CONTINUOUS, LineType.CONTINUOUS), speed_limit=speedlimits[1]))
        else :
            net.add_lane("ENPC", "TV",
                         CircularLane(center1, radii1, np.deg2rad(90), np.deg2rad(0), width=5, clockwise=False,
                                      line_types=(LineType.CONTINUOUS, LineType.NONE),
                                      speed_limit=speedlimits[1]))
            for i in range(nb_lane - 2):
                net.add_lane("ENPC", "TV",
                             CircularLane(center1, radii1 + 5*(i+1), np.deg2rad(90), np.deg2rad(-1), width=5, clockwise=False,
                                          line_types=(LineType.STRIPED, LineType.NONE), speed_limit=speedlimits[1]))
            net.add_lane("ENPC", "TV",
                         CircularLane(center1, radii1 + 5*(nb_lane - 1), np.deg2rad(90), np.deg2rad(-1), width=5, clockwise=False,
                                      line_types=(LineType.STRIPED, LineType.CONTINUOUS), speed_limit=speedlimits[1]))
        # ===============================================================================================================
        # 3 - Circular Arc #2
        center2 = center1
        radii2 = radii1
        if nb_lane == 1 :
            net.add_lane("TV", "ESIEE",
                         CircularLane(center2, radii2, np.deg2rad(-1), np.deg2rad(-90), width=5,
                                      clockwise=False, line_types=(LineType.CONTINUOUS, LineType.CONTINUOUS),
                                      speed_limit=speedlimits[2]))
        else :
            net.add_lane("TV", "ESIEE",
                         CircularLane(center2, radii2, np.deg2rad(-1), np.deg2rad(-90), width=5,
                                      clockwise=False, line_types=(LineType.CONTINUOUS, LineType.NONE),
                                      speed_limit=speedlimits[2]))
            for i in range(nb_lane - 2):
                net.add_lane("TV", "ESIEE",
                             CircularLane(center2, radii2 + 5*(i+1), np.deg2rad(-1), np.deg2rad(-90), width=5,
                                          clockwise=False, line_types=(LineType.STRIPED, LineType.NONE),
                                          speed_limit=speedlimits[2]))
            net.add_lane("TV", "ESIEE",
                         CircularLane(center2, radii2 + 5 * (nb_lane - 1), np.deg2rad(-1), np.deg2rad(-90), width=5,
                                      clockwise=False, line_types=(LineType.STRIPED, LineType.CONTINUOUS),
                                      speed_limit=speedlimits[2]))

        # ===============================================================================================================
        # 5 - Circular Arc #3
        center3 = center1
        radii3 = radius
        if nb_lane == 1 :
            net.add_lane("ESIEE", "RER",
                         CircularLane(center3, radii3, np.deg2rad(270), np.deg2rad(181), width=5,
                                      clockwise=False, line_types=(LineType.CONTINUOUS, LineType.CONTINUOUS),
                                      speed_limit=speedlimits[3]))
        else :
            net.add_lane("ESIEE", "RER",
                         CircularLane(center3, radii3, np.deg2rad(270), np.deg2rad(181), width=5,
                                      clockwise=False, line_types=(LineType.CONTINUOUS, LineType.NONE),
                                      speed_limit=speedlimits[3]))
            for i in range (nb_lane - 2):
                net.add_lane("ESIEE", "RER",
                             CircularLane(center3, radii3 + 5*(i+1), np.deg2rad(270), np.deg2rad(181), width=5,
                                          clockwise=False, line_types=(LineType.STRIPED, LineType.NONE),
                                          speed_limit=speedlimits[3]))
            net.add_lane("ESIEE", "RER",
                         CircularLane(center3, radii3 + 5*(nb_lane - 1), np.deg2rad(270), np.deg2rad(181), width=5,
                                      clockwise=False, line_types=(LineType.STRIPED, LineType.CONTINUOUS),
                                      speed_limit=speedlimits[3]))

        # ===============================================================================================================
        # 6 - Circular Arc #4
        center4 = center3
        radii4 = radii3
        if nb_lane == 1 :
            net.add_lane("RER", "ENPC",
                         CircularLane(center4, radii4 , np.deg2rad(180), np.deg2rad(90), width=5,
                                      clockwise=False, line_types=(LineType.CONTINUOUS, LineType.CONTINUOUS),
                                      speed_limit=speedlimits[4]))
        else:
            net.add_lane("RER", "ENPC",
                         CircularLane(center4, radii4 , np.deg2rad(180), np.deg2rad(90), width=5,
                                      clockwise=False, line_types=(LineType.CONTINUOUS, LineType.NONE),
                                      speed_limit=speedlimits[4]))
            for i in range (nb_lane - 2):
                net.add_lane("RER", "ENPC",
                             CircularLane(center4, radii4 + 5*(i+1), np.deg2rad(180), np.deg2rad(90), width=5,
                                          clockwise=False, line_types=(LineType.STRIPED, LineType.NONE),
                                          speed_limit=speedlimits[4]))
            net.add_lane("RER", "ENPC",
                         CircularLane(center4, radii4 + 5 * (nb_lane - 1), np.deg2rad(180), np.deg2rad(90), width=5,
                                      clockwise=False, line_types=(LineType.STRIPED, LineType.CONTINUOUS),
                                      speed_limit=speedlimits[4]))
        # ===============================================================================================================
        road = Road(network=net, np_random=self.np_random, record_history=self.config["show_trajectories"])
        self.road = road

    def _make_vehicles(self, type_vehicles) -> None:
        """
        Populate the road with one controlled vehicle and only IDM vehicles driving on a single lane.
        """
        print("type_vehicles", type_vehicles)
        rng = self.np_random
        nb_lane = self.config["number_of_lane"]

        # ==============================================================================================================
        # 1 Controlled vehicles

        self.controlled_vehicles = []
        for i in range(self.config["controlled_vehicles"]):
            lane_index = ("RER", "ENPC", 0) if i == 0 else \
                self.road.network.random_lane_index(rng)
            # lane_index = ("RER", "ENPC", rng.randint(nb_lane)) if i == 0 else \
            #     self.road.network.random_lane_index(rng)

            if type_vehicles == "sim":
                controlled_vehicle = IDMVehicle.make_on_lane(self.road, lane_index,
                                                             longitudinal=0., #  + self.road.network.get_lane(lane_index).length // 2,
                                                             speed=5)
            elif type_vehicles == "manual":
                controlled_vehicle = ManuallyControlledVehicle.make_on_lane(self.road, lane_index,
                                                             longitudinal=0., #  + self.road.network.get_lane(lane_index).length // 2,
                                                             speed=5)
            else:
                controlled_vehicle = self.action_type.vehicle_class.make_on_lane(self.road, lane_index,
                                                                    longitudinal=0., #  + self.road.network.get_lane(lane_index).length // 2,
                                                                    speed=5)
            self.controlled_vehicles.append(controlled_vehicle)
            self.road.vehicles.append(controlled_vehicle)


        # ==============================================================================================================
        # 2 Front vehicles

        list_of_nodes = ["ENPC", "TV", "ESIEE", "RER"]
        all_lanes_index = [("RER", "ENPC", 0),
        ("ENPC", "TV", 1),
        ("ENPC", "TV", 2),
        ("ESIEE", "RER", 3)]
        init_vehicle_dist = 9
        for nb_index, lane_index in enumerate(all_lanes_index[:nb_lane]):
            lane = self.road.network.get_lane(lane_index)
            len_road = 2*np.pi*self.road.network.get_lane(lane_index).radius
            init_vehicle_dist = len_road /(1+self.config["other_vehicles"]+self.config["controlled_vehicles"]) # veh length =5 here.
            vehicle_nb = 0
            for i, filled_street in enumerate(list_of_nodes) :
                vehicle_on_street = self.config["controlled_vehicles"] #TODO change when several lanes.
                enough_space = True
                while ( (vehicle_nb < self.config["other_vehicles"]) and (enough_space) ) :
                    current_lane = (filled_street, list_of_nodes[(i+1)%len(list_of_nodes)], nb_index)
                    vehicle = IDMVehicle.make_on_lane(self.road, current_lane,
                                                      longitudinal= 0. + vehicle_on_street*init_vehicle_dist,
                                                      speed = 5)

                    # Check whether we can add the new vehicle
                    end_of_the_lane = vehicle_on_street*init_vehicle_dist + vehicle.LENGTH > \
                                      self.road.network.get_lane(current_lane).length
                    if (end_of_the_lane) :
                        enough_space = False
                    else :
                        vehicle_on_street+=1
                        vehicle_nb+=1
                        self.road.vehicles.append(vehicle)


    def render(self, mode: str = 'human') -> Optional[np.ndarray]:
        """
        Render the environment.

        Create a viewer if none exists, and use it to render an image.
        :param mode: the rendering mode
        """
        self.rendering_mode = mode

        if self.viewer is None:
            self.viewer = EnvViewer(self)

        self.enable_auto_render = True

        self.viewer.display(fixed = True)

        if not self.viewer.offscreen:
            self.viewer.handle_events()
        if mode == 'rgb_array':
            image = self.viewer.get_image()
            return image


    def get_speeds(self) -> np.ndarray :
        """"
        Returns the list of the vehicle speeds present in the road.

        :return: speeds_list is an array containing the speeds
        """
        vehicle_number = len(self.road.vehicles)
        speeds_list = np.zeros((vehicle_number))
        for (i, vehicle) in enumerate(self.road.vehicles) :
            speeds_list[i] = vehicle.speed
        return speeds_list

    def var_speed(self) -> float:
        """
        :return: speed variance
        """
        sp = self.get_speeds()
        #return(sp)
        E = np.mean(sp)
        var = 0
        for i in range(len(sp)):
            var += (sp[i] - E)*(sp[i] - E)
        var = var/len(sp)
        return(var)

    def average_speed(self) -> float:
        """
        :return: speed average
        """
        sp = self.get_speeds()
        avg_speed = np.mean(sp)
        return avg_speed


register(
    id='mopsi-env-v0',
    entry_point='highway_env.envs:MopsiEnv',
)