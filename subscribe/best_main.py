import tkinter as tk
import traci
from _map import Map
from player import GridPlayer
from random import randrange, choice
from settings import Settings
import time
import numpy as np
from scipy.stats import truncnorm
from operator import mul
from functools import reduce
from postprocess import DataCapture, MultiCapture, PostGraphGrid
from math import exp
import pickle
import os
import datetime
from itertools import product as itpd
import logging
import copy
from collections import defaultdict
import itertools
import json
import argparse

#run simulation on same parameters as the paper
#implemnet the new algorithm on esp run simulartion and compare
#get results on the collection frequency of each crowdsourcer






class GridWin(tk.Tk):
	def __init__(self, gui=True, testing='budget', reward_matrix=None, player_matrix=None, save_dir=None, old_esp=False):
		super(GridWin, self).__init__()
		traci.start(["sumo", "-c", Settings.sumo_config])

		self.reward_matrix = reward_matrix
		self.player_matrix = player_matrix

		self.initial_player_list = []

		self.mode='default' #default, reward

		self.testing = testing #if testing budget keep capacity constant, if testing capacity keep budget constant

		self.env_map = Map(Settings.sumo_config, simple_grid=gui, grid=True)

		
		self.rowcol_to_junction = self.env_map.complex_row_col
		self.old_esp = old_esp



		self.row = int(self.env_map.rows)
		self.column = int(self.env_map.columns)

		self.rowcol_to_junction.update(dict((v, k) for k, v in self.rowcol_to_junction.items()))
		self.player_list = {} #stores location as key, player object as value in list # should be {location:{player_id:player}}
		self.reward_list = {} #stores location(grid) as key, reward value as value

		self.global_reward_list = None
		self.global_player_list = None


		self.random_uniform_reward_list = {} #akbas

		self.min_reward = 0 #min reward value


		self.gui = gui
		self.save_dir = save_dir



		self.setting = Settings()

		self.reward_distribution_center = [(0,0),  (0,self.column),(self.row, 0),(self.row, self.column)]
		#self.reward_distribution_center = [(0,self.column),(self.row, 0),(self.row, self.column)]



		if gui:
			self.protocol("WM_DELETE_WINDOW", self.on_closing)

			w=self.winfo_screenwidth()
			h=self.winfo_screenheight()
			size = str(int(w/2))+'x'+str(int(h/2))
			#print(size)
			self.geometry(size)

			self.import_frame = tk.Frame(self, bg='green')
			#self.import_frame.pack(expand=True, fill='both')

			self.grid_frame = tk.Frame(self, height=500, width=500, bg='red')
			self.grid_frame.pack(expand=True, fill='both')

			self.control_frame = tk.Frame(self)
			self.control_frame.pack(expand=True, fill='both')


			self.grid_list = [] #store all the buttons in grid
			self.spawn_grid()
			self.control_buttons()
			self.mainloop()
	
			
	def run_sim_no_gui(self, replay=False, spread_reward=True):
		if ((not replay) or self.testing == 'budget') and spread_reward:
			print("Generating Rewards....")

			for center in self.reward_distribution_center:
				self.generate_reward_spread(center[0], center[1], self.setting.reward_value_random[1], self.setting.reward_position_std, self.setting.reward_amount, mean=self.setting.reward_value_random[0])
				if self.setting.percent_reward_dist:
					#if we deicided to spread reward based off percentage, only need to do it once over the entire map
					break
			self.generate_reward_cost()

		logging.info(f"Starting simulation spreading rewward: {spread_reward} length: {len(self.reward_list)}")

		self.simulation(replay=replay)

	def generate_reward_cost(self): #this iterates through all rewards and generate cost for every player. make sure player and reward are poulated before call
		self.reward_mean_cost = {}
		for loc, reward_value in self.reward_list.items():
			try:
				self.reward_mean_cost[loc] = randrange(*self.setting.reward_mean_cost)
			except ValueError:
				self.reward_mean_cost[loc] = self.setting.reward_mean_cost[0]




	def default_mode(self):
		#each grid click spawns 1 vehicle, cells black
		#right click undo

		for i in range(self.row):
			for j in range(self.column):
				string_key = str(i) + '_' + str(j)

				self.grid_list[i][j].unbind('<Enter>')
				self.grid_list[i][j].unbind('<Leave>')
				self.grid_list[i][j].unbind('<MouseWheel>')

				if string_key in self.player_list:
					self.grid_list[i][j].configure(bg='black')
					self.grid_list[i][j].configure(text=str(len(self.player_list[string_key])))
				else:
					self.grid_list[i][j].configure(bg=self.default_button_color)
					self.grid_list[i][j].configure(text='')




				self.grid_list[i][j].configure(command = lambda i=i, j=j: self.add_player(i, j))
				self.grid_list[i][j].bind('<Button-3>', lambda event, a=i, b=j, color=self.default_button_color: self.remove_player(a, b, color))
				self.grid_list[i][j].bind('<Button-2>', lambda event, a=i, b=j: self.normal_distribute_players(a,b))
				self.grid_list[i][j].configure(fg='white')


	def ncr(self, n, r):
		r = min(r, n-r)
		numer = reduce(mul, range(n, n-r, -1), 1)
		denom = reduce(mul, range(1, r+1), 1)
		return (numer / denom)


	
	def spawn_reward_mode(self):
		if self.mode == 'default':
			self.mode='reward'
			self.select_rewards.configure(text='Select Vehicles')


			for i in range(self.row):
				for j in range(self.column):
					string_key = str(i) + '_' + str(j)
					self.grid_list[i][j].configure(command=lambda i=i, j=j: self.add_reward(i,j, 1))
					self.grid_list[i][j].configure(bg=self.default_button_color)
					self.grid_list[i][j].configure(fg='black')
					if string_key in self.reward_list:
						self.grid_list[i][j].configure(text=str(self.reward_list[string_key]))
					else:
						self.grid_list[i][j].configure(text='0')

					self.grid_list[i][j].bind('<Button-2>', lambda event, a=i, b=j: self.normal_distribute_players(a,b, False))

					self.grid_list[i][j].bind('<Enter>', lambda event, i=i, j=j: self.grid_list[i][j].bind('<MouseWheel>', lambda event, i=i, j=j:self.add_reward(i,j, int(event.delta/120))))#       self.reward_change(event, i, j)))
					self.grid_list[i][j].bind('<Leave>', lambda event: self.grid_list[i][j].unbind('<MouseWheel>'))
					self.grid_list[i][j].bind('<Button-3>', lambda event, i=i, j=j: self.reward_remove(i,j)) #this button used to clear rewards

		else:
			self.default_mode()
			self.mode='default'
			self.select_rewards.configure(text='Select Rewards')


	def reward_remove(self, row, column):
		string_key = str(row) + '_' + str(column)
		try:
			del self.reward_list[string_key]
			if self.gui:
				self.grid_list[row][column].configure(text='0')
		except KeyError:
			print('no rewards at this cell')


	def add_reward(self, row, column, scroll_value):
		string_key = str(row) + '_' + str(column)
		if string_key in self.reward_list:
			self.reward_list[string_key] += scroll_value
		else:
			self.reward_list[string_key] = scroll_value

		if self.reward_list[string_key] < 0:
			self.reward_list[string_key]=0


		if self.min_reward == 0 or (self.reward_list[string_key] < self.min_reward):
			self.min_reward = self.reward_list[string_key]
			#print(f'min reward value is {self.min_reward} at location {string_key}')
		


		if self.gui:
			self.grid_list[row][column].configure(text=str(self.reward_list[string_key]))





	def normal_distribute_players(self, a,b, dist_player=True):
		second_level = tk.Toplevel(self)
		second_level.title('normal distribution')

		std_label = tk.Label(second_level, text='STD: ').grid(row=0, column=0)
		number_label = tk.Label(second_level, text='Amount: ').grid(row=1, column=0)

		std_var = tk.StringVar()
		num_var = tk.StringVar()

		L1 = tk.Entry(second_level, justify='left', relief='ridge', background='#6699ff',textvariable=std_var)
		L1.grid(row=0, column=1)

		L2 = tk.Entry(second_level, justify='left', relief='ridge', background='#6699ff', textvariable=num_var)
		L2.grid(row=1, column=1)

		enter_button = tk.Button(second_level,text='Enter', command=lambda a=a, b=b, second_level=second_level,std=std_var, num_veh=num_var, dist_player=dist_player:self.generate_players(a,b, second_level ,std, num_var, dist_player))
		enter_button.grid(row=2, column=0)
		second_level.bind('<Return>', lambda event, a=a, b=b, second_level=second_level,std=std_var, num_veh=num_var:self.generate_players(a,b, second_level ,std, num_var))

	def generate_players(self, a,b, root, std=None, num_var=None, dist_player=True): #for normaly distributing players
		if std and num_var:
			std_value = float(std.get())
			num_var_value = int(num_var.get())
		else:
			print('no std and number chosen')
			#randomly generate
		x = self.get_truncated_normal(a, std_value, 0, 10).rvs(num_var_value+10000).round().astype(int)
		y = self.get_truncated_normal(b, std_value, 0, 10).rvs(num_var_value+10000).round().astype(int)		


		xPo = np.random.choice(x, num_var_value)
		yPo = np.random.choice(y, num_var_value)

		for x_points, y_points in zip(xPo, yPo):

			if dist_player:
				self.add_player(x_points, y_points)

			else:
				self.add_reward(x_points, y_points, 1)

		root.destroy()

	def generate_reward_spread(self, x, y, value_std, position_std, amount, mean=None):

		if self.setting.percent_reward_dist:
			print(f'length is {len(self.reward_list)}')
			#if defined percentage is true then spread reward based off the percentage value randomly over the map
			junction_list = np.array(list(self.env_map.junctions.keys()))
			choice_junctions = [self.rowcol_to_junction[x] for x in np.random.choice(junction_list, int(len(junction_list)*self.setting.percent_reward_dist), replace=False)]
			for junct_grid in choice_junctions:
				row, column = int(junct_grid.split('_')[0]), int(junct_grid.split('_')[1])
				if mean:
					mean_dist = self.get_truncated_normal(mean, value_std, 0, 10*value_std*mean).rvs(amount+10000).astype(float)
					self.add_reward(row, column, np.random.choice(mean_dist, 1)[0])

			assert len(self.reward_list) <= len(junction_list), f'Error reward list greater than junction'

			assert len(self.reward_list) == int(len(junction_list)*self.setting.percent_reward_dist), f'Error reward and expcted per not match expected {int(len(junction_list)*self.setting.percent_reward_dist)}, got {len(self.reward_list)} chocie {len(choice_junctions)}'
			return


		#if mean is not none generate distribution based off mean to add to rewards
		x, y = self.find_closest_road(x, y)

		x_dist = self.get_truncated_normal(x, position_std, 0, self.row).rvs(amount+10000).round().astype(int)
		y_dist = self.get_truncated_normal(y, position_std, 0, self.column).rvs(amount+10000).round().astype(int)
		

		xPo = np.random.choice(x_dist, amount)
		yPo = np.random.choice(y_dist, amount)
		
		zip_po = list(zip(xPo, yPo))

		i = 0
		while i < len(zip_po):
			x_points, y_points = zip_po[i]
			string_key = str(x_points) + '_' + str(y_points)
			if not string_key in self.rowcol_to_junction:
				#print(string_key, 'not in')
				zip_po[i] = (np.random.choice(x_dist, 1)[0], np.random.choice(y_dist, 1)[0])
				continue
			if mean:
				mean_dist = self.get_truncated_normal(mean, value_std, 0, 10*value_std*mean).rvs(amount+10000).astype(float)
				self.add_reward(x_points, y_points, np.random.choice(mean_dist, 1)[0])
			else:
				self.add_reward(x_points, y_points, 1)
			i+=1

		#assert len(self.reward_list) == amount, f'len of rewrd amount does not match {len(self.reward_list)}'
	
	def find_closest_road(self, x, y):
		closest = None
		for key, value in self.env_map.junctions.items():
			key = self.rowcol_to_junction[key]
			x1, y1 = int(key.split('_')[0]), int(key.split('_')[1])
			dist = np.linalg.norm(np.array([x,y])-np.array([x1, y1]))
			if not closest:
				closest = (key, dist)
			else:
				if dist < closest[1]:
					closest = (key, dist)

		return int(closest[0].split('_')[0]), int(closest[0].split('_')[1])



	def get_truncated_normal(self, mean=0, sd=1, low=0, upp=10000):
		return truncnorm((low - mean) / sd, (upp - mean) / sd, loc=mean, scale=sd)

	def control_buttons(self):
		for row in range(2):
			for column in range(3):
				self.control_frame.grid_columnconfigure(column, weight=1)
				self.control_frame.grid_rowconfigure(row, weight=1)

		start_sim_button = tk.Button(self.control_frame, text='START', command=self.start_sim)
		start_sim_button.grid(row=0, column=1, sticky=tk.N+tk.S+tk.W+tk.E)


		self.select_rewards = tk.Button(self.control_frame, text='Select Rewards', command = self.spawn_reward_mode)
		self.select_rewards.grid(row=0, column=0, sticky=tk.N+tk.S+tk.W+tk.E)

		clear_button = tk.Button(self.control_frame, text='CLEAR', command=self.clear)
		clear_button.grid(row=0, column=2,sticky=tk.N+tk.S+tk.W+tk.E)

		self.replay_button = tk.Button(self.control_frame, text='Find NQ Route', command=self.find_nash_route)
		self.replay_button.grid(row=1, column=1,sticky=tk.N+tk.S+tk.W+tk.E)

		self.save_button = tk.Button(self.control_frame, text='Save Simulation', command=self.save_simulation)
		self.save_button.grid(row=1, column=0,sticky=tk.N+tk.S+tk.W+tk.E)

		self.load_button = tk.Button(self.control_frame, text='Load Simulation', command=self.load_simulation)
		self.load_button.grid(row=1, column=2,sticky=tk.N+tk.S+tk.W+tk.E)


	def load_simulation(self):
		with open(Settings.sim_save, 'rb') as config_dictionary_file:
			self.cap = pickle.load(config_dictionary_file)
		print('simulation load sucess...')
		self.replay_simulation(load=True)


	def find_nash_route(self):
		print("finding nq route based on exsiting info ")
		#non-reapeating nodes 
		#veh starting location 
		#veh number 
		#our algorithm doesnt con

		if not self.player_list:
			print("no players in system to calculate")
			return

		empty_player_path = []

		for junct_id, player_list in self.player_list.items(): #
			for player in player_list:
				empty_player_path.append(player.all_path)

		all_combs_players = list(itpd(*empty_player_path))
		print(f"{len(all_combs_players)} combinations generated for {len(empty_player_path)} players")

		




	def replay_simulation(self, algo, load=False, sim_number=None):


		assert self.global_reward_list, f"I shouldnt be in replay there is no global reward list {self.global_reward_list}"
		assert self.global_player_list, f"I shouldnt be in replay there is no global player list {self.global_player_list}"


		if self.global_player_list: # for replay simulations we neeed to set the playerlist to the global player list
			self.player_list = copy.deepcopy(self.global_player_list)
		if self.global_reward_list:
			self.reward_list = copy.deepcopy(self.global_reward_list)

		self.cap.player_list=[]

		return self.start_sim(algo=algo, replay=True, load=load, sim_number=sim_number)


	def save_simulation(self):
		if not self.cap:
			print('No recent simulation, please run sim before save')
			return
		with open(Settings.sim_save, 'wb') as config_dictionary_file:
			pickle.dump(self.cap, config_dictionary_file)
		print('simulation saved success...')

	def spawn_grid(self):
		for i in range(self.row):
			temp_list = []
			for j in range(self.column):
				b= tk.Button(self.grid_frame)
				b.configure(font=("Courier", 20))
				b.grid(row=i, column=j, sticky=tk.N+tk.S+tk.W+tk.E, columnspan=1)
				self.default_button_color = b.cget('bg')
				self.grid_frame.grid_columnconfigure(j, weight=2)
				self.grid_frame.grid_rowconfigure(i, weight=2)
				temp_list.append(b)
			self.grid_list.append(temp_list)
		self.default_mode()


	def find_adjacent_cells(self, x_y, param='to'): #this function need to change to be determined using sumo
		adjacent_list_sumo = [self.rowcol_to_junction[x] for x in self.env_map.find_adjacent_cells(self.rowcol_to_junction[x_y], param=param)]
		if not adjacent_list_sumo:
			adjacent_list_sumo = [self.rowcol_to_junction[x] for x in self.env_map.find_adjacent_cells(self.rowcol_to_junction[x_y], param="both")]
		return adjacent_list_sumo

	def check_deadend(self, x_y): #check if cell is going to a different cell
		adjacent_list_sumo = [self.rowcol_to_junction[x] for x in self.env_map.find_adjacent_cells(self.rowcol_to_junction[x_y], param="to")]
		if not adjacent_list_sumo:
			return True
		return False


	def find_adjacent_players(self, x_y, list_players=False): #check for capacity

		player_list = []
		player_num = 0
		adjacent_list = self.find_adjacent_cells(x_y, param='from')

		deadend = self.check_deadend(x_y)
		for value in adjacent_list:
			
			try:
				player_num +=len(self.player_list[value])
				for player in self.player_list[value]:
					player.current_location = value
					player_list.append(player)
			except KeyError:
				continue

		if list_players:
			return player_num, player_list, deadend
		return player_num

	def remove_player(self, row, column, color):

		try:

			string_key = str(row) + '_' + str(column)	
			if len(self.player_list[string_key]) == 1:
				del self.player_list[string_key]
			else:
				self.player_list[string_key].pop(0)

			
			self.env_map.junctions[self.rowcol_to_junction[string_key]].number_players -= 1
			

			if self.env_map.junctions[self.rowcol_to_junction[string_key]].number_players == 0:
				self.grid_list[row][column].configure(text='')
				self.grid_list[row][column].configure(bg=color)
			else:
				self.grid_list[row][column].configure(text=self.env_map.junctions[self.rowcol_to_junction[string_key]].number_players)



		except KeyError:
			#try to delete  vehicle that doesnt exist
			pass
	def set_capacities(self):
		print("setting capacity...")
		print(f"mean: {self.setting.player_capacity_random[0]} std: {self.setting.player_capacity_random[1]}")
		for loc, players in self.player_list.items():
			for player in players:
				player.capacity = self.get_truncated_normal(self.setting.player_capacity_random[0], self.setting.player_capacity_random[1], 0, self.setting.player_capacity_random[0]*2).rvs(1)[0]




	def add_player(self, row, column, player=None, id_value=None): # add player to dictionary and return a dict


		row=int(row)
		column=int(column)

		player_instance = None

		string_key = str(row) + '_' + str(column)


		destination = self.setting.destination
		if destination =='random':
			destination = str(randrange(self.row))+'_'+str(randrange(self.column))

		if string_key == destination:
			print('start is destination')
			return False, player_instance

		try:	
			if player:
				player_instance = player
			else:
				player_instance = GridPlayer(id_value, self.rowcol_to_junction[string_key], self.rowcol_to_junction[destination])
				player_instance.path = self.env_map.find_best_route(player_instance.start, player_instance.destination)
				if not (player_instance.path and player_instance.path.edges):
					print('no path edges')
					return False, player_instance
				player_instance.node_path = [self.env_map.edges[x]._to for x in player_instance.path.edges]

			player_instance.capacity = self.get_truncated_normal(self.setting.player_capacity_random[0], self.setting.player_capacity_random[1], 0, self.setting.player_capacity_random[0]*2).rvs(1)[0]
			#print('plyer capacity is: ', player_instance.capacity)
		except KeyError as e:
			print(f'no key in dict {e}')
			return False, player_instance

		print(f'vehicle start at {string_key} end at {destination} capacity value is {player_instance.capacity}, reward list len is {len(self.reward_list)}')
		#self.env_map.graph_build.printAllPaths(self.rowcol_to_junction[string_key], self.rowcol_to_junction[destination])

		player_instance.shortest_path_length = copy.deepcopy(player_instance.node_path)
		#print(f"Vehicle {player_instance.id_value} Shortest path {player_instance.shortest_path_length}")
		ne_mapping_start = self.env_map.ne_mapping[self.rowcol_to_junction[string_key]]
		ne_mapping_end = self.env_map.ne_mapping[self.rowcol_to_junction[destination]]

		

		#player_instance.all_path = self.env_map.graph_build.printAllPaths(ne_mapping_start, ne_mapping_end)

		#print(f"ne mapping start {ne_mapping_start} end {ne_mapping_end} total path {len(player_instance.all_path)}")



		if string_key in self.player_list:
			self.player_list[string_key].append(player_instance)
		else:
			self.player_list[string_key] = [player_instance]




		

		if self.gui:
			self.env_map.junctions[self.rowcol_to_junction[string_key]].number_players += 1
			self.grid_list[row][column].configure(bg='black')
			self.grid_list[row][column].configure(text=self.env_map.junctions[self.rowcol_to_junction[string_key]].number_players)


		
		if self.setting.player_cost_sd == 0:
			player_instance.temp_random_cost = copy.deepcopy(self.reward_mean_cost)
		else:
			player_instance.temp_random_cost = {key:self.get_truncated_normal(value, sd=self.setting.player_cost_sd).rvs(1)[0] for key, value in self.reward_mean_cost.items()}

		#values = self.get_truncated_normal(player_instance.cost_mean, sd=self.setting.player_cost_sd).rvs(len(self.reward_list))
		#player_instance.temp_random_cost = dict(zip(keys, values))

		return True, player_instance



	def set_random_cost(self):
		print("setting random cost for players....")
		print(f"new std reward is {self.setting.player_cost_sd}")
		self.generate_reward_cost()
		for loc, players in self.player_list.items():
			for player in players:
				player.cost_sd = self.setting.player_cost_sd
				if self.setting.player_cost_sd  == 0:
					player.temp_random_cost = copy.deepcopy(self.reward_mean_cost)
				else:
					player.temp_random_cost = {key:self.get_truncated_normal(value, sd=self.setting.player_cost_sd).rvs(1)[0] for key, value in self.reward_mean_cost.items()}
				'''
				keys = list(self.reward_list.keys())
				values = self.get_truncated_normal(player.cost_mean, sd=self.setting. ).rvs(len(self.reward_list))
				player.temp_random_cost = dict(zip(keys, values))

				'''



	def redirect_route(self, player_instance, new_route):
		if new_route.edges[0] != player_instance.destination:
			player_instance.path = new_route # self.env_map.find_best_route(next_node, player_instance.destination)
			player_instance.node_path = [self.env_map.edges[x]._to for x in player_instance.path.edges]
			player_instance.node_index=0

		return player_instance

	

 
	def find_sensing_plan_count(self, player_count, adjacent_list, location):
		combs = list(itertools.combinations(adjacent_list, player_count))
		#print(f"finding combinations for {player_count}. {len(combs)} of combinations found")
		total_sp = 0
		for comb in combs:
			total_sp += self.compute_sensing_plan_new(comb, location, return_value=True)

		return total_sp

	



	def GTA_next_node(self, location, player_instance, current_node, cells):
		#takes in location, player, and next node return new next node and player instance
		#this function can be optimized, there are redundant check of cells can use dynamic programming to fix this later save the cells already checked
		
		assert cells, f'Junction has no where else to go {location}'


		new_route = player_instance.path

		#print('new route is ', new_route)

		max_utility = 0
		max_utility_cell = None
		deadend_cells = []
		no_dead_end = []



		for cell in cells:
			#print(f'cells value is {cells}')
			#cell is already in terms of buttons
			#consider all cells



			adjacent_players, player_list, deadend = self.find_adjacent_players(cell, list_players=True)
			if deadend:
				print(f"{cell} is a deadend")
				deadend_cells.append(self.rowcol_to_junction[cell])
				continue
			else:
				no_dead_end.append(cell)
			assert adjacent_players > 0, f'player is {adjacent_players} failed, location: {location}, surrounding cells: {cells}, player: {self.player_list[location]}'

			cell_utility = 0  #total utility at that cell 
			try:
				cell_utility = self.reward_list[cell]
				if cell_utility == 0:
					continue
			except KeyError:
				continue

			expected_utility = 0
			expected_sensing_plan = 0


			if adjacent_players == 1: #no one is around me
				expected_utility = (cell_utility - player_instance.temp_random_cost[cell])
				expected_sensing_plan = 1
			else:

				if self.old_esp:

					#sum the denomenator of the combination, store ncr in list to reuse later
					ncr_list = [self.ncr(adjacent_players-1, player_number) for player_number in range(0, adjacent_players)] #consists of a list from 0
					denom = reduce(lambda x,y: x+y, ncr_list) #from 0 to second to last in list
					for current_player in range(1, adjacent_players+1):

						numerator = ncr_list[current_player-1] #retrieve ncr value from list
						prM = numerator/denom
						expected_utility += (prM*(cell_utility/pow(current_player, 2)))

						expected_sensing_plan += (prM*(self.compute_sensing_plan(current_player, self.reward_list[cell], player_instance.temp_random_cost[cell])))

				
				
				else:
					comb_dict, mapping = self.find_all_combinations_new(player_list, player_instance)

					total_esp = 0
					total_eu = 0



					for i, combs in comb_dict.items():

						temp_esp = 0
						temp_eu = 0
						

						for comb in combs: # for each combination
							prob = 1
							for player in player_list:

								if player.id_value == player_instance.id_value:
									continue #when the player is myself, skip because the probability is 1
								else:
									if player.id_value in comb:
										prob *= (1/len(self.env_map.junctions[self.rowcol_to_junction[player.current_location]].adjacent_junctions))
									else:
										prob *= (1 - (1/len(self.env_map.junctions[self.rowcol_to_junction[player.current_location]].adjacent_junctions)))

							my_sp, all_player_sp = self.compute_sensing_plan_new([mapping[x] for x in comb], cell, return_value=True, player_instance=player_instance)

							temp_esp += (prob*my_sp) #suming all the esp for every comb
							#temp_eu += (prob*(cell_utility/pow(len(comb), 2)))
							temp_eu += (prob * (((my_sp/all_player_sp) * cell_utility) - (my_sp*player_instance.temp_random_cost[cell])))

						total_esp += temp_esp
						total_eu += temp_eu

					

					expected_utility = total_eu
					expected_sensing_plan = total_esp

					logging.info(f"player{player_instance.id_value} targeting cell {cell} esp:{total_esp} eu:{total_eu} cap:{player_instance.capacity} adj_players:{len(player_list)}")
					logging.debug(f"player{player_instance.id_value} creteria {expected_utility > max_utility} {expected_sensing_plan <= player_instance.capacity} {not cell in player_instance.past_recent_nodes} {max_utility} {expected_utility}")






			if (expected_utility > max_utility) and (expected_sensing_plan <= player_instance.capacity) and (not cell in player_instance.past_recent_nodes):
				#choose highest utility, with capacity taken into consideration, as well as no repeating within last 3 visited
				logging.debug(f"Setting player target player{player_instance.id_value} to location {cell} esp {expected_sensing_plan} eu {expected_utility} in recent {cell in player_instance.past_recent_nodes} cap {player_instance.capacity}")
				max_utility = expected_utility
				max_utility_cell = cell

		#this part to generate the weighted random path

		if not max_utility_cell:
			#if adj cells no rewards
			#if adj cells rewards dont fit capacity
			#weighted random need to priotize coverage good


			weight_dict, best_route = self.env_map.find_best_route(current_node, player_instance.destination, weights=True, ignore_cells = deadend_cells)
			#weight_dict = {key:value.travelTime*self.visited_cell_list[key]*len(value.edges) if key in self.visited_cell_list else value.travelTime for key, value in weight_dict.items()}
			#travel time multiple by cell visited number , multiple by number of edges before reaching destination



			try:
				total_sum = reduce(lambda x,y:x+y,[exp(self.setting.theta_random/x.travelTime) for x in weight_dict.values()])
				prob_distribute = [exp(self.setting.theta_random/x.travelTime)/total_sum for x in weight_dict.values()]

				selected_index = np.random.choice(len(weight_dict), 1, p=prob_distribute)
				next_node = list(weight_dict.keys())[selected_index[0]]

			except OverflowError:
				#when theta random value is too large just take the best route node
				next_node = self.env_map.edges[best_route.edges[0]]._to
			except TypeError: #it jumped to a node cant get back
				#next_node = self.env_map.edges[best_route.edges[0]]._to
				if not no_dead_end:
					next_node = self.rowcol_to_junction[choice(cells)]
				else:
					next_node = self.rowcol_to_junction[choice(no_dead_end)]

			player_instance.random_steps += 1
			player_instance.expecting_to_collect = False #im expecting to collect



		else:
			#when max utility cells is found its in terms of grid junction need to convert to sumo junction
			next_node = self.rowcol_to_junction[max_utility_cell]

			player_instance.expected_collection_steps += 1
			player_instance.expecting_to_collect = True

			logging.info(f"player{player_instance.id_value} going towards {next_node} esp: {expected_sensing_plan} cap: {player_instance.capacity}")


		player_instance = self.redirect_route(player_instance, new_route)
		player_instance = self.add_stm(player_instance, next_node)



		

		return next_node, player_instance


	def add_stm(self, player_instance, next_node):
		if len(player_instance.past_recent_nodes) < self.setting.max_memory_size:
			player_instance.past_recent_nodes.append(self.rowcol_to_junction[next_node]) #sumo junction is added to memory
		else:
			if self.setting.max_memory_size != 0:
				player_instance.past_recent_nodes.pop(0)
				player_instance.past_recent_nodes.append(self.rowcol_to_junction[next_node])

		return player_instance



	def simulation(self, replay=False):
		if self.testing == "player":
			self.post_cap = PostGraphGrid(f"player_amount_{self.setting.car_numbers}", columns=["algo","sim_number", "sim_step", "veh_id", "edge_id", "grid_id", "next_edge_id", "next_grid_id", "utility", "capacity"])
		elif self.testing == "capacity":
			self.post_cap = PostGraphGrid(f"capacity_mean_{self.setting.player_capacity_random[0]}", columns=["algo","sim_number", "sim_step", "veh_id", "edge_id", "grid_id", "next_edge_id", "next_grid_id", "utility", "capacity"])
		elif self.testing == "rewardstd":
			self.post_cap = PostGraphGrid(f"old_esp_{self.old_esp}_rewardstd_{self.setting.player_cost_sd}", columns=["algo","sim_number", "sim_step", "veh_id", "edge_id", "grid_id", "next_edge_id", "next_grid_id", "utility", "capacity", "old_esp"])

		for algo_index, algo in enumerate(self.setting.game_theory_algorithm):
			multi_data = MultiCapture('Traffic Simulation')
			i=0

			self.setting.current_algo_index = algo_index

			while i < self.setting.simulation_steps:
				print('iteration ', i)
				logging.info(f"Running simulation: {i} for ALGO: {algo} replay:{replay}")

				self.cap = DataCapture(len(self.env_map.junctions), self.rowcol_to_junction) #capture for each single simulation

				try:
					if replay:
						suc = self.replay_simulation(algo=algo, sim_number = i) #if replay is true, 
					else:
						suc = self.start_sim(algo=algo, sim_number=i) #first time running simulation generate random players save it to self.cap

				except AssertionError as e:
					print(f"ERROR {e} replay:{replay} iteration:{i} algo{algo}")
					logging.warning(f"ERROR {e} replay:{replay} iteration:{i} algo{algo}")
					suc = False

				



				if suc: #if simulation is success
					
					self.cap.setting = self.setting
					self.cap.reward_list = copy.deepcopy(self.reward_list)
					#self.cap.reward_list = self.global_reward_list.copy()

					self.cap.reward_junction_ratio = len(self.cap.reward_list)/len(self.env_map.junctions)
					cov = self.cap.calculate_coverage()
					test_cov = self.cap.calculate_test_coverage()
					print('road utilization is ', cov)
					print('coverage is ', test_cov)
					multi_data.simulation_conv_list.append(cov)
					multi_data.simulation_test_coverage.append(test_cov)
					multi_data.simulation_list.append(self.cap)


					replay=True

					result = self.cap.get_average_results()

					print(result)


					logging.info(f"Simulation RU: {cov} RC: {test_cov} RC_TEST: {self.cap.get_coverage_over_reward()}")
					logging.info("TP:{0} TN:{1} FP:{2} FN:{3} avg_random_step:{4} avg_exp_steps:{5} avg_collected_steps{6}".format(*result))

					logging.info("SIMULATION ENDED SUCCESS")



					if i == (self.setting.simulation_steps-1):
						if self.setting.percent_reward_dist:
							multi_data.pickle_save(os.path.join(self.save_dir, f'{self.setting.percent_reward_dist}_reward{self.setting.reward_value_random[0]}_capacity{self.setting.player_capacity_random[0]}_Step{self.setting.simulation_steps}_{algo}_cluster_reward.sim'))
						else:
							multi_data.pickle_save(os.path.join(self.save_dir, f'{self.setting.car_numbers}_reward{self.setting.reward_value_random[0]}_capacity{self.setting.player_capacity_random[0]}_Step{self.setting.simulation_steps}_{algo}_{self.old_esp}_{self.setting.player_cost_sd}_cluster_reward.sim'))
					i+=1
				
				self.player_list = {}
				self.reward_list = {}

		self.post_cap.to_csv(self.save_dir)
		
	




		
	def reward_spread_uniform(self, amount_rewards):
		#spread rewards uniformly based of ratio
		self.reward_list = {}

		if self.random_uniform_reward_list:
			for key, value in self.random_uniform_reward_list.items():
				self.random_uniform_reward_list[key] = randrange(self.setting.reward_value_random[0]-self.setting.reward_value_random[1], self.setting.reward_value_random[0]+self.setting.reward_value_random[1])

			self.reward_list = self.random_uniform_reward_list
		else:

			reward_locations = np.random.choice(list(self.env_map.junctions.keys()), round(amount_rewards))
			for value in reward_locations:
				value = self.rowcol_to_junction[value]
				x,y = int(value.split('_')[0]), int(value.split('_')[1])
				self.add_reward(x,y,randrange(self.setting.reward_value_random[0]-self.setting.reward_value_random[1], self.setting.reward_value_random[0]+self.setting.reward_value_random[1]))



	def greedy_next_node(self, location, player_instance, current_node, cells):
		'''
		location current location in terms of sumo
		player instance the player we are looking at
		current node is the location in terms of grid values
		next_node is predicted next node based on dex
		'''
		#shortest_path = False

		#cells return grid location not sumo location
		#reward list returns grid location as well


		max_utility_cell = None
		max_utility = 0
		for i, cell in enumerate(cells):
			try:
				self.reward_list[cell]
				#before going to the next cell i have to make the comparision with capacity, i cant simply just go the max cell around me or i can only cover 2 cells before


				#if (self.reward_list[cell] > max_utility) and (self.reward_list[cell]<=player_instance.capacity) and (not cell in player_instance.past_recent_nodes):
				if (self.reward_list[cell] > max_utility) and (not cell in player_instance.past_recent_nodes) and (player_instance.capacity != 0):# and (player_instance.capacity >= 1):
					#this will cause the player to explore abit, this is needed to determine when the player should go towards destination
					max_utility_cell = cell
					max_utility = self.reward_list[cell]


			except KeyError as e:
				#print(f'im here {i}/{len(cells)}')
				assert not cell in self.reward_list, f"failed {cell} is in reward_list"

				#when there are no rewards, max_util stays none

		#two cases, when no rewards around, or max utility cell is chosen
		#find smallest reward, if capacity falls below smallest reward, uses djk instead
		if not max_utility_cell:



			#let random jump decide on capacity that way greedy no need to implement
			next_node, player_instance= self.random_next_node(location, player_instance, current_node, cells) #remove random directly go towards destination shortest path
			#next node for random returns sumo cells

		else:
		
			next_node = max_utility_cell
			

			assert max_utility_cell in self.reward_list, f'something is wrong {max_utility_cell} supose in reward list'

			player_instance.collected_sp_list.append(next_node)

			next_node = self.rowcol_to_junction[next_node]
			player_instance.expected_collection_steps += 1
			player_instance.expecting_to_collect = True

			#next node normally return grid cells

			'''

			
			player_instance.capacity -= max_utility
			player_instance.reward += max_utility

			'''

			#this calculation is done after running 
		
			#player_instance =  self.add_stm(player_instance, next_node)

		if next_node: #next node returns none when player instance shortest path is true

			player_instance = self.add_stm(player_instance, next_node)


		return next_node, player_instance#, shortest_path






	def random_next_node(self, location, player_instance, current_node, cells):
		# capacity for random
		#weighted random should consider reward as well

		#shortest_path = False
		try:

			if player_instance.capacity <= 1:#take the shortest path
				player_instance.shortest_path = True
				next_node = None
				player_instance.path = self.env_map.find_best_route(current_node, player_instance.destination)
				player_instance.node_path = [self.env_map.edges[x]._to for x in player_instance.path.edges]
				player_instance.node_index = 0 #reset path info

			else:

				weight_dict, best_route = self.env_map.find_best_route(current_node, player_instance.destination, weights=True)
				
				total_sum = reduce(lambda x,y:x+y,[exp(self.setting.theta_random/x.travelTime) for x in weight_dict.values()])
				prob_distribute = [exp(self.setting.theta_random/x.travelTime)/total_sum for x in weight_dict.values()]

				#print('prob_distribute ', prob_distribute)
				#print('max value is {}, index value is {}, the next cell is {}, current cell is {}'.format(max(prob_distribute), prob_distribute.index(max(prob_distribute)), self.rowcol_to_junction[list(weight_dict.keys())[prob_distribute.index(max(prob_distribute))]], self.rowcol_to_junction[current_node]))
				selected_index = np.random.choice(len(weight_dict), 1, p=prob_distribute)
				next_node = list(weight_dict.keys())[selected_index[0]]

		except OverflowError:
			#when theta random value is too large just take the best route node
			next_node = self.env_map.edges[best_route.edges[0]]._to

		except Exception as e:
			next_node = self.rowcol_to_junction[choice(cells)]



		player_instance.random_steps += 1
		player_instance.expecting_to_collect = False




		return next_node, player_instance#, shortest_path


	def find_all_combinations(self, player_list, player_instance):
		#temp = defaultdict(list)
		#this need to return a combs of player list
		if len(player_list) == 1:
			return None
		#res = defaultdict(list)
		result = []
		mapping = {pl.id_value:pl for pl in player_list}
		keys = list(mapping.keys())
		for i in range(1, len(keys)+1):
			combs = itertools.combinations(keys, i)
			for comb in combs:
				if player_instance.id_value in comb:
					new_comb = [mapping[p] for p in comb] #contains a list of player objects as combs
					#res[i].append(new_comb)
					result.append(new_comb)

		return result

	def find_all_combinations_new(self, player_list, player_instance):
		comb_dict = defaultdict(list) # for each i value in player list
		
		mapping = {pl.id_value:pl for pl in player_list}

		keys = list(mapping.keys())

		logging.debug(f"Generating Combs for {player_instance.id_value}:")

		for i in range(1, len(keys)+1):
			combs = list(itertools.combinations(keys, i))
			for comb in combs:
				if player_instance.id_value in comb:
					logging.debug(f"#{i} combs {comb}")
					comb_dict[i].append(comb)

		return comb_dict, mapping


	def start_sim(self, algo="gta", replay=False, load=False, sim_number=None):

		#shortest_path = False

		#print('len reward is ', len(self.reward_list))

		#simulation start
		if self.gui:
			self.default_mode()
			

		sim_step = 0

		logging.info(f"Algorithm {algo} simulation step: {sim_step}")

		#if not replay: self.cap = DataCapture(len(self.env_map.junctions), self.rowcol_to_junction) #reset if its not replay


		#if no predefined players, randomly spawn players
		if (not self.player_list) and (not replay):
			print(f"No players in the system generating random players {len(self.player_list)}")
			i = 0
			#assert not self.initial_player_list, f"wtfff im not initial list is not empty {replay}"
			self.initial_player_list = []
			while i < self.setting.car_numbers:
				row_col = choice(list(self.env_map.junctions.keys()))
				row, column = self.rowcol_to_junction[row_col].split('_')[0], self.rowcol_to_junction[row_col].split('_')[1]
				suc, p_instance = self.add_player(row, column, id_value=i)

				if suc:
					i +=1
					self.initial_player_list.append(p_instance) #for keeping the players initially incase if needed to stay constant
					print(f'player added to {row}, {column}')
				else:
					print(f'failed to add player at {row}, {column}')


			## this populates the cost for every player to every rewards
			'''
			for location, players in self.player_list.items():
				for player in players:
					player.cost_mean = randrange(*self.setting.player_cost_mean)
					player.cost_sd = self.setting. 
					#player.poi_cost = self.get_truncated_normal(player_mean, sd=self.setting. ).rvs(len(self.reward_list))

					#print(f"{player.poi_cost.shape} poi costs added to player")

			'''

		arrived_locations = [] #destinations of all vehicles to reset after



		


		if not self.global_player_list:
			self.global_player_list = copy.deepcopy(self.player_list) #avoid user defined types such as list as values
		if not self.global_reward_list:
			self.global_reward_list = copy.deepcopy(self.reward_list)

		#after setting rewards and players


		for loc, plist in self.player_list.items():
			for play in plist:
				#logging.info(f"ID:{play.id_value} Cap: {play.capacity}")
				print(f"ID:{play.id_value} Cap: {play.capacity}")
					

		while self.player_list:
			player_left = 0

			if self.gui:
				self.update()
				time.sleep(self.setting.simulation_delay)
			temp_dict = {}
			for location, players in self.player_list.items():

				#find combinations for all players

				cells = self.find_adjacent_cells(location) #return grid junction



				for i, player in enumerate(players):

					player_left+=1

					
					#junction value in sumo

					#insert logic for game theory, 
					if algo=='gta' and not load: #if its loading from file then just play players
						next_node, player = self.GTA_next_node(location, player, self.rowcol_to_junction[location], cells)


					elif algo=='greedy' and not load:
						#run greedy algo, only go towards highest rewards. check capacity and reduce capacity based on reward value else result in infinite loop
						if not player.shortest_path:
							next_node, player = self.greedy_next_node(location, player, self.rowcol_to_junction[location], cells)

						if player.shortest_path:
							print('player taking shortest path in greedy')
							next_node = player.get_next()

					elif algo=='random' and not load:
						if not player.shortest_path:
							next_node, player = self.random_next_node(location, player, self.rowcol_to_junction[location], cells)
						
						if player.shortest_path:
							print('player taking shortest path in random')
							next_node = player.get_next()


					elif algo == 'base' and not load:
						next_node = player.get_next()
						
						
						


					if sim_number:
						if self.testing=="rewardstd":
							self.post_cap.append_row([algo, sim_number, sim_step, player.id_value, self.rowcol_to_junction[location], location, next_node, self.rowcol_to_junction[next_node], player.reward, player.capacity, self.old_esp])
						else:
							self.post_cap.append_row([algo, sim_number, sim_step, player.id_value, self.rowcol_to_junction[location], location, next_node, self.rowcol_to_junction[next_node], player.reward, player.capacity])
												#["algo","sim_number", "sim_step", "veh_id", "edge_id", "grid_id", "next_edge_id", "next_grid_id", "utility", "capacity"]


					'''

					if algo == "base":
						print(f"next node for base is {self.rowcol_to_junction[next_node]} current is {location} containsR:{self.rowcol_to_junction[next_node] in self.reward_list} CAP:{player.capacity}")
						if self.rowcol_to_junction[next_node] in self.reward_list:
							print(f"reward value {self.reward_list[self.rowcol_to_junction[next_node]]}")
							if self.reward_list[self.rowcol_to_junction[next_node]] <= player.capacity:

								print("im collecting for base")
								player.collected_sp_list.append(self.rowcol_to_junction[next_node])
								player.capacity -= self.reward_list[self.rowcol_to_junction[next_node]]
								player.reward += self.reward_list[self.rowcol_to_junction[next_node]]
					'''

					player.node_hit.append(next_node) # for post processing
					player.reward_hit.append(player.capacity) # for post processing

					button_name = self.rowcol_to_junction[next_node]

					button_row, button_column = button_name.split('_')

					if next_node == player.destination:
						print(f'player has arrived to {self.rowcol_to_junction[player.destination]} from {self.rowcol_to_junction[player.start]} nodes traveled:{len(player.node_hit)}')
						arrived_locations.append(player.destination)
						self.cap.player_list.append(player) #add player to the post processing list

					else:
						#if final destination is not reached add it to the temp dict

						if button_name in temp_dict:
							temp_dict[button_name].append(player)
						else:
							temp_dict[button_name] = [player]
					
					

					if self.gui:
						self.env_map.junctions[self.rowcol_to_junction[button_name]].number_players += 1
						self.env_map.junctions[self.rowcol_to_junction[location]].number_players -= 1
						self.grid_list[int(button_row)][int(button_column)].configure(bg='black')
						self.grid_list[int(button_row)][int(button_column)].configure(text=self.env_map.junctions[self.rowcol_to_junction[button_name]].number_players)


				#every time a player move away check if the edge contains more players
			
				if self.gui:
					player_number = self.env_map.junctions[self.rowcol_to_junction[location]].number_players
					prev_button_row, prev_button_column = location.split('_')

					if player_number == 0:
						self.grid_list[int(prev_button_row)][int(prev_button_column)].configure(bg='white')
					else:
						self.grid_list[int(prev_button_row)][int(prev_button_column)].configure(text=player_number)


			self.player_list = copy.deepcopy(temp_dict)

			print(f'{player_left} remaining')

			#if capacity too low make random jumps towards destination

			#if algo=='gta': #reduce capacity based on sensing plan

			for location, players in self.player_list.items():
				print('location is ', location)

				#location_cost = self.env_map.junctions[self.rowcol_to_junction[location]].cost
				adjusted_value = None
				
				#if algo=="gta"
				self.adjusting_sensing_plan_new(players, location)

				adjusted_value = self.adjusting_sensing_plan_paper(players, location)

				if adjusted_value: #this is only for atne and if this is not none basically means there are rewards

					comb, sp_dict = adjusted_value
					for i, player in enumerate(players):

						if player.id_value in comb:


							assert player.capacity >= sp_dict[player.id_value], f"adjustd sp failed id: {player.id_value} Cap: {player.capacity} SP: {sp_dict}"

							player.visited_sp_list.append(location)
							player.capacity -= sp_dict[player.id_value]
							player.collected_sp_list.append(location)

							player.reward += ((sp_dict[player.id_value]/sum(list(sp_dict.values()))) * self.reward_list[location]) - (sp_dict[player.id_value]*player.temp_random_cost[location])
							#addding reward to the player


							player.actual_collection_steps += 1

							if player.expecting_to_collect:
								player.true_positive += 1
							else:
								player.false_positive += 1
						else:

							if player.capacity < 1: #this if statement is needed to tell the vehicle start to go towards destination
								player.capacity = 0

							if player.expecting_to_collect:
								player.true_negative += 1
							else:
								player.false_negative += 1






				else:

					for i, player in enumerate(players):


						try:
							cell_utility = self.reward_list[location]

							player.visited_sp_list.append(location)

							my_sp, all_player_sp = self.compute_sensing_plan_new(players, location, return_value=True, player_instance=player)

							#self.player_list[location][i].reward += (self.reward_list[location]/len(self.player_list[location])) #question mark.. if location no reward dont calculate sensing plan

							player.reward += ((my_sp/all_player_sp) * cell_utility) - (my_sp*player.temp_random_cost[location])

							
							
							logging.info(f"player {player.id_value} at {location} ASP: {my_sp} cap: {player.capacity} player_here: {len(players)}")


							player_sensing_plan = my_sp
							if self.reward_list[location] != 0:
								# if you arrived and your cost is more than your player capacity might as well take what ever your capacity can handle
								if player_sensing_plan <= player.capacity:
									self.player_list[location][i].collected_sp_list.append(location)
									self.player_list[location][i].capacity -= player_sensing_plan

									player.actual_collection_steps += 1

									if player.expecting_to_collect:
										player.true_positive += 1
									else:
										player.false_positive += 1


									if self.player_list[location][i].capacity < 0: 
										self.player_list[location][i].capacity = 0
								else:
									if player.capacity < 1: #this if statement is needed to tell the vehicle start to go towards destination
										player.capacity = 0

									if player.expecting_to_collect:

										player.true_negative += 1

										if algo == "greedy": #if greedy is expecting to collect, but didnt collect then i set the 
											player.capacity /= 2
									else:
										player.false_negative += 1

									#print(f'{player_sensing_plan} and cap is {player.capacity} Data cant be collected')

							

							

							
						except KeyError as e:

							if player.expecting_to_collect:
								player.true_negative += 1
								if algo == "greedy": #if greedy is expecting to collect, but didnt collect then i set the 
									player.capacity /= 2
							else:
								player.false_negative += 1

							continue
						except TypeError as t:
							#print(f'no player matching adjust at {location}, {number_players}')
							#type error occurs when ajusting sensing plan returns None
							continue

			sim_step += 1


		self.cap.simulation_steps = sim_step
		logging.info(f"Simulation {sim_number} completed, ALGO: {algo} total steps: {sim_step}")

		
		#self.reset_junction_players(arrived_locations)
		return True


	def compute_sensing_plan(self, player_amount, reward, cost):

		#this need to be adjusted based on given H parameter
		if player_amount ==1:
			return 1
		return ((player_amount-1)*reward)/((player_amount**2)*cost)


	def compute_sensing_plan_new(self, player_consider_list, location, return_value=False, player_instance=None, return_dict=False):


		number_players = len(player_consider_list)



		player_sp_dict = {}

		total_sensing_plan = 0

		player_sensing_plan = 0

		H = [0, 1]
		i = 2

		try:
			sorted_player_list = sorted(player_consider_list, key=lambda x: x.temp_random_cost[location]) #this would only cause error

			
			for index_value, value in enumerate(sorted_player_list):
				if index_value >= i: #making sure we start at the i value, and not 0
					

					compare_function = (sum([sorted_player_list[index].temp_random_cost[location] for index in H]) + value.temp_random_cost[location])/len(H)
					if value.temp_random_cost[location] < compare_function:
						H.append(index_value)
					else:
						break
		except KeyError:
			#temprandomcost location failed due to no reward
			sorted_player_list = player_consider_list # if we get key error due to trying to sort list
			#assert not return_value, f"no reward at location {location} shouldve skipped" 

		

		for index_value, player in enumerate(sorted_player_list):

			temp_sensing_plan = 0


			if number_players == 1:
				temp_sensing_plan = 1
			else:
				if index_value in H:
					
					denom = sum([sorted_player_list[index].temp_random_cost[location] for index in H])
					temp_sensing_plan = (((len(H) -1) * self.reward_list[location])/denom)*(1 - (((len(H) -1) * player.temp_random_cost[location])/denom)) 

					
					
				else:
					temp_sensing_plan = 0

			

			if return_value:
				if player.id_value == player_instance.id_value:
					player_sensing_plan = temp_sensing_plan

			player_sp_dict[player.id_value] = temp_sensing_plan

			#return sensing plan only for the particular player instance

			total_sensing_plan += temp_sensing_plan

		if return_value:

			return player_sensing_plan, total_sensing_plan

		if return_dict:

			return player_sp_dict

	def adjusting_sensing_plan_paper(self, list_players, location):
		mapping = {x.id_value:x for x in list_players}
		player_ids = list(mapping.keys())

		try:
			self.reward_list[location]
		except KeyError:
			return None

		if len(player_ids) == 1:
			return None

		
		while player_ids:
			list_found = True
			sp_dict = self.compute_sensing_plan_new([mapping[x] for x in player_ids], location, return_dict=True)

			for id_value in copy.deepcopy(player_ids):
				try:
					if mapping[id_value].capacity <= sp_dict[id_value]:
						player_ids.remove(id_value)
						list_found = False
				except KeyError:
					player_ids.remove(id_value)
					list_found = False

			if list_found:
				logging.debug(f"paper adjusted sensing plan passed for {player_ids}, {sp_dict}")
				return (player_ids, sp_dict)


		return None


		

	def adjusting_sensing_plan_new(self, list_players, location):
		mapping = {x.id_value:x for x in list_players}
		player_ids = mapping.keys()

		try:
			self.reward_list[location]
		except KeyError:
			return None

		if len(player_ids) == 1:
			return None

		for i in range(len(player_ids), 0, -1):
			combs = itertools.combinations(player_ids, i)
			for comb in combs:
				sp_dict = self.compute_sensing_plan_new([mapping[x] for x in comb], location, return_dict=True)
				logging.debug(f"sensing plan for {comb} is: {sp_dict}")
				cap_dict = {mapping[p].id_value:mapping[p].capacity for p in comb}
				logging.debug(f"capacity: {cap_dict}")

				passed = True
				for p in comb:
					try:
						if (sp_dict[p] > mapping[p].capacity) or (sp_dict[p] == 0):
							#should remove the one with least capacity
							passed = False
							break
					except KeyError:
						passed = False
						break

				if passed:
					logging.debug(f"myself adjusted sensing plan passed for {comb}, {sp_dict}")
					return (comb, sp_dict)

		


	def adjusting_sensing_plan(self, players, location, location_cost):
		#return key error because the location has no reward?
		#this has to be dropped in the new sensing plan calculation
		#we cant compute sensing plan if we dont have a defined list of players

		try:
			for i in range(len(players), 0, -1):
				temp_player_list = []
				esp = self.compute_sensing_plan(i, self.reward_list[location], location_cost)
				counter = 0 #this to count how many fits the capacity
				for player in players:
					if esp<=player.capacity:
						temp_player_list.append(player)
						counter+=1
					#print(f'esp:{esp} cap:{player.capacity} len:{len(players)}')
				if counter == i:
					return counter, temp_player_list

			#print(f'i find no one matching sensing plan')
			return len(players), players
		except KeyError:
			#print('i sense no rewards')
			return len(players), players



	def clear(self):
		if self.mode == 'default':
			self.player_list = {}
			self.default_mode()
		else:
			self.mode='default'
			self.reward_list = {}
			self.spawn_reward_mode()


	def reset_junction_players(self, arrived_locations):
		
		if self.gui:
			for value in set(arrived_locations):
				self.env_map.junctions[value].number_players = 0
			self.clear()
		self.player_list = {}
		self.reward_list = {}
		

	def on_closing(self):
		self.destroy()
		traci.close()

