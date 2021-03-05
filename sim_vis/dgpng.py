# dgpng.py
# Author: Quentin Goss
# Creates a .png image from SUMO map data
import xml.etree.ElementTree as ET
import sys
import os
import pickle
import math
import operator
from bisect import bisect_left
from PIL import Image, ImageDraw
import json
import numpy as np

def main():
    global OPTIONS; OPTIONS = get_options(); validate_options()
    global EDGES; global NODES; global NODE_INT_IDS
    if OPTIONS.load == None:
        EDGES = []; load_edges()
        NODES = []; load_nodes()
        NODES.sort(key=operator.attrgetter('int_ID'))
        NODE_INT_IDS = []; node_int_ids()
        EDGES = update_edges()
    else:
        EDGES, NODES = load()
    if not OPTIONS.color_ssv == None:
        load_colors()
    if OPTIONS.bw:
        force_bw()
    if not OPTIONS.no_png:
        draw_png()
    if not OPTIONS.save == None: save()
    print('COMPLETE!')
    return

# Parse arguments from Command Line
def get_options():
    from optparse import OptionParser
    parser = OptionParser()
    #
    parser.add_option('--version', dest='version', action="store_true", default=False, help="Shows version information.")
    # Files
    parser.add_option('-e','--edg.xml', dest='edg_xml', type='string', default=None, help='*.edg.xml file.')
    parser.add_option('-n','--nod.xml', dest='nod_xml', type='string',default=None, help='*.nod.xml file.')
    parser.add_option('-o','--png', dest='png', type='string', default='dg.png', help='The path of the img that is output.')
    # Update Colors
    parser.add_option('--color.ssv',dest='color_ssv',type='string',default=None,help='Color rules file. Use if you want to specify colors for individual items.\nThe first line must be TYPE,ID,COLOR\nAs an example EDGE:\nEDGE road1 (255,0,0,255)\nAs an example NODE:\nNODE junct5 (0,255,0,255)')
    # Saving/Loading
    parser.add_option('-x','--save', dest='save', type='string', default=None, help='Filepath to a file to store exported graph data that can be loaded later.')
    parser.add_option('-l','--load', dest='load',
    type='string', default=None, help='Filepath to a file to import graph data.')
    # Image
    parser.add_option('--padding',dest='padding',type='int',default=10,help='Paddind around the canvas in px')
    parser.add_option('--directional-arrows',dest='directional_arrows',default=False,action='store_true',help='Enable directional arrows on lines (EXPERIEMENTAL)')
    parser.add_option('--no-png',dest='no_png',default=False,action='store_true',help='Do not create a .png')
    # Scale
    parser.add_option('-s','--scale',dest='scale',type='int',default=100,help='Scale of the image. Increase or degrease distance between nodes')
    # Colors
    parser.add_option('--edge-color', dest='edge_color', type='string', default='(0,0,0,255)', help='Color of edges (R,G,B,A)')
    parser.add_option('--node-color',dest='node_color', type='string', default='(0,0,0,255)', help='Color of nodes (R,G,B,A)')
    parser.add_option('--internal-node-color', dest='internal_node_color', type='string', default='(0,0,0,255)', help='Color of internal nodes (R,G,B,A)')
    parser.add_option('--background-color', dest='background_color', type='string', default='(0,0,0,0)', help='Background Color (R,G,B,A)')
    parser.add_option('--bw',dest='bw',default=False,action='store_true',help='Force Black and White. Will still retain alpha.')
    # Thickness
    parser.add_option('--edge-thickness', dest='edge_thickness', type='int', default=1, help='Thickness of edges in px')
    #parser.add_option('--node-thickness', dest='node_thickness', type='int', default=1, help='Thickness of nodes in px')
    #parser.add_option('--internal-node-thickness', dest='internal_node_thickness', type='int', default=1, help='Thickness of internal nodes in px')
    # Diameter
    parser.add_option('--node-diameter', dest='node_diameter', type='int', default=2, help='Node diameter in px')
    parser.add_option('--internal-node-diameter', dest='internal_node_diameter', type='int', default=1, help='Internal Node diameter in px')
    parser.add_option('--folder', dest="folder", type='string', default="./sims_json/reward", help='Folder contains rewards')

    # Text
    #parser.add_option('--edge-weight-label', dest='edge_weight_label'
    #
    (options,args) = parser.parse_args()
    return options

