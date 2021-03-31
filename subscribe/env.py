import numpy as np
from player import Player
import heapq
from _map import Map
import traci.constants as tc
from random import choice, randrange
#from settings import GraphSetting
from multiprocessing import cpu_count, Manager, Queue, Pool
import traci
from operator import itemgetter
import itertools
from util import *
from functools import reduce

import time as tm
from concurrent.futures import ThreadPoolExecutor as pool
import threading

from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

import logging
import copy

from math import exp
import sys
import os
#sys.path.append("./../poibin-master")
#print(os.getcwd())
sys.path.append("./poibin-master")

from poibin import PoiBin

from sklearn import preprocessing 
from postprocess import DataCaptureGraph

#todo:
'''

handling when junction name is cluster cant find path: done
fix inside setbucket to properly getting all the edges even with : done
fix map parsing to handle : done
fix vehicle not arriving at final destination: the problem is that the vehicle is also setting next poi to current poi


'''

#improvements
'''
sensing plan often calculated with only 1 player at the poi: possible solution harish algo
not helping with road utilization because each vehcle takes similar path, maybe can figure out a way to smartly distribute the rewards to max util
the esp and eu values are too low

consider deviation cost, this will allow the vehicle to see that larger picture, maybe planning multiple poi ahead of time
as of right now the vehicle is only considering one poi at a time without considering its original path

reward adjustments regarding to time, solve the 1 vehicle problem, allowing vehicles to have a more diverse route
also adds more chaos on top of only considering the number of possible player being there





for temperal coverage create a function interms of average time gap collected at poij

'''






