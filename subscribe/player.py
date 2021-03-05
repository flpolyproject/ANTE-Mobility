from collections import defaultdict


class Player(object):
	def __init__(self, veh_id, routes, passed_junction, dest_junc, target_poi=None):


		#constants
		self.veh_id = veh_id

		#not constants
		self.routes = routes
		self.index = veh_id.split('_')[1]
		self.start = routes[0]
		self.dest_junc = dest_junc
		self.destination = routes[-1]
		self.current_edge = routes[0]
		self.capacity = 100
		self.prev_junction = passed_junction
		self.prev_poi = None  #keep track of veh enter and leaving junction
		self.prev_poi_junct = None
		self.reward = 0
		self.target_poi = target_poi #the poi that the veicle is currently going towards
		self.current_poi_distribution = {} #distribution buckets to every poi, {"poi_key":np.histogram}
		self.temp_edges = {} #edges to every poi
		self.participation = True
		self.combinations = defaultdict(list) #this contains all the combinations that contains this player
		self.distance_capacity = None
		self.poi_potential = {} #populate the potential pois at assignment so combinations can be generated based on this
		
		#self.player_poi_cost = None #cost map to every poi location
		self.poi_to_destination = {}  #this contains distance from every poi to destination for the player

		self.poi_distance_temp = {} #store distance to every poi regardless of within distance capacity, #poi as key showing weight for each poi updated in generate bucket
		
		self.past_recent_nodes = [] #short term memory, in terms of grid junction

		self.goinghome=False #determine if the veh should be going towards destination



		#track of what poi and how many players the sp is calculate for


		#grid post proessing stuff
		self.node_hit = [] #for post processing keep track of all the nodes its been through
		self.collected_sp_list = []  #for calculated real coverage and not ru #store as poi key, the poi key the player is collected from
		self.visited_sp_list = [] # the poi key where the player visited


		self.expecting_to_collect = False
		self.random_steps = 0
		self.expected_collection_steps = 0
		self.actual_collection_steps = 0

		self.true_negative = 0 #expected to collect, but didnt collect
		self.false_positive = 0 # didnt expect to collect, but collected
		self.true_positive = 0 #expected to collect and collected
		self.false_negative = 0 #didnt expect to collect and didnt collect

		self.base_travel_time = None

		self.pois_visited = {}
		


		
	def modify(self, routes):
		#this for when updating players
		self.routes = routes
		self.current_edge = routes[0]

		
class GridPlayer(object):
	def __init__(self, id_value, start, destination):
		self.id_value = id_value
		self.node_hit = [] #for post processing keep track of all the nodes its been through
		self.collected_sp_list = []  #for calculated real coverage and not ru
		self.visited_sp_list = []
		self.reward_hit = [] # for post processing keep track of the capacity at each node
		self.node_index = 0
		self.shortest_path_length = None #stores the node in player shortest path all in terms of sumo junctions, not grid
		self.start = start
		self.destination = destination
		self.path = None
		self.node_path = None 
		self.capacity = 100
		self.reward=0
		self.past_recent_nodes = [] #short term memory, in terms of grid junction
		self.participation = False
		self.all_path = None
		self.temp_random_cost = None
		self.cost_mean = None
		self.cost_sd = None
		self.temp_sensing_plan = None
		self.predicted_sensing_plan = None

		self.shortest_path = False
		self.current_location = None


		self.expecting_to_collect = False
		self.random_steps = 0
		self.expected_collection_steps = 0
		self.actual_collection_steps = 0

		self.true_negative = 0 #expected to collect, but didnt collect
		self.false_positive = 0 # didnt expect to collect, but collected
		self.true_positive = 0 #expected to collect and collected
		self.false_negative = 0 #didnt expect to collect and didnt collect

		

	def get_next(self):
		#print(self.node_path, self.node_index)
		value= self.node_path[self.node_index]
		self.node_index+=1
		return value


	def __repr__(self):
		#return repr((self.start, self.destination, self.node_hit, self.reward_hit))
		return repr(self.id_value)


