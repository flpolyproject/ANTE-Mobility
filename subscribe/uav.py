import os,sys, glob
sys.path.append("./../GIA")
import traci
from visualize import Visualize
from traci_env import EnvironmentListener

import traci.constants as tc
from GIA import *
from concurrent.futures import ThreadPoolExecutor as pool
from random import choice
import time

from settings import GraphSetting

from util import *
import numpy as np
import dill as pickle
import datetime


class algo_result(object):
	def __init__(self, function, name):
		self.name=name
		self.poly_ids = []
		self.winners = []
		self.aiou = []  #aiou value each round
		self.function = function
		self.prev_winner_poly = []
		self.all_users = None
		self.len_active =[] #active users each round
		self.allwinners = [] #winners list each round
		self.covered = None #determined by montecarlo


class algo_result_multi(object):
	def __init__(self, name=None):
		self.algo_result_list = {} #name:[]
		self.name = name

	def save(self):
		path = f"./../results/UAV_objects/{self.name}.uav"
		with open(path, "wb") as f:
			pickle.dump(self, f)
			print(f"uav saved to {path}")
	
	def load(self, path):
		with open(path, 'rb') as config_dictionary_file:
			value = pickle.load(config_dictionary_file)
			self.name = os.path.basename(path).split(".")[0]
			return value


	

class UAV(EnvironmentListener):
	def __init__(self, sim_number, _seed=None):
		super(UAV, self).__init__(sim_number, _seed=_seed, ATNE=False)

		self.tick=0
		self.last_route = GraphSetting.car_numbers
		self.budget = 5

		self.algo_result_multi = algo_result_multi(self.budget)

	
		self.gia_algo = algo_result(GIAmap, "gia")
		self.min_algo = algo_result(choose_min, "min")
		self.algo_list = [self.gia_algo, self.min_algo]


	def get_arrived_veh(self):
		arrived = traci.simulation.getArrivedIDList()

		edge_list = list(self.sim_env.map_data.edges.keys())
		for veh_id in arrived:

			print(f"{veh_id} arrived, recreating")
			new_dest = choice(edge_list)
			new_start = choice(edge_list)

			while True:
				try:
					new_route = traci.simulation.findRoute(new_start, new_dest)
					if (new_dest == new_start) or (not new_route.edges):
						new_dest = choice(edge_list)
						new_start = choice(edge_list)
						continue
					break
				except Exception:
					continue


			route_id = 'route_'+str(self.last_route)
			
			traci.route.add(route_id, new_route.edges)
			self.last_route +=1


			traci.vehicle.add(veh_id, route_id ,departLane='random')

			#print(f"{veh_id} added successfully, starting {new_start}, end {new_dest} {traci.vehicle.getPosition(veh_id)}")




	def step(self, t=0):
		self.vehicle_sub()
		self.populate_post()
		self.get_arrived_veh()

		

		for algo in self.algo_list:

			if not algo.all_users:
				algo.all_users = set_users(self.sim_env.veh_data, algo.name)

			if self.tick % 20 == 0:
				#choose_min vs GIAmap
				
				algo.all_users, algo.winners, len_active = algo.function(algo.all_users, self.sim_env.veh_data, budget=self.budget)

				algo.len_active.append(len_active)
				aiou = average_iou(algo.winners)/len_active  #iou per active player value is better for gia

				if algo.winners:
					algo.aiou.append(aiou)
					algo.allwinners.append(algo.winners)

				print(f"{algo.name}{self.tick} {len(algo.winners)}/{len(self.sim_env.veh_data)} Average IOU value:{aiou} #active:{len_active}")


				
			else:
				algo.winners = []


		

		self.tick += 1

		if self.tick % 1000 == 0:
			#self.break_condition = True
			print(np.mean(self.algo_list[0].aiou), np.mean(self.algo_list[1].aiou))
			print(np.mean(self.algo_list[0].len_active), np.mean(self.algo_list[1].len_active))

			for algo in self.algo_list:
				self.algo_result_multi.algo_result_list[algo.name] = algo

			self.algo_result_multi.save()
			self.budget+= 5
			self.algo_result_multi = algo_result_multi(self.budget)

		if self.tick == 10000:
			self.break_condition = True




		
		
