
import traci
import traci.constants as tc
from postprocess import PostGraph
from env import Environment
from random import choice, seed
import math
#from settings import GraphSetting
import dill as pickle
import os, glob
from util import *
from _map import Poi
import time as tm

from visualize import Visualize
import logging
import json
import copy

from postprocess import DataCaptureGraph

#env is for storing data contains map and players
#try to keep all traci calls in here


class EnvironmentListener(traci.StepListener):
	def __init__(self, sim_number, init=True, _seed=None, setting_obj=None, algo="ATNE", main_env=None, post_process_graph=None, new_players=False):
		super(EnvironmentListener, self).__init__()
		seed(_seed)

		self.GraphSetting = setting_obj

		self.GraphSetting.current_running_algo = algo

		self.sim_number = sim_number

		self.post_process = PostGraph(sim_number, columns=["sim_number", "sim_step", "veh_id", "edge_id", "speed", "capacity", "budget", "prev_poi", "algo"])


		#self.post_process = PostGraph(self.sim_number, columns=["sim_number", "sim_step", "veh_id", "edge_id", "speed", "capacity", "budget", "prev_poi"]) #this is handling for saving csv
		self.t = 0
		self.main_env = main_env
		self.new_players = new_players

		self.break_condition = False #condition to check if all vehicles has arrived

		
		file_dir = os.path.dirname(self.GraphSetting.sumo_config)
		map_list = glob.glob(os.path.join(file_dir, r"*.map"))
		try:
			self.sim_env = self.read(map_list[0])
			print(f"loaded map from {map_list[0]}")
			self.sim_env.GraphSetting = setting_obj #loading map need to change setting of the map
 

		except IndexError:
			print(f".map file generating for {self.GraphSetting.sumo_config}")
			self.sim_env = Environment(setting_obj = self.GraphSetting)
			self.save(self.GraphSetting.sumo_config, self.sim_env)

		self.algo = algo

		self.sim_env.algo = algo

		logging.info(f"RUNNING ALGO {algo} simulation {sim_number}")

		if init:
			self.initial_reward_random(self.GraphSetting.reward_numbers)
			self.initial_route_random(self.GraphSetting.car_numbers)


		self.junction_sub()


		
	def read(self, target_path):
		with open(target_path, "rb") as f:
			return pickle.load(f)
	def save(self, source_path, target_object):
		file_name = f"{os.path.basename(source_path).split('.')[0]}.map"
		file_dir = os.path.dirname(source_path)
		target_path = os.path.join(file_dir, file_name)
		with open(target_path, "wb") as f:
			pickle.dump(target_object, f)
			print(f"map saved to {target_path}")

	def reward_to_json(self, file_path):

		reward_dict = {obj.junction: obj.value for key, obj in self.sim_env.map_data.pois.items()}
		with open(os.path.join(file_path, "reward.json"), "w") as f:
			json.dump(reward_dict, f)


		

	def initial_route_random(self, amount, seed=None):

		logging.info(f"Initializing routes for {self.algo} sim {self.sim_number}")


		if (not self.main_env) or self.new_players:



			if self.new_players:

				print("IM RESETTING THE DATA CAPTUER")
				self.sim_env.post_process_graph = DataCaptureGraph()
				self.sim_env.post_process_graph.reward_list =  self.sim_env.map_data.pois

			self.route_dict = {}
			self.veh_dict = {}


			list_edges = list(self.sim_env.map_data.edges)
			list_juncts = list(self.sim_env.map_data.junctions)


			for i in range(amount):
				veh_id = 'veh_'+str(i)
				route_id = 'route_'+str(i)
				
				while True:
					try:
						start = choice(list_juncts)
						end = self.GraphSetting.destination
						if self.GraphSetting.destination == "random":
							end = choice(list_juncts)

						if start == end:
							continue

						route = self.sim_env.map_data.find_best_route(start, end)

						if not route.edges:
							continue


						break
					except traci.exceptions.TraCIException:
						continue
					except Exception as e:
						logging.debug(f"Failed addinv vehicle {veh_id}")
						continue
				route_edges = route.edges

				try:

					traci.route.add(route_id, route_edges)
					traci.vehicle.add(veh_id, route_id,departLane='random')


					self.route_dict[route_id] = route_edges
					self.veh_dict[veh_id] = route_id

				except traci.exceptions.TraCIException:
					assert True, f"FAILED TO ADD ROUTE {veh_id}, edges:{route_edges}"



				self.sim_env.add_player(veh_id, route, end)
				

			#after all vehicles added
			#if self.sim_env.algo == "ATNE":

			if self.sim_env.algo != "BASE":
				self.sim_env.set_combinations(add=True) #initially set vehicle destination
			#self.sim_env.set_combinations_new(add=True)
			#combination is called after all players are added

			logging.info(f"Players added total {amount} in inital no mainenv")

			self.global_player_list = copy.deepcopy(self.sim_env.player_list)

		else:
			logging.info("adding players in replay simulation")

			for veh_id, route_id in self.main_env.veh_dict.items():
				try:

					traci.route.add(route_id, self.main_env.route_dict[route_id])
					traci.vehicle.add(veh_id, route_id,departLane='random')

				except traci.exceptions.TraCIException:
					assert True, f"FAILED TO ADD ROUTE {veh_id}, {self.main_env.route_dict[route_id]}"

			self.sim_env.player_list = copy.deepcopy(self.main_env.global_player_list)




	def change_capacity(self): #change the capacity of global player list

		for veh_id, veh_value in self.global_player_list.items():
			self.global_player_list[veh_id].capacity = get_truncated_normal(self.GraphSetting.player_capacity_random[0], self.GraphSetting.player_capacity_random[1], 0, self.GraphSetting.player_capacity_random[0]*2).rvs(1)[0]
			logging.info(f"resetting capacity values {veh_id} {self.global_player_list[veh_id].capacity}")

	def change_distance_capacity(self):
		for veh_id, veh_value in self.global_player_list.items():

			try:

				if self.GraphSetting.distance_capacity[0] == self.GraphSetting.distance_capacity[1]:
					self.global_player_list[veh_id].distance_capacity = (self.GraphSetting.distance_capacity[0] * self.global_player_list[veh_id].base_travel_time)


				else:
					self.global_player_list[veh_id].distance_capacity = np.random.randint(self.global_player_list[veh_id].base_travel_time * self.GraphSetting.distance_capacity[0], self.global_player_list[veh_id].base_travel_time * self.GraphSetting.distance_capacity[1])
			except ValueError:
				self.global_player_list[veh_id].distance_capacity = 0





	def initial_reward_random(self, amount): #initialize all the rewards

		#traci.junction.subscribeContext(GraphSetting.destination, tc.CMD_GET_VEHICLE_VARIABLE, 20, [tc.VAR_EDGES, tc.VAR_ROAD_ID])

		if not self.main_env:

			all_junctions = list(self.sim_env.map_data.junctions.keys())

			for i in range(amount):

				id_value = f'poi_{str(i)}'
				junction=choice(all_junctions)

				self.sim_env.map_data.pois[id_value] = Poi(junction, \
					get_truncated_normal(self.GraphSetting.player_reward_random[0], self.GraphSetting.player_reward_random[1], 0, self.GraphSetting.player_reward_random[0]*2).rvs(1)[0]) #add poi to dict with poi id as key

				#self.sim_env.poi_que[id_value] = {}
				self.sim_env.poi_list[id_value]= {}
				self.sim_env.poi_to_junct[id_value] = junction
				self.sim_env.poi_to_junct[junction] = id_value

				traci.poi.add(id_value, *traci.junction.getPosition(junction), color=(255,0,255,255), layer=10, height=10)
				#print(tuple(*traci.junction.getPosition(junction)))

				#Visualize.polygon(traci.junction.getPosition(junction), (255,0,255,255), 30)


				traci.poi.subscribeContext(id_value, tc.CMD_GET_VEHICLE_VARIABLE, self.GraphSetting.poi_radius, [tc.VAR_EDGES, tc.VAR_ROAD_ID])
				print(f'added {id_value} to location {junction}')

			self.global_poi = copy.deepcopy(self.sim_env.map_data.pois)

		else:
			#for when prev poi is set up
			for key, obj in self.main_env.global_poi.items():

				junction = obj.junction
				id_value = key


				self.sim_env.map_data.pois[id_value] = Poi(junction, obj.value) #add poi to dict with poi id as key

				#self.sim_env.poi_que[id_value] = {}
				self.sim_env.poi_list[id_value]= {}
				self.sim_env.poi_to_junct[key] = junction
				self.sim_env.poi_to_junct[junction] = id_value

				traci.poi.add(id_value, *traci.junction.getPosition(junction), color=(255,0,255,255), layer=10, height=10)
				#print(tuple(*traci.junction.getPosition(junction)))

				#Visualize.polygon(traci.junction.getPosition(junction), (255,0,255,255), 30)


				traci.poi.subscribeContext(id_value, tc.CMD_GET_VEHICLE_VARIABLE, self.GraphSetting.poi_radius, [tc.VAR_EDGES, tc.VAR_ROAD_ID])
				print(f'added {id_value} to location {junction}')


		self.sim_env.post_process_graph.reward_list =  self.sim_env.map_data.pois


	def step(self, t=0):
		#action performed after each step aka simulation step

		self.vehicle_sub() #constant sub to veh to handle veh being added during simulation
		self.break_condition = self.populate_post() #for populating post processing data, and set break condition to get when all vehicle arrives
		self.sim_env.process_poi(self.t)
		self.sim_env.process_destination() #subscribe to destination of veh to make sure it arrives
		self.sim_env.stop_vehicle_handle(self.t)
		self.t+=1



		
	def populate_post(self): #for post processing and make sure vehicle all arrives
		self.sim_env.veh_data = traci.vehicle.getAllSubscriptionResults()
		if self.sim_env.veh_data:
			for veh_id, values in self.sim_env.veh_data.items():

				post_list = [self.sim_number, self.t, veh_id, values[tc.VAR_ROAD_ID], values[tc.VAR_SPEED], \
				self.sim_env.player_list[veh_id].capacity, self.sim_env.player_list[veh_id].reward, self.sim_env.player_list[veh_id].prev_poi, self.sim_env.algo\
				]

				self.sim_env.player_list[veh_id].node_hit.append(values[tc.VAR_ROAD_ID])

				self.post_process.append_row(post_list)

			return False

		#this is when the simulation is finished
		for key, value in self.sim_env.player_list.items():
			self.sim_env.post_process_graph.player_list.append(value)

		self.sim_env.post_process_graph.simulation_steps = self.t
		self.sim_env.post_process_graph.map_junctions = len(self.sim_env.map_data.junctions) + len(self.sim_env.map_data.edges)


		#add in the total simulation step into the list of steps
		for key, value in self.sim_env.post_process_graph.temp_coverage.items():
			value.append(self.t)
			if value[0] != 0:
				value.insert(0, 0)


		
		return True








	def vehicle_sub(self):
		for veh_id in traci.vehicle.getIDList():
			traci.vehicle.subscribe(veh_id, [tc.VAR_POSITION, tc.VAR_SPEED, tc.VAR_EDGES, tc.VAR_ROUTE_INDEX,tc.VAR_ROAD_ID])


	def junction_sub(self):
		len_junction = 0
		for junc, junc_obj in self.sim_env.map_data.junctions.items():
			if not ':' in junc:
				dist_from_junc = EnvironmentListener.mean([self.sim_env.map_data.edges[x].distance for x in junc_obj.adjacent_edges_from])
				if dist_from_junc:
					#traci subscribe need to convert miles to meters
					try:
						traci.junction.subscribeContext(junc, tc.CMD_GET_VEHICLE_VARIABLE, (dist_from_junc/4)*1609.34, [tc.VAR_EDGES, tc.VAR_ROAD_ID])
						len_junction+=1

					except Exception as e:
						pass

		#print('len junctions sub to ', len_junction) #show number of junc sub to



	@staticmethod
	def mean(list_value):
		if len(list_value) == 0:
			return
		return sum(list_value)/len(list_value)



