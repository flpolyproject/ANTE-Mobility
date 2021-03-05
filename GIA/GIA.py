
# Cooperative incentive Mechanism for recurrent Crowd Sensing
# Simulation
# Ian Bishop
# Additional comments by Trevor Hillsgrove (explanatory in nature)

import random
import math
import numpy
import functools
from numpy import random as rand
import matplotlib.pyplot as plt

import traci
import traci.constants as tc

# constant simulation parameters
AREA_WIDTH = 500
#defined as good radius to use in text
RADIUS = 500

active_users = []
active_users_min = []

#for saving information about the icm and gia rounds

class RoundMetadata:
    def __init__(self):
        pass  #no initialization stuff, just storing data
    totalUsers = 0
    icmActive = []
    icmTotal = []
    giaActive = []
    giaTotal = []


'''

class GIAClass(object):
    def __init__(self):
        self.roundInfo = RoundMetadata()
        self.AREA_WIDTH = 500
        self.RADIUS = 500
        self.active_users = []
        self.all_users = None

    def GIAmap(self, veh_data, budget=500, roi_th=0.5,eroi_th=0.5):
        for user in self.all_users:
            user.pos_x = veh_data[user.name][tc.VAR_POSITION][0]
            user.pos_y = veh_data[user.name][tc.VAR_POSITION][1]
            
        maxwin = 0
        #grab list of winners from gia algorithm
        winners = Gia(active_users,budget)
        #adding earned amount to users
            
        #checking to see if a user needs to drop out; then checking rejoin mechanism
        for user in all_users:
            if user in winners:
                # winner


                if(user.bid > maxwin):
                    maxwin = user.bid
                user.earned+=user.bid
                user.participation+=1
                if bool(random.getrandbits(1)):
                    user.bid += (user.bid * 0.10) #50 % chance the winner

                user.vpc = 0


            else:
                #active users who are not winners
                if user in active_users:
                    # loser


                    user.participation+=1
                    # ROI calculation
                    roi = Roi(user)
                    if roi < roi_th:
                        # drop
                        active_users.remove(user)

                    user.vpc += 0.5
                    user.bid -= (user.bid *0.20)
                    user.bid -= user.vpc

                else:
                    #not participating
                    # rejoin mechanism
                    #calculates expected return of investment
                    eroi = Eroi(user, maxwin)
                    #exptected return greater than threshold
                    #print("eroi "+str(eroi)+" eroi_th "+str(eroi_th))
                    if eroi > eroi_th:
                        #print("Trying to rejoin")
                        #probability of rejoining, if above 0.5 the user will decide to rejoin. (50/50 chance)
                        if random.random() > 0.5:
                            active_users.append(user)
        return all_users, winners

   
'''








roundInfo = RoundMetadata()


users_set = []

# Incentive Cooperative Mechanism

