# please run 'prepare_dataset.py' before this
# this file aims to generate the multi-person and cross-view dataset mapping the 3D and 2D
# better run it in terminal

import os
import numpy as np
from tqdm import tqdm
from operator import itemgetter
from arguments import parse_args

from camera_utils import *
from utils.random_function import *
from utils.collision import collision_eliminate as col_eli
from utils.camera import *

args = parse_args()
print(args)


print('Loading data...')

dataset = np.load('data_3d_' + args.dataset + '.npz', allow_pickle=True)['positions_3d'].item()
dict_keys = dataset.keys()

if not os.path.exists('output'):
    print('Creating output path...')
    os.makedirs('output')


print('Loading camera...')
# a dictionary to store the information of camera
camera_metadata = suggest_metadata(args.camera)


print('Generating data...')

for count in tqdm(range(args.number)):
    # randomly get data from dataset
    keys = extract(dict_keys, args.min, args.max)
    sub_dataset = itemgetter(*keys)(dataset)
    # for each data do randomly transforming
    temp, frame_list = list(), list()
    for data in sub_dataset:
        data, f = pre_process(data, args.shift, args.translation, args.rotation)
        frame_list.append(f)
        temp.append(data)
    # all the single data should be in one frame
    frame = np.min(frame_list)
    data_3d_std = list()
    for data in temp:
        data = data[:frame]
        data_3d_std.append(data)
    data_3d_std = np.array(data_3d_std, dtype=np.float32)

    # data_3d_std = eliminate_collision(data_3d_std)
    data_c_std = w2c(data_3d_std, camera_metadata, frame)
    # data_2d_std = c2s(data_c_std, camera_metadata['inmat'])
    
    # saving data...
    # keys: list(str)
    # data_3d_std: array
    # data_2d_std: list(array)

    # np.savez_compressed('output/'+str(count), keys=keys, data_3d_std=data_3d_std, data_2d_std=data_2d_std)

print('Done.')