class BaseEnv(EnvironmentListener):
	def __init__(self, sim_number, init=True, _seed=None, setting_obj=None, main_env=None, algo="BASE", post_process_graph=None, new_players=False):
		super(BaseEnv, self).__init__(sim_number, init=init, _seed =_seed, setting_obj=setting_obj, algo=algo, main_env=main_env, post_process_graph=post_process_graph, new_players=new_players)


	def step(self, t=0):
		#action performed after each step aka simulation step

		self.vehicle_sub() #constant sub to veh to handle veh being added during simulation
		self.break_condition = self.populate_post() #for populating post processing data, and set break condition to get when all vehicle arrives
		self.sim_env.process_poi(self.t)
		self.sim_env.process_destination() #subscribe to destination of veh to make sure it arrives
		self.sim_env.stop_vehicle_handle(self.t)
		self.t+=1

class GreedyEnv(EnvironmentListener):
	def __init__(self, sim_number, init=True, _seed=None, setting_obj=None, post_process=None, main_env=None, post_process_graph=None, new_players=False):
		super(GreedyEnv, self).__init__(sim_number, init=init, _seed =_seed, setting_obj=setting_obj, algo="GREEDY", main_env=main_env, post_process_graph=post_process_graph, new_players=new_players)

	def step(self, t=0):
		#action performed after each step aka simulation step

		self.vehicle_sub() #constant sub to veh to handle veh being added during simulation
		self.break_condition = self.populate_post() #for populating post processing data, and set break condition to get when all vehicle arrives
		self.sim_env.process_poi(self.t)
		self.sim_env.process_destination() #subscribe to destination of veh to make sure it arrives
		self.sim_env.stop_vehicle_handle(self.t)
		self.t+=1

class RandomEnv(EnvironmentListener):
	def __init__(self, sim_number, init=True, _seed=None, setting_obj=None, post_process=None, main_env=None, post_process_graph=None, new_players=False):
		super(RandomEnv, self).__init__(sim_number, init=init, _seed =_seed, setting_obj=setting_obj, algo="RANDOM", main_env=main_env, post_process_graph=post_process_graph, new_players=new_players)

	def step(self, t=0):
		#action performed after each step aka simulation step

		self.vehicle_sub() #constant sub to veh to handle veh being added during simulation
		self.break_condition = self.populate_post() #for populating post processing data, and set break condition to get when all vehicle arrives
		self.sim_env.process_poi(self.t)
		self.sim_env.process_destination() #subscribe to destination of veh to make sure it arrives
		self.sim_env.stop_vehicle_handle(self.t)
		self.t+=1





