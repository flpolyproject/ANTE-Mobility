import os, glob, sys
import json
from settings import GraphSetting

import traci
import numpy as np
import pandas as pd
import math

from traci_env import EnvironmentListener, BaseEnv

layer = 9

poly_id = 0
result_path = "./../results/resultbase"

all_csv = glob.glob(os.path.join(result_path, r"*.csv"))

all_csv.sort(key=os.path.getmtime)

base = all_csv.pop(-1)


color_dict = {}

frames = [pd.read_csv(f, index_col=0) for f in all_csv]
result = pd.concat(frames, ignore_index=True)

#https://kite.com/blog/python/pandas-groupby-count-value-count/


def adjust_dataframe(df, base=False):
	group_count = df.groupby("edge_id").size().reset_index(name="counts")


	min_sub_value = 255
	max_sub_value = 255


	result_norm = group_count.assign(color_norm = group_count["counts"].transform(lambda x: ((max_sub_value - min_sub_value)*((x-x.min())/(x.max()-x.min())))+(min_sub_value)    ))

	if base:
		result_norm_color = result_norm.assign(color_g = 255, color_r = result_norm["color_norm"].transform(lambda x: int(255-x)), color_b=result_norm["color_norm"].transform(lambda x: int(255-x)))
	else:
		result_norm_color = result_norm.assign(color_r = 255, color_g = result_norm["color_norm"].transform(lambda x: int(255-x)), color_b=result_norm["color_norm"].transform(lambda x: int(255-x)))

	return result_norm_color




def get_poly_points(x1 , y1, x2, y2, thickness=5):
	result_points = []



	if (x2-x1) == 0:
		result_points.append((x1+thickness, y1))
		result_points.append((x1- thickness, y1))

		result_points.append((x2-thickness, y2))
		result_points.append((x2+thickness, y2))
		

	elif (y2-y1) == 0: #undefined
		result_points.append((x1, y1+thickness))
		result_points.append((x1, y1-thickness))

		result_points.append((x2, y2-thickness))

		result_points.append((x2, y2+thickness))
		
	else:
		new_slope = -1*((x2-x1)/(y2-y1))

		thickness *= 2

		dx = thickness/(math.sqrt(thickness + (new_slope * new_slope)))
		dy = new_slope * dx


		result_points.append((x1 + dx, y1+ dy))
		result_points.append((x1 - dx, y1- dy))

		result_points.append((x2-dx, y2-dy))


		result_points.append((x2+dx, y2+dy))
		
	return result_points






def change_color(x_row):
	global poly_id, map_data, layer

	road_id = x_row["edge_id"]
	color_value = (x_row["color_r"], x_row["color_g"], x_row["color_b"], 255)
	try:

		edge_obj = map_data.edges[road_id]
		from_junct = map_data.junctions[map_data.edges[road_id]._from]
		to_junct = map_data.junctions[map_data.edges[road_id]._to]


		shape = get_poly_points(from_junct.x, from_junct.y, to_junct.x, to_junct.y)


		traci.polygon.add(f"poi_{poly_id}", shape, color_value, fill=True, layer=layer)

		poly_id += 1

		print(f"success added {poly_id} to road {road_id}")

	except KeyError:
		print(f"failed to add to {road_id}")




result_norm_color = adjust_dataframe(result)

result_norm_base = adjust_dataframe(pd.read_csv(base, index_col=0), base=True)

traci_env_obj = EnvironmentListener(sim_number=0, _seed=None, init=False)
map_data = traci_env_obj.sim_env.map_data

traci.start(["sumo-gui", "-c", GraphSetting.sumo_config])

#result_norm_color.apply(change_color, axis=1)
#layer += 1 
result_norm_base.apply(change_color, axis=1)