#roi_th is return of investment threshold, used to tell if a user is dropping out or not
#eroi_th is expected return of investment; if is greater than this threshold then a losing participant will rejoin, included
#in set of active participants
def Icm(budget=500,instances=100,num_rounds=10,roi_th=0.5,eroi_th=0.5,graph=False,move=False):
    print("Running ICM\n")
    #setting up all the users randomly, places users into all_users array
    all_users = setupUsers(instances)
    # print("active users:",len(active_users))
    # round simulation
    #for number of rounds to test with
    for r in range(num_rounds):
        #maximum winnings; this is utilized in the rejoin mechanism eroi function to save the maximum win within a round
        maxwin = 0
        #greedy incentive algorithm called, with current active users and budget, returns who won
        winners = Gia(active_users,budget)
        # print("round:",r,"winners:",len(winners))
        # give bids first
        for winner in winners:
            #this saves the maximum won per round to maxwin
            if(winner.bid > maxwin):
                maxwin = winner.bid
            winner.earned+=winner.bid
            #winner negotiation algorithm called with whatever winner won, and all neighbors within radius of the winner
            #(who are active)
            Wna(winner, GetNeighbors(winner, active_users))
        #decides if a user stays in or not
        for user in all_users:
            if user in winners:
                # winner
                user.participation+=1
            else:
                #active users who are not winners
                if user in active_users:
                    # loser
                    user.participation+=1
                    #winner's neighbor negotiation algorithm called using the loser user and their neighbors
                    # to see what all rewards they get, sets their bid amount.
                    #A loser may be able to get rewards from many different users
                    user.bid = Wnna(user, GetNeighbors(user, active_users))
                    # ROI calculation
                    roi = Roi(user)
                    if roi < roi_th:
                        # drop
                        active_users.remove(user)
                    #eval roi
                    #NOTE: where is the addition of bid to earnings, if they accept the deal?  Check this
                else:
                    #not participating
                    # rejoin mechanism
                    #calculates expected return of investment
                    eroi = Eroi(user, maxwin)
                    #exptected return greater than threshold
                    #print("eroi "+str(eroi)+" eroi_th "+str(eroi_th))
                    if eroi > eroi_th:
                        #print("Trying to rejoin")
                        #probability of rejoining, if above 0.5 the user will decide to rejoin. (50/50 chance, or close enough)
                        if random.random() > 0.5:
                            active_users.append(user)
        #loops through all winners, uses winner negotiation algorithm decision & resets the user bid to that value
        for winner in winners:
            winner.bid = WnaDesicion(winner, GetNeighbors(winner, active_users))
        #moves a user after each round if implemented, generates graph if move set to true
        if move:
            #in charge of moving users after a round is completed; useful when doing multiple rounds
            moveUsers(graph, all_users, True)
            
    # print([all_users[i].pos_x for i in range(len(all_users))],"\n",[all_users[i].pos_y for i in range(len(all_users))])
    #final graphing of all users
    if graph:
        graph_users(all_users)



def GIAmap(all_users, veh_data,  budget=500, roi_th=0.5,eroi_th=0.5):
    global active_users
    #maximum winnings; this is utilized in the rejoin mechanism eroi function to save the maximum win within a round
    for user in all_users:
        try:
            user.pos_x = veh_data[user.name][tc.VAR_POSITION][0]
            user.pos_y = veh_data[user.name][tc.VAR_POSITION][1]
        except KeyError:
            pass
        
    maxwin = 0
    #grab list of winners from gia algorithm
    winners = Gia(active_users,budget)
    #adding earned amount to users
        
    #checking to see if a user needs to drop out; then checking rejoin mechanism
    for user in all_users:
        if user in winners:
            # winner


            if(user.bid > maxwin):
                maxwin = user.bid
            user.earned+=user.bid
            user.participation+=1
            if bool(random.getrandbits(1)):
                user.bid += (user.bid * 0.10) #50 % chance the winner

            user.vpc = 0


        else:
            #active users who are not winners
            if user in active_users:
                # loser


                user.participation+=1
                # ROI calculation
                roi = Roi(user)
                if roi < roi_th:
                    # drop
                    active_users.remove(user)

                user.vpc += 0.5
                user.bid -= (user.bid *0.20)
                user.bid -= user.vpc

            else:
                #not participating
                # rejoin mechanism
                #calculates expected return of investment
                eroi = Eroi(user, maxwin)
                #exptected return greater than threshold
                #print("eroi "+str(eroi)+" eroi_th "+str(eroi_th))
                if eroi > eroi_th:
                    #print("Trying to rejoin")
                    #probability of rejoining, if above 0.5 the user will decide to rejoin. (50/50 chance)
                    if random.random() > 0.5:
                        active_users.append(user)
    return all_users, winners, len(active_users)



