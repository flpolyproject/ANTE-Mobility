#when the car moves its always have be aware of its neighboors, need the broadcast to find the naighboor location


#this map class is handled by the server
#to update user map the server handle requests
from util import *
from xml.dom import minidom
from settings import Settings
import traci
from operator import attrgetter
from concurrent.futures import ProcessPoolExecutor as pool
from multiprocessing import cpu_count
import os
import math
import numpy as np
from graph import Graph
from util import *



class Poi(object):
	def __init__(self, junction, value):
		self.junction = junction
		self.value = value
		self.player_potential = {} #player_id:distance from poi to player_destination #this tells the poi which player is going to it
		self.combinations = {} #combinations for each potential players
		self.other_poi_cost = {} #dynamic programming going towards other pois from this poi. poi_id:distance


class Edge(object):
	def __init__(self, _from, _to, speed, distance, std = 10, grid=False):
		self._from = _from
		self._to = _to
		self._speed = speed
		self._distance = distance
		self.speed = mps_to_Mph(speed)
		self.distance = meter_to_miles(distance)
		self.std = std
		if not grid:
			self.distribution = generate_speed_distribution(self.distance/self.speed, self.std) #nparray
			self.bucket = generate_speed_bucket(self.distribution)
			self.distribution_time = self.distance/self.distribution #nparray



class Junctions(object):
	def __init__(self, coord, junction_id):
		#each junction would contain a utility matrix showing
		self.junction_id = junction_id
		self.coord=coord
		self.adjacent_edges_to = [] #what edges this junction goes to
		self.adjacent_edges_from = [] # what edges goes to this junction
		self.utility = {}
		self.x = self.coord[0]
		self.y = self.coord[1]
		self.number_players = 0
		self.adjacent_junctions = [] # adjacent junctions can be traveled to. can be used to calculate the probability when player in this cell
		self.cost = 5

	def __repr__(self):
		return repr((self.junction_id, self.x,self.y))
		



