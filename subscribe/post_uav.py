import os, sys, glob
import plotly.express as px
import plotly.graph_objects as go

from uav import algo_result_multi

import numpy as np
import pandas as pd

from util import *
import traci
import traci.constants as tc
from settings import Settings


dir_path = "./../results/UAV_objects"





class Plot_view(object):
	def __init__(self, uav_objects=None):
		self.uav_objects = self.get_uav_object() if not uav_objects else uav_objects
		

	def line_plot(self, df, x="x", y="y", color=None):
		fig = px.line(df, x=x, y=y, color=color)
		fig.show()

	def get_aiou(self):
		aiou_average ={}
		for key, value in self.uav_objects.algo_result_list.items():
			aiou_average[key] = np.mean(value.aiou)

		return aiou_average



	def get_uav_object(self, path =None, all_files=False): #when all files is true returns all the files in the folder and return a list
		global dir_path
		simulti = algo_result_multi()
		if not path:
			files = glob.glob(os.path.join(dir_path, r"*.uav"))
			sorted_files = sorted(files, key=os.path.getctime)
			if all_files:
				return [simulti.load(x) for x in sorted_files]
			path = sorted_files[0]
			print("path is ", path)
		return simulti.load(path)

	def get_area(self):
		try:
			traci.start(["sumo-gui", "-c", Settings.sumo_config])
		except traci.exceptions.TraCIException:
			pass

		covered_average = {}
		for key, value in self.uav_objects.algo_result_list.items():


			if value.covered:
				covered_average[key] = value.covered
			else:
				_count = 0
				_total = 0
				for winner_list in value.allwinners:
					count, total = MonteCarloNew(winner_list).run()
					_count += count
					_total += total

				value.covered = (_count/_total)*100
				covered_average[key] = (_count/_total)*100
				self.uav_objects.save()

		return covered_average

	def get_active_players(self):
		active_average ={}
		for key, value in self.uav_objects.algo_result_list.items():
			active_average[key] = np.mean(value.len_active)

		return active_average



if __name__ == "__main__":
	my_view = Plot_view()
	all_uav_obj = my_view.get_uav_object(all_files =True)

	df_list = []

	start_budget=10
	for obj in all_uav_obj:
		my_view.uav_objects = obj

		area_value = my_view.get_area()
		print(area_value)

		#print(my_view.get_aiou())



	'''
		


		for key, value in my_view.get_aiou().items():
			df_list.append([start_budget, value, key])
		start_budget += 10
	my_view.line_plot(pd.DataFrame(df_list, columns=["budget", "active players", "algo"]), x="budget", y="active players", color="algo")

	'''


	#print(my_view.get_active_players())
	#print(my_view.get_aiou())
	#print(my_view.get_area())