def choose_min(all_users, veh_data, budget=500, roi_th=0.5,eroi_th=0.5):
    global active_users_min
    for user in all_users:
        try:
            user.pos_x = veh_data[user.name][tc.VAR_POSITION][0]
            user.pos_y = veh_data[user.name][tc.VAR_POSITION][1]
        except KeyError:
            pass


    maxwin = 0
    #grab list of winners from gia algorithm
    

    winners = sorted(active_users_min, key=lambda x: x.bid)

    final_winners = []

    for win in winners:
        if win.bid <= budget:
            budget -= win.bid
            final_winners.append(win)
        else:
            break

    for user in all_users:
        if user in final_winners:
            # winner


            if(user.bid > maxwin):
                maxwin = user.bid
            user.earned+=user.bid
            user.participation+=1
            if bool(random.getrandbits(1)):
                user.bid += (user.bid * 0.10) #50 % chance the winner

            user.vpc = 0


        else:
            #active users who are not winners
            if user in active_users_min:
                # loser


                user.participation+=1
                # ROI calculation
                roi = Roi(user)
                if roi < roi_th:
                    # drop
                    active_users_min.remove(user)

                user.vpc += 0.5
                user.bid -= (user.bid *0.20)
                user.bid -= user.vpc

            else:
                #not participating
                # rejoin mechanism
                #calculates expected return of investment
                eroi = Eroi(user, maxwin)
                #exptected return greater than threshold
                #print("eroi "+str(eroi)+" eroi_th "+str(eroi_th))
                if eroi > eroi_th:
                    #print("Trying to rejoin")
                    #probability of rejoining, if above 0.5 the user will decide to rejoin. (50/50 chance)
                    if random.random() > 0.5:
                        active_users_min.append(user)



    return all_users, final_winners, len(active_users_min)









#this is meant for simulating rounds within the GIA algorithm.  The regular gia algorithm is meant to work with Icm
#however, we need a standalone simulation too.  That's where this comes in at.  It calls many of the same functions
#icm does; just in a similar manner to the icm Simulation
def GIAsimul(budget=500, instances=100, num_rounds=10,roi_th=0.5,eroi_th=0.5, graph=False, move=False):


    #wtf moments in this function
    #the budget should be evenly distributed to each round. budget for each round = budget/instances where is that?
    #the left over budget from previous rounds should be passed into the next round? where is that?


    print("Running GIA simulation")
    #setting up all the users randomly, places users into all_users array
    all_users = setupUsers(instances)
    #going through rounds within GIA
    for r in range(num_rounds):
        #maximum winnings; this is utilized in the rejoin mechanism eroi function to save the maximum win within a round
        maxwin = 0
        #grab list of winners from gia algorithm
        winners = Gia(active_users,budget)
        #adding earned amount to users
        for winner in winners:
            #this saves the maximum won per round to maxwin    ???? why loop it twice
            if(winner.bid > maxwin):
                maxwin = winner.bid
            winner.earned+=winner.bid
        #checking to see if a user needs to drop out; then checking rejoin mechanism
        for user in all_users:
            if user in winners:
                # winner
                user.participation+=1
            else:
                #active users who are not winners
                if user in active_users:
                    # loser
                    user.participation+=1
                    # ROI calculation
                    roi = Roi(user)
                    if roi < roi_th:
                        # drop
                        active_users.remove(user)
                else:
                    #not participating
                    # rejoin mechanism
                    #calculates expected return of investment
                    eroi = Eroi(user, maxwin)
                    #exptected return greater than threshold
                    #print("eroi "+str(eroi)+" eroi_th "+str(eroi_th))
                    if eroi > eroi_th:
                        #print("Trying to rejoin")
                        #probability of rejoining, if above 0.5 the user will decide to rejoin. (50/50 chance)
                        if random.random() > 0.5:
                            active_users.append(user)
        #moves a user after each round if implemented, generates graph if move set to true
        if move:
            #in charge of moving users after a round is completed; useful when doing multiple rounds
            moveUsers(graph, all_users, False)
    #final graphing of all users
    if graph:
        graph_users(all_users)
    

