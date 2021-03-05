import numpy as np
import matplotlib.pyplot as plt
#import seaborn
import json
from operator import attrgetter
import pickle
import os, glob
from settings import Settings
import pandas as pd
from scipy import stats
from itertools import combinations
import numpy as np
import datetime

import traci
import random
import math
import argparse
import matplotlib

from collections import defaultdict





import seaborn as sns;

#the esp can be computed using old sensing plan formula

#matplotlib.rcParams.update({'errorbar.capsize': 2})



# Set the font to be serif, rather than sans


sns.set(font='serif', rc={'figure.figsize':(20,8.27)})

sns.set_context("paper")

# Make the background white, and specify the
# specific font family
sns.set_style("white", {
    "font.family": "serif",
    "font.serif": ["Times", "Palatino", "serif"]
})

sns.set_style("ticks", {"xtick.major.size": 8, "ytick.major.size": 8})


def entropy_calculation(prob_arry):
    return sum([x*np.log(1/x) for x in prob_arry])

    


class PostGraph(object):
    def __init__(self, sim_number, columns = ["sim_number", "sim_step", "veh_id", "edge_id", "speed"], dir_name=None):
        self.df_list = []
        self.columns = columns
        self.sim_number = sim_number
        self.dir_name = dir_name

    def append_row(self, row_value):
        self.df_list.append(row_value)

    def to_df(self):
        return pd.DataFrame(self.df_list, columns=self.columns)

    def to_csv(self):
        results = self.to_df()
        filename = os.path.join(self.dir_name, f"{self.sim_number}.csv") #dir name already contains the full path
        print(f"file saving to: {filename}")
        results.to_csv(filename, chunksize=1000)
        print(f"file saved complete to {filename}")



class PostGraphGrid(object):
    def __init__(self, sim_number, columns = ["sim_number", "sim_step", "veh_id", "edge_id", "speed", "grid_id"]):
        self.df_list = []
        self.columns = columns
        self.sim_number = sim_number
    def append_row(self, row_value):
        self.df_list.append(row_value)

    def to_csv(self, path):
        filename = os.path.join(path, f"{self.sim_number}.csv")
        print(f"file saving to: {filename}")
        pd.DataFrame(self.df_list, columns=self.columns).to_csv(filename, chunksize=1000)
        print(f"file saved complete to {filename}")


class T_test(object):

    def __init__(self, data1, data2):
        self.data1 = data1
        self.data2 = data2
        self.t_value, self.p_value = stats.ttest_ind(data1, data2, equal_var=True)
        self.get_cl()
    def __repr__(self):
        return f"{self.p_value}"

    def __str__(self):
        return f"T:{self.t_value} P:{self.p_value} mean: {(np.mean(self.data1), np.mean(self.data2))} sd:{(np.std(self.data1), np.std(self.data2))} cl: {self.MoE} dm:{self.diff_mean} interval: {self.interval}"

    def get_cl(self):
        self.diff_mean = abs(np.mean(self.data1) - np.mean(self.data2))
        self.df = len(self.data1) + len(self.data2) - 2
        t_val = stats.t.ppf([0.975], self.df) # this is for 95% cl
        std_avg = np.sqrt(((len(self.data1) - 1)*(np.std(self.data1))**2 + (len(self.data2) - 1)*(np.std(self.data2))**2) / self.df)
        last_comp = np.sqrt(1/len(self.data1) + 1/len(self.data2))
        self.MoE = abs(t_val *std_avg * last_comp) #margin of error this is +- from diff mean to get range of 95% conf interval
        self.interval = [self.diff_mean - self.MoE, self.diff_mean + self.MoE]



class DataCapture(object): #object per simulation
    def __init__(self, map_junctions, rowcol_to_junction):
        self.simulation_steps = 0
        self.player_list = [] #player node hit is inters of row column grid
        self.map_junctions = map_junctions #number of junctions
        self.reward_list = [] #interms of sumo junctions as key the rewards for that simulation
        self.rowcol_to_junction = rowcol_to_junction #conversion from grid to junctions
        self.reward_junction_ratio = None #ratio of total number of reward cells over total junctions
        self.setting=None
        self.sim_player_list = None


    def get_all_cells_visited(self, repeat=False, reward=False, total=False):
        player_coverage_list = []

        reward_total_list = [] #total number of reward visited unique
        
        player_avg_reward = []
        for player in self.player_list:
            cells_that_are_reward = []

            player_coverage_list.append(player.start)
            if self.rowcol_to_junction[player.start] in self.reward_list:
                cells_that_are_reward.append(player.start)
                reward_total_list.append(player.start)
            for node in player.node_hit:
                player_coverage_list.append(node)
                if self.rowcol_to_junction[node] in self.reward_list:
                    cells_that_are_reward.append(node)
                    reward_total_list.append(node)

            player_avg_reward.append(len(set(cells_that_are_reward)))
        if repeat:
            return player_coverage_list
        if reward:
            if not total:
                return np.mean(player_avg_reward)
            else:
                return len(set(reward_total_list))


        return set(player_coverage_list)
        

    #{node:{hit:#, players:[]}}
    def calculate_coverage(self, repeat=False): #road utilization amount of cells visited over all cells
        return (len(self.get_all_cells_visited(repeat))/self.map_junctions)*100

    def calculate_test_coverage(self): #actually coverage amount rewarded cells visited over total reward cells
        reward_cell_visited = []
        reward_hit_number = 0

        #collected_sp_list need to contain node interms of grid

        for player in self.player_list:
            #print(f'player len node are {player.node_hit}')
            for node in player.collected_sp_list:
                if (node in self.reward_list) and (node not in reward_cell_visited):
                    reward_hit_number +=1
                    reward_cell_visited.append(node)
        print(f'coverage cells hit:{reward_hit_number}, total rewards cells:{len(self.reward_list)}')
        return (reward_hit_number/len(self.reward_list))*100


    def calculate_test_coverage_temp(self): #actually coverage amount rewarded cells visited over total reward cells
        reward_cell_visited = []
        reward_hit_number = 0

        #collected_sp_list need to contain node interms of grid

        for player in self.player_list:
            #print(f'player len node are {player.node_hit}')
            for node in player.collected_sp_list:
                if (node in self.reward_list):
                    reward_hit_number +=1
        #print(f'coverage cells hit:{reward_hit_number}, total rewards cells:{len(self.reward_list)}')
        return (reward_hit_number/len(self.reward_list))*100

    def get_average_results(self):
        total_tp = np.mean([x.true_positive for x in self.player_list])
        total_tn = np.mean([x.true_negative for x in self.player_list])
        total_fp = np.mean([x.false_positive for x in self.player_list])
        total_fn = np.mean([x.false_negative for x in self.player_list])

        avg_random_steps = np.mean([x.random_steps for x in self.player_list])
        avg_exp_steps = np.mean([x.expected_collection_steps for x in self.player_list])
        avg_actual_steps = np.mean([x.actual_collection_steps for x in self.player_list])


        tp_over_ecs = np.mean([(x.true_positive/(x.expected_collection_steps)) if x.expected_collection_steps != 0 else 0 for x in self.player_list])


        return [total_tp, total_tn, total_fp, total_fn, avg_random_steps, avg_exp_steps, avg_actual_steps, tp_over_ecs]

    def get_coverage_over_reward(self):
        shortest_path_cells = []
        for player in self.player_list:
            shortest_path_cells += player.shortest_path_length
        shortest_path_cells = set(shortest_path_cells)

        return ((len(self.get_all_cells_visited(False)) - len(shortest_path_cells)) / self.map_junctions) * 100

    def get_player_steps(self):
        return np.mean([len(x.node_hit) for x in self.player_list])

    def get_player_utilization(self):
        return (np.mean([len(set(x.node_hit)) for x in self.player_list]) / self.map_junctions) * 100


    def get_player_coverage(self):
        return (np.mean([len(set(x.collected_sp_list)) for x in self.player_list]) / len(self.reward_list)) * 100