# Validate Options
def validate_options():
    if OPTIONS.edg_xml == None:
        print('Must specify an *.edg.xml file with -e.')
        sys.exit(0)
    elif OPTIONS.nod_xml == None:
        print('Must specify a *.nod.xml file with -n.')
        sys.exit(0)
    elif not OPTIONS.color_ssv == None:
        with open(OPTIONS.color_ssv,'r') as ssv:
            for line in ssv:
                if not line.strip() == 'TYPE ID COLOR':
                    print("""Invalid color.ssv file.\nThe first line must be TYPE,ID,COLOR\nAs an example EDGE:\nEDGE road1 (255,0,0,255)\nAs an example NODE:\nNODE junct5 (0,255,0,255)""")
                    sys.exit(0)
                break
                
    if OPTIONS.version:
        version_banner()
    return

# Version Banner
def version_banner():
    print('dgpng Version 3.0 by Quentin Goss')
    print('Creates a .png from a SUMO map.')
    return

# Classes
class Node(object):
    def __init__(self,x=None,y=None,ID=None,internal=False,color=None):
        self.x = x      # float(x coordinate)
        self.y = y      # float(y coordinate)
        self.ID = ID    # ID (Internal nodes have no ID)
        self.internal = internal # Bool Internal Node or Node?
        if color == None:        # Color
            if self.internal:
                self.color = str2rgba(OPTIONS.internal_node_color)
            else:
                self.color = str2rgba(OPTIONS.node_color)
        else:
            self.color = color
        
        try:
            self.int_ID = int(''.join(str(ord(c)) for c in self.ID))
        except:
            self.int_ID = 0
        self.redraw = False
        
        
class Edge(object):
    def __init__(self,node_from,node_to,weight,ID=None,color=None):
        self.node_from = node_from  # From
        self.node_to = node_to      # To
        self.weight = weight        # Weight
        self.ID = ID                # ID
        if color == None:           # Color
            self.color = str2rgba(OPTIONS.edge_color)
        else:
            self.color = color          
        self.redraw = False

# Checks if a given xml object has an attribute
# @param ElementTree-xml-object xml = xml tag
# @param string attrib =  attribute to check the existence of
# @return True if exists, False otherwise
def xml_has_atrribute(xml,attrib):
    try:
        len(xml.attrib[attrib])
        return True
    except:
        pass
    return False

# Loads the edges from file
def load_edges():
    # XML file loading
    tree = ET.parse(OPTIONS.edg_xml)
    root = tree.getroot()
    
    # Iterate through all edge tags.
    for edge in root.findall('edge'):
        
        # If the edge has a 'from' and a 'to' attribute, then it is valid
        if xml_has_atrribute(edge,'from') and xml_has_atrribute(edge,'to'):            
            # Does the edge have a shape?
            # Yes -  We make internal nodes for the middle coordinate pairs
            #  and connections to them.
            if xml_has_atrribute(edge,'shape'):
                edge_with_shape(edge)
            
            # No - We'll have to look up in the nod.xml file to get the
            #   coordinates. We do know what the IDs of the from and to
            #   nodes are, so we'll add them to the Edge object.
            else:
                edge_without_shape(edge)
        continue
    return

# Determines the weight of the edge by counting the number of lanes
# @param edge = xml tag
# @return int weight = The number of <lane> children
def weight(edge):
    n_lanes = 0; weight = 1
    for lane in edge: n_lanes += 1
    if n_lanes > 0: weight = n_lanes
    return weight