def graph_users(all_users):
    xpoints=[]
    ypoints=[]
    cols=[]
    #loop through all users
    lengthActive = len(active_users)
    lengthInactive = len(all_users)-len(active_users)
    #print("active users: "+str(lengthActive)+"\n")
    #print("inactive users: "+str(lengthInactive)+"\n")
    for i in range(len(all_users)):
        #adds the user coords to points to respective array
        xpoints.append(all_users[i].pos_x)
        ypoints.append(all_users[i].pos_y)
        #puts black descriptor on a user if it is active, otherwise labels as white
        cols.append("black" if active_users.count(all_users[i])>0 else "white")
    #creates a scatter plot with given user coords and color
    plt.scatter(xpoints,ypoints,c=cols)
    #sets x,y limits of current tick locations/labels. (x/y axis markers, every 20 to end it adds a marker)
    #plt.xticks(range(0, AREA_WIDTH+1, 20))
    #plt.yticks(range(0, AREA_WIDTH+1, 20))
    plt.show()

def clamp(num, minNum, maxNum):
    return min(max(num,minNum),maxNum)

# Neighbor discovery 
def GetNeighbors(user, active_users):
    neighbors = []
    #loop through all active users
    for au in active_users:
        #user is not current user, checks distance between current user and testing user, if close enough is a neighbor
        if user != au:
            if Distance(au,user) <= RADIUS:
                neighbors.append(au)
    return neighbors
     
#goes through every user, checks if it was covered, if it was within the radius, and if it is not the passed user
#0 on fail, 1 on pass
def NumUncoveredNeigbors(user, active_users):
    ns = 0
    for au in active_users:
        if not au.covered:
            if Distance(au,user) <= RADIUS:
                if user != au:
                    ns+=1
    return ns

# Return on Investment
def Roi(user):
    tolerance = 0
    # print(user.earned, user.participation, user.true_valuation)
    return (user.earned + tolerance) / (user.participation * user.true_valuation + tolerance)

# Expected return on Investment
def Eroi(user, maxwinIn):
    tolerance = 0
    #CHANGED user.min_profit to the maximum won per round.  This is saved at the top of the round loop
    #print("total earned: "+str(user.earned)+" maxwin "+str(maxwinIn)+" user.participation "+str(user.participation)+" user.true_valuation: "+str(user.true_valuation))
    #old statement VVV
    #return (user.earned + user.min_profit + tolerance) / ((user.participation + 1)* user.true_valuation + tolerance)
    return (user.earned + maxwinIn + tolerance) / ((user.participation + 1)* user.true_valuation + tolerance)

# Greedy Area Prices
def GAP(active_users, budget):
    g=[]
    c=0
    u=[u for u in active_users]  #only processing active users here ?????? what is this omg why iterate over it againe if active user already in list 
    total_w = 0
    while(len(u)>0):
        # select user that maximizes w'/c
        max_wu = 0
        su = u[0]
        for user in u:
            #denote the total number of elements covered by set Si but not covered by any set in G = NumUncoveredNeighbors
            wu = NumUncoveredNeigbors(user, active_users) / (user.bid)
            if wu > max_wu:
                su = user   #select the user we want, eventually gets the max
                max_wu = wu
        # mark as winner if we can afford it
        if c+su.bid<=budget:
            g.append(su)
            c+=su.bid
            total_w+=NumUncoveredNeigbors(su, active_users)
            # mark self and neighbors as winners so they dont get recounted
            su.covered = True
            su_n = GetNeighbors(su,active_users)
            for n in su_n:
                n.covered = True
        u.remove(su)  #NOTE: in text says U' \ Sj, just means to remove that element
    return g, total_w
    
# Greedy Area
def GA(active_users, budget):
    g=[]
    c=0
    u=[u for u in active_users]
    total_w = 0
    while(len(u)>0):
        #select user that maximizes w'/c
        max_wu = 0
        su = u[0]
        for user in u:
            wu = NumUncoveredNeigbors(user, active_users)
            if wu > max_wu:
                su = user
                max_wu = wu
        if c+su.bid<=budget:
            g.append(su)
            c+=su.bid
            total_w+=NumUncoveredNeigbors(su, active_users)
            su_n = GetNeighbors(su,active_users)
            su.covered = True
            for n in su_n:
                n.covered = True
        u.remove(su)
    return g, total_w

