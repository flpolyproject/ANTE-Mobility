import os, glob, sys
import matplotlib.pyplot as plt
import numpy as np
import cv2

path = "./sims_json/out"


def resize_read(x):
	img = cv2.imread(x)
	res = cv2.resize(img, (500, 500))

	lab = ''

	if "base" in x:
		lab="Baseline"
	elif "greedy" in x:
		lab="Greedy"
	elif "random" in x:
		lab="Random"
	elif "atne" in x:
		lab = "ATNE"
  
	# font 
	font = cv2.FONT_HERSHEY_SIMPLEX 
	  
	# org 
	org = (370, 30) 
	  
	# fontScale 
	fontScale = 1
	   
	# Red color in BGR 
	color = (0, 0, 0) 
	  
	# Line thickness of 2 px 
	thickness = 2

	res = cv2.putText(res, lab, org, font, fontScale, color, thickness, cv2.LINE_AA, False)
	return res

if __name__ == "__main__":
	image_path = glob.glob(os.path.join(path, r"*.png"))

	images_obj = [resize_read(x) for x in image_path]

	print([x.shape for x in images_obj])

	

	
	numpy_horizontal_concat = np.concatenate((images_obj[0], images_obj[1]), axis=1)
	numpy_horizontal_concat1 = np.concatenate((images_obj[2], images_obj[3]), axis=1)

	final = np.concatenate((numpy_horizontal_concat, numpy_horizontal_concat1), axis=1)

	cv2.imwrite("./output170ap.png", final)

	cv2.imshow("test", final)

	cv2.waitKey()