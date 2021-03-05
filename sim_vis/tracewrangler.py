# tracewrangler.py
# Author: Quentin Goss
# Process a grid NSF trace into a 

# Options Validation
import sys


sys.path.append("./../subscribe")
# Input
import json
import xml.etree.ElementTree as ET

# Binary Search
import operator
from bisect import bisect_left

def main():
    # Get Command Line Arguments
    global OPTIONS; OPTIONS = get_options()
    validate_options()
    
    # Load the Edges from .edg.xml
    global EDGES; EDGES = {}; load_edges_new()
    
    # Quantify the edges for binary search
    #EDGES.sort(key=operator.attrgetter('key'))
    #global EDGE_KEYS; EDGE_KEYS = []
    #for edge in EDGES: EDGE_KEYS.append(edge.key)
    
    # Correlate the trace data with the edges
    navigate_trace()
    
    # Write the color.ssv file
    color_ssv()
    return

# Parse arguments from Command Line
def get_options():
    from optparse import OptionParser
    parser = OptionParser()
    #
    parser.add_option('--version', dest='version', action="store_true", default=False, help="Shows version information.")
    # Input
    parser.add_option('-t','--trace.json',type='string',default=None,dest='trace_json',help='Input trace.json')
    parser.add_option('-e','--edg.xml', dest='edg_xml', type='string', default=None, help='*.edg.xml file.')
    # Output
    parser.add_option('-o','--color.ssv',dest='color_ssv',type='string',default='color.ssv',help='Color rules file. Use if you want to specify colors for individual items.')
    # Colors
    parser.add_option('--edge-color', dest='edge_color', type='string', default='(255,0,0,255)', help='Color of edges (R,G,B,A)')
    parser.add_option('--node-color',dest='node_color', type='string', default='(255,0,0,255)', help='Color of nodes (R,G,B,A)')
    #
    (options,args) = parser.parse_args()
    return options

def validate_options():
    if OPTIONS.version:
        version_banner() 
        sys.exit(1)
    elif OPTIONS.trace_json == None or not('.json' in OPTIONS.trace_json):
        print('Please specify a .json file using -i or --input-trace.')
        sys.exit(0)
    if OPTIONS.edg_xml == None:
        print('Must specify an *.edg.xml file with -e.')
        sys.exit(0)
    return
    
def version_banner():
    print('tracewrangler.py version 1.0')
    print('author: Quentin Goss')
    print('Wrangles NSF trace data into a format that dgpng can use.')
    print('Requires a .json NSF trace and .edg.xml file')
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

# Generates an integer by concatenating ascii values
# @param s = string of characters    
def ascii2int(s):
    return int(''.join(str(ord(c)) for c in s))

# Decodes a JSON object from file.
# @param string _file = filepath
# @return dictionary data = JSON data
def decode_json(_file):
    import json
    with open(_file,'r') as f:
        data = json.load(f)
    return data

class Edge(object):
    def __init__(self,eid,nid_from,nid_to):
        self.eid = eid           # Edge ID
        self.nid_from = nid_from # Node ID (from)
        self.nid_to = nid_to     # Node ID (to)
        self.weight = 0
        self.key = ascii2int(self.nid_from + self.nid_to) # Quantified ID
        return

# Loads edges from a file

def load_edges_new():
    # XML file loading
    tree = ET.parse(OPTIONS.edg_xml)
    root = tree.getroot()
    
    # Iterate through all edge tags.
    for edge in root.findall('edge'):
        # If the edge has a 'from' and a 'to' attribute, then it is valid
        if xml_has_atrribute(edge,'from') and xml_has_atrribute(edge,'to'):
            EDGES[edge.attrib['id']] = Edge(edge.attrib['id'], edge.attrib['from'], edge.attrib['to'])



    return

def load_edges():
    # XML file loading
    tree = ET.parse(OPTIONS.edg_xml)
    root = tree.getroot()
    
    # Iterate through all edge tags.
    for edge in root.findall('edge'):
        # If the edge has a 'from' and a 'to' attribute, then it is valid
        if xml_has_atrribute(edge,'from') and xml_has_atrribute(edge,'to'): 
            EDGES.append(
                Edge(
                    edge.attrib['id'],
                    edge.attrib['from'],
                    edge.attrib['to']
                )
            )
        continue
    return

# Load the trace.json file and obtain the traces
def navigate_trace():
    # Loade the file
    data = decode_json(OPTIONS.trace_json)
    
    # Go through the trace of each vehicle
    for veh_id in data:
        trace = data[veh_id]

        correlate_new(trace)
        continue
    return

# Correlates a trace to the edges
# @param [str] trace = A list of every node id that a vehicle has visted

def correlate_new(trace): #requires the traces to be edges
    # Valide the length of trace. It needs to have traveled to at least two nodes
    if len(trace) <= 1: return
    
    # Grab from/to node pairs
    for i in trace:
        try:
            EDGES[i].weight += 1
        except KeyError:
            continue
        


def correlate(trace):
    # Valide the length of trace. It needs to have traveled to at least two nodes
    if len(trace) <= 1: return
    
    # Grab from/to node pairs
    for i in range(len(trace)-1):
        nid_from = trace[i]; nid_to = trace[i+1]
        key = ascii2int(nid_from+nid_to)
        #print(f"from {trace[i]} to {trace[i+1]}")
        print(f"from {trace[i]} to {trace[i+1]}")
        try:
            n = index(EDGE_KEYS,key)
            EDGES[n].weight += 1
        except ValueError:
            print(f"FAILED from {trace[i]} to {trace[i+1]}")
            
    return
    
def color_ssv():
    # Storage
    class markme: edges = []; nodes = []
    
    # Look at all the edges
    for key, edge in EDGES.items():
        # If the weight is larger than 0 then we will color it
        if edge.weight > 0:
            markme.edges.append(edge.eid)
            markme.nodes.append(edge.nid_from)
            markme.nodes.append(edge.nid_to)
        continue
    
    # Write to file
    with open(OPTIONS.color_ssv,'w') as ssv:
        ssv.write('TYPE ID COLOR\n')
        for eid in markme.edges:
            ssv.write('EDGE %s %s\n' % (eid,OPTIONS.edge_color))
        for nid in markme.nodes:
            ssv.write('NODE %s %s\n' % (nid,OPTIONS.node_color))
            
    return
main()
