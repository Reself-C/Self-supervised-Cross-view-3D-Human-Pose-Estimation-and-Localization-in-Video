import numpy as np

"""Note(Jack BAI):
    This file is to deal with the camera part, incl. 
    - converting the camera from 3D to 2D
    - decide the extrinsic and intrinsic camera params.
    - simulate the translational movements of the camera 
"""


def get_center(data_3d_std):
    """
    Get the center of all the users

    Get the center coordinates of all the humans in the plot. Note that the center point is on the horizontal
    plane, so it has a z-value of 0.

    Args:
        data: the 3-D coordinates of the raw data, i.e. data_cluster, data_3d, all of size [n, x, 17, 3]

    Returns:
        datas: of the same size as input data, i.e. [n, x, 17, 3]
    """

    center = np.array([np.sum(data_3d_std[:, 0, 10, 0]), np.sum(data_3d_std[:, 0, 10, 1]), 0]) / 3
    return center

def get_angle(data):
    """
    Get the camera euclidean angle from given directional vector

    Args:
        frame: the total frame of the output array
        data: directional vector data

    Returns:

        [frame,3] ndarray of euclidean angle
    """
    if len(data.shape()) == 1:
        result = np.zeros(3)
                
        x = data[0]; y = data[1]; z = data[2]
        result[2] = (np.add(np.atan2(y, x),np.pi/2))
        result[0] =  np.pi/2
    else:
        result = np.zeros(data.shape(0), 3)
                
        x = data[:, 0]; y = data[:, 1]; z = data[:, 2]
        result[:, 2] = (np.add(np.atan2(y, x),np.pi/2))
        result[:, 0] =  np.pi/2
            
        
    return result

def get_endpoint(center, distance, height, cross):
    """
    input: distance, cross, center location, height
    output: two endpoint location
    """

    height = np.random.randint(height[0], height[1], 1)

    start_angle = np.random.random()*2*np.pi

    start_distance = np.random.randint(distance[0],distance[1],1)
    start = center + np.array([start_distance*np.cos(start_angle), start_distance*np.sin(start_angle), height]).reshape(-1)

    if cross:
        end_angle = np.random.random()*2*np.pi
    else:
        end_angle = start_angle + (np.random.random()-0.5)/np.pi/4

    end_distance = np.random.randint(distance[0],distance[1],1)
    end = center + np.array([end_distance*np.cos(end_angle), end_distance*np.sin(end_angle), height]).reshape(-1)

    return start, end


def T(endpoint, frame):
    """
    input: two endpoint location, frame
    output: location of camera by the time
    """

    T_mat = np.linspace(endpoint[0], endpoint[1], frame)
    return T_mat

    
def generate_exmat(T_mat, center, tracking):
    """
    Generate the extrinsic matrix for the camera.

    Develop the extrinsic matrix for the camera, which is used for transforming the object in the world coordinate
    system into the homogeneous camera coordinate system. Note that the intermediate variable H_o2k (from outside
    coordinate system to the camera coordinate system) has the size
    [ R T    where R is the rotational matrix, calculated by the camera orientation, with R_z * R_y * R_x.
      0 1 ]  T is the translational matrix, calculated by -R*(-1) * X, where X is the camera position in the
                world coordinate.

    Args:
        self.camera_pos: the position of the camera.

    Returns:
        self.exmat: of size [x, 4, 4], where x is the number of frames (self.frames), so it's frame-dependent.

    Raises:
        NOError: no error occurred up to now
    """

    for i in range(T_mat.shape(1)):
        posCamera = T_mat[i]
        if tracking is True:
            argCamera = get_angle(np.subs(center - posCamera))
        else:
            argCamera = get_angle(np.subs(center - T_mat[0]))
            pass

        Rz = np.array(
                [[np.cos(argCamera[2]), -np.sin(argCamera[2]), 0.], [np.sin(argCamera[2]), np.cos(argCamera[2]), 0.],
                 [0., 0., 1.]], dtype=np.float16)
        Ry = np.array([[np.cos(argCamera[1]), 0., np.sin(argCamera[1])], [0., 1., 0.],
                                        [-np.sin(argCamera[1]), 0., np.cos(argCamera[1])]], dtype=np.float16)
        Rx = np.array([[1., 0., 0.], [0., np.cos(argCamera[0]), -np.sin(argCamera[0])],
                                        [0., np.sin(argCamera[0]), np.cos(argCamera[0])]], dtype=np.float16)

        Rotation = np.matmul(Rz, Ry)
        Rotation = np.matmul(Rotation, Rx)
        Rotation = Rotation.transpose(0,1)
            

        Translation = - np.matmul(Rotation, np.array(posCamera, dtype=np.float16).reshape(3, 1))

        H_o2k = np.concatenate((Rotation, Translation), 1)
        H_o2k = np.concatenate((H_o2k, np.array([[0., 0., 0., 1.]])), 0)

        if i == 0:
            exmat = H_o2k.reshape(1, 4, 4)
        else:
            exmat = np.concatenate((exmat, H_o2k.reshape(1, 4, 4)), 0)

    return exmat


def w2c(data_3d_std, camera_metadata, frame):
    """
    input: camera_metadata, data_3d_std
    output: data_c_std
    """

    center = get_center(data_3d_std)
    print(center)

    distance = camera_metadata['distance']
    height = camera_metadata['height']
    cross = camera_metadata['cross']
    tracking = camera_metadata['tracking']

    endpoint = get_endpoint(center, distance, height, cross)
    
    T_mat = T(endpoint, frame)
    exmat = generate_exmat(T_mat, center, tracking)

    data_c_std = None

    return data_c_std
    

def c2s(data_c_std, inmat):
    """
    Use the intrinsic matrix to switch the graph from camera coordinate to pixel coordinate

    Transform the tensor in homogeneous camera coordinate into euclidean
    equivalent to pixel coordinate (2d to 2d).

    Args:
        data: the 3-D coordinates of the raw data, i.e. data_cluster, data_3d, all of size [n, x, 17, 3]

    Returns:
        data: of the same size as input data, i.e. [n, x, 17, 3]
    """
    
    data = np.matmul(inmat, data_c_std[:,:,:,:,np.newaxis])
    data_2d_std = (data / np.abs(data[:,:,:,np.newaxis,2])).squeeze()

    return data_2d_std