# Performs operations on an edge without a shape
# @param edge = xml tag
def edge_without_shape(edge):
    EDGES.append(
        Edge(
            Node(ID=edge.attrib['from']),
            Node(ID=edge.attrib['to']),
            weight(edge),
            ID = edge.attrib['id'],
            color = str2rgba(OPTIONS.edge_color)
        )
    )
    return

# Performs operations on an edge with a shape
# @param edge = xml tag
def edge_with_shape(edge):
    # Clean the string and split it up into xy pairs
    shape = edge.attrib['shape'].strip().split(' ')
    
    # For each xy pair
    index = 0; index_of_last = len(shape)-1; prev_node = None
    for xy in shape:
        
        # Retrieve the x,y values and cast them to float
        x,y = xy.split(','); x = float(x); y = float(y)
        
        # If this is the first or last coordinate pair, then
        #   they get IDs and they aren't Internal
        ID = None; internal = True
        color = str2rgba(OPTIONS.internal_node_color)
        if index == 0:
            ID = edge.attrib['from']
            internal = False
            color = str2rgba(OPTIONS.node_color)
        elif index == index_of_last:
            ID = edge.attrib['to']
            internal = False
            color = str2rgba(OPTIONS.node_color)
        
        # Create the edges that are between the internal nodess
        if index > 0: prev_node = node
        node = Node(ID=ID,internal=internal,x=x,y=y, color=color)
        if index > 0:
            EDGES.append(
                Edge(
                    prev_node,
                    node,
                    weight(edge),
                    ID=edge.attrib['id'],
                    color=str2rgba(OPTIONS.edge_color)
                )
            )
        
        # Increment index
        index += 1
        continue
    return
    
# Loads the nodes from file
def load_nodes():
    # XML file loading
    tree = ET.parse(OPTIONS.nod_xml)
    root = tree.getroot()
    
    # Iterate through all node tags.
    for node in root.findall('node'):
        
        # A valid node has 'id', 'x', and 'y'
        if xml_has_atrribute(node,'id') and xml_has_atrribute(node,'x') and xml_has_atrribute(node,'y'):
            
            # Construct a node object and append it to the list of nodes
            NODES.append(
                Node(
                    ID = node.attrib['id'],
                    x = float(node.attrib['x']),
                    y = float(node.attrib['y']),
                )
            )
        continue
    return

# We weren't able to determine the coordinates 
# @return updated_edges = A list of updated edges
def update_edges():
    # Updated edges will go here. To update EDGES at the end
    updated_edges = []
    
    # Consider each edge
    n = 0; total = len(EDGES)
    for edge in EDGES:
        # Node from
        if edge.node_from.x == None or edge.node_from.y == None:
            try:
                edge.node_from = NODES[index(NODE_INT_IDS,edge.node_from.int_ID)]
            except ValueError:
                for node in NODES:
                    if edge.node_from.ID == node.ID:
                        edge.node_from = node; break
            
        # Node to
        if edge.node_to.x == None or edge.node_to.y == None:
            try:
                edge.node_to = NODES[index(NODE_INT_IDS,edge.node_to.int_ID)]
            except ValueError:
                for node in NODES:
                    if edge.node_to.ID == node.ID:
                        edge.node_to = node; break
            
        # Add the updated edge to the list of updated edges
        updated_edges.append(edge)
        n += 1; print('Generating Map %6.2f%%' % (float(n)/float(total)*100),end='\r')
        continue
    print()
    return updated_edges

# Determine Width/Height of the img.
# @return (int(width),int(height)) of the image
def img_width_height():
    #We obtain all of the x and y values for each node
    x = []; y = []
    for node in NODES:
        x.append(int(node.x)); y.append(int(node.y))
    
    # Then the take the largest of those lengths and heights
    # We consider padding on two sides
    img_width  = max(x) - min(x) + 5 * OPTIONS.padding
    img_height = max(y) - min(y) + 5 * OPTIONS.padding
    
    # The return should be a tuple
    return (int(img_width),int(img_height))