def save_dict(dict_value, path):
	with open(path, 'w') as f:
		json.dump(dict_value, f)


def increasing_memory(dir_name, increments = 2):
	#player stays the same
	#reward stays the same
	#setting max_memory_size change
	player_value = None
	reward_value = None
	max_memory_size = None



	for i in range(5):

		save_dir = os.path.join(dir_name, f"{i}")
		os.mkdir(save_dir)


		root = GridWin(gui=False, testing='capacity', save_dir = save_dir)
		if not player_value:
			root.run_sim_no_gui()
			player_value = copy.deepcopy(root.global_player_list)
			reward_value = copy.deepcopy(root.global_reward_list)
			max_memory_size = root.setting.max_memory_size + increments

		else:
			root.player_list = copy.deepcopy(player_value)
			root.reward_list = copy.deepcopy(reward_value)
			root.setting.max_memory_size = max_memory_size

			root.run_sim_no_gui(spread_reward=False)
			max_memory_size = root.setting.max_memory_size + increments

		root.on_closing()

	save_dict(reward_value, os.path.join(dir_name, "reward.json"))


def increasing_rewards(dir_name, increments=40):
	#players stays the same
	player_value = None
	reward_amount = None

	for i in range(5):
		save_dir = os.path.join(dir_name, f"{i}")
		os.mkdir(save_dir)
		root = GridWin(gui=False, testing='capacity', save_dir = save_dir)
		if not player_value:
			root.run_sim_no_gui()
			player_value = copy.deepcopy(root.global_player_list)
			reward_amount = root.setting.reward_amount + increments
		else:
			root.player_list = copy.deepcopy(player_value)
			root.setting.reward_amount = reward_amount
			root.run_sim_no_gui()
			reward_amount = root.setting.reward_amount + increments

		root.on_closing()

		save_dict(root.global_reward_list, os.path.join(save_dir, "reward.json"))





