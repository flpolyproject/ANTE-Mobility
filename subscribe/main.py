

import os, sys, glob
import traci
import traci.constants as tc
from settings import Settings, GraphSetting
from random import choice
sys.path.append("./../")
from traci_env import EnvironmentListener, BaseEnv, GreedyEnv, RandomEnv
from visualize import Visualize
from postprocess import PostGraph, MultiCaptureGraph
from uav import UAV
import datetime

import logging
import pandas as pd
import copy

import traceback
import sys


def start_simulation(Env, sim_number, gui=False, _seed=None, setting_obj=None, dir_name=None, main_env=None, new_players=False):

	if gui:
		traci.start(["sumo-gui", "-c", Settings.sumo_config])
	else:
		traci.start(["sumo", "-c", Settings.sumo_config])


	
	env = Env(sim_number=sim_number, _seed=_seed, setting_obj=setting_obj, main_env=main_env, new_players=new_players)
	my_vis = Visualize(env)

	while True:

		traci.simulationStep()
		traci.addStepListener(env)
		if gui:
			my_vis.show()  #this is for visualization of the path
		if env.break_condition:
			break


	#env.reward_to_json(os.path.join(dir_name, f"{sim_number}"))

	print("veh succesffuly arrived ", env.sim_env.success_veh)
	traci.close()



	#env.post_process.to_csv()
	return env.post_process, env

	#return env.sim_env


def run(gui=False, number=1, Env=EnvironmentListener, setting_obj=None, file_title=None, dir_name=None, main_env=None, new_players=False):  #handle all the simulations with one simulation parameter
	_seed=3

	post_process = PostGraph(file_title, columns=["sim_number", "sim_step", "veh_id", "edge_id", "speed", "capacity", "budget", "prev_poi", "algo"], dir_name=dir_name)

	#Here is the global multi capture

	multi_cap = MultiCaptureGraph("capture")

	sim_number = 1
	while sim_number <= number:

		try:
			

			temp_process, env = start_simulation(Env, sim_number, gui=gui, _seed=_seed, setting_obj=setting_obj, dir_name=dir_name, main_env=main_env, new_players=new_players)

			post_process.df_list = post_process.df_list + temp_process.df_list
			logging.info(f'SUCCESS FINISHED simulation {sim_number}')

			sim_number+=1

			env.sim_env.post_process_graph.setting = env.sim_env.GraphSetting
			multi_cap.simulation_list.append(env.sim_env.post_process_graph)

			

		except traci.exceptions.TraCIException as e:
			#print("Restarting simulation failed at number ", sim_number, e)
			logging.info(f"Failed simulation {sim_number} {str(e)}")

			traci.close()


	multi_cap.pickle_save(os.path.join(dir_name, f'{file_title}.sim'))
	post_process.to_csv()

	return env


def increase_cap(start, end, inc, dir_name):

	main_env = None


	for i in range(start, end + inc, inc):
		mySetting = GraphSetting()
		mySetting.player_capacity_random = (i, mySetting.player_capacity_random[1])
		gui= False

		
		#run(gui=True, number=3, Env=RandomEnv, setting_obj = mySetting, file_title=f"{mySetting.player_capacity_random[0]}_ATNE", dir_name = dir_name, main_env=main_env)
		#exit()



		if not main_env:
			main_env = run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.player_capacity_random[0]}_BASE", dir_name = dir_name)
		else:
			main_env.GraphSetting = mySetting
			main_env.change_capacity()
			run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.player_capacity_random[0]}_BASE", dir_name = dir_name, main_env=main_env)


		run(gui=gui, number=20, Env=EnvironmentListener, setting_obj = mySetting, file_title=f"{mySetting.player_capacity_random[0]}_ATNE", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=20, Env=GreedyEnv, setting_obj = mySetting, file_title=f"{mySetting.player_capacity_random[0]}_GREEDY", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=20, Env=RandomEnv, setting_obj = mySetting, file_title=f"{mySetting.player_capacity_random[0]}_RANDOM", dir_name = dir_name, main_env=main_env)


	main_env.reward_to_json(dir_name)