class MultiCapture(object): #object for multiple simulations
    def __init__(self, title):
        self.simulation_list = []
        self.title=title
        self.simulation_conv_list = []
        self.simulation_test_coverage = []



    def pickle_save(self, save_path):
        with open(save_path, 'wb') as config_dictionary_file:
            pickle.dump(self, config_dictionary_file)
        print('simulation saved success...')

    def pickle_load(self, save_path, directory=False, json_format=False):


        if directory:
            if json_format:
                store_location = os.path.join(save_path, "json_out")
                if not os.path.exists(store_location):
                    os.mkdir(store_location)
                    print("created new folder ", store_location)

                files = glob.glob(os.path.join(save_path, r'*.sim'))
                print(f"total number of files ", len(files))
                for file in files:
                    with open(file, 'rb') as config_dictionary_file:
                        value = pickle.load(config_dictionary_file)
                        player_trace = {}
                        for i, player in enumerate(value.simulation_list[0].player_list):
                            player_trace[i] = player.node_hit
                        json_file = os.path.basename(file).split('.')[0]+'.json'
                        json_file = os.path.join(store_location, json_file)
                        print(f'json path is {json_file}')
                        with open(json_file, 'w') as json_write:
                            json.dump(player_trace, json_write)

                return
            else:
                save_path = self.find_recent_sim(save_path)

        #print('Loading from existing file... ', save_path)

        with open(save_path, 'rb') as config_dictionary_file:
            value = pickle.load(config_dictionary_file)
            return value
            
    def average_reward(self, box_plot=False, avg_player=False):
        total_reward = []
        for sim in self.simulation_list:
            sim_reward = []
            for player in sim.player_list:
                sim_reward.append(player.reward)
            total_reward.append(sum(sim_reward)/len(sim_reward))

        if box_plot:
            return total_reward
        return sum(total_reward)/len(total_reward)

        

    def average(self, box_plot=False, avg_player=False): #average for road util
        total = 0
        for value in self.simulation_conv_list:
            total+=value

        if box_plot:
            return self.simulation_conv_list
        return total/len(self.simulation_conv_list)

    def average_coverage(self, box_plot =False, avg_player=False):
        total = 0
        for value in self.simulation_test_coverage:
            total += value
        if box_plot:
            return self.simulation_test_coverage
        return total/len(self.simulation_test_coverage)


    def find_recent_sim(self, folder):
        file_list = glob.glob(os.path.join(folder, r'*.sim'))
        return max(file_list, key=os.path.getctime)


    def find_all_cov_cells(self,_iter =False):
        new_cov_test = []
        for sim in self.simulation_list:
            new_cov_test.append(sim.calculate_test_coverage_temp())

        if _iter:
            return new_cov_test
        return np.mean(new_cov_test)

    def find_all_util_cells(self):
        new_cov_test = []
        for sim in self.simulation_list:
            new_cov_test.append(sim.calculate_coverage(repeat=True))

        return np.mean(new_cov_test)
    def average_util_over_base(self, box_plot=False, avg_player=False):
        value_list = []
        for sim in self.simulation_list:
            value_list.append(sim.get_coverage_over_reward())

        if box_plot:
            return value_list
        return np.mean(value_list)

    def get_reward_visited(self, total=False, box_plot=False, avg_player=False): #unique over all players vs unique over only a single player
        #number of cells viisted that are crowdsourcers
        if box_plot:
            return [x.get_all_cells_visited(reward=True, total=total) for x in self.simulation_list]

        return np.mean([x.get_all_cells_visited(reward=True, total=total) for x in self.simulation_list])
        
        

    def get_average_result(self):
        return np.mean([x.get_average_results() for x in self.simulation_list], axis=0)


    def get_average_total_steps(self):
        return np.mean([x.simulation_steps for x in self.simulation_list])

    def get_average_player_steps(self):
        return np.mean([x.get_player_steps() for x in self.simulation_list])

    def get_average_player_utilization(self, box_plot = False):
        if box_plot:
            return [x.get_player_utilization() for x in self.simulation_list]
        return np.mean([x.get_player_utilization() for x in self.simulation_list])

    def get_average_player_coverage(self, box_plot=False, avg_player=False):
        if box_plot:
            return [x.get_player_coverage() for x in self.simulation_list]
        return np.mean([x.get_player_coverage() for x in self.simulation_list])











def plot_graph_folder(folder, x_interval,x_label,y_label): #plot the graph based on the mean of the simulation
    file_list = glob.glob(os.path.join(folder, r'*.sim'))
    file_list.sort(key=os.path.getctime)

    y_interval = [MultiCapture('test').pickle_load(x, directory=False).average() for x in file_list]

    plt.plot(x_interval, y_interval, marker='o', markersize=5, color='black', linestyle='dashed')
    #plt.plot(np.unique(x_interval), np.poly1d(np.polyfit(x_interval, y_interval, 1))(np.unique(x_interval)), color='black')
    #for xy in zip(x_interval, y_interval):                         
        #plt.annotate(f'{xy[1]:.2f}%', xy=xy, textcoords='data')

    plt.xlabel(x_label)
    plt.ylabel(y_label)
    #plt.grid()
    plt.show()


def plot_graph_multiple(folder, x_label, y_label, catogories): # x-axis number of simulation steps, y is the coverage, and multiple lines representing each capacity or budget value
    file_list = glob.glob(os.path.join(folder, r'*.sim'))
    file_list.sort(key=os.path.getctime)
    y_interval = [[j for j in MultiCapture('test').pickle_load(x, directory=False).simulation_conv_list] for x in file_list]
    x_interval = [x for x in range(1, len(y_interval[0])+1)]

    colors=['red','blue','yellow','purple','black']

    for i, simulation in enumerate(y_interval):
        plt.plot(x_interval, simulation, marker='o', markersize=4, color=colors[i], linestyle='', label=catogories[i])
        plt.plot(np.unique(x_interval), np.poly1d(np.polyfit(x_interval, simulation, 1))(np.unique(x_interval)), color=colors[i])
    plt.legend(loc='best')
    plt.grid()
    plt.show()