class Environment(object):
	def __init__(self, setting_obj=None):


		self.post_process_graph = DataCaptureGraph() #stores informatino in python files

		self.GraphSetting = setting_obj

		self.map_data = Map(self.GraphSetting.sumo_config)
		self.player_list = {}
		self.poi_to_junct = {}  #enter poi id to get junction, enter junction to get poi id
		self.index_counter = 0

		

		self.poi_list = {}     #poi {poi_key:{veh_key:veh_value}} to keep track of if vehcle is being tracked by the poi to know if
		#veh is leaving or entering junction


		self.success_veh = [] #vehicle success arrived dest
		self.poi_que = {} # {poiid:{vehid:edge, vehid:edge}} #when player arived to raidus add to this, every 10 sec this is cleared

		self.veh_poi = {} #to keep track of vehicles that are paused on a poi veh:poi need to remove vehicle when leaving


		#below are the variables for guis
		self.veh_data = None #result of veh storing location
		self.track_veh = None #id storing the vehicle to track

		self.algo = None

		self.t = 0





	def stop_vehicle_handle(self, t): #handle when vehicle is stopped calculate the sensing plan with buffered vehicles

		self.t = t

		if (t % self.GraphSetting.buffer_interval) == 0: #the number of sec passed by
			#print("im checking for que ", self.t)
			if self.poi_que:

				if not self.algo == "BASE":
					self.generate_bucket() #generate bucket first then reroute #this is the initial loop over all veh and rewards
					#this is freezing in time all vehicles are not going to move


				for poi_key, veh_waiting_list in self.poi_que.items():
					sp, number_players = self.update_veh_collection_status(veh_waiting_list, poi_key) #this is only called when veh is being handled at poi
					try:

						reward_value = (self.map_data.pois[poi_key].value/pow(number_players, 2))
					except TypeError:
						reward_value = 0

					for veh, edge in veh_waiting_list.items():




						#adjusting sensing plan generate the buckets and combination this is called for every player wtf?
						next_poi_junct = self.adjust_sensing_plan(poi_key, veh, sp, edge, reward_value) #when veh route is adjusted does this really need to be adjusted for every veh or maybe it should be only per poi

						#self.player_list[veh].reward += (self.map_data.pois[poi_key].value/pow(len(veh_waiting_list), 2))

						

						try:
							traci.vehicle.setStop(veh, edge, duration=0)
							#print(f"i succeeded at resuming {veh}. routes: {traci.vehicle.getRoute(veh)}, index : {traci.vehicle.getRouteIndex(veh)}, current: {traci.vehicle.getRoute(veh)[traci.vehicle.getRouteIndex(veh)]} shouldbe {edge}")
						except traci.exceptions.TraCIException as e:
							logging.info(f"i failed at resuming {veh}. routes: {traci.vehicle.getRoute(veh)}, index : {traci.vehicle.getRouteIndex(veh)}, current: {traci.vehicle.getRoute(veh)[traci.vehicle.getRouteIndex(veh)]} shouldbe {edge}")
							#traci.vehicle.setStop(veh, edge, duration=0)

							logging.info(f"retrying to start using current edge {traci.vehicle.getRoute(veh)[traci.vehicle.getRouteIndex(veh)]}")

							try:
								#traci.vehicle.setStop(veh, traci.vehicle.getRoute(veh)[traci.vehicle.getRouteIndex(veh)], duration=0) 
								routes = self.map_data.find_route_reroute(traci.vehicle.getRoute(veh)[traci.vehicle.getRouteIndex(veh)], next_poi_junct).edges
								traci.vehicle.setRoute(veh, routes)

								#traci.vehicle.setStop(veh, traci.vehicle.getRoute(veh)[traci.vehicle.getRouteIndex(veh)], duration=0)
								

							except traci.exceptions.TraCIException as e:
								logging.info(f"reattempt failed too... {traci.vehicle.getRoute(veh)} {e}")
								self.track_veh = veh

						
								raise traci.exceptions.TraCIException("i failed here wtf")


							

							#traci.vehicle.setStop(veh, edge, duration=0)
							
						

						#traci.vehicle.setStop(veh, traci.vehicle.getRoute(veh)[traci.vehicle.getRouteIndex(veh)], duration=0)
						logging.info(f"Moving {veh} at step {t}, sp calcaulated for {len(veh_waiting_list)} player(s)")

					self.post_process_graph.poi_visited_instance[t][poi_key] = list(veh_waiting_list.keys()) #for storing simultanous poi visits from all players at a poi

				self.veh_poi = {} #rest vehles that are paused at a poi
				self.poi_que = {}

				self.post_process_graph.rc_visited_instance[t] = self.post_process_graph.calculate_test_coverage(custom_player_list=list(self.player_list.values()))
				self.post_process_graph.rw_visited_instance[t] = self.post_process_graph.get_avg_reward(custom_player_list=list(self.player_list.values()))



	def calculate_next_poi_greedy(self, veh_id, current_node, add=False):
		player = self.player_list[veh_id]
		max_eu = 0
		max_eu_location=None
		final_distance_cap = None

		player_data = self.player_list if add else traci.vehicle.getAllSubscriptionResults()
		len_player = len(player_data)

		assert len_player >0, 'something is wrong no player in system'



		top_index = int(self.GraphSetting.poi_consider * self.GraphSetting.reward_numbers)

		weight_dict_sorted = {k: v for k, v in sorted(self.player_list[veh_id].poi_distance_temp.items(), key=lambda item: item[1]) if not k in player.past_recent_nodes} #sort the dict based on distance to mysel


		weight_dict = {key:weight_dict_sorted[key] for key in list(weight_dict_sorted.keys())[:top_index]}

		print("weight dict value for greedy is ", weight_dict)



		#for poi_id, self.map_data.pois[poi_id] in self.map_data.pois.items(): #iteration over every poi
		for poi_id, weight_value in weight_dict.items():

			try:
				total_cost = self.map_data.pois[poi_id].player_potential[veh_id] + self.player_list[veh_id].poi_potential[poi_id]
				print(f"{veh_id} considering going to {poi_id}")

			except KeyError as e:
				continue

			if total_cost > self.player_list[veh_id].distance_capacity:
				continue

			if self.GraphSetting.none_repeat_poi:	
				if poi_id in self.player_list[veh_id].pois_visited:
					continue

			#assert total_cost <= self.player_list[veh_id].distance_capacity, f"failed {veh_id} dist cap {self.player_list[veh_id].distance_capacity} < {total_cost} going to {poi_id}"
			assert poi_id in self.player_list[veh_id].current_poi_distribution, f"failed {poi_id} not in {veh_id} distribution"

			e_u = self.map_data.pois[poi_id].value

			if (e_u > max_eu) and (player.capacity != 0) and (poi_id != player.target_poi) and (not poi_id in player.past_recent_nodes):
				max_eu = e_u
				max_eu_location = poi_id
				final_distance_cap = total_cost



		if final_distance_cap:
			self.player_list[veh_id].distance_capacity -= final_distance_cap

		return max_eu_location





	def calculate_next_poi_random(self, veh_id, current_node, add=False):

		#find the n number of closest pois 

		player = self.player_list[veh_id]

		max_eu_location = None #returns none or target poi id


		player_data = self.player_list if add else traci.vehicle.getAllSubscriptionResults()
		len_player = len(player_data)
		assert len_player >0, 'something is wrong no player in system'


		#weight_dict = copy.deepcopy(player.poi_to_destination) #weight dict is simply the distance from poi to destination of player
		top_index = int(self.GraphSetting.poi_consider * self.GraphSetting.reward_numbers)

		#focus on the top percentage of pois thats closest to me

		weight_dict_sorted = {k: v for k, v in sorted(self.player_list[veh_id].poi_distance_temp.items(), key=lambda item: item[1]) if not k in player.past_recent_nodes} #sort the dict based on distance to mysel


		weight_dict = {key:weight_dict_sorted[key] for key in list(weight_dict_sorted.keys())[:top_index]}


		#add destination as a poi target. the weight for the destination is the distance between the current position to target destination
		#which means the closer the vehicle is to it destination, the more likely its able to choose the destination as the next poi

		cost_to_dest = self.map_data.find_best_route(current_node, player.dest_junc).travelTime

		weight_dict[player.dest_junc] = cost_to_dest #destnation poi added in using 

		logging.debug(f"Random top {top_index} pois {weight_dict_sorted} after choice {weight_dict}")

		if self.GraphSetting.none_repeat_poi:

			weight_dict = {key:value for key, value in weight_dict.items() if (value!=0) and (not key in self.player_list[veh_id].pois_visited)}

		else:

			weight_dict = {key:value for key, value in weight_dict.items() if (value!=0)}



		#if weight dict is none means the vehicle cant go to any poi due to its distance capacity

		if weight_dict:

			#total_sum = reduce(lambda x,y:x+y,[exp(1/x) for x in weight_dict.values()])
			#prob_distribute = [exp(1/x)/total_sum for x in weight_dict.values()]

			total_sum = reduce(lambda x,y:x+y,[exp(self.GraphSetting.theta_random/x) for x in weight_dict.values()])
			prob_distribute = [exp(self.GraphSetting.theta_random/x)/total_sum for x in weight_dict.values()]

			logging.debug(f"Probability Distribution is {prob_distribute}")

			selected_index = np.random.choice(len(weight_dict), 1, p=prob_distribute)

			poi_id_choice = list(weight_dict.keys())[selected_index[0]]

			try:

				final_distance_cap = weight_dict[poi_id_choice] + self.player_list[veh_id].poi_potential[poi_id_choice]
			except KeyError:

				final_distance_cap = weight_dict[poi_id_choice]


			#logging.info(f"{poi_id_choice} {self.player_list[veh_id].target_poi}")

			if poi_id_choice == self.player_list[veh_id].target_poi:
				logging.info(f"next poi same as current poi going towards destination {self.player_list[veh_id].dest_junc}")
				#max_eu_location = self.player_list[veh_id].destination
			else:
				max_eu_location = poi_id_choice

			logging.info(f"{veh_id} Random choice next poi is {poi_id_choice}")
			
			self.player_list[veh_id].distance_capacity -= final_distance_cap

		else:
			logging.info(f"{veh_id} no poi can go due to distance capacity {player.distance_capacity}")







		return max_eu_location


	def calculate_next_poi_new(self, veh_id, current_node, add=False):#add to show that its initializing
		#this is called when player is added and is called every time a play arrived at a poi
		#loops through every player and every poi to find the player prob for every poi


		#print("current node is ", current_node)



		player = self.player_list[veh_id]


		max_eu = 0
		max_eu_location=None
		final_distance_cap = None

		player_data = self.player_list if add else traci.vehicle.getAllSubscriptionResults()
		len_player = len(player_data)


		esp_dict = {} #this contains the esp values to all the pois that are within the distance capcity


		top_index = int(self.GraphSetting.poi_consider * self.GraphSetting.reward_numbers)

		weight_dict_sorted = {k: v for k, v in sorted(self.player_list[veh_id].poi_distance_temp.items(), key=lambda item: item[1]) if not k in player.past_recent_nodes} #sort the dict based on distance to mysel


		#weight_dict = {key:weight_dict_sorted[key] for key in list(weight_dict_sorted.keys())[:top_index]}



		

		#for poi_id, self.map_data.pois[poi_id] in self.map_data.pois.items():
		#for poi_id, weight_value in weight_dict.items():
		for i, (poi_id, weight_value) in enumerate(weight_dict_sorted.items()): #find the percentage of rad

			assert len_player >0, 'something is wrong no player in system'


			if not poi_id in self.player_list[veh_id].poi_potential:
				#player cant go to this poi due to distance capacity
				continue
		


			print(f"{veh_id} considering going to {poi_id}")

			try:
				total_cost = self.map_data.pois[poi_id].player_potential[veh_id] + self.player_list[veh_id].poi_potential[poi_id]
			except KeyError as e:
				continue 


			if self.GraphSetting.none_repeat_poi:	
				if poi_id in self.player_list[veh_id].pois_visited:
					continue


			if total_cost > self.player_list[veh_id].distance_capacity:
				continue
			#assert total_cost <= self.player_list[veh_id].distance_capacity, f"failed {veh_id} dist cap {self.player_list[veh_id].distance_capacity} < {total_cost} going to {poi_id}"
			assert poi_id in self.player_list[veh_id].current_poi_distribution, f"failed {poi_id} not in {veh_id} distribution"





			if len_player <=1:  #im the only one there
				e_u = self.map_data.pois[poi_id].value
				e_sp = self.GraphSetting.sensing_plan_one #1#(self.map_data.pois[poi_id].value /5) /2 #updated sensing plan
			else:
				#self.calculate_utility_new(veh_id, poi_id, self.map_data.pois[poi_id].value, player_data)
				e_u, e_sp = self.calculate_utility_new(veh_id, poi_id, self.map_data.pois[poi_id].value, player_data)




			esp_dict[poi_id] = e_sp*total_cost #this dict conatins the sensing plan with cost*esp 


			if (e_u > max_eu) and (e_sp <= player.capacity) and (poi_id != player.target_poi) and (not poi_id in player.past_recent_nodes): #max eu, fit esp, not current poi, and not prev poi
				max_eu = e_u
				max_eu_location = poi_id
				final_distance_cap = total_cost

				if i > top_index:
					#this means the 30% is already finsished, find the first max eu location and break
					break




			#reset poi potential players or it might affect next time bucket generation
			#self.map_data.pois[poi_id].player_potential = {}
				


		if final_distance_cap:
			self.player_list[veh_id].distance_capacity -= final_distance_cap

		#self.player_list[veh_id].poi_potential = {}

		'''

		if (not max_eu_location) and esp_dict:  #this is only considering esp dictionary
			#no poi is chosen weighted random here based on esp and eu and



			weight_dict = esp_dict



			total_sum = sum([1/x for x in weight_dict.values()])
			prob_distribute = [(1/x)/total_sum for x in weight_dict.values()] #the smallest esp value will have the highest prob

			logging.debug(f"Weighted random in ATNE {weight_dict}, prob: {prob_distribute}")

			selected_index = np.random.choice(len(weight_dict), 1, p=prob_distribute)

			max_eu_location = list(weight_dict.keys())[selected_index[0]]
		'''

		return max_eu_location #this returns the poi id


	@timer
	def calculate_utility_new(self, veh_id, poi_id, reward, player_data):
		'''
		calculate the expected util for particular i veh_id to poi_id
		sum up all the times
		'''
		#the new function finds all the prob of all 4 players being there all i have to do is iterate through each time bucket for each player
		time_eu_dict = {} #time as key m_eu_dict as value
		time_esp_dict = {}

		dbg_prob_dict = {}
		dbg_esp_dict = {}

		for index, time in enumerate(self.player_list[veh_id].current_poi_distribution[poi_id][1]): #iterate over the time bucket of the current player
			#find the time arrival in other bucketsw

			m_eu_dict = {} #number of players as key, eu as value
			m_esp_dict = {}

			temp_prob_list = [self.find_probability(time, self.player_list[veh_id].current_poi_distribution[poi_id]) for veh_id, veh_value in player_data.items() if poi_id in self.player_list[veh_id].current_poi_distribution]
			
			#above line gets an error not finding poi id as key


			pbd = PoiBin(temp_prob_list)

			prob_dict = {} #for dbg
			sp_dict = {} # for dbg

			for m in range(1, len(player_data)+1): #probability of zero players behing there is infinity
				try:
					prob = pbd.pmf(m)
				except AssertionError as e:
					prob = 0

				#logging.debug(f"NEW PROB {veh_id} to {poi_id} for {m} players {prob}")

				eu = prob*(reward/pow(m, 2))
				esp = prob*self.compute_sensing_plan(m, (reward/pow(m, 2)), self.map_data.junctions[self.map_data.pois[poi_id].junction].cost)

				prob_dict[m] = prob
				sp_dict[m] = self.compute_sensing_plan(m, (reward/pow(m, 2)), self.map_data.junctions[self.map_data.pois[poi_id].junction].cost)

				m_eu_dict[m] = eu
				m_esp_dict[m] = esp

			#logging.debug(f"{veh_id} to {poi_id} time bucket: {time} original_prob:{temp_prob_list} meu:{m_eu_dict} mesp:{m_esp_dict}")
			dbg_prob_dict[time] = prob_dict
			dbg_esp_dict[time] = sp_dict

			time_eu_dict[time] = m_eu_dict
			time_esp_dict[time] = m_esp_dict

			#logging.debug(f"{veh_id} for time {time} prob list is {temp_prob_list}")


		logging.debug(f"prob and sp {veh_id} to {poi_id} sp:{dbg_esp_dict} prob:{dbg_prob_dict}")

		total_eu = sum([sum(_m.values()) for _time, _m in time_eu_dict.items()])

		total_esp = sum([sum(_m.values()) for _time, _m in time_esp_dict.items()])

		logging.info(f"{veh_id} to {poi_id} eu is {total_eu} esp is {total_esp} current cap:{self.player_list[veh_id].capacity}")

		return total_eu, total_esp




			
				



	def calculate_utility(self, veh_id, poi_id, reward, player_data):
		'''
		calculate the expected util for particular i veh_id to poi_id
		sum up all the times
		'''


		#iteration through poi_combintaions and populate

		self.player_list[veh_id].combinations = defaultdict(list)  #reset player combinations

		self.set_combs(poi_id) #setting the combinations for all the players that are potentially going to this poi
		player_data = self.map_data.pois[poi_id].player_potential

		player_data_keys = list(player_data.keys())


		time_eu_dict = {} #time as key m_eu_dict as value
		time_esp_dict = {}

		for index, time in enumerate(self.player_list[veh_id].current_poi_distribution[poi_id][1]):

			#filter out the ones that are not going there that means i have to regenerate combinations...... thats even more costly
			#combinations are assumed that all players have some probalit
			#even if i remove the player from the consideration list

			#self.filter_participants()

			#using binomial distribution for prob estimation? 

			for m, combs in self.player_list[veh_id].combinations.items(): #m is r {1:[10c1], 2:[10c2]} r 1:n #this is set using set_combos
				prob = 1
				m_eu_dict = {} #number of players as key, eu as value
				m_esp_dict = {}
				for key, value in player_data.items(): #iteration of all players potentially going to poi #potential player list
					if key in combs:
						arriving_prob = self.find_probability(time, self.player_list[key].current_poi_distribution[poi_id])
						if key == veh_id:
							assert self.player_list[veh_id].current_poi_distribution[poi_id][0][index] == arriving_prob,\
								f"time dist doesnt match {veh_id} {self.player_list[veh_id].current_poi_distribution[poi_id][0][index]} {arriving_prob}"
					else:
						arriving_prob = (1 - self.find_probability(time, self.player_list[key].current_poi_distribution[poi_id]))


					prob *= arriving_prob

				logging.debug(f"OLD PROB {veh_id} to {poi_id} for {m} players {prob}")
				
				eu = prob*(reward/pow(m, 2))
				esp = prob*self.compute_sensing_plan(m, (reward/pow(m, 2)), self.map_data.junctions[self.map_data.pois[poi_id].junction].cost)
				m_eu_dict[m] = eu
				m_esp_dict[m] = esp

			time_eu_dict[time] = m_eu_dict
			time_esp_dict[time] = m_esp_dict


		
		total_eu = sum([sum(_m.values()) for _time, _m in time_eu_dict.items()])

		total_esp = sum([sum(_m.values()) for _time, _m in time_esp_dict.items()])

		

		logging.info(f"OLD: {veh_id} to {poi_id} eu is {total_eu} esp is {total_esp} current cap:{self.player_list[veh_id].capacity}")

		return total_eu, total_esp




	#this function need to be parallized or written in c
	def generate_bucket(self, veh_id=None):

		#when veh arrive at destination the bucket should be changed for each veh the same combination no longer apply


		#this also sets the potential players to every potential pois based on distance cap

		#this is caled everytime player arrive at a poi
		@timer
		def set_bucket(veh_id, current_edge, add=False):

			print(f"Generating buckets for {veh_id}....")

			#for each veh need to reset their dic before generating buckets

			

			for poi_id, poi_value in self.map_data.pois.items():

				#poi_value.player_potential = {} #testing to reset poi potential in her




				key = self.map_data.pois[poi_id].junction
				value = self.map_data.pois[poi_id].value

				
				#route_value = self.map_data.find_route_reroute(current_edge, key) #find it from the vehicle to the poi

				if veh_id in self.veh_poi:
					#vehicle is paused at a poi just use the poi cost to another poi if its there

					if poi_id == self.veh_poi[veh_id]:
						continue

					
					try:
						#print("im here")
						route_value = self.map_data.pois[poi_id].other_poi_cost[self.veh_poi[veh_id]]
					except KeyError:
						try:
							#print("im here again")
							#check the other poi
							route_value = self.map_data.pois[self.veh_poi[veh_id]].other_poi_cost[poi_id]
						except KeyError:
							#print("im here again again")
							#both dont have the stored now calculate

							route_value = self.map_data.find_best_route(key, self.map_data.pois[self.veh_poi[veh_id]].junction)

							#print(f"{self.veh_poi[veh_id]} {poi_id}")

							self.map_data.pois[poi_id].other_poi_cost[self.veh_poi[veh_id]] = route_value
							self.map_data.pois[self.veh_poi[veh_id]].other_poi_cost[poi_id] = route_value

					

				else:
					try:
						route_value = self.map_data.find_route_reroute(current_edge, key)
					except Exception as e:
						print(f"i failed at 627 {e} {veh_id} {current_edge} {key}")
						exit()

				

				if add:
					route_value_todest = self.map_data.find_best_route(key, self.player_list[veh_id].dest_junc) #this can be static but incase if destination is changing
					self.player_list[veh_id].poi_to_destination[poi_id] = route_value_todest
				else:
					route_value_todest = self.player_list[veh_id].poi_to_destination[poi_id]

				#assert route_value and route_value_todest, f"wtf one of the value is returning NONE {route_value} {route_value_todest} {veh_id} {poi_id} {veh_id in self.veh_poi}"
				total_time = 0

				if route_value:
					total_time += route_value.travelTime
				if route_value_todest:
					total_time += route_value_todest.travelTime

				#total_time = route_value.travelTime + route_value_todest.travelTime

				try:
					self.player_list[veh_id].poi_distance_temp[poi_id] = route_value.travelTime #poi need to be static
				except AttributeError:
					#print(f"WTTFFFF I failed at adding in travel time from {key} to {self.map_data.pois[self.veh_poi[veh_id]].junction} {route_value}")
					self.player_list[veh_id].poi_distance_temp[poi_id] = 0



				if self.player_list[veh_id].distance_capacity < total_time:
					#when distance capacity is less than the total time the poi is not considered for 
					logging.debug(f"SKIPPED buckets for {veh_id} to {poi_id} total cost {total_time} cap left {self.player_list[veh_id].distance_capacity}")
					continue
					#the player combination to poi is not updated

				logging.debug(f"SETTING buckets {veh_id} to {poi_id} total cost {total_time} cap left {self.player_list[veh_id].distance_capacity}")

				try:
					self.player_list[veh_id].poi_potential[poi_id] = route_value.travelTime  #from veh to poi
				except AttributeError:
					#print(f"WTTFFFF I failed at adding in travel time from {key} to {self.map_data.pois[self.veh_poi[veh_id]].junction} {route_value}")
					self.player_list[veh_id].poi_distance_temp[poi_id] = 0
				try:

					self.map_data.pois[poi_id].player_potential[veh_id] = route_value_todest.travelTime  #from poi to veh destination #if vehicle desitnation is dynamic it works too
				except AttributeError:
					self.map_data.pois[poi_id].player_potential[veh_id] = 0

				
				if route_value:

					route_edges = route_value.edges
					self.player_list[veh_id].temp_edges[key]=route_edges


					#start_time = tm.perf_counter()

					new_mean = sum([self.map_data.edges[e].distance/self.map_data.edges[e].speed for e in route_edges if not ':' in e]) #sum of the means of edges within the route to each poi
					new_std = reduce(lambda x,y:np.sqrt(x**2+y**2), [self.map_data.edges[e].std for e in route_edges if not ':' in e]) # combine the std of all the edges

					#logging.debug(f"combinging mean and std for roads using TIME {tm.perf_counter() - start_time}")

					#: is for junctions, when vehicle in motion, tc.roadid can return junction

					route_array = generate_speed_distribution(new_mean, new_std) #distribution data generated based on new mean and std

					result = generate_speed_bucket(route_array, bins_num=6) #generate histogram with bin number


					self.player_list[veh_id].current_poi_distribution[poi_id] = result #save this histogram information to the player object
						



					#current poi_distribution {poi_id:histogram}
	



		if veh_id: #finding dict for only 1 vehicle
			set_bucket(veh_id, self.player_list[veh_id].current_edge, add=True)
			
		else: #for when 1 vehicle arrived at a poi need to evaluate the next poi thus need to update every other players bucket


			
			for poi_id, poi_value in self.map_data.pois.items():
				poi_value.player_potential = {}

			for veh_id, veh_value in traci.vehicle.getAllSubscriptionResults().items():
				self.player_list[veh_id].poi_potential = {}

			

			for veh_id, veh_value in traci.vehicle.getAllSubscriptionResults().items():
				#self.player_list[veh_id].poi_potential = {}
				veh_edge_current = veh_value[tc.VAR_ROAD_ID]

				if not veh_edge_current:
					veh_edge_current = veh_value[tc.VAR_EDGES][veh_value[tc.VAR_ROUTE_INDEX]]


				if not veh_edge_current:
					print(f"cant find the cureent edge {veh_id} values is {veh_value} index is {tc.VAR_ROAD_ID} list of arrival {self.success_veh}")
					exit()

				set_bucket(veh_id, veh_edge_current)

			#because we are in the player loop after updating the potential pois for this particular player, go ahead and generate the combination for this player

	
		
	def set_combs(self, poi_id, add=False): #setting the combinations of those players who are potentially able to participate in this poi
		total_players = len(self.map_data.pois[poi_id].player_potential)
		print(f"{poi_id} is generating combinations for {total_players}")
		for i in range(total_players):
			combs = itertools.combinations(list(self.map_data.pois[poi_id].player_potential.keys()), i+1) #try optimizing using numpy or iterators instread

			self.map_data.pois[poi_id].combinations[i+1] = combs #
			self.set_combinations_player(i+1, combs) #setting combs for theplayers based off the comb


	






	def compute_sensing_plan(self, player_amount, reward, cost):
		#print('player amount is ', player_amount)
		if player_amount == 1:
			return self.GraphSetting.sensing_plan_one
			#return (reward/cost)/2

		sensing_plan = ((player_amount-1)*reward)/((player_amount**2)*cost)

		#print('sensning plan value is ', sensing_plan)
		return sensing_plan


	def print_pc(self):
		for key, value in self.player_list.items():
			print(value.combinations)

			#value.combinations = defaultdict(list)


	def set_combinations_player(self, i, combs):
		
		


		while True:
			try:
				comb = next(combs)#combs.pop()
				#print(f"combinations for {i} players {comb}")
				for player in comb:
					self.player_list[player].combinations[i].append(comb)
			except StopIteration as e:
				break



	def set_combinations(self, add = False):
		#this gets combinations for all the players after all the players has been initialized
		#intialize combination
		#this need to be fixed for memory error cant store all combinations for every number of vehicles
		#where should the poi potential players be populated, shoudl be inside calculate next poi new, but if its populated there then combinations should be generated per poi based


		'''
		
		print(f"All players added len: {len(self.player_list)} generating combinations...")
		player_keys = list(self.player_list.keys())
		all_combs = {}


		for i in range(len(self.player_list)):
			#print("generating combinations")
			combs = list(itertools.combinations(player_keys, i+1))
			#all_combs[i+1] = combs
			#print("setting combinations")
			self.set_combinations_player(i+1, combs)

		'''

		if add:

			for player_id, player_value in self.player_list.items():

				self.next_poi_reroute(player_id, player_value.start, player_value.prev_junction, add=add)




	#this function has a bug
	def find_probability(self, time, distribution):
		'''
		given time and distribution of a veh at poi, find the prob of that time for the veh
		[0] is the probability, [1] is the intervals/bins
		'''
		buckets = distribution[1]
		upper_index = None
		lower_index = None

		try:
			upper_index = np.min(np.where(buckets>=time)) #index of upper boundary of time
			lower_index = np.max(np.where(buckets<=time)) #index of lower boundary of time

			logging.debug(f"BEFORE UPPER {upper_index} lower {lower_index} time {time} DISTRIBUTION {distribution}")	

			if upper_index == lower_index and upper_index==len(distribution[0]):
				lower_index -= 1



			#print(f'time searching for is {time}, upper:{upper_index}, lower:{lower_index}')
			#print(f'bucket is:', buckets)	
			#print(f'prob is:', distribution[0])	
		except ValueError:
			lower_index = None

		logging.debug(f"AFTER UPPER {upper_index} lower {lower_index} time {time} DISTRIBUTION {distribution}")

		if (not lower_index) and (lower_index!=0):
			return 0
		else:
			return distribution[0][lower_index]


	def add_player(self, veh_id, routes, dest_junc, player=None):  #this is called before setting combinations
		assert not veh_id in self.player_list, f"failed more than one player with {veh_id}"
		assert self.index_counter == int(veh_id.split('_')[1]), 'player id doesnt match counter'

		route_edges = routes.edges

		self.player_list[veh_id] = Player(veh_id, route_edges, self.map_data.edges[route_edges[0]]._from, dest_junc)

		self.player_list[veh_id].capacity = get_truncated_normal(self.GraphSetting.player_capacity_random[0], self.GraphSetting.player_capacity_random[1], 0, self.GraphSetting.player_capacity_random[0]*2).rvs(1)[0]

		self.player_list[veh_id].base_travel_time = routes.travelTime

		logging.info(f"Generating capacity for {veh_id} mean:{self.GraphSetting.player_capacity_random[0]} sd:{self.GraphSetting.player_capacity_random[1]} actual capacity {self.player_list[veh_id].capacity}")

		try:
			print(f"{veh_id} shortest path travel time {routes.travelTime}")




			if self.GraphSetting.distance_capacity[0] == self.GraphSetting.distance_capacity[1]:
				self.player_list[veh_id].distance_capacity = (self.GraphSetting.distance_capacity[0] * routes.travelTime)


			else:
				self.player_list[veh_id].distance_capacity = np.random.randint(routes.travelTime * self.GraphSetting.distance_capacity[0], routes.travelTime * self.GraphSetting.distance_capacity[1])
		except ValueError:
			self.player_list[veh_id].distance_capacity = 0

		#if not self.algo == "BASE":
		self.generate_bucket(veh_id=veh_id)


		self.index_counter+=1

		print(f"Added player {veh_id}, dist_cap: {self.player_list[veh_id].distance_capacity} going towards {dest_junc}")

		logging.info(f"Added player {veh_id}, dist_cap: {self.player_list[veh_id].distance_capacity} going towards {dest_junc}")



	def reroute(self, veh_id, current_edge, upcome_edge, destination, add=False):
		try:
			print(f'{veh_id} traveling on {upcome_edge} change direction going towards {destination}({self.poi_to_junct[destination]})')
		except KeyError:
			print(f'{veh_id} traveling on {upcome_edge} change direction going towards {destination}(Destination)')
		print()

		shortest_route = self.map_data.find_route_reroute(upcome_edge, destination)
		

		shortest_route = list(shortest_route.edges)

		traci.vehicle.changeTarget(veh_id, shortest_route[-1])



		return shortest_route



		

	def update_capacity(self, veh, esp):

		try:
			#assert self.player_list[veh].capacity >= esp, f"CAPACITY change ERROR cap:{self.player_list[veh].capacity} esp:{esp}"
			if esp > self.player_list[veh].capacity and esp == 1: #in the case of 1 player esp is set to 1 but still higher than 
				self.player_list[veh].capacity = 0
			else:
				self.player_list[veh].capacity -= esp

				#for postprocessing



			if self.player_list[veh].capacity <= 0:
				self.player_list[veh].capacity = 0
				self.player_list[veh].goinghome=True

		except KeyError:
			print(veh_value, 'Error')






	def update_veh_collection_status(self, veh_value, poi_key):
		#iterate through all the vehicles
		'''
		this function have issue when the diff of esp(i) and esp(i-1)
		eg. if esp(2) is 5.3 esp(1) is 1, player capacitys are 3 and 20
		when calc esp of 2, 1 fit. but when calc esp of 1, 2 fits

		the len(veh_value) is mostly 1, only when multiple vehicles arrives in the same radius will the length >1

		'''
		keys_list = list(veh_value.keys())
		cap_list = []
		veh_cap_list = []
		counter_list = []
		i_list = []

		if len(veh_value) == 1:
			return self.GraphSetting.sensing_plan_one, 1 #1#(self.map_data.pois[poi_key].value / 5), 1

		temp_veh_value = veh_value.copy()

		for i in range(len(veh_value), 0, -1):
			esp = self.compute_sensing_plan(i, self.map_data.pois[poi_key].value, self.map_data.junctions[self.poi_to_junct[poi_key]].cost)
			cap_list.append(esp)
			veh_cap_list.append(self.player_list[keys_list[i-1]].capacity)
			counter = 0 #this to count how many fits the capacity
			min_cap_veh_id = None #only remove one veh with smallest capacity if not fit
			for new_key, new_value in veh_value.items():

				if esp<=self.player_list[new_key].capacity:
					counter+=1
					self.player_list[new_key].participation = True
				else:
					self.player_list[new_key].participation = False
					if not min_cap_veh_id:
						min_cap_veh_id = new_key
					else:
						if self.player_list[new_key].capacity < self.player_list[min_cap_veh_id].capacity:
							min_cap_veh_id = new_key


			if min_cap_veh_id:
				del temp_veh_value[min_cap_veh_id]
				veh_value = temp_veh_value

			if counter == i: #this line
				if i==1:
					esp = self.GraphSetting.sensing_plan_one #1#(self.map_data.pois[poi_key].value / 5) /2 #updated sensing plan
				return esp, i




			counter_list.append(counter)
			i_list.append(i)

		print("I should not be here ") #it gets here because no one can collect
		print(f'length is {len(veh_value)}, esp list:{cap_list}, cap list:{veh_cap_list} counter {counter_list}, ilist {i_list}')

		return None, None
		#exit()

	def process_destination(self):

		arrived_id = traci.simulation.getArrivedIDList()
		if arrived_id:
			for veh_id in arrived_id:
				if not veh_id in self.success_veh:
					self.success_veh.append(veh_id)
					print(f"vehicle {veh_id} arrived at destination")


	def wait_in_radius(self, poi_key,veh_id):
		#print("before stop routes ", traci.vehicle.getRoute(veh_id))

		#this function is for stopping vehicles
		routes = traci.vehicle.getRoute(veh_id)
		route_index = traci.vehicle.getRouteIndex(veh_id)
		start_edge = routes[route_index]
		start_index = route_index
		while True:
			try:
				traci.vehicle.setStop(veh_id, routes[route_index])
			

				break
			except traci.exceptions.TraCIException:

				route_index += 1
			except IndexError:
				#because the stopping edge is determined before rerouting to he next poi, the route index might be out of range because its reached the poi and dk where to go
				#print(f"oh well im out of index trying to stop {veh_id} at {poi_key} starting {start_edge} index {start_index}")
				#print(f"Routes: {routes}")
				#exit()

				routes = self.map_data.find_route_reroute(start_edge, self.GraphSetting.destination).edges
				route_index = 0
				traci.vehicle.setRoute(veh_id,routes)

		print(f"stopping.... {veh_id} at {poi_key}")


		
		edge = routes[route_index]
			
		try:

			if not self.poi_que[poi_key]:
				self.poi_que[poi_key]= {veh_id:edge}
			else:
				self.poi_que[poi_key][veh_id] = edge
		except KeyError as e:
			self.poi_que[poi_key]= {veh_id:edge}

		self.veh_poi[veh_id] = poi_key


		self.track_veh = veh_id



		#print(self.poi_que[poi_key])
		#print("after stop routes ", traci.vehicle.getRoute(veh_id))

	@timer
	def adjust_sensing_plan(self, key, veh, sp, current_edge, reward_value):
		#key is the current poi key
		#self.player_list[veh].target_poi = self.map_data.pois[key].junction #incase veh accidentally encounter poi, need to update
		#if vehicle predetermined to go to destination but encounter a poi then update

		#if not self.algo == "BASE":
		#	self.generate_bucket() #generate bucket first then reroute #this is the initial loop over all veh and rewards

		self.player_list[veh].visited_sp_list.append(key)

		if self.player_list[veh].participation:

			before_capacity = self.player_list[veh].capacity
			self.player_list[veh].reward += reward_value
			self.update_capacity(veh, sp)
			logging.info(f"{veh} CAP_before:{before_capacity} CAP_after:{self.player_list[veh].capacity}: SP:{sp} at junction {key}({self.poi_to_junct[key]})")
			#self.player_list[veh].participation = False
			#postprocessing
			self.player_list[veh].collected_sp_list.append(key)

		else:

			logging.info(f"{veh} not participating at {key} sp:{sp} cap:{self.player_list[veh].capacity}")

			if self.algo == "RANDOM" or True:
				#random failed to collect sending to home
				logging.info(f"{veh} not collecting at {key} in {self.algo} going home directly")
				self.player_list[veh].goinghome = True
				self.player_list[veh].distance_capacity = 0



		if self.algo == "BASE":
			return None


		next_poi_junct = self.next_poi_reroute(veh, current_edge, self.map_data.pois[key].junction)

		return next_poi_junct



	def add_stm(self, veh_id, next_node):
		#the passt recent nodes contains the poi id


		if len(self.player_list[veh_id].past_recent_nodes) < self.GraphSetting.max_memory_size:
			self.player_list[veh_id].past_recent_nodes.append(next_node) #sumo junction is added to memory
		else:
			if self.GraphSetting.max_memory_size != 0:
				self.player_list[veh_id].past_recent_nodes.pop(0)
				self.player_list[veh_id].past_recent_nodes.append(next_node)

		

	def next_poi_reroute(self, veh, current_edge, prev_junction, add=False): #this is called everytime we want to determine poi and reroute

		if self.algo == "ATNE":
			next_poi = self.calculate_next_poi_new(veh, prev_junction, add=add) #maybe this function can return none for going towards dest
		elif self.algo == "GREEDY":
			next_poi = self.calculate_next_poi_greedy(veh, prev_junction, add=add)
		elif self.algo == "RANDOM":
			next_poi = self.calculate_next_poi_random(veh, prev_junction, add=add)

		if self.GraphSetting.poi_limit != 0:
			try:
				self.player_list[veh].pois_visited[next_poi] += 1

				if not self.GraphSetting.none_repeat_poi: #when the vehicles are allowed to visit pois multiple times
					if self.player_list[veh].pois_visited[next_poi] > self.GraphSetting.poi_limit:
						self.player_list[veh].goinghome = True
						logging.info(f"{veh} visited {next_poi} {self.player_list[veh].pois_visited[next_poi]} times, going towards dest")

			except KeyError:
				self.player_list[veh].pois_visited[next_poi] = 0

		if self.player_list[veh].distance_capacity <= 0:
			self.player_list[veh].goinghome = True
			print(f"player {veh} distance capacity limit reached going towards destination...")
			logging.info(f"player {veh} distance capacity limit reached going towards destination...")




		
		if (not next_poi) or self.player_list[veh].goinghome:
			#this is the weighted random jumps
			#right now set to go home if none fit
			logging.info(f'{veh} no next poi, going towards destination')
			next_junct = self.player_list[veh].dest_junc
			self.player_list[veh].distance_capacity = 0
		else:

			try:
				next_junct = self.map_data.pois[next_poi].junction

			except KeyError:
				logging.info(f"randomly selected to go towards destination {veh}")
				self.player_list[veh].distance_capacity = 0
				next_junct = next_poi

			#logging.info(f"{veh} setting prev poi {next_poi}")

			self.player_list[veh].target_poi = next_poi

			self.add_stm(veh, next_poi) #add stm after the next poi is decided


			#logging.info(f"next poi deteremined setting visited")
			logging.info(f"{veh} going towards {next_poi} DC:{self.player_list[veh].distance_capacity} CAP:{self.player_list[veh].capacity}")



		st = self.reroute(veh, None, current_edge, next_junct)

		return next_junct




	def process_poi(self, t):
		#should check is the vehicle is currently on the poi adjacent edges

		poi_data = traci.poi.getAllContextSubscriptionResults() #poi data is {poikey:{vehid:sub_info_veh}}
		if poi_data:
			for key, value in poi_data.items(): #loop through all poi list

				#generate bucket should be only for one player that arrived at junction
				
				#print(f'esp is {esp}, {number_players}')
				for veh, veh_value in value.items(): #loop through all vehicles in junctions
					if self.player_list[veh].goinghome:
						if self.algo != "RANDOM":
							continue

					if not veh in self.poi_list[key] and self.player_list[veh].prev_poi != key: #this if statement for when vehicle first enter junction
						#update capacity and reward first
						#print('vehicle approaching poi', veh, key)

						#maybe i shouldnt check for if veh at target poi if accidentally stomble then still try to collect
						#current_edge = veh_value[tc.VAR_ROAD_ID]
						self.track_veh = veh

						logging.info(f"{veh} arrived at {key} at step {t}")

						self.wait_in_radius(key, veh) #this process poi function need to stop vehicle and everything else happens in the stop handle function for updating sp

						if not t in self.post_process_graph.temp_coverage[key]:
							self.post_process_graph.temp_coverage[key].append(t)


						#self.post_process_graph.rc_visited_instance[t] = self.post_process_graph.calculate_test_coverage(custom_player_list=list(self.player_list.values()))
						#self.post_process_graph.rw_visited_instance[t] = self.post_process_graph.get_avg_reward(custom_player_list=list(self.player_list.values()))
					

						self.poi_list[key][veh] = veh_value #add vahicle in poi list for removal later

					elif veh in self.poi_list[key] and self.player_list[veh].prev_poi != key:
						#check if it should delete vehicle
						try:
							if self.map_data.edges[veh_value[tc.VAR_ROAD_ID]]._to != key:
								#print('vehicle left junction')
								self.player_list[veh].prev_poi = key
								del self.poi_list[key][veh]
								self.track_veh = None
						except KeyError:
							#print('reached junction')
							continue




if __name__ == '__main__':
	pass
	#problem, high expected sensing plan, but when 