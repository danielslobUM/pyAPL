import matplotlib.pyplot as plt
import json
from matplotlib import colormaps
import glob

def get_points_for_structure(dvh_obj, structure_name):
    for structure in dvh_obj["containsStructureDose"]:
        
        if structure["structureName"]==structure_name:
            dvh_points = structure["dvh_curve"]["dvh_points"]
            d_points = [dvh_point["d_point"] for dvh_point in dvh_points ]
            v_points = [dvh_point["v_point"] for dvh_point in dvh_points ]
            color = structure["color"]
            
            return {"d_points": d_points, "v_points": v_points }

folderName = "Z:\\Projects\\phys\\p0728-automation\\ICoNEA\\DICOM\\P0728C0006I13396344"
dvh_obj_list = glob.glob(folderName + "/*.jsonld")
print(dvh_obj_list)

data_objects = [ ]

for dvh_obj in dvh_obj_list:
    with open(dvh_obj, "r") as f:
        data_objects.append(json.load(f))
print(data_objects)

structure_name="Heart"

colors = ['r', 'b', 'g', 'c', 'm', 'y', 'k']

i=0
for data in data_objects:
    data_breast_r_points = get_points_for_structure(data, structure_name)

    plt.scatter(data_breast_r_points["d_points"], data_breast_r_points["v_points"], color=colors[i])
    i+=1

plt.title(structure_name)
plt.show()