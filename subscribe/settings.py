import os,sys,glob
import json
sys.path.append("./../GIA")
from GIA import *

class Settings(object):

	#reward list didnt reset after 
	TEST=True
	base_default = os.path.abspath('./')

	default = os.path.abspath('./maps') #default is E:\Python\sumo-windows10\projects
	#sumo_config = os.path.join(default, "grid4/data/grid4.sumocfg")

	#sumo_config = os.path.join(default, "london-seg4/data/london-seg4.sumocfg")
	sumo_config = os.path.join(default, "grid_speed_dist/100/london-seg4.100.sumocfg")

	#sumo_config = os.path.join(default, "grid4/data/grid4.sumocfg")

	sim_save_path = os.path.join(base_default, "subscribe/simulations")
	sim_save_path_graph = os.path.join(base_default, "results")
	sim_save = os.path.join(default, "subscribe/simulations/recent.sim")
	plot_path = os.path.join(default, "subscribe/simulations/plots")

	def __init__(self):

		#test params for getting result from simulation

		if self.TEST:
			self.car_numbers = 200 #set the random amount to spawn when no prev defined cars
			self.simulation_delay = 0 #delay for visualization, 0 runs fast
			self.game_theory_algorithm = ['gta']
			#self.game_theory_algorithm = ['gta', 'greedy','random', 'base'] #gta, greedy, base, random
			#self.game_theory_algorithm = ["greedy", "random"]
			#self.game_theory_algorithm = ['base']
			self.destination = '0_2' #'random' #set to 0 row and 0 column, can be set to 'random'
			self.theta_random = 200000  #used in softmax to determine prob, higher this value the less random it is
			self.simulation_steps = 10 #how many times to repeat simulation

			self.player_capacity_random = (30, 5) #mean,std for capacity
			self.reward_value_random = (50, 10) #mean, std for reward
			
			
			self.reward_amount = 400
			self.reward_position_std = 10

			self.percent_reward_dist = None #can choose percentage of total cells in the cluster that will contain reward

			self.max_memory_size = 3 #3 conseqtive. how many max nodes store in player memory, these cells are not in the reward consideration list
			#thus when cells is NONE resort to weighted random which uses the gloabal cov cells to determine which weight to choose
			#uniform distribtuion

			self.current_algo_index = 0 #track current algorithm thats running
			self.player_cost_sd = 1
			self.reward_mean_cost = [20, 20]
			'''
			self.car_numbers = 200 #set the random amount to spawn when no prev defined cars
			self.simulation_delay = 0 #delay for visualization, 0 runs fast
			self.game_theory_algorithm = ['random', 'base'] #gta, greedy, base, random
			#self.game_theory_algorithm = ["greedy", "random"]
			#self.game_theory_algorithm = ['base']
			self.destination = '0_2' #'random' #set to 0 row and 0 column, can be set to 'random'
			self.theta_random = 8000  #used in softmax to determine prob, higher this value the less random it is
			self.simulation_steps = 50 #how many times to repeat simulation

			self.player_capacity_random = (70, 1) #mean,std for capacity
			self.reward_value_random = (50, 1) #mean, std for reward
			
			
			self.reward_amount = 400
			self.reward_position_std = 10

			self.percent_reward_dist = None #can choose percentage of total cells in the cluster that will contain reward

			self.max_memory_size = 3 #3 conseqtive. how many max nodes store in player memory, these cells are not in the reward consideration list
			#thus when cells is NONE resort to weighted random which uses the gloabal cov cells to determine which weight to choose
			#uniform distribtuion

			self.current_algo_index = 0 #track current algorithm thats running
			self.player_cost_sd = 1
			self.reward_mean_cost = [2, 5]
			'''
		else:

			self.car_numbers = 10  #set the random amount to spawn when no prev defined cars
			self.simulation_delay = 0 #delay for visualization, 0 runs fast
			self.game_theory_algorithm = ['gta', 'greedy','random', 'base'] #gta, greedy, base, random
			#self.game_theory_algorithm = ["gta", "base"]
			#self.game_theory_algorithm = ["greedy", "random"]
			self.destination = '0_2' #'random' #set to 0 row and 0 column, can be set to 'random'
			self.theta_random = 8000  #used in softmax to determine prob, higher this value the less random it is
			self.simulation_steps = 1 #how many times to repeat simulation

			self.player_capacity_random = (50, 5) #mean,std for capacity 170 capacity
			self.reward_value_random = (40, 10) #mean, std for reward
			
			
			self.reward_amount = 200
			self.reward_position_std = 10

			self.percent_reward_dist = None #can choose percentage of total cells in the cluster that will contain reward

			self.max_memory_size = 3 #3 conseqtive. how many max nodes store in player memory, these cells are not in the reward consideration list
			#thus when cells is NONE resort to weighted random which uses the gloabal cov cells to determine which weight to choose


			self.current_algo_index = 0 #track current algorithm thats running
			self.player_cost_sd = 1

			self.reward_mean_cost = [2, 5]

#minimize repeating nodes

class GraphSetting(Settings):
	def __init__(self):

		self.car_numbers = 150 #150
		self.reward_numbers= 20 #poi change
		#destination='5761000259' #london
		#destination = "gneJ49" #grid4
		#destination = "random"#"cell0_2"

		self.theta_random = 120 #200
		self.destination='cell0_2'
		self.distance_capacity = [7,7]#he limit the player can travel within the. 2 to 3 times the cost from start to end 
		#this multipliar can be determined based on how far the veh is to their destination. the rate of reduction is changed as veh is approaching their destination
		#this gas capacity takes priority over the utility and sensing plan, means if we have capacity left the vehicle still wont collect

		self.player_reward_random = (1000, 5)
		self.player_capacity_random = (40, 5)
		self.buffer_interval = 30 #50 #every few simulation steps checks for stopped vehicles at the poi radius that needs to be assigned 
		self.poi_radius = 30 #50
		self.gia_radius = 20

		self.max_memory_size = 2

		self.chance_to_dest = 0.1


		self.poi_limit = 0 #the most number times a poi can be visited 0 means it can visit infinite times. usually 0 

		self.poi_consider = 1 #percentage of total poi to consider for weighted random
		
		self.sensing_plan_one = 1 #30 before

		self.none_repeat_poi = False #if true then no poi can be repeated usually False

		self.current_running_algo = None








if __name__ == "__main__":
	pass

