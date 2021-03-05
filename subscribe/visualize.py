import traci
import traci.constants as tc
import math
from settings import GraphSetting

import numpy as np
from util import *

class Visualize(object):
	def __init__(self, step_object):
		self.step_object = step_object
		#self.define_background((144,238,144))
		self.deleted_number = 0
		self.prev_winner_poly = []

		try:
			traci.gui.setSchema(traci.gui.DEFAULT_VIEW, schemeName = "real world")
			self.default_zoom = traci.gui.getZoom()
			self.current_zoom = self.default_zoom
			self.none_tick = 0
			self.draw_poi()
		except Exception as e:
			pass
		
	def circle(self, point, radius, color, fine=250):
		x, y=point
		polyid = f"poly_{len(traci.polygon.getIDList())+1+self.deleted_number}"
		angle = 360/fine
		shape = []
		for i in np.arange(0, 360+angle, angle):
			rad = (i * math.pi)/180
			temp_point = (radius*math.cos(rad) + x, radius*math.sin(rad) + y)
			shape.append(temp_point)

		traci.polygon.add(polyid, shape, color, fill=False, layer=9)
		return polyid


	def polygon(self, point, color, size):
		x,y = point
		polyid = f"poly_{len(traci.polygon.getIDList())+1+self.deleted_number}"
		#print("making polygon ", polyid)
		shape = [(x-size, y-size),(x-size, y+size),(x+size, y+size),(x+size, y-size)]
		traci.polygon.add(polyid, shape, color, fill=True, layer=9)

	def show_trace(self):
		data = self.step_object.sim_env.veh_data
		if data:
			for veh_id, veh_value in data.items():
				#print(f"{veh_id} position is {veh_value[tc.VAR_POSITION]}")
				self.polygon(veh_value[tc.VAR_POSITION], (249,56,34), 5)
		



		if self.step_object.sim_env.track_veh:
			self.none_tick = 0
			print("Currently Tracking ", self.step_object.sim_env.track_veh)
			try:
				traci.gui.trackVehicle(traci.gui.DEFAULT_VIEW, self.step_object.sim_env.track_veh)
			except Exception as e:
				self.step_object.sim_env.track_veh = None

			traci.gui.setZoom(traci.gui.DEFAULT_VIEW,1440)
		else:
			self.none_tick +=1

			#if self.none_tick == 50: #this is for when view zooms out 
			#	traci.gui.setZoom(traci.gui.DEFAULT_VIEW, self.default_zoom)


	def show(self):
		self.show_trace()
		#self.show_winners()

	def draw_poi(self):
		for poi_key, poi_obj in self.step_object.sim_env.map_data.pois.items():
			self.polygon(traci.junction.getPosition(poi_obj.junction), (255,0,255,255), 30)



	def show_winners(self):
		for algo in self.step_object.algo_list:

			if algo.winners:
				for item in algo.prev_winner_poly:
					traci.polygon.remove(item)
					self.deleted_number += 1
				algo.prev_winner_poly=[]
				for winner in algo.winners:
					if algo.name == "gia":
						id_value = self.circle((winner.pos_x, winner.pos_y), GraphSetting.gia_radius, color=(255,0,0,255))
					else:
						id_value = self.circle((winner.pos_x, winner.pos_y), GraphSetting.gia_radius, color=(0,0,255,255))

					algo.prev_winner_poly.append(id_value)
				#mc = MonteCarlo(traci.gui.getBoundary(), algo.winners)



			





	def define_background(self, color):
		ll,ur = traci.gui.getBoundary() #return lower left and upper right coords

		llx, lly = ll
		urx, ury = ur

		ulx, uly = (llx, ury)
		lrx, lry = (urx, lly)

		polyid = f"poly_{len(traci.polygon.getIDList())+1}"
		shape = [(ulx, uly),(llx, lly),(lrx, lry),(urx, ury)]
		traci.polygon.add(polyid, shape, color, fill=True, layer=1)




		