def increase_radius(dir_name, increments=-5):

	player_value = None #player value stays the same
	reward_position_std = None

	for i in range(5):
		root = GridWin(gui=False, testing='budget', save_dir = dir_name)
		if not player_value:
			root.run_sim_no_gui()
			player_value = copy.deepcopy(root.global_player_list)
			reward_position_std = root.setting.reward_position_std + increments
		else:

			root.player_list = copy.deepcopy(player_value)
			root.setting.reward_position_std = reward_position_std
			root.run_sim_no_gui()
		root.on_closing()

		save_dict(reward_value, os.path.join(dir_name, "reward.json"))






def increasing_random_sd(dir_name, increments=0.1):
	random_mean= None #random mean stays the same
	reward_value = None #reward statys the same
	player_value = None #player value stays the same
	rewardstd = None
	std_start = None #the starting value of  

	inc_cust = np.logspace(-2, 1.5, 40, endpoint=True) #0-10, step= 40

	index = 0

	print("INC CUST", inc_cust)


	for k in range(2):
		if k == 1:
			index = 0

			#rewardstd = std_start
		for i in inc_cust:
		#for i in range(10):
			root = GridWin(gui=False, testing='rewardstd', save_dir = dir_name, old_esp=bool(k))
			root.setting.player_cost_sd = i

			if not player_value:

				root.run_sim_no_gui()
				player_value = copy.deepcopy(root.global_player_list)
				reward_value = copy.deepcopy(root.global_reward_list)
				#std_start = root.setting.player_cost_sd
				#rewardstd = root.setting.player_cost_sd  + increments
				
			else:

				root.player_list = copy.deepcopy(player_value)
				root.reward_list = copy.deepcopy(reward_value)

				#root.setting.player_cost_sd  = rewardstd
				root.set_random_cost()
				root.run_sim_no_gui(spread_reward=False)
				#rewardstd = root.setting.player_cost_sd  + increments

			root.on_closing()
	save_dict(reward_value, os.path.join(dir_name, "reward.json"))