# Greedy incentive algortihm (aka greedy budgeted maximum coverage algorithm for GIA)
def Gia(active_users,budget):
    #initializing, clearing stuff
    winners = []
    for user in active_users:
        user.covered = False
    G, wG = GAP(active_users,budget) #greedy area price(s) has been called
    #clearing stuff
    for user in active_users:
        user.covered = False
    Gp, wGp = GA(active_users,budget) #greedy area(s) has been called
    if wG>=wGp:
        winners = G
        # print("g won", wG, wGp)
    else:
        winners = Gp
        # print("g prime won", wG, wGp)
    return winners

#!!!Switching tracks from greedy to cooperative.  Greedy was backbone for cooperative, so had to define it first

# Winner negotiation algorithm
def Wna(user, neighbors):
    # no neighbors case
    if len(neighbors)==0:
        return
    r = user.bid - (user.true_valuation + user.min_profit)
    base_deal = r / sum ([1 / n.bid for n in neighbors])  #constant part of d (the base deal calculation), taken out here for simplicity
    user.deal_accepted = False
    for neighbor in neighbors:
        # compute deal to offer each neighbor
        deal = base_deal * (1 / neighbor.bid)  #final val of d  #CHANGED added () for order of operations
        neighbor.OfferDeal(deal,user)  #offer the calculated deal to the user

def WnaDesicion(user, neighbors):   #if the user actually accepts the deal, continuation of WNA algorithm
    if len(neighbors)==0:
        return user.bid
    if user.deal_accepted: # any were accepted
        min_bid = min([n.bid for n in neighbors])
        user.bid = (min_bid - user.bid) * (user.risk - 1) + min_bid
    else: #none accepted
        user.bid = (user.bid - user.true_valuation - user.min_profit) * (user.risk - 1) + user.bid
    user.deal_accepted = False
    return user.bid


# Winner's neighbor negotiation algorithm
def Wnna(user, neighbors):
    if len(neighbors)==0:
        return user.bid
    deal_sum = sum(user.deals)
    maxW = max([n.bid for n in neighbors])

    accepted = False
    if deal_sum > user.min_profit:
        accepted = True
    elif maxW < user.true_valuation + user.min_profit:
        accepted = True
    
    if accepted:
        user.bid = user.bid
        for dealer in user.deal_offerers:
            dealer.deal_accepted = True
    else:
        user.bid = (user.bid - user.true_valuation - user.min_profit) * (user.risk - 1) + user.bid
    user.deals = []
    user.deal_offerers = []
    return user.bid
    
#moves the users after a round is completed; specified in 2012 based paper
def moveUsers(graphIn, all_users, icmCheck):
    global roundInfo
    roundInfo.totalUsers = len(all_users)
    if(icmCheck):
        roundInfo.icmActive.append(len(active_users))
    else:
        roundInfo.giaActive.append(len(active_users))
    for au in all_users:
        max_move_speed = 4
        au.pos_x += rand.uniform(-max_move_speed,max_move_speed)
        au.pos_y += rand.uniform(-max_move_speed,max_move_speed)
        au.pos_x = clamp(au.pos_x, 0, AREA_WIDTH)
        au.pos_y = clamp(au.pos_y, 0, AREA_WIDTH)
    if graphIn:
        graph_users(all_users)
    else:
        lengthActive = len(active_users)
        lengthInactive = len(all_users)-len(active_users)
        #print("active users: "+str(lengthActive)+"\n")
        #print("inactive users: "+str(lengthInactive)+"\n")