class Map(object):
	def __init__(self, sumo_cfg, grid=False, simple_grid=False):
		'''
		load global map traci
		'''

		self.grid = grid
		self.simple_grid = simple_grid #gui is for simple maps
		self.sumo_cfg = sumo_cfg
		self.edges = {}
		self.junctions = {}
		self.pois = {} #poi value as key, poi object as object


		if self.grid:
			if not self.simple_grid: #simple grid is for visualization to find ne
				#self.sumo_cfg = Settings.gui_sumo_config
				self.complex_row_col = self.populate_edges_junctions() #this is for grid maps
			else:
				self.complex_row_col = self.row_col()

		else:
			self.parse_map()
		

	@staticmethod
	def mps_to_Mph(mps):
		return ((mps * 3600)/1609.34)
		
	@staticmethod
	def get_distance(x2,y2,x1,y1):
		return math.sqrt((x2 - x1)**2+(y2 - y1)**2)


	def parse_map(self): #new parse map for grid london

		print("parsing map...")
		edge_file = self.sumo_cfg.replace(".sumocfg", ".edg.xml")
		node_file = self.sumo_cfg.replace(".sumocfg", ".nod.xml")

		assert os.path.exists(edge_file) and os.path.exists(node_file), "Check node file and edge file"

		print("parsing edge file..")
		edge_xml = minidom.parse(edge_file)
		print("parsing node file...")
		node_xml = minidom.parse(node_file)

		edge_list = [x for x in edge_xml.getElementsByTagName('edge')]
		junction_list = [x for x in node_xml.getElementsByTagName('node')]

		speed_std_dict = self.get_uber_speed("uberspeed.xml")



		for item in junction_list:
			junct_id = item.attributes['id'].value
			self.junctions[junct_id] = Junctions((float(item.attributes['x'].value), float(item.attributes['y'].value)), item.attributes['id'].value)


		for item in edge_list:
			#self.edges[item.attributes['id'].value] = Edge(item.attributes['from'].value, item.attributes['to'].value, float(item.attributes['speed'].value), self.calculate_distance(item.attributes['from'].value, item.attributes['to'].value))
			self.edges[item.attributes['id'].value] = Edge(item.attributes['from'].value, item.attributes['to'].value, float(speed_std_dict[item.attributes['id'].value][0]), self.calculate_distance(item.attributes['from'].value, item.attributes['to'].value), std=float(speed_std_dict[item.attributes['id'].value][1]), grid=False)
			self.junctions[item.attributes['from'].value].adjacent_edges_to.append(item.attributes['id'].value) #takes edge and append it to adjacent edge list of from node
			self.junctions[item.attributes['to'].value].adjacent_edges_from.append(item.attributes['id'].value)
			self.junctions[item.attributes['from'].value].adjacent_junctions.append(item.attributes['to'].value)

		print(f"PARSE MAP COMPLETED {len(edge_list)} Edges and {len(junction_list)} Junctions")

	def get_uber_speed(self, file):
		speed_std_dict = {} #{id:()}
		speed_xml = minidom.parse(file)
		speed_list = [x for x in speed_xml.getElementsByTagName('edge')]
		for item in speed_list:
			speed_std_dict[item.attributes['id'].value] = tuple((item.attributes["mean"].value, item.attributes["std"].value))

		return speed_std_dict


	def populate_edges_junctions(self): #need this for grid4 still and grid in general


		self.ne_mapping = {}

		row_col_dict = {}
		sumo_xml = minidom.parse(self.sumo_cfg)
		try:
			self.rows = int(sumo_xml.getElementsByTagName('grid-dimension')[0].attributes['rows'].value)
			self.columns = int(sumo_xml.getElementsByTagName('grid-dimension')[0].attributes['cols'].value)

			self.graph_build = Graph(self.rows*self.columns)
		except Exception as e:
			print('parsing row and column failure ', e)
		map_path = sumo_xml.getElementsByTagName('net-file')[0].attributes['value'].value
		map_path = os.path.join(os.path.dirname(self.sumo_cfg), map_path)

		print('map path is ', map_path)

		doc = minidom.parse(map_path)
		edge_list = [x for x in doc.getElementsByTagName('edge') if not ':' in x.attributes['id'].value]
		junction_list = [x for x in doc.getElementsByTagName('junction') if not ':' in x.attributes['id'].value]
		print("parsing nodes... ")
		for i, item in enumerate(junction_list):
			junct_id = item.attributes['id'].value
			self.ne_mapping[i] = junct_id
			self.junctions[junct_id] = Junctions((float(item.attributes['x'].value), float(item.attributes['y'].value)), item.attributes['id'].value)


			#print(junct_id)
			row_col_dict[junct_id] = junct_id[4:]

		self.ne_mapping.update(dict((v, k) for k, v in self.ne_mapping.items()))

		print("parsing edges... ")

		for item in edge_list:
			#print(f"parsing {item}")
			self.edges[item.attributes['id'].value] = Edge(item.attributes['from'].value, item.attributes['to'].value, float(item.childNodes[1].attributes['speed'].value), self.calculate_distance(item.attributes['from'].value, item.attributes['to'].value), grid=True)
			self.junctions[item.attributes['from'].value].adjacent_edges_to.append(item.attributes['id'].value) #takes edge and append it to adjacent edge list of from node
			self.junctions[item.attributes['to'].value].adjacent_edges_from.append(item.attributes['id'].value)
			self.junctions[item.attributes['from'].value].adjacent_junctions.append(item.attributes['to'].value)
			#self.graph_build.addEdge(item.attributes['from'].value, item.attributes['to'].value)
			self.graph_build.addEdge(self.ne_mapping[item.attributes['from'].value], self.ne_mapping[item.attributes['to'].value])

		print("parsing complete")

		return row_col_dict

	def row_col(self):

		self.populate_edges_junctions()

		row = self.rows
		column = self.columns
		row_col_dict = {}
		sorted_junctions = sorted(self.junctions.values(), key= attrgetter('y', 'x'), reverse=True)
		assert len(sorted_junctions) == row*column, f'converting map from sumo failed {len(sorted_junctions)}!={row*column}'
		index = 0
		for i in range(row):
			for j in range(column-1, -1, -1):
				row_col_dict[str(i)+'_'+str(j)] = sorted_junctions[index].junction_id
				index+=1

		return row_col_dict


	def calculate_distance(self, junc_from, junc_to):
		return Map.get_distance(self.junctions[junc_to].x, self.junctions[junc_to].y, self.junctions[junc_from].x, self.junctions[junc_from].y)


	#given edge and dest node find best route, can combine with find best route
	@timer
	def find_route_reroute(self, upcome_edge, destination): #this should be combined with find best route
		shortest_route = None
		#print(self.map_data.junctions)
		for edge in self.junctions[destination].adjacent_edges_from:
			route = traci.simulation.findRoute(upcome_edge, edge)
			if not shortest_route:
				shortest_route = route
			else:
				if route.travelTime<shortest_route.travelTime:
					shortest_route = route

		return shortest_route

	

	#o(n^2) need to loop through all the edges that is connected to the node from and to
	@timer
	def find_best_route(self, start, end, weights=False, ignore_cells = None):
		if start == end:
			return
		weight_dict = {} #if weights is required, populate this dic with path weights
		best_route = None
		for end_edge in self.junctions[end].adjacent_edges_from:

			for start_edge in self.junctions[start].adjacent_edges_to:
				if ignore_cells: # for the deadend adjacenet cells ignore
					if start_edge in ignore_cells:
						continue
				current_route = traci.simulation.findRoute(start_edge, end_edge)

				if not current_route.edges:
					print(f"no route between {start_edge} to {end_edge}")
					continue


				if not best_route:
					best_route = current_route	
				else:
					if current_route.travelTime < best_route.travelTime:
						best_route = current_route

				if weights:
					key_val = self.edges[start_edge]._to
					if key_val in weight_dict:
						weight_dict[key_val] = min(current_route, weight_dict[key_val], key=attrgetter('travelTime'))
					else:
						weight_dict[key_val] = current_route

		if weights:


			return weight_dict, best_route

		return best_route

	def find_adjacent_cells(self, sumo_junction, param='to'):
		adjacent_list = []

		if param == 'to' or param == 'both':
			for edge in self.junctions[sumo_junction].adjacent_edges_to:
				adjacent_list.append(self.edges[edge]._to)

		if param == 'from' or param == 'both':
			for edge in self.junctions[sumo_junction].adjacent_edges_from:
				adjacent_list.append(self.edges[edge]._from)


		return adjacent_list






if __name__ == '__main__':
	pass