def increasing_capacity(dir_name, increments=40, reward_actual=False):
	#
	player_value = None
	capacity_num = None
	reward_value = None

	reward_mean_cost = None

	rowcol_to_junction = None



	for i in range(5):

		save_dir = os.path.join(dir_name, f"{i}")
		os.mkdir(save_dir)

		root = GridWin(gui=False, testing='capacity', save_dir = save_dir)


		#print('im here ', i)
		if not player_value:#initial
			#print('root value 1', root.player_capacity_random)
			root.run_sim_no_gui() #this one needs fix
			player_value = copy.deepcopy(root.global_player_list)
			reward_value = copy.deepcopy(root.global_reward_list)
			capacity_num =  (root.setting.player_capacity_random[0] + increments, 5)
			reward_mean_cost = copy.deepcopy(root.reward_mean_cost)

			rowcol_to_junction = copy.deepcopy(root.rowcol_to_junction)
		else:
			#print('root value not 1', root.player_capacity_random)
			root.player_list = copy.deepcopy(player_value)
			root.reward_list = copy.deepcopy(reward_value)
			root.setting.player_capacity_random = capacity_num
			root.reward_mean_cost = copy.deepcopy(reward_mean_cost)

			root.set_capacities()

			root.run_sim_no_gui(spread_reward=False)

			capacity_num =  (root.setting.player_capacity_random[0] + increments, 5)
		root.on_closing()


		logging.info(f"Simulation parameter {root.setting.player_capacity_random}")
	save_dict(reward_value, os.path.join(dir_name, "reward.json"))
	if reward_actual:
		save_dict({rowcol_to_junction[key]:value for key, value in reward_value.items()}, os.path.join(dir_name, "reward_actual.json"))