def set_users(veh_data, algo_name): #veh_data consists {veh_id:vvalues}
    instances = len(veh_data)
    all_users = []
    #quarter of users
    quart = math.ceil(instances / 4)
    sig=10
    true_valuation_dist = []
    true_valuation_dist.extend(rand.normal(5,2,quart))
    true_valuation_dist.extend(rand.normal(10,2,quart))
    true_valuation_dist.extend(rand.normal(15,2,quart))
    true_valuation_dist.extend(rand.normal(20,2,quart))
    #clears out all of the active users
    global active_users
    global active_users_min
    active_users.clear()
    active_users_min.clear()


    for i , (veh_id, veh_value) in enumerate(veh_data.items()):
    
        user = User(veh_id)
        #user.pos_x = clamp(dep_distx[i],0,AREA_WIDTH)
        user.pos_x = veh_value[tc.VAR_POSITION][0]
        #sets user y value, constrains to correct boundaries
        user.pos_y = veh_value[tc.VAR_POSITION][1]
        user.true_valuation = true_valuation_dist[i]
        #creates risk value for user, float val
        user.risk = rand.uniform(0,1.0)
        #generates bid value for a user randomly, up to 1.5 of their base cost of services
        user.bid = rand.uniform(user.true_valuation,user.true_valuation*1.5)
        #sets earned amount to 0, participation counter to 0, appends to all users/active users
        user.earned = 0
        user.participation = 0
        all_users.append(user)
        if algo_name == "gia":
            active_users.append(user)

        else:
            active_users_min.append(user)

    #print(len(all_users))
    #graph_users(all_users)

    #exit()
    return all_users


        




#setting up what is required for generating random users; moved out if ICM class to be able to use with GIA as well
def setupUsers(instances):
    # random setup
    all_users = []
    #quarter of users
    quart = math.ceil(instances / 4)
    sig=10
    dep_distx = []
    #extend just adds elements to array
    #rand.normal gives normal distribution of random numbers, with (mean, standard deviation of distro, output of size
    #to be generated
    #randomly generates x coords around deployment distro laid out in paper
    dep_distx.extend(rand.normal(30, sig, quart))
    dep_distx.extend(rand.normal(80, sig, quart))
    dep_distx.extend(rand.normal(50, sig, quart))
    dep_distx.extend(rand.normal(90, sig, quart))
    dep_disty = []
    #randomly generates y coords around deployment distro laid out in paper
    dep_disty.extend(rand.normal(80, sig, quart))
    dep_disty.extend(rand.normal(80, sig, quart))
    dep_disty.extend(rand.normal(50, sig, quart))
    dep_disty.extend(rand.normal(30, sig, quart))
    #randomly generates true valuation for each of the users, divided into 4 groups, laid out in paper
    true_valuation_dist = []
    true_valuation_dist.extend(rand.normal(5,2,quart))
    true_valuation_dist.extend(rand.normal(10,2,quart))
    true_valuation_dist.extend(rand.normal(15,2,quart))
    true_valuation_dist.extend(rand.normal(20,2,quart))
    #clears out all of the active users
    global active_users
    active_users.clear()
    #for every user/instance
    for i in range(instances):
        #create user object
        user = User()
        #sets user x value, constrains to correct boundaries
        user.pos_x = clamp(dep_distx[i],0,AREA_WIDTH)
        #sets user y value, constrains to correct boundaries
        user.pos_y = dep_disty[i]
        #sets user true valuation
        user.true_valuation = true_valuation_dist[i]
        #creates risk value for user, float val
        user.risk = rand.uniform(0,1.0)
        #generates bid value for a user randomly, up to 1.5 of their base cost of services
        user.bid = rand.uniform(user.true_valuation,user.true_valuation*1.5)
        #sets earned amount to 0, participation counter to 0, appends to all users/active users
        user.earned = 0
        user.participation = 0
        all_users.append(user)
        active_users.append(user)
    
    return all_users

class User:
    def __init__(self, name):
        self.name = name
    bid = 0
    true_valuation = 0
    min_profit = 0
    participation = 0
    covered = False
    pos_x = 0
    pos_y = 0
    deals = []
    deal_offerers = []
    deal_accepted = False
    risk = 0
    earned = 0
    vpc =0


    def __str__(self):
        return  (self.name, self.pos_x, self.pos_y)

    def __repr__(self):
        return (f"{self.name}")

    def OfferDeal(self, deal, dealer):
        self.deals.append(deal)
        self.deal_offerers.append(dealer)

def Distance(userA, userB):
    x_dist = (userA.pos_x - userB.pos_x)
    y_dist = (userA.pos_y - userB.pos_y)
    return math.sqrt(x_dist*x_dist+y_dist*y_dist)

def num_covered(users):
    num=0
    for user in users:
        if user.covered:
            num+=1
    return num

