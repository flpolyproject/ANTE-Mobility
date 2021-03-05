from concurrent.futures import ProcessPoolExecutor as pool
from multiprocessing import Queue, cpu_count
import traci
import os, sys, glob
from settings import Settings
from functools import partial
from itertools import cycle




class MyPool(object):
	def __init__(self, instance_num =5):
		self.instance_num = instance_num
		self.glob_pool = pool(cpu_count())
		self.avalible_instance = cycle([x for x in range(instance_num)])
		self.start_traci()
	def start_traci(self): #run this early
		self.glob_pool.map(lambda: traci.start(["sumo", "-c", Settings.sumo_config], label=str(value)), [x for x in range(self.instance_num)])
		print("started traci sim process ")
		

	def manager_func(self, work_list):
		pass


		'''
		next_instance = self.avalible_instance.get()
		result = self.map(partial(slave_func, instance_value = next_instance), work_list)
		self.avalible_instance.put(next_instance)

		print(list(result))

		return result
		'''



	