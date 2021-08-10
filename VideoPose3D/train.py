
import torch
from torch.utils.data import DataLoader
import torch.optim as optim

from tqdm import tqdm
import numpy as np
import os
import errno
import sys

from common.arguments import parse_args
from common.model import *
from common.regressor import *
from common.generators import ChunkedGenerator

args = parse_args()
print(args)

try:
    # Create checkpoint directory if it does not exist
    os.makedirs(args.checkpoint)
except OSError as e:
    if e.errno != errno.EEXIST:
        raise RuntimeError('Unable to create checkpoint directory:', args.checkpoint)

print('Loading dataset...')
dataset_path = 'data/data_multi_' + args.dataset + '.npz'
print('- Loading file', dataset_path)
dataset_zip = np.load(dataset_path, allow_pickle=True)['dataset']


print('Loading Model...')
filter_widths = [int(x) for x in args.architecture.split(',')]
model_pos = TemporalModel(args.keypoints_number, 2, args.keypoints_number, filter_widths, 
            args.causal, args.dropout, args.channels, args.dense)

chk_filename = os.path.join(args.checkpoint, args.load)
print('- Loading checkpoint', chk_filename)
checkpoint = torch.load(chk_filename, map_location=lambda storage, loc: storage)
model_pos.load_state_dict(checkpoint['model_pos'])
if torch.cuda.is_available():
    print('- Running on device', torch.cuda.get_device_name())
    model_pos = model_pos.cuda()

receptive_field = model_pos.receptive_field()
lr = checkpoint['lr']
lr_decay = args.lr_decay  
initial_momentum = 0.1
final_momentum = 0.001
optimizer = optim.Adam(model_pos.parameters(), lr=lr, amsgrad=True)
if 'optimizer' in checkpoint and checkpoint['optimizer'] is not None:
    optimizer.load_state_dict(checkpoint['optimizer'])


print('Preparing data...')
dataset = ChunkedGenerator(dataset_zip)
data_iter = DataLoader(dataset, shuffle=True)
loss_list = list()
  
print('Processing...')

epoch = 0
model_pos.train()

while epoch < args.epochs:
    print('- epoch {}'.format(epoch))
    pbar = tqdm(total=dataset.__len__())
    
    for cameras, _, pose_2ds, count in data_iter:
        # initial the output format
        # cut the useless dimention
        # pose_2d - [view,number,frame,joint,2]
        # camera - [view,4] [cx,cy,fx,fy]
        # shape - [view,number,frame,joint,2]
        cameras = cameras.squeeze(0)
        pose_2ds = pose_2ds.squeeze(0)
        shape = pose_2ds.shape
        
        # pose_2ds -> reshape to [view*number,frame,joint,3]
        pose_2ds = pose_2ds.reshape(-1,shape[2],shape[3],shape[4])
        pose_pred = model_pos(pose_2ds)
        
        # here we make a cut for pose_2d via receptive_field
        # make a assignment x=(x-c)/f, y=(y-c)/f
        pose_2ds = pose_2ds.reshape(shape)
        cameras = cameras[:,None,None,None,:]
        pose_2ds[...,0].add_(-cameras[...,0]).mul_(1/cameras[...,2])
        pose_2ds[...,1].add_(-cameras[...,1]).mul_(1/cameras[...,3])
        pose_2ds = pose_2ds.reshape(-1,shape[2],shape[3],shape[4])
        pose_2ds = pose_2ds[:, receptive_field-1:]
        
        T, loss = regressor(pose_pred, pose_2ds, args.width)
        # reshape back to [view, number, frame, joint, 2/3]
        pose_2ds = pose_2ds.reshape(shape[0],shape[1],-1,shape[3],2)      
        pose_pred = pose_pred.reshape(shape[0],shape[1],-1,shape[3],3)
        T = T.reshape(shape[0],shape[1],-1,3)                  
         
        optimizer.zero_grad()          
        loss.backward()
        loss_list.append(loss.item())
        optimizer.step()          
        pbar.update(1)
    pbar.close()

    # Decay learning rate exponentially
    lr *= lr_decay
    for param_group in optimizer.param_groups:
        param_group['lr'] *= lr_decay
      
    # Decay BatchNorm momentum
    momentum = initial_momentum * np.exp(-epoch/args.epochs * np.log(initial_momentum/final_momentum))
    model_pos.set_bn_momentum(momentum)

    epoch += 1

print('Saving model...')
chk_path = os.path.join(args.checkpoint, args.save)
print('- Saving checkpoint to', chk_path)
            
torch.save({
    'lr': lr,
    'optimizer': optimizer.state_dict(),
    'model_pos': model_pos.state_dict(),
}, chk_path)


# Save training curves after every epoch, as .png images (if requested)

print('Saving traning curve...')
if 'matplotlib' not in sys.modules:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

plt.figure()
x = np.arange(0, len(loss_list))
plt.plot(x, loss_list, linestyle='-', color='C0')
plt.xlabel('Batch')
plt.ylabel('Regression loss')
plt.savefig(os.path.join(args.checkpoint, 'loss_3d.png'))
plt.close('all')

print('Done.')