def increasing_players(dir_name, increments=20, reward_actual=False):
	reward_value=None
	player_num = None
	cap_value = None

	reward_mean_cost = None

	rowcol_to_junction = None


	#save_dict({"test":"what"}, os.path.join(dir_name, "reward.json"))

	for i in range(20):

		save_dir = os.path.join(dir_name, f"{i}")
		os.mkdir(save_dir)
		root = GridWin(gui=False, testing='player', save_dir=save_dir)

		if reward_value:  #increasing parameters
			root.reward_list = copy.deepcopy(reward_value)
			root.setting.car_numbers = player_num
			root.reward_mean_cost = copy.deepcopy(reward_mean_cost)
			root.run_sim_no_gui(spread_reward=False)
			player_num += increments


		else:
			root.run_sim_no_gui() #run simultion 50 times with different algorithm
			reward_value = copy.deepcopy(root.global_reward_list)
			reward_mean_cost = copy.deepcopy(root.reward_mean_cost)
			player_num = (root.setting.car_numbers + increments)
			rowcol_to_junction = copy.deepcopy(root.rowcol_to_junction)

		root.on_closing()

	save_dict(reward_value, os.path.join(dir_name, "reward.json"))
	if reward_actual:
		save_dict({rowcol_to_junction[key]:value for key, value in reward_value.items()}, os.path.join(dir_name, "reward_actual.json"))


if __name__ == "__main__":

	parser = argparse.ArgumentParser(description="NSF simulation experiements")
	#parser.add_argument("--option", type=str, default="player", help="define what changes for simulation player / capacity ")#--means optional args no -- means positional
	parser.add_argument("--option", type=str, default="player", help="define what changes for simulation player / capacity / rewardstd")
	args = parser.parse_args()


	dt = datetime.datetime.utcnow().timestamp()
	dir_name = os.path.join(Settings.sim_save_path, str(dt))
	os.mkdir(dir_name)


	logging.basicConfig(filename=os.path.join(dir_name, 'output.log'), filemode='w', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

	if args.option == "player":
		print("increasing players")
		increasing_players(dir_name, reward_actual=True, increments=10)
	elif args.option == "capacity":
		print("increasing capacity")
		increasing_capacity(dir_name, reward_actual=True, increments=20)
	elif args.option == "rewardstd":
		print("increasing sd for reward")
		increasing_random_sd(dir_name)
	elif args.option == "memory":
		print("Increasing memory")
		increasing_memory(dir_name)

	elif args.option =="reward":
		print("increasing reward amount")
		increasing_rewards(dir_name)

	