# budget changes
def GraphA(fig):
    # active participants per budget (100-600)
    # 10 rounds, average of 50 tries
    xr = range(100,601,100)
    yvals = []
    iterations = 10
    for i in xr:
        avg_activeu = 0
        for j in range(iterations):
            Icm(budget=i)
            avg_activeu+=len(active_users)
        avg_activeu/=iterations
        yvals.append(avg_activeu)
        print(i,avg_activeu)
    fig.plot([x for x in xr],yvals)
    plt.xticks([x for x in xr])
    fig.set_xlabel('Budget')
    fig.set_title('GraphA')
    

# overpopulated
def GraphB(fig):
    # active participants per number of participants (10-100)
    # 10 rounds, average of 50 tries
    # fixed budget at 500
    xr = range(10,101,10)
    yvals = []
    iterations = 10
    for i in xr:
        avg_activeu = 0
        for j in range(iterations):
            Icm(instances=i)
            avg_activeu+=len(active_users)
        avg_activeu/=iterations
        yvals.append(avg_activeu)
        print(i,avg_activeu)
    fig.plot([x for x in xr],yvals)
    plt.xticks([x for x in xr])
    fig.set_xlabel('Initial Participants')
    fig.set_title('GraphB')
    

# coverage
def GraphC(fig):
    # covered participants per number of participants (10-600)
    # 10 rounds, average of 50 tries
    # covered participants will have a bid because they lost (or won)
    xr = range(50,601,50)
    yvals = []
    iterations = 10
    for i in xr:
        avg_coveredu = 0
        for j in range(iterations):
            Icm(instances=i)
            avg_coveredu+=num_covered(active_users)
        avg_coveredu/=iterations
        # make percentage
        avg_coveredu*=100/i
        yvals.append(avg_coveredu)
        print(i,avg_coveredu)
    fig.plot([x for x in xr],yvals)
    plt.xticks([x for x in xr])
    fig.set_xlabel('Initial Participants')
    fig.set_ylabel('Covered Participants')
    fig.set_title('GraphC')

# retention rate
def GraphD(fig):
    # active participants per number of rounds
    # average of 50 tries
    xr = range(5,51,5)
    yvals = []
    iterations = 10
    for i in xr:
        avg_activeu = 0
        for j in range(iterations):
            Icm(num_rounds=i)
            avg_activeu+=len(active_users)
        avg_activeu/=iterations
        yvals.append(avg_activeu)
        print(i,avg_activeu)
    fig.plot([x for x in xr],yvals)
    plt.xticks([x for x in xr])
    fig.set_xlabel('Num rounds')
    fig.set_title('GraphD')

# ROI impact
def GraphE(fig):
    # active participants per ROI (0.5 - 2)
    # 10 rounds, average of 50 tries
    xr = range(1,20,1)
    xr = [i/10 for i in xr]
    yvals = []
    iterations = 4
    for i in xr:
        avg_activeu = 0
        for j in range(iterations):
            Icm(roi_th=i)
            avg_activeu+=len(active_users)
        avg_activeu/=iterations
        yvals.append(avg_activeu)
        print(i,avg_activeu)
    fig.plot([x for x in xr],yvals)
    plt.xticks([x for x in xr])
    fig.set_xlabel('ROI Threshold')
    fig.set_title('GraphE')

#graphing the number of participants per round, with user movement shift enabled
#comparison between cooperative algorithm modeling and competitive algorithm modeling
def graphAlgComp(pltIn, numOfRounds, numOfParticipants):
    global roundInfo
    #sets the number of rounds and the number of participants to be run
    fig = pltIn.subplot(1, 1, 1)
    
    IcmSim = functools.partial(Icm, num_rounds = numOfRounds, instances = numOfParticipants)
    GIAsim = functools.partial(GIAsimul, num_rounds = numOfRounds, instances = numOfParticipants)
    
    IcmSim(graph=False, move=True)
    GIAsim(graph=False, move=True)
    roundInfo.icmActive.insert(0,numOfParticipants)
    roundInfo.giaActive.insert(0,numOfParticipants)
    fig.set_ylabel('Active Participants')
    fig.set_xlabel('Round #')
    fig.set_title('Active Participants per Round')
    pltIn.xticks( numpy.arange(0, numOfRounds+1, 5) )
    pltIn.yticks( numpy.arange(0, numOfParticipants+1, 5) )
    fig.plot(roundInfo.icmActive)
    fig.plot(roundInfo.giaActive)
    fig.legend(['ICM algorithm','GIA algorithm'])
    plt.show()
    
    #reset metadata back to original
    roundInfo.totalUsers = 0
    roundInfo.icmActive.clear()
    roundInfo.giaActive.clear()

