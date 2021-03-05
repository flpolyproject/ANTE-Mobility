import glob, os, sys
import pandas as pd
import numpy as np
import json
#this is for the generating vis for graph map
#https://www.shanelynn.ie/select-pandas-dataframe-rows-and-columns-using-iloc-loc-and-ix/
#this generate the vehicle traces for graph version of ATNE


from traci_env import EnvironmentListener
from settings import Settings, GraphSetting
import traci
import traci.constants as tc


mySetting = GraphSetting()


def to_json_traces(cap_number, sim_number, path):
	traci.start(["sumo", "-c", Settings.sumo_config])

	env = EnvironmentListener(sim_number=1, _seed=3, setting_obj=mySetting, main_env=None, init=False)


	files = glob.glob(os.path.join(path, r"*.csv"))
	print("Found total files ", len(files))

	json_output = os.path.join(path, "json_output")
	try:
		os.mkdir(json_output)
	except Exception as e:
		print("Folder already exist")



	files_base = [process_per_file(pd.read_csv(x, index_col="sim_number").loc[[sim_number], :], os.path.join(json_output, os.path.basename(x).replace(".csv", ".json")), env.sim_env.map_data) for x in files if int(os.path.basename(x).split("_")[0]) == cap_number]

	#print(files_base)


def process_per_file(pd_df, json_output_file, env_map):

	new_df = pd_df.groupby('veh_id')['edge_id'].apply(list).reset_index(name="edge_id")

	new_df["veh_id"] = new_df["veh_id"].str.extract(r'(\d+)')
	
	result = dict(zip(new_df["veh_id"], new_df["edge_id"]))


	for key, value in result.items():
		result[key] = list(set([x for x in value]))
		#print(value)

	

	print("saving file ", json_output_file)

	with open(json_output_file, "w") as f:
		json.dump(result, f)



def test(filn):
	print(filn)
	

def main():
	file_path = os.path.join(mySetting.sim_save_path_graph,"fiftest")
	to_json_traces(150, 1, file_path)

if __name__ == "__main__":
	main()