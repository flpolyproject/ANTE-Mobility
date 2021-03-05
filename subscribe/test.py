import numpy as np
import os,glob, sys

def entropy_calculation(prob_arry):
	return sum([x*np.log(1/x) for x in prob_arry])

def tempo_coverage(poi_dict):
	prob_dist_dict = {key:entropy_calculation(np.diff(value_list)/np.sum(np.diff(value_list))) for key, value_list in poi_dict.items()}

	print(prob_dist_dict)


temp_dict = {"poi1":[0, 2, 4,6,8], "poi3":[0, 2, 4,6, 8, 10, 12, 14], "poi4":[x*2 for x in range(10000000)]}

tempo_coverage(temp_dict)