def inc_distance_cap(start, end, inc, dir_name):

	main_env = None
	global_poi = None


	for i in range(start, end + inc, inc):
		mySetting = GraphSetting()
		mySetting.distance_capacity = [i, i]
		gui= False

		
		#run(gui=True, number=1, Env=GreedyEnv, setting_obj = mySetting, file_title=f"{mySetting.player_capacity_random[0]}_ATNE", dir_name = dir_name, main_env=main_env)
		#exit()

		if not main_env:
			main_env = run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.distance_capacity[0]}_BASE", dir_name = dir_name)
			global_poi = main_env.global_poi
		else:
			main_env.GraphSetting = mySetting
			main_env.change_distance_capacity()
			run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.distance_capacity[0]}_BASE", dir_name = dir_name, main_env=main_env)
			main_env.global_poi = global_poi


		run(gui=gui, number=5, Env=EnvironmentListener, setting_obj = mySetting, file_title=f"{mySetting.distance_capacity[0]}_ATNE", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=5, Env=GreedyEnv, setting_obj = mySetting, file_title=f"{mySetting.distance_capacity[0]}_GREEDY", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=5, Env=RandomEnv, setting_obj = mySetting, file_title=f"{mySetting.distance_capacity[0]}_RANDOM", dir_name = dir_name, main_env=main_env)


	main_env.reward_to_json(dir_name)


def increase_sp(sp_list, dir_name):

	main_env = None


	for i, value in enumerate(sp_list):
		mySetting = GraphSetting()
		mySetting.sensing_plan_one = value
		gui= False

		
		#run(gui=True, number=1, Env=GreedyEnv, setting_obj = mySetting, file_title=f"{mySetting.player_capacity_random[0]}_ATNE", dir_name = dir_name, main_env=main_env)
		#exit()

		if not main_env:
			main_env = run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.sensing_plan_one}_BASE", dir_name = dir_name)
		else:
			main_env.GraphSetting = mySetting
			run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.sensing_plan_one}_BASE", dir_name = dir_name, main_env=main_env)


		run(gui=gui, number=5, Env=EnvironmentListener, setting_obj = mySetting, file_title=f"{mySetting.sensing_plan_one}_ATNE", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=5, Env=GreedyEnv, setting_obj = mySetting, file_title=f"{mySetting.sensing_plan_one}_GREEDY", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=5, Env=RandomEnv, setting_obj = mySetting, file_title=f"{mySetting.sensing_plan_one}_RANDOM", dir_name = dir_name, main_env=main_env)


	main_env.reward_to_json(dir_name)


def increase_player(start, end, inc, dir_name):

	main_env = None
	global_poi = None

	for i in range(start, end + inc, inc):
		mySetting = GraphSetting()
		mySetting.car_numbers = i
		gui= False

	


		if not main_env:
			main_env = run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.car_numbers}_BASE", dir_name = dir_name, main_env=main_env)
			global_poi = main_env.global_poi
		else:
			main_env.GraphSetting = mySetting
			main_env = run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.car_numbers}_BASE", dir_name = dir_name, main_env=main_env, new_players=True)
			main_env.global_poi = global_poi

		#run(gui=gui, number=3, Env=RandomEnv, setting_obj = mySetting, file_title=f"{mySetting.car_numbers}_RANDOM", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=1, Env=EnvironmentListener, setting_obj = mySetting, file_title=f"{mySetting.car_numbers}_ATNE", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=1, Env=GreedyEnv, setting_obj = mySetting, file_title=f"{mySetting.car_numbers}_GREEDY", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=1, Env=RandomEnv, setting_obj = mySetting, file_title=f"{mySetting.car_numbers}_RANDOM", dir_name = dir_name, main_env=main_env)


	main_env.reward_to_json(dir_name)

def inc_random_theta(start, end, inc, dir_name):

	main_env = None

	for i in range(start, end + inc, inc):
		mySetting = GraphSetting()
		mySetting.theta_random = i
		gui= False

		
		#run(gui=True, number=1, Env=GreedyEnv, setting_obj = mySetting, file_title=f"{mySetting.player_capacity_random[0]}_ATNE", dir_name = dir_name, main_env=main_env)
		#exit()

		if not main_env:
			main_env = run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.theta_random}_BASE", dir_name = dir_name)
		else:
			main_env.GraphSetting = mySetting
			run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.theta_random}_BASE", dir_name = dir_name, main_env=main_env)


		run(gui=gui, number=5, Env=RandomEnv, setting_obj = mySetting, file_title=f"{mySetting.theta_random}_RANDOM", dir_name = dir_name, main_env=main_env)


	main_env.reward_to_json(dir_name)


