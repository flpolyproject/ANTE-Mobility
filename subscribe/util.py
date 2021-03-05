from scipy.stats import truncnorm
import numpy as np
import itertools

from settings import GraphSetting

from concurrent.futures import ThreadPoolExecutor as pool
from concurrent.futures import as_completed
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count

import traci
import traci.constants as tc
from collections import deque
import functools
import time
import logging



class MonteCarloNew(object):
	def __init__(self, winners, amount=100000, chunks=100):

		#traci.start(["sumo-gui", "-c", GraphSetting.sumo_config])
		self.ll, self.ur = traci.gui.getBoundary()
		#print(f"lower left:{self.ll} upper right:{self.ur}")
		self.chunks = chunks
		self.amount = amount
		self.winners = winners
		

	def process_function(self,amount):

		covered = 0

		for i in range(int(amount)):
			x = np.random.uniform(self.ll[0], self.ur[0])
			y = np.random.uniform(self.ll[1], self.ur[1])

			#print(f"random point generated {x}{y}")

			for winner in self.winners:
				d = eu_distance(x, winner.pos_x, y, winner.pos_y)
				if d<=GraphSetting.gia_radius:
					covered += 1
					break

		return covered

	def run(self):
		jobs = [self.amount/self.chunks for x in range(self.chunks)]

		assert np.sum(jobs) == self.amount, f"chunks and total amount doesnt match {int(np.sum(jobs))} != {self.amount}"

		all_results = []
		with ProcessPoolExecutor(max_workers=cpu_count()) as e:
			for result in e.map(self.process_function, jobs):
				all_results.append(result)

		return (np.sum(all_results), self.amount)



class MonteCarlo(pool):
	def __init__(self, boundaries, winners, chunks = 1000):
		super(MonteCarlo, self).__init__(max_workers=6)
		self.boundaries = boundaries #traci .getboundaries
		

		self.llx, self.lly = self.boundaries[0]
		self.urx, self.ury = self.boundaries[1]

		self.ulx, self.uly = (self.llx, self.ury)
		self.lrx, self.lry = (self.urx, self.lly)

		self.winners = winners
		self.que_list = [] #(ulx, uly, lrx, lry)
		self.chunk_size = int((self.urx - self.ulx)/chunks)

		print(f"my boundary is {self.boundaries} chunk_size {self.chunk_size}")


		self.populate_que()

		self.total = 0
		self.covered = 0

		for result in as_completed(self.map(self.process_function, self.que_list)): #results contains future obj
			print(result)
			self.total += result[1]
			self.covered += result[0]

		print("total coverage is ", (self.covered/self.total)*100)

	def process_function(self, element):
		ulx, uly, lrx, lry = element
		covered=0
		total = 0


		for x in np.arange(ulx, lrx):
			for y in np.arange(lry, uly):
				#print(f"processing {x} {y}")
				for winner in self.winners:
					d = eu_distance(x, winner.pos_x, y, winner.pos_y)
					if d<=GraphSetting.gia_radius:
						covered += 1
						break
				total += 1

		print("im done here")

		return (covered, total)


	def populate_que(self):
		for x in np.arange(self.ulx, self.urx, self.chunk_size):
			self.que_list.append((x, self.uly, x+self.chunk_size, self.lry))



		
def timer(func, logging_function=logging.debug):
    """Print the runtime of the decorated function"""
    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):
        start_time = time.perf_counter()  # 1
        value = func(*args, **kwargs)
        end_time = time.perf_counter()  # 2
        run_time = end_time - start_time  # 3
        logging_function(f"TIME FUNCTION {func.__name__!r} in {run_time:.4f} secs")
        return value
    return wrapper_timer



def get_truncated_normal(mean=0, sd=1, low=0, upp=10):
	return truncnorm((low - mean) / sd, (upp - mean) / sd, loc=mean, scale=sd)


def meter_to_miles(meter):
	return meter/1609.34


def mps_to_Mph(mps):
	return ((mps * 3600)/1609.34)

@timer
def generate_speed_bucket(dist, bins_num=6):
	#print(f'speed is {self.speed} distance is {self.distance}, std is {self.std}')
	result =  np.histogram(dist, bins=np.linspace(np.min(dist), np.max(dist), num=bins_num))
	#print(result)
	result = (result[0]/np.sum(result[0]), result[1])
	#result returns tuple of 2, first contains the prob value, second contains the intervals
	#print(result)
	#exit()
	return result


@timer
def generate_speed_distribution(mean, std, upp=200, amount=100, file=None):
	if not file:
		#if no pparse generate with mean as speed limit, std=1 and max speed is 200
		dist = get_truncated_normal(mean=mean,sd=std, upp=upp).rvs(amount)
	else:
		dist = None # none for now when avliable load from another place

	return dist


def to_rad(degree):
	return degree*np.pi/180

def eu_distance(x1,x2,y1,y2):
	return np.sqrt((x1-x2)**2 + (y1-y2)**2)


def iouCircle(r1, r2, distance):
	r = r1
	R = r2
	d = distance
	if(R < r):
	    r = r2
	    R = r1

	if distance !=0:

		p1_angle = to_rad((d*d + r*r - R*R)/(2*d*r))
		p2_angle = to_rad((d*d + R*R - r*r)/(2*d*R))
		p3 = (-d+r+R)*(d+r-R)*(d-r+R)*(d+r+R)


		#print(p1_angle, p2_angle, p3)

		part1 = r*r*np.arccos(p1_angle)
		part2 = R*R*np.arccos(p2_angle)
		part3 = 0.5*np.sqrt(abs(p3))

		intersectionArea = part1 + part2 - part3

		if distance >= (r1+r2):
			intersectionArea  = 0

	else:

		intersectionArea = pow((min(r1, r2)), 2)* np.pi


	union = (np.pi * r1 *r1) + (np.pi*r2*r2) - intersectionArea

	return intersectionArea/union


def average_iou(list_users):


	combs = list(itertools.combinations(list_users, 2))

	player_iou_dict = {}

	iou_list = []

	for comb in combs:
		
		
		
		eu_d = iouCircle(GraphSetting.gia_radius, GraphSetting.gia_radius, eu_distance(comb[0].pos_x, comb[1].pos_x, comb[0].pos_y, comb[1].pos_y))
		iou_list.append(eu_d)

		for item in comb:
			if not item in player_iou_dict:
				player_iou_dict[item] = [eu_d]
			else:
				player_iou_dict[item].append(eu_d)

	key_sum_list = []

	for key, value_list in player_iou_dict.items():
		key_sum_list.append(sum(value_list))

	return np.mean(key_sum_list)




if __name__ == "__main__":
	mc = MonteCarlo(boundaries=[(100,100),(2000,0)], winners=None)


	


		