def autolabel(rects, ax):
    """Attach a text label above each bar in *rects*, displaying its height."""
    for rect in rects:
        height = rect.get_height()
        ax.annotate('{0:.2f}'.format(height),
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')




def plot_sd(folder, y_axis="ru"):


    label_order = ["dynamic", "static"]

    files = glob.glob(os.path.join(folder, r'*.sim'))
    df_list = [] #sd, oldesp, coverage, road util
    for file in files:
        oldesp = file.split("_")[-4]
        #print(oldesp)
        obj = MultiCapture('test').pickle_load(file, directory=False)
        sd_value = float(obj.simulation_list[0].setting.player_cost_sd)
        assert sum([x.setting.player_cost_sd == sd_value for x in obj.simulation_list]), f"not all sd value is the same in {file}. {[x.setting.player_cost_sd == sd_value for x in obj.simulation_list]}"
        coverage = obj.average()
        utilization = obj.average_coverage()
        average_utility = obj.average_reward(box_plot=False)
        result = obj.get_average_result()

        temp_list = [sd_value, oldesp, coverage, utilization, average_utility] + result.tolist()
        df_list.append(temp_list)


    df = pd.DataFrame(df_list, columns=['SD_value','static_sp','rc','ru', "average_utility", 'tp', 'tn', 'fp', 'fn', 'rs', 'ecs', 'acs', 'tp_over_ecs'])
    #df_melt = pd.melt(df, id_vars=["SD_value", "static_sp"], value_vars=["rc", "ru"], var_name="metric", value_name="value")
    
    #print(df_melt)
    df["step_ratio"] = (df["tp"] / df['ecs'])
    print(df)


    #df = df[df.SD_value < 1]

    xticks = df.SD_value

    yticks = df[y_axis]

    print(yticks)

    xticks = np.linspace(min(xticks), max(xticks) + 5, 6)

    print(df[y_axis])

    #if no col parameter passed in, it will only generate data on one plot 
    kw = {'color': ["red", "blue"], 'ls' : ["--","--"], "marker":["x", "o"]}

    df = df.sort_values(by=['SD_value']) #this is needed for the plt.plot with facetgrid works properly
     
    g = sns.FacetGrid(df, hue='static_sp', hue_kws=kw, legend_out=False)
    g.map(plt.plot, "SD_value", y_axis)
    g.map(plt.scatter, "SD_value", y_axis, alpha=0.7, linewidth=.1, edgecolor="white", s=1)
    
    g.add_legend(title="Algorithm", loc=0, ncol = 2,columnspacing=0.5, handletextpad=0, labelspacing=0, prop={'size':10}, borderpad=0, fancybox=True, framealpha=0, labels=label_order)



    ylabel = y_axis
    file_save = y_axis

    if y_axis == "ru":
        ylabel = "Road Utilization"
        file_save = "incomplet-road.eps"
    elif y_axis == "rc":
        ylabel = "Crowdsourcer Coverage"
        file_save = "incomplete-game.eps"
    elif y_axis == "reward_visited":
        ylabel = "Average Crowdsourcers Visited"

    elif y_axis == "average_utility":
        file_save = "incomplete-utility.eps"
        ylabel = "Average Utility Collected"
    elif y_axis == "reward_visited_total":
        ylabel = "Total Crowdsourcers Visited"
    elif y_axis == "tp":
        ylabel = "True Positives"

    elif y_axis == "step_ratio":
        #ylabel = "True Positive / Expected collection steps"
        ylabel = "True Positive Ratio"
        file_save = "comlete-incomplet-postiverate.eps"
    elif y_axis == "reward_visited":
        ylabel = "Average Crowdsourcers Visited"



    g.set(xlim=(min(xticks), max(xticks)), xticks=xticks, xlabel="Standard Deviation", ylabel=ylabel, ylim=(min(yticks)*0+0.98,max(yticks)*0 + 1))
    g.set(xscale="log")#, ylim=(3800, 4600))
    #plt.xscale('log')


    #for t, l in zip(g._legend.texts, label_order): t.set_text(l)
    plt.savefig(os.path.join(folder, file_save), dpi=300)



    plt.show()

def get_convert(y_axis):
    ylabel = y_axis
    if y_axis == "ru":
        ylabel = "Road Utilization"
    elif y_axis == "rc":
        ylabel = "Crowdsourcer Coverage"
    elif y_axis == "reward_visited":
        ylabel = "Average Crowdsourcers Visited"
    elif y_axis == "average_utility":
        ylabel = "Average Utility Collected"
    elif y_axis == "reward_visited_total":
        ylabel = "Total Crowdsourcers Visited"

    return ylabel

def plot_others(folder, plot_values = "reward", y_axis="ru", box_plot=None, avg_player=False, to_csv=False, horizontal=False, scatter=False, tTest=False, normalize=False, error_bar=False, save=False, combine_graph=False):
    #reward values can be either reward or stm
    '''
    box_plot: what each boxplot is divided by
    '''

    order = ["base", "greedy", "gta", "random"]
    label_order = ["BaseLine", "Greedy", "ATNE", "Random"]

    divided_list = []

    df_list = []

    folders = sorted([x for x in glob.glob(os.path.join(folder, r"*")) if os.path.isdir(x)], key=lambda x: int(x.split("\\")[-1]))


    for single_folder in folders:
        sort_dict = {}
        files = glob.glob(os.path.join(single_folder, r'*.sim'))
        for file in files:
            for i, x in enumerate(order):
                if x in file:
                    sort_dict[i] = file
                    break

        order_dict = [sort_dict[x] for x in sorted(sort_dict)]

        divided_list.append(order_dict)


    


    for group in divided_list:
        base_rc = None
        base_ru = None

        for i, single_file in enumerate(group):
            obj = MultiCapture('test').pickle_load(single_file, directory=False)
            if plot_values == "reward":
                identifier = obj.simulation_list[0].setting.reward_amount
            elif plot_values == "stm":
                identifier = obj.simulation_list[0].setting.max_memory_size
            elif plot_values == "cap":
                identifier = obj.simulation_list[0].setting.player_capacity_random[0]
            elif plot_values == "player":
                identifier = obj.simulation_list[0].setting.car_numbers


            print("reward junction ration is ", obj.simulation_list[0].reward_junction_ratio)


            algo = obj.simulation_list[0].setting.game_theory_algorithm[obj.simulation_list[0].setting.current_algo_index]
            player_amount = obj.simulation_list[0].setting.car_numbers
            capacity_mean = obj.simulation_list[0].setting.player_capacity_random[0]

            
            utilization = obj.average(box_plot=box_plot)
            #coverage = obj.average_coverage(box_plot=box_plot)
            #util_o_base = obj.average_util_over_base(box_plot=box_plot)
            #reward_visited = obj.get_reward_visited(box_plot=box_plot)
            #average_utility = obj.average_reward(box_plot=box_plot)
            #average_utilization = obj.get_average_player_utilization(box_plot=box_plot)
            #average_coverage = obj.get_average_player_coverage(box_plot=box_plot)
            #reward_visited_total = obj.get_reward_visited(total=True, box_plot=box_plot)



            if not box_plot:
                if normalize:
                    if i == 0:
                        base_ru = utilization
                        base_rc = coverage
                        utilization = 1
                        coverage = 1

                    else:
                        utilization /= base_ru
                        coverage /= base_rc

                temp_list = [identifier, algo, coverage, utilization, player_amount, cells, util_o_base, reward_visited, average_utility, capacity_mean, average_utilization, average_coverage, reward_visited_total]
                df_list.append(temp_list)

            elif scatter or box_plot:

                algo = [x.setting.game_theory_algorithm[x.setting.current_algo_index] for x in obj.simulation_list] 
                identifier = [identifier] * len(obj.simulation_list)
                player_amount = [x.setting.car_numbers for x in obj.simulation_list] 
                cells = [x.setting.max_memory_size for x in obj.simulation_list]
                capacity_mean = [x.setting.player_capacity_random[0] for x in obj.simulation_list]  
                zip_list = zip(*[identifier, algo, coverage, utilization, player_amount, cells, util_o_base, reward_visited, average_utility, capacity_mean, average_utilization, average_coverage, reward_visited_total])
                for value in zip_list:
                    df_list.append(list(value))






            

    df = pd.DataFrame(df_list, columns=[plot_values,'algo','rc','ru',"player_amount", "cells", "ru_over_base", "reward_visited", "average_utility", "capacity_mean", "average_utilization", "average_coverage", "reward_visited_total"])

    '''
    Setting the aestheics of the graph
    '''

    xlabel = plot_values
    if plot_values == "player":
        xlabel = "Participants"
    elif plot_values == "cap":
        xlabel = "Capacity"

    ylabel = y_axis
    if y_axis == "ru":
        ylabel = "Road Utilization"
        if normalize:
            ylabel = "Normalized Road Utilization"
    elif y_axis == "rc":
        ylabel = "Crowdsourcer Coverage"
        if normalize:
            ylabel = "Normalized Crowdsourcer Coverage"
    elif y_axis == "reward_visited":
        ylabel = "Average Crowdsourcers Visited"
    elif y_axis == "average_utility":
        ylabel = "Average Utility Collected"
    elif y_axis == "reward_visited_total":
        ylabel = "Total Crowdsourcers Visited"



    if tTest:
        print(t_test_independent(divided_list, y_axis, plot_values,only_gta=True))
        exit()


    print(df)

    xticks = sorted(set(list(df[plot_values])))
    '''

    from palettable.cubehelix import Cubehelix
    palette = Cubehelix.make(start=0.3, rotation=-0.5, n=16)

    cmap = plt.get_cmap('gnuplot2')
    indices = np.linspace(0, cmap.N, 6)
    my_colors = [cmap(int(i)) for i in indices]
    my_colors = my_colors[1:-1]

    print(palette)
    '''

    color =  ["red", "blue", "purple", "black"]
    ls = ["--","--","--","--"]
    marker = ["+", "x", "o", "^"]

    if (not box_plot):

        if normalize:
            df = df[df.algo != "base"]
            label_order.pop(0)
            color.pop(0)
            ls.pop(0)
            marker.pop(0)

        if len(xticks) > 6:
            xticks = np.linspace(min(xticks), max(xticks) + 10, 6)




        kw = {'color':  color, 'ls' : ls, "marker": marker}
        if not combine_graph:
            print("single graph with not box plot")
            g = sns.FacetGrid(df, hue='algo', hue_kws=kw, legend_out=False)
            g.map(plt.scatter, plot_values, y_axis, alpha=0.5, linewidth=.5, edgecolor="white", s=1)
            g.map(plt.plot, plot_values, y_axis)
            g.set(xlabel=xlabel, ylabel=ylabel, xticks=xticks)

            g.add_legend(title="Algorithm", loc=0, ncol = 2,columnspacing=0.5, handletextpad=0, labelspacing=0, prop={'size':7}, borderpad=0, fancybox=True, framealpha=0, labels=label_order)
            

        else:
            df = pd.melt(df, id_vars=[plot_values, "algo"], value_vars=["rc", "ru"], var_name="metric", value_name="value")
            print(df)
            g = sns.FacetGrid(df, hue='algo', hue_kws=kw, legend_out=False, col="metric", sharey=False)
            g.map(plt.scatter, plot_values, "value", s=5, alpha=0.5, linewidth=.5, edgecolor="white")
            g.map(plt.plot, plot_values, "value")
            g.set(xlabel=xlabel, xticks=xticks)

            for ax in g.axes.flat:
                ax.set_ylabel(get_convert(ax.get_title().split(" = ")[1]))
                ax.legend(title="Algorithm", loc=0, ncol = 2,columnspacing=0.5, handletextpad=0, labelspacing=0, prop={'size':8}, borderpad=0, fancybox=True, framealpha=0.5, labels=label_order)
                ax.set_title("")

        

        #g.add_legend(title="Algorithm", loc=0, ncol = 2,columnspacing=0.5, handletextpad=0, labelspacing=0, prop={'size':8}, borderpad=0, fancybox=True, framealpha=0.5, labels=label_order)
        
        #for t, l in zip(g._legend.texts, label_order): t.set_text(l)

        #plt.tight_layout()
        #g.legend(loc="lower left", mode = "expand", ncol = 4)

        plt.savefig(os.path.join(folder, f'{y_axis}.eps'), dpi=300)
        '''

        if len(xticks) > 6:
            xticks = np.linspace(min(xticks), max(xticks) + 10, 6)

        kw = {'color':  ["red", "blue", "purple", "black"], 'ls' : ["--","--","--","--"], "marker": ["+", "x", "o", "^"]}

        palette = dict(zip(order, kw["color"]))
        
        #g = sns.lmplot(x=plot_values, y=y_axis, hue="algo", data=df, palette=palette, markers=kw["marker"], legend_out=True, scatter_kws={"s": 30})


        g = sns.FacetGrid(df, hue='algo', size=5, hue_kws=kw, legend_out=True)#.add_legend("Algorithm")
        g.map(plt.scatter, plot_values, y_axis, s=50, alpha=0.7, linewidth=.5, edgecolor="white")
        g.map(plt.plot, plot_values, y_axis)

       #g._legend.set_title("Algorithm")
        g.set(xlabel=xlabel, ylabel=ylabel, xticks=xticks)


        #for t, l in zip(g._legend.texts, label_order): t.set_text(l)
        '''

    else:
        if scatter:
            kw = {'color': ["red", "blue", "purple", "black"], "marker":["D", "s", "o", "X"]}
            g = sns.FacetGrid(data=df, legend_out=True, hue="algo", hue_kws=kw) \
            .map(sns.stripplot, plot_values, y_axis, size=15, alpha=0.4) \
            .add_legend(title="Algorithm") \
            .set(xlabel=xlabel, ylabel=ylabel)

   

            for t, l in zip(g._legend.texts, label_order): t.set_text(l)




        elif horizontal:
            sns.violinplot(x="player",y=y_axis,hue='algo',data=df)

        elif error_bar:
            
            #sns.lineplot(x="player",y=y_axis,hue='algo',data=df, err_style="bars")
            ax = sns.pointplot(x="player", y=y_axis, hue="algo",
                   data=df,
                   markers=["o", "o", "o", "o"],
                   linestyles=["--", "--", "--", "--"])


        else:
            if plot_values == "player":
                title = "Participants"
                df  = df[df.player!=100]
            elif plot_values == "cap":
                title = "Capacity "
                df = df[df.cap!=90]
            df.loc[df.algo=="gta", "algo"] = "ATNE"
            df.loc[df.algo=="random", "algo"] = "Random"
            df.loc[df.algo=="base", "algo"] = "BaseLine"
            df.loc[df.algo=="greedy", "algo"] = "Greedy"

            g = sns.FacetGrid(data=df, col=box_plot, legend_out=False, col_wrap=2, sharey=False, sharex=False) \
            .map(sns.boxplot, "algo", y_axis,linewidth=0.5) \
            .set(xlabel="Algorithm", ylabel=ylabel) 

            for ax in g.axes:
               print(ax.get_title())
               tit = ax.get_title().split(" = ")[1]
               ax.set_title(f"{title}: {tit}")
               for label in ax.get_xticklabels():
                   label.set_rotation(30)


            plt.tight_layout()
            plt.savefig(os.path.join(folder, f'{y_axis}_box.eps'), dpi=300)
            #plt.subplots_adjust(hspace=0.4, wspace=0.4)

    plt.show()

def plot_others_graph(folder, plot_values = "reward", y_axis="ru", box_plot=None, avg_player=False, to_csv=False, horizontal=False, scatter=False, tTest=False, normalize=False, error_bar=False, save=False, combine_graph=False, ylim=None, xlim=None):
    #reward values can be either reward or stm
    '''
    box_plot: what each boxplot is divided by
    '''

    order = ["base", "greedy", "gta", "random"]
    label_order = ["our", "baseline", "greedy", "random"]

    divided_list = []

    df_list = []

    sort_dict = {}
    files = glob.glob(os.path.join(folder, r'*.sim'))

    divided_list = [files]


    print(divided_list)
    


    for group in divided_list:

        base_rc = None
        base_ru = None
        print("Plotting ", plot_values)

        for i, single_file in enumerate(group):

            print("procssing ", os.path.basename(single_file))
            obj = MultiCapture('test').pickle_load(single_file, directory=False)
            print("im here")
            if plot_values == "reward":
                identifier = obj.simulation_list[0].setting.reward_amount
            elif plot_values == "stm":
                identifier = obj.simulation_list[0].setting.max_memory_size
            elif plot_values == "cap":
                identifier = obj.simulation_list[0].setting.player_capacity_random[0]
            elif plot_values == "player":
                identifier = obj.simulation_list[0].setting.car_numbers
            elif plot_values == "sp":
                identifier = obj.simulation_list[0].setting.sensing_plan_one
            elif plot_values == "random_theta":
                identifier = obj.simulation_list[0].setting.theta_random
            elif plot_values == "poiradius":
                identifier = obj.simulation_list[0].setting.poi_radius
            elif (plot_values == "bufferinterval") or (plot_values == "bufferpoi"):
                identifier = obj.simulation_list[0].setting.buffer_interval
            elif plot_values == "distcap":
                identifier = obj.simulation_list[0].setting.distance_capacity[0]
                #identifier = int(os.path.basename(single_file).split("_")[0])
                #print("im here", identifier)





            #print("im here outside ", identifier)

            #print("reward junction ration is ", obj.simulation_list[0].reward_junction_ratio)


            algo = obj.simulation_list[0].setting.current_running_algo #obj.simulation_list[0].setting.game_theory_algorithm[obj.simulation_list[0].setting.current_algo_index]

            algo = algo.lower()
            if algo == "atne":
                algo="ours"

            player_amount = obj.simulation_list[0].setting.car_numbers
            cells = obj.simulation_list[0].setting.max_memory_size
            capacity_mean = obj.simulation_list[0].setting.player_capacity_random[0]

            
            utilization = obj.average(box_plot=box_plot)
            coverage = obj.average_coverage(box_plot=box_plot)
            temp_coverage = obj.average_coverage_temp(box_plot=box_plot)
            average_utility = obj.average_reward(box_plot=box_plot)
            #util_o_base = obj.average_util_over_base(box_plot=box_plot)
            #reward_visited = obj.get_reward_visited(box_plot=box_plot)
            #average_utility = obj.average_reward(box_plot=box_plot)
            #average_utilization = obj.get_average_player_utilization(box_plot=box_plot)
            #average_coverage = obj.get_average_player_coverage(box_plot=box_plot)
            #reward_visited_total = obj.get_reward_visited(total=True, box_plot=box_plot)



            if not box_plot:
                if normalize:
                    if i == 0:
                        base_ru = utilization
                        base_rc = coverage
                        utilization = 1
                        coverage = 1

                    else:
                        utilization /= base_ru
                        coverage /= base_rc

                temp_list = [identifier, algo, coverage, utilization, player_amount, temp_coverage, average_utility]

                #temp_list = [identifier, algo, coverage, utilization, player_amount, cells, util_o_base, reward_visited, average_utility, capacity_mean, average_utilization, average_coverage, reward_visited_total]
                df_list.append(temp_list)

            elif scatter or box_plot:

                algo = [x.setting.current_running_algo for x in obj.simulation_list] 

                #algo = [x.setting.game_theory_algorithm[x.setting.current_algo_index] for x in obj.simulation_list] 
                identifier = [identifier] * len(obj.simulation_list)
                player_amount = [x.setting.car_numbers for x in obj.simulation_list] 
                cells = [x.setting.max_memory_size for x in obj.simulation_list]
                capacity_mean = [x.setting.player_capacity_random[0] for x in obj.simulation_list]  
                #zip_list = zip(*[identifier, algo, coverage, utilization, player_amount, cells, util_o_base, reward_visited, average_utility, capacity_mean, average_utilization, average_coverage, reward_visited_total])
                #print(f"{len(identifier)} {len(algo)} {coverage.shape} {utilization.shape} {temp_coverage.shape} {average_utility.shape} {player_amount.shape}")
                zip_list = zip(*[identifier, algo, coverage, utilization, player_amount, temp_coverage, average_utility])
                for value in zip_list:
                    df_list.append(list(value))






            
    df = pd.DataFrame(df_list, columns=[plot_values,'algo','rc', 'ru',"player_amount", 'tc', 'rw'])

    #df = df.sort_values(by=[plot_values])

    #df.to_csv("testout.csv")
   # df = pd.DataFrame(df_list, columns=[plot_values,'algo','rc','ru',"player_amount", "cells", "ru_over_base", "reward_visited", "average_utility", "capacity_mean", "average_utilization", "average_coverage", "reward_visited_total"])

    '''
    Setting the aestheics of the graph
    '''

    xlabel = plot_values
    if plot_values == "player":
        xlabel = "Number of participants"
    elif plot_values == "cap":
        xlabel = "Data capacity"
    elif plot_values == "distcap":
        xlabel = "Distance capacity"
    elif plot_values == "bufferpoi":
        xlabel = "Interval & Radius"

    ylabel = y_axis
    if y_axis == "ru":
        ylabel = "Road Utilization"
        if normalize:
            ylabel = "Normalized Road Utilization"
    elif y_axis == "rc":
        ylabel = "Crowdsourcer Coverage"
        if normalize:
            ylabel = "Normalized Crowdsourcer Coverage"
    elif y_axis == "reward_visited":
        ylabel = "Average Crowdsourcers Visited"
    elif y_axis == "average_utility":
        ylabel = "Average Utility Collected"
    elif y_axis == "reward_visited_total":
        ylabel = "Total Crowdsourcers Visited"
    elif y_axis == "tc":
        ylabel = "Average poi temporal coverage"
    elif y_axis == "rw":
        ylabel = "Average utility gain"



    if tTest:
        print(t_test_independent(divided_list, y_axis, plot_values,only_gta=True))
        exit()


    print(df)

    xticks = sorted(set(list(df[plot_values])))
    '''

    from palettable.cubehelix import Cubehelix
    palette = Cubehelix.make(start=0.3, rotation=-0.5, n=16)

    cmap = plt.get_cmap('gnuplot2')
    indices = np.linspace(0, cmap.N, 6)
    my_colors = [cmap(int(i)) for i in indices]
    my_colors = my_colors[1:-1]

    print(palette)
    '''

    #color =  ["red", "blue", "purple", "black"]
    marker = ["x", "^", "+", "o"]
    ls = ["--","--","--","--"]
    #ls = ["--","-.",":", "-"]
    color =  ["red", "blue", "purple", "black"]
    #marker = ["o", "x", "^", "+"]
    if (not box_plot):

        if normalize:
            df = df[df.algo != "base"]
            label_order.pop(0)
            color.pop(0)
            ls.pop(0)
            marker.pop(0)

        if len(xticks) > 6:
            xticks = np.linspace(min(xticks), max(xticks) + 10, 6)




        #kw = {'color':  color, 'ls' : ls}#, "marker": marker}
        kw = {'color':  color, 'ls' : ls, "marker": marker}
        if not combine_graph:
            print("single graph with not box plot")
            g = sns.FacetGrid(df, hue='algo', hue_kws=kw, legend_out=False)
            g.map(plt.scatter, plot_values, y_axis, alpha=1, linewidth=1, s=20)
            g.map(plt.plot, plot_values, y_axis)
            g.set(xlabel=xlabel, ylabel=ylabel, xticks=xticks,ylim=ylim, xlim=xlim)

            g.add_legend(title="", loc="upper left", ncol = 1,columnspacing=0, handletextpad=0, labelspacing=0, prop={'size':8}, borderpad=0, fancybox=True, framealpha=0)#, labels=label_order)
            #bbox_to_anchor is (x,y, width, height) x,y is 0,0 and lower left corner all the way til 1,1, ,bbox_to_anchor=(0.8, 0.05, 0.2, 0.5)

        else:
            df = pd.melt(df, id_vars=[plot_values, "algo"], value_vars=["rc", "ru"], var_name="metric", value_name="value")
            print(df)
            g = sns.FacetGrid(df, hue='algo', hue_kws=kw, legend_out=False, col="metric", sharey=False)
            g.map(plt.scatter, plot_values, "value", s=5, alpha=0.5, linewidth=.5, edgecolor="white")
            g.map(plt.plot, plot_values, "value")
            g.set(xlabel=xlabel, xticks=xticks)

            for ax in g.axes.flat:
                ax.set_ylabel(get_convert(ax.get_title().split(" = ")[1]))
                ax.legend(title="", loc=0, ncol = 2,columnspacing=0.5, handletextpad=0, labelspacing=0, prop={'size':8}, borderpad=0, fancybox=True, framealpha=0.5, labels=label_order)
                ax.set_title("")

        

        #g.add_legend(title="Algorithm", loc=0, ncol = 2,columnspacing=0.5, handletextpad=0, labelspacing=0, prop={'size':8}, borderpad=0, fancybox=True, framealpha=0.5, labels=label_order)
        
        #for t, l in zip(g._legend.texts, label_order): t.set_text(l)

        #plt.tight_layout()
        #g.legend(loc="lower left", mode = "expand", ncol = 4)

        plt.savefig(os.path.join(folder, f'{y_axis}.eps'), dpi=600)
        plt.savefig(os.path.join(folder, f'{y_axis}.png'))
        '''

        if len(xticks) > 6:
            xticks = np.linspace(min(xticks), max(xticks) + 10, 6)

        kw = {'color':  ["red", "blue", "purple", "black"], 'ls' : ["--","--","--","--"], "marker": ["+", "x", "o", "^"]}

        palette = dict(zip(order, kw["color"]))
        
        #g = sns.lmplot(x=plot_values, y=y_axis, hue="algo", data=df, palette=palette, markers=kw["marker"], legend_out=True, scatter_kws={"s": 30})


        g = sns.FacetGrid(df, hue='algo', size=5, hue_kws=kw, legend_out=True)#.add_legend("Algorithm")
        g.map(plt.scatter, plot_values, y_axis, s=50, alpha=0.7, linewidth=.5, edgecolor="white")
        g.map(plt.plot, plot_values, y_axis)

       #g._legend.set_title("Algorithm")
        g.set(xlabel=xlabel, ylabel=ylabel, xticks=xticks)


        #for t, l in zip(g._legend.texts, label_order): t.set_text(l)
        '''

    else:
        if scatter:
            kw = {'color': ["red", "blue", "purple", "black"], "marker":["D", "s", "o", "X"]}
            g = sns.FacetGrid(data=df, legend_out=True, hue="algo", hue_kws=kw) \
            .map(sns.stripplot, plot_values, y_axis, size=15, alpha=0.4) \
            .add_legend(title="Algorithm") \
            .set(xlabel=xlabel, ylabel=ylabel)

   

            for t, l in zip(g._legend.texts, label_order): t.set_text(l)




        elif horizontal:
            sns.violinplot(x="player",y=y_axis,hue='algo',data=df)

        elif error_bar:
            
            #sns.lineplot(x="player",y=y_axis,hue='algo',data=df, err_style="bars")
            ax = sns.pointplot(x="player", y=y_axis, hue="algo",
                   data=df,
                   markers=["o", "o", "o", "o"],
                   linestyles=["--", "--", "--", "--"])


        else:
            if plot_values == "player":
                title = "Participants"
                df  = df[df.player!=100]
            elif plot_values == "cap":
                title = "Capacity "
                df = df[df.cap!=90]

            print("here new")
            df.loc[df.algo=="gta", "algo"] = "ATNE"
            df.loc[df.algo=="random", "algo"] = "Random"
            df.loc[df.algo=="base", "algo"] = "BaseLine"
            df.loc[df.algo=="greedy", "algo"] = "Greedy"
            order_tick = ["RANDOM", "GREEDY", "ATNE", "BASE"]
            

            g = sns.FacetGrid(data=df, col=box_plot, legend_out=False, col_wrap=2, sharey=False, sharex=False)
            g.map(sns.boxplot, "algo", y_axis,linewidth=0.5, palette="Set3")
            g.set(xlabel="Algorithm", ylabel=ylabel) 
            print("here again again")

            
            for i, ax in enumerate(g.axes):
                print(ax.get_title())
                tit = ax.get_title().split(" = ")[1]
                ax.set_title(f"{title}: {tit}")
                #ax.set_xticklabels(order_tick)
                for label in ax.get_xticklabels():
                    label.set_rotation(30)
            

            plt.tight_layout()
            plt.savefig(os.path.join(folder, f'{y_axis}_box.eps'), dpi=300)
            plt.savefig(os.path.join(folder, f'{y_axis}_box.png'))
            #plt.subplots_adjust(hspace=0.4, wspace=0.4)

    plt.show()



def plot_result(folder, plot_values = "player", y_axis="tp"):
    order = ["base", "greedy", "gta", "random"]


    divided_list = []

    label_order = ["BaseLine", "Greedy", "ATNE", "Random"]

    folders = sorted([x for x in glob.glob(os.path.join(folder, r"*")) if os.path.isdir(x)], key=lambda x: int(x.split("\\")[-1]))

    
    df_list = [] #algo, capacity, tp, tn, fp, fn, rs, ecs acs, steps

    if not folders:
        sort_dict = {}
        files = glob.glob(os.path.join(folder, r'*.sim'))

        print(files)
        for file in files:
            for i, x in enumerate(order):
                if x in file or x.upper() in file:
                    sort_dict[i] = file
                    break

        order_dict = [sort_dict[x] for x in sorted(sort_dict)]

        divided_list.append(order_dict)



    for single_folder in folders:
        sort_dict = {}
        files = glob.glob(os.path.join(single_folder, r'*.sim'))
        for file in files:
            for i, x in enumerate(order):
                if x in file:
                    sort_dict[i] = file
                    break

        order_dict = [sort_dict[x] for x in sorted(sort_dict)]

        divided_list.append(order_dict)

    print(divided_list)

    for group in divided_list:
        for i, single_file in enumerate(group):
            #print("reading file", single_file)
            obj = MultiCapture('test').pickle_load(single_file, directory=False)

            if plot_values == "reward":
                identifier = obj.simulation_list[0].setting.reward_amount
            elif plot_values == "stm":
                identifier = obj.simulation_list[0].setting.max_memory_size
            elif plot_values == "cap":
                identifier = obj.simulation_list[0].setting.player_capacity_random[0]
            elif plot_values == "player":
                identifier = obj.simulation_list[0].setting.car_numbers


            print(single_file)

            #cap = obj.simulation_list[0].setting.player_capacity_random[0]

            algo = obj.simulation_list[0].setting.game_theory_algorithm[obj.simulation_list[0].setting.current_algo_index]

            if (algo != "greedy") and (algo != "gta"):
                continue
            print(algo)
            result = obj.get_average_result()
            steps = obj.get_average_total_steps()
            player_avg_steps = obj.get_average_player_steps()
            #print(type(result))
            df_list.append([identifier, algo, steps, player_avg_steps] + result.tolist())

    df = pd.DataFrame(df_list, columns=[plot_values ,'algo',  'steps', 'player_avg_steps','tp', 'tn', 'fp', 'fn', 'rs', 'ecs', 'acs', 'tp_over_ecs'])  
    df["step_ratio"] = (df["tp"] / df['ecs'])
    print(df)

    xlabel = plot_values
    if plot_values == "player":
        xlabel = "Participants"
    elif plot_values == "cap":
        xlabel = "Capacity"



    ylabel = y_axis
    if y_axis == "tp":
        ylabel = "Average True Positives"
    elif y_axis == "step_ratio":
        #ylabel = "True Positive / Expected collection steps"
        ylabel = "True Positive Ratio"
    elif y_axis == "reward_visited":
        ylabel = "Average Crowdsourcers Visited"


    xticks = sorted(set(list(df[plot_values])))


    xticks = np.linspace(min(xticks), max(xticks) + 10, 6)

    marker = ["x", "o"]


    kw = {'color': ["blue", "purple", "red", "black"], 'ls' : ["--","--","--","--"], "marker":marker}
    g = sns.FacetGrid(df, hue='algo', hue_kws=kw, legend_out=False) \
    .map(plt.scatter, plot_values, y_axis, alpha=0.7, linewidth=.5, edgecolor="white") \
    .map(plt.plot, plot_values, y_axis ) \
    .add_legend(title="Algorithm") \
    .set(xlabel=xlabel, ylabel=ylabel, xticks=xticks) \
    .add_legend(title="Algorithm", loc=0, ncol = 2,columnspacing=0.5, handletextpad=0, labelspacing=0, prop={'size':9}, borderpad=0, fancybox=True, framealpha=0.5, labels=[x for x in label_order if (x == "Greedy" or x == "ATNE")])

    #for t, l in zip(g._legend.texts, [x for x in label_order if (x == "Greedy" or x == "ATNE")]): t.set_text(l)

    plt.savefig(os.path.join(folder, f'{y_axis}.eps'), dpi=300)

    plt.show()



    




def plot_result_graph(folder, plot_values = "player", y_axis="tp"):
    order = ["base", "greedy", "gta", "random"]


    divided_list = []

    label_order = ["BaseLine", "Greedy", "ATNE", "Random"]

    
    df_list = [] #algo, capacity, tp, tn, fp, fn, rs, ecs acs, steps


    sort_dict = {}
    files = glob.glob(os.path.join(folder, r'*.sim'))

    print(files)
    for file in files:
        for i, x in enumerate(order):
            if x in file or x.upper() in file:
                sort_dict[i] = file
                break

    order_dict = [sort_dict[x] for x in sorted(sort_dict)]

    divided_list.append(order_dict)



 

    print(divided_list)

    for group in divided_list:
        for i, single_file in enumerate(group):
            print("reading file", single_file)
            obj = MultiCapture('test').pickle_load(single_file, directory=False)

            if plot_values == "reward":
                identifier = obj.simulation_list[0].setting.reward_amount
            elif plot_values == "stm":
                identifier = obj.simulation_list[0].setting.max_memory_size
            elif plot_values == "cap":
                identifier = obj.simulation_list[0].setting.player_capacity_random[0]
            elif plot_values == "player":
                identifier = obj.simulation_list[0].setting.car_numbers


            print(single_file)

            #cap = obj.simulation_list[0].setting.player_capacity_random[0]

            algo = os.path.basename(single_file).split("_")[1].split(".")[0]

            print(algo)
            result = obj.get_average_result()
            steps = obj.get_average_total_steps()
            player_avg_steps = obj.get_average_player_steps()
            #print(type(result))
            df_list.append([identifier, algo, steps, player_avg_steps] + result.tolist())

    df = pd.DataFrame(df_list, columns=[plot_values ,'algo',  'steps', 'player_avg_steps','tp', 'tn', 'fp', 'fn', 'rs', 'ecs', 'acs', 'tp_over_ecs'])  
    df["step_ratio"] = (df["tp"] / df['ecs'])
    print(df)

    xlabel = plot_values
    if plot_values == "player":
        xlabel = "Participants"
    elif plot_values == "cap":
        xlabel = "Capacity"



    ylabel = y_axis
    if y_axis == "tp":
        ylabel = "Average True Positives"
    elif y_axis == "step_ratio":
        #ylabel = "True Positive / Expected collection steps"
        ylabel = "True Positive Ratio"
    elif y_axis == "reward_visited":
        ylabel = "Average Crowdsourcers Visited"


    xticks = sorted(set(list(df[plot_values])))


    xticks = np.linspace(min(xticks), max(xticks) + 10, 6)

    marker = ["x", "o"]


    kw = {'color': ["blue", "purple", "red", "black"], 'ls' : ["--","--","--","--"], "marker":marker}
    g = sns.FacetGrid(df, hue='algo', hue_kws=kw, legend_out=False) \
    .map(plt.scatter, plot_values, y_axis, alpha=0.7, linewidth=.5, edgecolor="white") \
    .map(plt.plot, plot_values, y_axis ) \
    .add_legend(title="Algorithm") \
    .set(xlabel=xlabel, ylabel=ylabel, xticks=xticks) \
    .add_legend(title="Algorithm", loc=0, ncol = 2,columnspacing=0.5, handletextpad=0, labelspacing=0, prop={'size':9}, borderpad=0, fancybox=True, framealpha=0.5, labels=[x for x in label_order if (x == "Greedy" or x == "ATNE")])

    #for t, l in zip(g._legend.texts, [x for x in label_order if (x == "Greedy" or x == "ATNE")]): t.set_text(l)

    plt.savefig(os.path.join(folder, f'{y_axis}.eps'), dpi=300)

    plt.show()



def t_test_independent(files, y_axis, plot_values, only_gta=False):


    t_test_result_dict = {}
    summary_dict = {}
    for fourfile in files:
        combs = list(combinations(fourfile, 2))
        for comb in combs:
            #sim_obj1 = MultiCapture('test').pickle_load(comb[0], directory=False).simulation_test_coverage
            #sim_obj2 = MultiCapture('test').pickle_load(comb[1], directory=False).simulation_test_coverage
            #sim_obj1 = MultiCapture('test').pickle_load(comb[0], directory=False).find_all_cov_cells(_iter=True)
            #sim_obj2 = MultiCapture('test').pickle_load(comb[1], directory=False).find_all_cov_cells(_iter=True)

            sim_obj1 = MultiCapture('test').pickle_load(comb[0], directory=False) #road util
            sim_obj2 = MultiCapture('test').pickle_load(comb[1], directory=False) #road util

            if y_axis == "ru":
                test_obj = T_test(sim_obj1.simulation_conv_list, sim_obj2.simulation_conv_list)
            elif y_axis == "rc":
                test_obj = T_test(sim_obj1.average_coverage(box_plot=True), sim_obj2.average_coverage(box_plot=True))
            elif y_axis == "reward_visited":
                test_obj = T_test(sim_obj1.get_reward_visited(box_plot=True), sim_obj2.get_reward_visited(box_plot=True))
            elif y_axis == "average_utility":
                test_obj = T_test(sim_obj1.average_reward(box_plot=True), sim_obj2.average_reward(box_plot=True))
            elif y_axis == "reward_visited_total":
               test_obj = T_test(sim_obj1.get_reward_visited(total=True, box_plot=True), sim_obj2.get_reward_visited(total=True,box_plot=True))




            #sim_obj1 = MultiCapture('test').pickle_load(comb[0], directory=False).average_reward(True) #utility
            #sim_obj2 = MultiCapture('test').pickle_load(comb[1], directory=False).average_reward(True)

            
    
            #assert comb[0].split("_")[-5] == comb[1].split("_")[-5], f"{comb[0].split('_')[-5]} != {comb[1].split('_')[-5]}"


            
            algo_1 = sim_obj1.simulation_list[0].setting.game_theory_algorithm[sim_obj1.simulation_list[0].setting.current_algo_index]
            algo_2 = sim_obj2.simulation_list[0].setting.game_theory_algorithm[sim_obj2.simulation_list[0].setting.current_algo_index]

            if plot_values == "player":
                player_amount = sim_obj1.simulation_list[0].setting.car_numbers
            elif plot_values == "cap":
                player_amount = sim_obj1.simulation_list[0].setting.player_capacity_random[0]

            key = f"{algo_1}_{algo_2}_{player_amount}"



            t_test_result_dict[key] = test_obj
    if only_gta:
        return {key:value for key, value in t_test_result_dict.items() if "gta" in key}
        
    return t_test_result_dict


    #the t value shows the difference and p value shows the significance of that difference, you want it to be <0.05 to accept the hypothesis

def comp(folder, group_by):
    file_list = glob.glob(os.path.join(folder, r'*.sim'))
    file_list.sort(key=os.path.getctime)

    for file in file_list:
        print(file)
        obj = MultiCapture('test').pickle_load(file, directory=False)
        print(obj.average_coverage())

def generate_weighted_graph(sumo_cfg):
    from _map import Map
    traci.start(["sumo", "-c", sumo_cfg])
    env_map = Map(sumo_cfg)

    weight_dict = {}

    destination = "cell0_2"

    max_time = 0

    for junct_id, junct_obj in env_map.junctions.items():
         route_obj = env_map.find_best_route(junct_id, destination)
         if not route_obj:
            print("no travel time ", junct_id)
         else:
            #weight_dict[junct_id] = math.exp(-0.5 *(route_obj.travelTime**2))
            #print(route_obj)
            #exit()
            weight_dict[junct_id] = route_obj.travelTime
            if route_obj.travelTime > max_time:
                max_time = route_obj.travelTime


    for key, value in weight_dict.copy().items():
        weight_dict[key] = math.exp(-0.5 *((value/max_time)**2))

    return weight_dict





def plot_time_series(folder, plot_values = "sim", y_axis="rc"):

    order = ["base", "greedy", "gta", "random"]
    label_order = ["BaseLine", "Greedy", "ATNE", "Random"]

    divided_list = []

    df_list = [] #list that will be converted to df after

    sort_dict = {}
    files = glob.glob(os.path.join(folder, r'*.sim'))

    divided_list = [files]


    print(divided_list)



    if y_axis=="poi":

        for group in divided_list:

            base_rc = None
            base_ru = None

            for i, single_file in enumerate(group):

                print("procssing ", os.path.basename(single_file))
                obj = MultiCapture('test').pickle_load(single_file, directory=False) 
                print(obj.simulation_list[0].poi_visited_instance)



                for i, sim_number in enumerate(obj.simulation_list):

                    algo = sim_number.setting.current_running_algo

                    for step, value in sim_number.poi_visited_instance.items():

                        avg_poi_sim_visit = sum([len(tmp_list) for tmp_list in value.values()]) / len(value)

                        df_list.append([algo, i, step, avg_poi_sim_visit])

        df = pd.DataFrame(df_list, columns=['algo',  'sim_number', 'step','poi'])


    
    elif y_axis == "rc" or y_axis=="rw":

        for group in divided_list:

            base_rc = None
            base_ru = None

            for i, single_file in enumerate(group):

                print("procssing ", os.path.basename(single_file))
                obj = MultiCapture('test').pickle_load(single_file, directory=False) 
                #print(obj.simulation_list[0].rc_visited_instance)


                #print("temp coverage ", obj.simulation_list[0].get_avg_temp_coverage())
                for i, sim_number in enumerate(obj.simulation_list):
                    print("temp coverage ", sim_number.get_avg_temp_coverage())
                    print(sim_number.temp_coverage)

                    print()

                    algo = sim_number.setting.current_running_algo
                    algo = algo.lower()
                    if algo == "atne":
                        algo = "ours"

                    if y_axis == "rc":
                        for step, cov in sim_number.rc_visited_instance.items():

                            df_list.append([algo, i, step, cov])
                    if y_axis == "rw":
                        for step, cov in sim_number.rw_visited_instance.items():

                            df_list.append([algo, i, step, cov])


        df = pd.DataFrame(df_list, columns=['algo',  'sim_number', 'step',y_axis])




        #df = df[df['algo']!="RANDOM"]

        #exit()

    

    df = df.groupby(['algo', 'step']).mean().reset_index()
    df = df[df["algo"] != "base"]

    print(df[df["algo"]=="BASE"])


    marker = ["o", "^", "s", "x"]
   # xticks = np.linspace(min(xticks), max(xticks) + 10, 6)


    kw = {'color': ["purple", "red", "black", "black"], 'ls' : ["--","-.",":"]}#, "marker":marker}
    g = sns.FacetGrid(df, hue='algo', hue_kws=kw, legend_out=False)
    #g.map(plt.scatter, "step", y_axis, alpha=0.5, linewidth=1, s=20)
    g.map(plt.plot, "step", y_axis)  
    g.set(ylim=None, xlabel="Time step", ylabel="Average utility") 
    g.add_legend(title="Algorithm", loc="upper left", ncol = 4,columnspacing=0.3, handletextpad=0, labelspacing=0, prop={'size':6.5}, borderpad=0, fancybox=True, framealpha=0)#, labels=label_order)#[x for x in label_order if (x == "Greedy" or x == "ATNE")])

    #for t, l in zip(g._legend.texts, [x for x in label_order if (x == "Greedy" or x == "ATNE")]): t.set_text(l)
    #plt.grid()
    plt.savefig(os.path.join(folder, f'{y_axis}.eps'), dpi=300)
    plt.savefig(os.path.join(folder, f'{y_axis}.png'))

    plt.show()





class DataCaptureGraph(DataCapture): #object per simulation
    def __init__(self, map_junctions=None, rowcol_to_junction=None):
        super(DataCaptureGraph, self).__init__(map_junctions=map_junctions, rowcol_to_junction=rowcol_to_junction)
        self.poi_visited_instance = defaultdict(dict) #step:{poikey:[vehid], poikey:[vehid]} # to capture all the times  
        #self.ru_visited_instance = {} #this can be calcualted using the csv files
        self.rc_visited_instance = {} #step, 
        self.rw_visited_instance = {}
        self.temp_coverage = defaultdict(list) #poi:[]



    def calculate_test_coverage(self, custom_player_list=None): #actually coverage amount rewarded cells visited over total reward cells
        #crowsourcer coverage
        reward_cell_visited = {}
        #collected_sp_list need to contain node interms of grid

        if custom_player_list:
            temp_player_list = custom_player_list
        else:
            temp_player_list = self.player_list


        for player in temp_player_list:
            #print(f'player len node are {player.node_hit}')
            for node in player.collected_sp_list:
                if node in reward_cell_visited:
                    reward_cell_visited[node] += 1
                else:
                    reward_cell_visited[node] = 1


        #print(f'coverage cells hit:{reward_hit_number}, total rewards cells:{len(self.reward_list)}')
        return (len(reward_cell_visited)/len(self.reward_list))*100



    def get_all_cells_visited(self, repeat=False, reward=False, total=False):
        edge_junct_visited = {}

        for player in self.player_list:
            for node in player.node_hit:
                if node in edge_junct_visited:
                    edge_junct_visited[node] += 1
                else:
                    edge_junct_visited[node] = 1

        return len(edge_junct_visited)

    def get_avg_reward(self, custom_player_list=None):

        if custom_player_list:
            temp_player_list = custom_player_list
        else:
            temp_player_list = self.player_list

        return np.mean([player.reward for player in temp_player_list])

    def get_avg_temp_coverage(self):
        for key, value in self.temp_coverage.items():
            if value[0] != 0:
                value.insert(0, 0)
        #print(self.temp_coverage)

        prob_dist_dict = {key:entropy_calculation(np.diff(value_list)/np.sum(np.diff(value_list))) for key, value_list in self.temp_coverage.items()}
        return (sum(prob_dist_dict.values())/len(self.reward_list)) #dictionary contains the probabilty ditribtuion for every poi, first get the gap between simulation steps, then calculate the probabily for the gaps might need softmax




class MultiCaptureGraph(MultiCapture):
    def __init__(self, title=None):
        super(MultiCaptureGraph, self).__init__(title=title)


    def average(self, box_plot=False, avg_player=False): #average for road util
        list_ru = [(sim.get_all_cells_visited() / sim.map_junctions)*100 for sim in self.simulation_list]
        if box_plot:
            return list_ru

        return np.mean(list_ru)

    def average_coverage(self, box_plot =False, avg_player=False):
        list_rc = [sim.calculate_test_coverage() for sim in self.simulation_list]
        if box_plot:
            return list_rc
        return np.mean(list_rc)

    def average_reward(self, box_plot=False, avg_player=False):
        list_rw = [sim.get_avg_reward() for sim in self.simulation_list]
        if box_plot:
            return list_rw
        return np.mean(list_rw)

    def average_coverage_temp(self, box_plot=False, avg_player=False):
        list_tc = [sim.get_avg_temp_coverage() for sim in self.simulation_list]
        if box_plot:
            return list_tc
        return np.mean(list_tc)



if __name__== "__main__":

    parser = argparse.ArgumentParser(description="NSF simulation RESULTS")
    #parser.add_argument("--option", type=str, default="player", help="define what changes for simulation player / capacity ")#--means optional args no -- means positional
    parser.add_argument("--option", type=str, default="plot", help="define plot or json")
    args = parser.parse_args()


    if args.option == "json":
        obj = MultiCapture('test').pickle_load(os.path.join(Settings.sim_save_path_graph, 'json_folder'), directory=True, json_format=True) # for converting json
    elif args.option == "plot":
        
        #plot_sub(os.path.join(Settings.sim_save_path, "inc_cap_gr_new"), capacity_change=True, box_plot=False, player_change=False, average_distance=False, weight_dict=None, algo_amount=2, normalize=False, ru_value=False, rc_value=True, rw_value=False, directory=True)
        #plot_sd(os.path.join(Settings.sim_save_path_graph, 'inc_sd_test6'), y_axis="step_ratio")
        #plot_result(os.path.join(Settings.sim_save_path_graph, "testpython"), plot_values="player", y_axis = "ru")
        #plot_others(os.path.join(Settings.sim_save_path, "inc_cap_test11"), plot_values="cap", y_axis="rc", box_plot=None, avg_player=False, horizontal=False, scatter=False, tTest=False, error_bar=False, save=True, normalize=False, combine_graph=False)

        #road utilization shows that we are not exploring the different cells beacuse we tend to visit same cells regardless of increase in capactiy

        #plot_result_graph(os.path.join(Settings.sim_save_path_graph, "timeseries"), plot_values="player", y_axis = "ru")



        plot_others_graph(os.path.join(Settings.sim_save_path_graph, "inc_cap_multiple"), plot_values="cap", y_axis="rw", box_plot="cap", avg_player=False, horizontal=False, scatter=False, tTest=False, error_bar=False, save=True, normalize=False, combine_graph=False, ylim=None)

        #plot_time_series(os.path.join(Settings.sim_save_path_graph, "fiftest"), y_axis="rw")