def inc_poi_radius(start, end, inc, dir_name):
	main_env = None
	global_poi = None

	for i in range(start, end + inc, inc):
		mySetting = GraphSetting()
		mySetting.poi_radius = i
		gui= False

		

		if not main_env:
			main_env = run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.poi_radius}_BASE", dir_name = dir_name, main_env=main_env)
			global_poi = main_env.global_poi
		else:
			main_env.GraphSetting = mySetting
			run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.poi_radius}_BASE", dir_name = dir_name, main_env=main_env)
			main_env.global_poi = global_poi


		run(gui=gui, number=3, Env=EnvironmentListener, setting_obj = mySetting, file_title=f"{mySetting.poi_radius}_ATNE", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=3, Env=GreedyEnv, setting_obj = mySetting, file_title=f"{mySetting.poi_radius}_GREEDY", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=3, Env=RandomEnv, setting_obj = mySetting, file_title=f"{mySetting.poi_radius}_RANDOM", dir_name = dir_name, main_env=main_env)


def inc_buffer_interval(start, end, inc, dir_name):
	main_env = None
	global_poi = None


	for i in range(start, end + inc, inc):
		mySetting = GraphSetting()
		mySetting.buffer_interval = i
		mySetting.poi_radius = i
		gui= False

		
		#run(gui=True, number=1, Env=GreedyEnv, setting_obj = mySetting, file_title=f"{mySetting.player_capacity_random[0]}_ATNE", dir_name = dir_name, main_env=main_env)
		#exit()

		if not main_env:
			main_env = run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.buffer_interval}_BASE", dir_name = dir_name)
			global_poi = main_env.global_poi
		else:
			main_env.GraphSetting = mySetting
			run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.buffer_interval}_BASE", dir_name = dir_name, main_env=main_env)
			main_env.global_poi = global_poi


		run(gui=gui, number=5, Env=EnvironmentListener, setting_obj = mySetting, file_title=f"{mySetting.buffer_interval}_ATNE", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=5, Env=GreedyEnv, setting_obj = mySetting, file_title=f"{mySetting.buffer_interval}_GREEDY", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=5, Env=RandomEnv, setting_obj = mySetting, file_title=f"{mySetting.buffer_interval}_RANDOM", dir_name = dir_name, main_env=main_env)


def inc_buffer_poi(start, end, inc, dir_name):
	main_env = None
	global_poi = None
	for i in range(start, end + inc, inc):
		mySetting = GraphSetting()
		mySetting.buffer_interval = i
		gui= False

		

		if not main_env:
			main_env = run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.buffer_interval}_BASE", dir_name = dir_name, main_env=main_env)
		else:
			main_env.GraphSetting = mySetting
			main_env = run(gui=gui, number=1, Env=BaseEnv, setting_obj = mySetting, file_title=f"{mySetting.buffer_interval}_BASE", dir_name = dir_name, main_env=main_env)

		run(gui=gui, number=3, Env=EnvironmentListener, setting_obj = mySetting, file_title=f"{mySetting.buffer_interval}_ATNE", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=3, Env=GreedyEnv, setting_obj = mySetting, file_title=f"{mySetting.buffer_interval}_GREEDY", dir_name = dir_name, main_env=main_env)
		run(gui=gui, number=3, Env=RandomEnv, setting_obj = mySetting, file_title=f"{mySetting.buffer_interval}_RANDOM", dir_name = dir_name, main_env=main_env)




if __name__ == '__main__':
	print(traci.__file__)


	dt = datetime.datetime.utcnow().timestamp()
	dir_name = os.path.join(Settings.sim_save_path_graph, str(dt))
	os.mkdir(dir_name)

	print("making dir ", dir_name)


	logging.basicConfig(filename=os.path.join(dir_name, 'output.log'), filemode='w', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

	increase_cap(70, 90, 20, dir_name)
	#inc_distance_cap(1, 11, 2, dir_name)

	#increase_player(10, 300, 10, dir_name)
	#increase_sp([1, 5, 10, 30, 70, 100, 200], dir_name)
	#inc_random_theta(10, 290, 50, dir_name)
	#inc_poi_radius(10, 110, 20, dir_name)
	#inc_buffer_interval(10, 110, 20, dir_name)

	#inc_buffer_poi(10, 110, 20, dir_name)


	
