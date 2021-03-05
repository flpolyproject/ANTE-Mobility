# visualize_dgpng
# Author: Quentin Goss
import pantherine as purr
import os

def main():
    # Modules
    dgpng = './dgpng.py'
    tracewrangler = './tracewrangler.py'
    
    # Map files
    map_dir = '../maps/grid_speed_dist/100'
    edg_xml = purr.mrf(map_dir,r'*.edg.xml')
    nod_xml = purr.mrf(map_dir,r'*.nod.xml')
    
    # Hot file
    hot = './sims_json'
    
    # Working Dir
    temp = 'temp'
    if not os.path.exists(temp):
        os.mkdir(temp)
        
    # Output dir
    out = '%s/out' % (hot)
    if not os.path.exists(out):
        os.mkdir(out)
    
    # Retrieve everthing in the hotfile
    sims = purr.lsdir(hot)
    
    # For each simulation
    for sim in sims:
        if not '.json' in sim:
            continue
        path = '%s/%s' % (hot,sim)
        
        # Trace Wrangler
        cmd = 'python %s ' % (tracewrangler)
        cmd += '--trace.json=%s ' % (path)
        cmd += '--edg.xml=%s ' % (edg_xml)
        cmd += '--color.ssv=%s/%s.ssv ' % (temp,sim)
        cmd += '--node-color=(255,255,255,255) '
        cmd += '--edge-color=(0,0,0,255)'
        os.system(cmd)
        
        # dgpng
        cmd = 'python %s ' % (dgpng)
        cmd += '--edg.xml=%s ' % (edg_xml)
        cmd += '--nod.xml=%s ' % (nod_xml)
        cmd += '--png=%s/%s.png ' % (out,sim)
        cmd += '--background-color=(255,255,255,0) '
        cmd += '--node-color=(255,255,255,255) '
        cmd += '--edge-color=(0,0,0,50) '
        cmd += '--internal-node-color=(0,0,0,0) '
        cmd += '--edge-thickness=10 '
        cmd += '--padding=10 '
        cmd += '--color.ssv=%s/%s.ssv ' % (temp,sim)
        os.system(cmd)
        continue
    
    # Clean up
    purr.deldir(temp)
    return

if __name__ == '__main__':
    main()