# Parses an (R,B,G,A) string into a tuple of ints
# @param string rgba = (R,B,G,A) as a string
# @return (int(red),int(green),int(blue),int(alpha))
def str2rgba(rgba):
    red,green,blue,alpha = rgba.strip('()').split(',')
    return ( int(red),int(green),int(blue),int(alpha) )

# Determines offset of x and y coordinates
# @return ( int(offset_x),int(offset_y) )
def node_offset():
    # We'll obtain all of the x and y values from each node
    x = []; y = []
    for node in NODES:
        x.append(int(node.x)); y.append(int(node.y))
    
    # The offset is the smallest of these values
    offset_x = min(x) - OPTIONS.padding
    offset_y = min(y) - OPTIONS.padding
    
    # Return a is a tuple of ints
    return (offset_x,offset_y)

# Draw the PNG
def draw_png():
    # Initialize Img
    width, height = img_width_height()
    img = Image.new('RGBA',(width,height),str2rgba(OPTIONS.background_color))
    
    # Draw the data
    draw = ImageDraw.Draw(img)
    
    draw_shapes(draw)
    draw_shapes(draw,redraw=True, reward=True)
    
    # Save img to file
    img.save(OPTIONS.png,'PNG')
    return

def norm(min_sub_value, max_sub_value, min_value, max_value, value):

    #print(f"{max_sub_value} {min_sub_value} {value} {min_value} {max_value}")
    #print("after")

    return ((max_sub_value - min_sub_value)*((value-min_value)/(max_value - min_value)))+(min_sub_value) 


    
def draw_shapes(draw,redraw=False,reward=False):
    width, height = img_width_height()
    #
    class offset: x,y = node_offset()
    class center: x,y = (None,None)
    # Statistics
    n = 0; total = len(EDGES)

    data = None

    try:
        if reward:
            print("Reward needed searching for reward file.....")
            with open(os.path.join(OPTIONS.folder, "reward.json"), "r") as f:

                oj_data = json.load(f)
                

                values = list(oj_data.values())


                #data = {f"cell{key}": norm(0, 255, min(values), max(values), value) for key, value in data.items()}
                data = {key: norm(0, 255, min(values), max(values), value) for key, value in oj_data.items()}


                size_data = {key: norm(1, 100, min(values), max(values), value) for key, value in oj_data.items()}

                #print(data)
                

    except FileNotFoundError:
        print("Asking to trace rewards but no file found...")

    for edge in EDGES:

        #print(f"test from {edge.node_from.ID} to edge: {edge.node_to.ID}")
        # Draw edge
        x0 = int(edge.node_from.x - offset.x)
        y0 = int(edge.node_from.y - offset.y)
        x1 = int(edge.node_to.x - offset.x)
        y1 = int(edge.node_to.y - offset.y)
        
        # Since SUMO's y=0 is at the bottom and an images y=0
        #  is at the top, the y values should be inverted
        y0 = height - y0; y1 = height - y1
        
        # Draw the edge
        if (not redraw) or (redraw and edge.redraw):
            draw.line(
                (x0,y0,x1,y1),
                width = OPTIONS.edge_thickness,
                fill = edge.color
            )
        
        # Draw Nodes
        for node in (edge.node_from,edge.node_to):


            if (not redraw) or (redraw and node.redraw):
                # Center of the circle
                center.x = node.x - offset.x
                center.y = node.y - offset.y
                
                # Since SUMO's y=0 is at the bottom and an images y=0
                #  is at the top, the y values should be inverted
                center.y = height - center.y
                
                # Radius and Color
                r = OPTIONS.node_diameter
                # Internal Node variation
                if node.internal:
                    r = OPTIONS.internal_node_diameter
                    
                # Draw the circle
                draw.ellipse(
                    (center.x-r,center.y-r,center.x+r,center.y+r),
                    outline = node.color
                )
            if data:
                try:
                    data[node.ID]
                    dia = size_data[node.ID]

                    #dia = 100

                    center.x = node.x - offset.x
                    center.y = node.y - offset.y
                    
                    # Since SUMO's y=0 is at the bottom and an images y=0
                    #  is at the top, the y values should be inverted
                    center.y = height - center.y

                    params = (center.x-dia, center.y-dia, center.x+dia, center.y+dia)
                    print(f"Drawing reward at {params} size:{dia} opacity: {int(data[node.ID])}")


                    draw.ellipse(
                        params,
                        outline = (255,0, 0, 255),#node.color
                        fill=(255,0,0,int(data[node.ID]))
                    )   

                    #print()
                except KeyError:
                    pass
                    #print(f"{node.ID} not in datalist")

            continue
            
        # Progress update
        n += 1
        print('Drawing %6.2f%%' % (float(n)/float(total)*100),end='\r')
        continue
    print()
    return
    