def graphAlgCompAverage(trials, pltIn, numOfRounds, numOfParticipants):
    #set metadata values to start before working
    global roundInfo
    fig = pltIn.subplot(1, 1, 1)
    roundInfo.icmTotal.clear()
    roundInfo.giaTotal.clear()
    #initialize icmTotal and giaTotal arrays based on the total number of rounds
    roundInfo.icmTotal = [0] * numOfRounds
    roundInfo.giaTotal = [0] * numOfRounds
    
    #for all of the trials
    for x in range(trials):
        #running the actual simulations, with passed values
        IcmSim = functools.partial(Icm, num_rounds = numOfRounds, instances = numOfParticipants)
        GIAsim = functools.partial(GIAsimul, num_rounds = numOfRounds, instances = numOfParticipants)
        IcmSim(graph=False, move=True)
        GIAsim(graph=False, move=True)
        #inserting base case into the array
        roundInfo.icmActive.insert(0,numOfParticipants)
        roundInfo.giaActive.insert(0,numOfParticipants)
        #printing values
        #print("icm array")
        #print(roundInfo.icmActive)
        #print("gia array")
        #print(roundInfo.giaActive)
        #logging metadata for the round, resetting for next go
        roundInfo.totalUsers = 0
        #adding values in active array to total, will use this to find the average
        for i in range(numOfRounds):
            roundInfo.icmTotal[i]+=roundInfo.icmActive[i]
            roundInfo.giaTotal[i]+=roundInfo.giaActive[i]
        #printing values
        #print(roundInfo.icmTotal)
        #print(roundInfo.giaTotal)
        #resetting active arrays for next round
        roundInfo.icmActive.clear()
        roundInfo.giaActive.clear()
    #after the trials are done, gets the average based on the total active participants and the trial count
    for i in range(numOfRounds):
        roundInfo.icmTotal[i] = roundInfo.icmTotal[i] / trials
        roundInfo.giaTotal[i] = roundInfo.giaTotal[i] / trials
    print("icm array averaged")
    print(roundInfo.icmTotal)
    print("gia array averaged")
    print(roundInfo.giaTotal)
    #graphing the results
    fig.set_ylabel('Active Participants')
    fig.set_xlabel('Round #')
    fig.set_title('Average Active Participants per Round('+str(trials)+' Trials)')
    pltIn.xticks( numpy.arange(0, numOfRounds+1, 5) )
    pltIn.yticks( numpy.arange(0, numOfParticipants+1, 5) )
    fig.plot(roundInfo.icmTotal)
    fig.plot(roundInfo.giaTotal)
    fig.legend(['ICM algorithm average','GIA algorithm average'])
    plt.show()





def main():
    #Icm(graph=False, move=True, num_rounds=100)
    #GIAsimul(graph=False, move=True, num_rounds=100)
    #graphAlgComp(plt, 100, 100)
    graphAlgCompAverage(5, plt, 100, 100)
    
    return
    #stuff not executed, assuming was testing stuff below
    fig = plt.subplot(1,1,1)
    # fig.plot([1,2,3,3],[5,12,2,5])
    # plt.xticks([x for x in range(0,6)])
    # fig.set_xlabel('')
    fig.set_ylabel('Active Participants')
    fig.set_title('Graph')
    GraphE(fig)
    plt.yticks([y for y in range(0,101,10)])
    
    plt.show()

if __name__ == "__main__":
    main()