def save():
    print('Saving map to %s' % (OPTIONS.save))
    with open(OPTIONS.save,'wb') as f:
        pickle.dump([EDGES,NODES],f)
    return
    
def load():
    print('Loading map from %s' % (OPTIONS.load))
    with open(OPTIONS.load,'rb') as f:
        EDGES , NODES = pickle.load(f)
    return (EDGES, NODES)

# Load a color definition file (slow)
def load_colors():
    # Read through the file once to get the total
    with open(OPTIONS.color_ssv,'r') as ssv:
        total = 0;
        for line in ssv:
            total += 1
    
    # Now load the colors
    n = 0
    with open(OPTIONS.color_ssv,'r') as ssv:
        for line in ssv:
            # Skip the first line
            if n == 0:
                n += 1; continue
                
            # Retrieve the info
            _type,ID,color = line.strip().split(' ')
            color = str2rgba(color)
            
            if _type == 'EDGE':
                # Find the edge and update
                for i in range(len(EDGES)):
                    if ID == EDGES[i].ID:
                        EDGES[i].color = color
                        EDGES[i].redraw = True
                        break
            
            elif _type == 'NODE':
                # Find the node and update
                for i in range(len(EDGES)):
                    if ID == EDGES[i].node_from.ID:
                        EDGES[i].node_from.color = color
                        EDGES[i].node_from.redraw = True
                    elif ID == EDGES[i].node_to.ID:
                        EDGES[i].node_to.color = color
                        EDGES[i].node_to.redraw = True
            
            # Progress update
            n += 1
            print('Updating Colors %6.2f%%' % (float(n)/float(total)*100),end='\r')
            continue
    print()
    return

# Def Adds a directional Arrow
# @param draw = canvas that's being drawn to
# @param Edge edge = edge
# @param x0, y0, x1, y1 = coordinates
def directional_arrow(draw,edge,x0,y0,x1,y1):
    hypotenuse = math.sqrt( (x1-x0)**2 + (y1-y0)**2 )
    print(hypotenuse)
    return

# Populates a list of node.int_IDS
def node_int_ids():
    for node in NODES:
        NODE_INT_IDS.append(node.int_ID)
    return

# Binary search
# @param [int] lst = List of integers
# @param int el = element that is being looked for 
def index(lst,el):
    # Locate the leftmost value exactly equal to x
    i = bisect_left(lst,el)
    if i != len(lst) and lst[i] == el:
        return i
    raise ValueError

# Makes everything Black and White but keeps alpha.
def force_bw():
    for edge in EDGES:
        edge.color = (0,0,0,edge.color[3])
        edge.node_from.color = (0,0,0,edge.node_from.color[3])
        edge.node_to.color = (0,0,0,edge.node_to.color[3])
    return

main()
